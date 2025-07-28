import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox, ttk
import numpy as np
from pyproj import Geod
import rasterio
import geopandas as gpd
from rasterio import features
import pandas as pd
from shapely.geometry import Point, LineString
import os
import tempfile
from collections import defaultdict
import logging
import traceback
import shutil
from typing import List, Tuple, Dict, Optional, Union

tempfile.tempdir = "D:/temp"  # Change this to a drive with free space

# Create the directory if it doesn't exist
os.makedirs(tempfile.tempdir, exist_ok=True)

# Configure PROJ environment
os.environ['PROJ_LIB'] = '/usr/share/proj'  # Adjust path if needed on your system

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_INFLOW = [100.0] * 2  # 9 days of default inflow in m³/s
DEFAULT_K = 2.0  # days
DEFAULT_X = 0.2  # dimensionless (0 to 0.5)
DEFAULT_TIME_STEP = "daily"
EVAPORATION_RATE = (5.787e-8) / 5 * 7  # m³/m²/s
INFILTRATION_RATE = 5e-7  # m³/m²/s
CANAL_WIDTH = 10.0  # meters
FLOW_THRESHOLD = 2  # m³/s
MAX_PIXEL_SEARCH_RADIUS = 10000  # meters
ELEVATION_THRESHOLD = 50  # meters
COMMAND_AREA_RADIUS = 500  # meters
STREAM_BUFFER_RADIUS = 500  # meters

def geo_to_pixel(lon: float, lat: float, transform: rasterio.Affine) -> Tuple[int, int]:
    """Convert geographic coordinates to pixel coordinates."""
    try:
        col, row = ~transform * (lon, lat)
        return int(round(col)), int(round(row))
    except Exception as e:
        logger.error(f"Error in geo_to_pixel: {e}")
        raise ValueError(f"Coordinate conversion failed for ({lon}, {lat})")

def pixel_to_geo(x: int, y: int, transform: rasterio.Affine) -> Tuple[float, float]:
    """Convert pixel coordinates to geographic coordinates."""
    try:
        lon, lat = transform * (x, y)
        return lon, lat
    except Exception as e:
        logger.error(f"Error in pixel_to_geo: {e}")
        raise ValueError(f"Pixel conversion failed for ({x}, {y})")

def get_circular_pixels(
    lon: float, 
    lat: float, 
    radius_m: float, 
    transform: rasterio.Affine, 
    geod: Geod, 
    dem_shape: Tuple[int, int], 
    dem_data: np.ndarray, 
    wwtp_elev: Optional[float] = None, 
    elevation_threshold: Optional[float] = None
) -> List[Tuple[int, int]]:
    """Get all pixels within a circular radius of a point, optionally filtered by elevation."""
    try:
        if radius_m <= 0:
            return []
            
        if radius_m > MAX_PIXEL_SEARCH_RADIUS:
            logger.warning(f"Requested search radius {radius_m}m exceeds maximum allowed ({MAX_PIXEL_SEARCH_RADIUS}m)")
            radius_m = MAX_PIXEL_SEARCH_RADIUS

        x_center, y_center = geo_to_pixel(lon, lat, transform)
        if not (0 <= x_center < dem_shape[1] and 0 <= y_center < dem_shape[0]):
            logger.warning(f"Center point ({x_center}, {y_center}) is outside DEM bounds")
            return []

        circular_pixels = []
        clon, clat = pixel_to_geo(x_center, y_center, transform)
        
        # Calculate pixel size in meters (approximate)
        east_x = min(x_center + 1, dem_shape[1] - 1)
        east_lon, east_lat = pixel_to_geo(east_x, y_center, transform)
        _, _, dist_east = geod.inv(clon, clat, east_lon, east_lat)
        
        max_dx = int(np.ceil(radius_m / max(dist_east, 1e-6)))  # Avoid division by zero
        
        for dx in range(-max_dx, max_dx + 1):
            for dy in range(-max_dx, max_dx + 1):
                x = x_center + dx
                y = y_center + dy
                
                if 0 <= x < dem_shape[1] and 0 <= y < dem_shape[0]:
                    plon, plat = pixel_to_geo(x, y, transform)
                    _, _, distance = geod.inv(lon, lat, plon, plat)
                    
                    if distance <= radius_m:
                        try:
                            pixel_elev = dem_data[y, x]
                            if np.ma.is_masked(pixel_elev):
                                continue
                                
                            elev_condition = True
                            if wwtp_elev is not None and elevation_threshold is not None:
                                elev_condition = (pixel_elev <= wwtp_elev + elevation_threshold)
                            
                            if elev_condition:
                                circular_pixels.append((y, x))
                        except IndexError:
                            continue
    
        return circular_pixels
    except Exception as e:
        logger.error(f"Error in get_circular_pixels: {e}")
        raise

def calculate_stream_length(coords: List[Tuple[float, float]], geod: Geod) -> float:
    """Calculate the total length of a stream in meters."""
    if len(coords) < 2:
        return 0.0
    
    total_length = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        _, _, distance = geod.inv(lon1, lat1, lon2, lat2)
        total_length += distance
        
    return total_length

def calculate_muskingum_coefficients(K: float, X: float, dt: float) -> Tuple[float, float, float]:
    """Calculate Muskingum routing coefficients."""
    try:
        if K <= 0:
            raise ValueError("K must be positive")
        if X < 0 or X > 0.5:
            raise ValueError("X must be between 0 and 0.5")
        if dt <= 0:
            raise ValueError("Time step must be positive")

        denominator = 2 * K * (1 - X) + dt
        if denominator <= 0:
            raise ValueError("Denominator in Muskingum coefficients calculation must be positive")
            
        C0 = (dt - 2 * K * X) / denominator
        C1 = (dt + 2 * K * X) / denominator
        C2 = (2 * K * (1 - X) - dt) / denominator
        
        # Check for stability
        coeff_sum = C0 + C1 + C2
        if not 0.95 <= coeff_sum <= 1.05:
            logger.warning(f"Muskingum coefficients unstable: C0={C0:.4f}, C1={C1:.4f}, C2={C2:.4f}, sum={coeff_sum:.4f}")
            
        return C0, C1, C2
    except Exception as e:
        logger.error(f"Error in calculate_muskingum_coefficients: {e}")
        raise

class WWTPModelApp:
    """GUI application for WWTP flow tracing with Muskingum routing."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WWTP Flow Tracing with Muskingum Routing")
        
        # Initialize variables
        self.dem_file = None
        self.excel_file = None
        self.output_dir = os.path.join(os.path.expanduser("~"), "wwtp_model_output")
        self.inflow_series = defaultdict(list)
        self.wwtp_data = []
        self.processing = False
        
        # Create GUI
        self.create_widgets()
        self.add_muskingum_parameters()
        
        # Make window resizable
        self.root.grid_rowconfigure(8, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        
    def create_widgets(self):
        """Create all GUI widgets."""
        ttk.Label(self.root, text="DEM File:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.dem_entry = ttk.Entry(self.root, width=50)
        self.dem_entry.grid(row=0, column=1, padx=10, pady=5, sticky="we")
        ttk.Button(self.root, text="Browse", command=self.browse_dem).grid(row=0, column=2, padx=10, pady=5)
        
        ttk.Label(self.root, text="WWTP Locations (Excel/CSV):").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.excel_entry = ttk.Entry(self.root, width=50)
        self.excel_entry.grid(row=1, column=1, padx=10, pady=5, sticky="we")
        ttk.Button(self.root, text="Browse", command=self.browse_excel).grid(row=1, column=2, padx=10, pady=5)
        
        ttk.Label(self.root, text="Output Directory:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.output_entry = ttk.Entry(self.root, width=50)
        self.output_entry.grid(row=2, column=1, padx=10, pady=5, sticky="we")
        self.output_entry.insert(0, self.output_dir)
        ttk.Button(self.root, text="Browse", command=self.browse_output).grid(row=2, column=2, padx=10, pady=5)
    
    def add_muskingum_parameters(self):
        """Add Muskingum parameter controls to the GUI."""
        ttk.Label(self.root, text="Muskingum K (days):").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.K_entry = ttk.Entry(self.root, width=10)
        self.K_entry.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        self.K_entry.insert(0, str(DEFAULT_K))
        
        ttk.Label(self.root, text="Muskingum X (0-0.5):").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        self.X_entry = ttk.Entry(self.root, width=10)
        self.X_entry.grid(row=4, column=1, padx=10, pady=5, sticky="w")
        self.X_entry.insert(0, str(DEFAULT_X))
        
        ttk.Label(self.root, text="Time Step:").grid(row=5, column=0, padx=10, pady=5, sticky="e")
        self.time_step_var = tk.StringVar(value=DEFAULT_TIME_STEP)
        ttk.Radiobutton(self.root, text="Hourly", variable=self.time_step_var, value="hourly").grid(row=5, column=1, sticky="w")
        ttk.Radiobutton(self.root, text="Daily", variable=self.time_step_var, value="daily").grid(row=5, column=2, sticky="w")
        
        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Load WWTPs", command=self.load_wwtps).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Set Inflow Series", command=self.set_inflow_series).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Clear All", command=self.clear_data).pack(side="left", padx=5)
        
        run_frame = ttk.Frame(self.root)
        run_frame.grid(row=7, column=0, columnspan=3, pady=10)
        
        self.run_button = ttk.Button(run_frame, text="Run Model", command=self.run_model)
        self.run_button.pack(side="left", padx=5)
        
        ttk.Button(run_frame, text="Clear Log", command=self.clear_calculations).pack(side="left", padx=5)
        
        list_frame = ttk.Frame(self.root)
        list_frame.grid(row=8, column=0, columnspan=3, padx=10, pady=5, sticky="nsew")
        
        self.wwtp_listbox = tk.Listbox(list_frame, height=10, width=80)
        self.wwtp_listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.wwtp_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.wwtp_listbox.config(yscrollcommand=scrollbar.set)
        
        self.wwtp_listbox.bind('<<ListboxSelect>>', self.show_inflow_status)
        
        self.status_label = ttk.Label(self.root, text="No WWTPs loaded", relief="sunken", padding=5)
        self.status_label.grid(row=9, column=0, columnspan=3, padx=10, pady=5, sticky="we")
        
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=300, mode="determinate")
        self.progress.grid(row=10, column=0, columnspan=3, padx=10, pady=5)
        
        # Add calculation log frame
        calc_frame = ttk.Frame(self.root)
        calc_frame.grid(row=11, column=0, columnspan=3, padx=10, pady=5, sticky="nsew")
        
        ttk.Label(calc_frame, text="Calculation Log:").pack(anchor="w")
        self.calc_log = tk.Text(calc_frame, height=10, wrap=tk.WORD, state="disabled")
        scrollbar = ttk.Scrollbar(calc_frame, orient="vertical", command=self.calc_log.yview)
        self.calc_log.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.calc_log.pack(side="left", fill="both", expand=True)
        
        # Make the calculation log area resizable
        self.root.grid_rowconfigure(11, weight=1)
    
    def log_calculation(self, message):
        """Add a calculation message to the log."""
        self.calc_log.config(state="normal")
        self.calc_log.insert(tk.END, message + "\n")
        self.calc_log.see(tk.END)
        self.calc_log.config(state="disabled")
        self.root.update()

    def clear_calculations(self):
        """Clear the calculation log."""
        self.calc_log.config(state="normal")
        self.calc_log.delete(1.0, tk.END)
        self.calc_log.config(state="disabled")
    
    def browse_dem(self):
        """Browse for DEM file."""
        file = filedialog.askopenfilename(
            title="Select DEM File",
            filetypes=[("GeoTIFF files", "*.tif *.tiff"), ("All files", "*.*")]
        )
        if file:
            self.dem_file = file
            self.dem_entry.delete(0, tk.END)
            self.dem_entry.insert(0, self.dem_file)
    
    def browse_excel(self):
        """Browse for Excel or CSV file with WWTP locations."""
        file = filedialog.askopenfilename(
            title="Select WWTP Locations File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file:
            self.excel_file = file
            self.excel_entry.delete(0, tk.END)
            self.excel_entry.insert(0, self.excel_file)
    
    def browse_output(self):
        """Browse for output directory."""
        directory = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=self.output_dir
        )
        if directory:
            self.output_dir = directory
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, self.output_dir)
    
    def clear_data(self):
        """Clear all loaded data."""
        self.wwtp_data = []
        self.inflow_series.clear()
        self.wwtp_listbox.delete(0, tk.END)
        self.status_label.config(text="No WWTPs loaded")
        self.clear_calculations()
    
    def load_wwtps(self):
        """Load WWTP locations from Excel or CSV file."""
        if not self.excel_file:
            messagebox.showerror("Error", "Please select an Excel or CSV file first")
            return
        
        try:
            try:
                df = pd.read_excel(self.excel_file)
            except Exception:
                df = pd.read_csv(self.excel_file)
            
            required_columns = ['longitude', 'latitude', 'wwtp']
            available_columns = [col.lower() for col in df.columns]
            
            missing_columns = [col for col in required_columns if col not in available_columns]
            if missing_columns:
                messagebox.showerror(
                    "Error", 
                    f"File must contain columns: {', '.join(required_columns)}\nMissing: {', '.join(missing_columns)}"
                )
                return
            
            col_map = {
                'longitude': [c for c in df.columns if c.lower() == 'longitude'][0],
                'latitude': [c for c in df.columns if c.lower() == 'latitude'][0],
                'wwtp': [c for c in df.columns if c.lower() == 'wwtp'][0]
            }
            
            self.wwtp_data = []
            self.inflow_series.clear()
            self.wwtp_listbox.delete(0, tk.END)
            
            for _, row in df.iterrows():
                try:
                    lon = float(row[col_map['longitude']])
                    lat = float(row[col_map['latitude']])
                    name = str(row[col_map['wwtp']])
                    
                    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                        logger.warning(f"Invalid coordinates for WWTP {name}: ({lon}, {lat})")
                        continue
                        
                    self.wwtp_data.append((lon, lat, name))
                    self.wwtp_listbox.insert(tk.END, f"{name} (Lon: {lon:.6f}, Lat: {lat:.6f})")
                except ValueError as e:
                    logger.warning(f"Skipping row {_}: {e}")
                    continue
            
            if not self.wwtp_data:
                messagebox.showerror("Error", "No valid WWTP locations found in file")
                return
                
            self.status_label.config(text=f"Loaded {len(self.wwtp_data)} WWTPs | Using default inflow for all")
            messagebox.showinfo("Success", f"Loaded {len(self.wwtp_data)} valid WWTP locations")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load WWTPs:\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}")
    
    def show_inflow_status(self, event=None):
        """Update status label with selected WWTP's inflow information."""
        selected = self.wwtp_listbox.curselection()
        if selected:
            idx = selected[0]
            wwtp_name = self.wwtp_data[idx][2]
            
            if idx in self.inflow_series:
                inflow = self.inflow_series[idx]
                status = f"Selected: {wwtp_name} | Custom inflow: {inflow[:3]}... (length: {len(inflow)})"
            else:
                status = f"Selected: {wwtp_name} | Using default inflow"
                
            self.status_label.config(text=status)
    
    def set_inflow_series(self):
        """Open dialog to set inflow series for selected WWTP."""
        if not self.wwtp_data:
            messagebox.showerror("Error", "Please load WWTPs first")
            return
        
        selected = self.wwtp_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Please select a WWTP from the list")
            return
        
        idx = selected[0]
        wwtp_name = self.wwtp_data[idx][2]
        
        inflow_window = tk.Toplevel(self.root)
        inflow_window.title(f"Inflow Series for {wwtp_name}")
        inflow_window.grab_set()
        
        main_frame = ttk.Frame(inflow_window, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        ttk.Label(main_frame, text=f"Enter inflow values (m³/s) for {wwtp_name}:").pack(pady=5)
        
        canvas = tk.Canvas(main_frame, borderwidth=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            
        scrollable_frame.bind("<Configure>", on_frame_configure)
        
        current_inflow = self.inflow_series.get(idx, DEFAULT_INFLOW.copy())
        entries = []
        
        for i in range(len(current_inflow)):
            row_frame = ttk.Frame(scrollable_frame)
            row_frame.pack(fill="x", padx=5, pady=2)
            
            ttk.Label(row_frame, text=f"Step {i+1}:").pack(side="left")
            entry = ttk.Entry(row_frame, width=15)
            entry.pack(side="left", padx=5)
            entry.insert(0, str(current_inflow[i]))
            entries.append(entry)
            
            if i == len(current_inflow) - 1:
                add_btn = ttk.Button(row_frame, text="+", width=3, 
                                   command=lambda: self.add_inflow_step(entries, scrollable_frame))
                add_btn.pack(side="left", padx=2)
                
                if len(current_inflow) > 1:
                    remove_btn = ttk.Button(row_frame, text="-", width=3,
                                          command=lambda: self.remove_inflow_step(entries, scrollable_frame))
                    remove_btn.pack(side="left", padx=2)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        def save_inflow():
            try:
                inflow = []
                for entry in entries:
                    val = entry.get().strip()
                    if val:
                        inflow.append(float(val))
                    else:
                        inflow.append(0.0)
                
                if not any(inflow):
                    messagebox.showerror("Error", "At least one inflow value must be greater than 0")
                    return
                
                self.inflow_series[idx] = inflow
                self.show_inflow_status()
                messagebox.showinfo("Success", f"Inflow series saved for {wwtp_name}")
                inflow_window.destroy()
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers")
        
        ttk.Button(button_frame, text="Save", command=save_inflow).pack(side="left", padx=10)
        ttk.Button(button_frame, text="Use Default", 
                  command=lambda: self.reset_to_default(entries)).pack(side="left", padx=10)
        ttk.Button(button_frame, text="Cancel", command=inflow_window.destroy).pack(side="left", padx=10)
    
    def add_inflow_step(self, entries: List[ttk.Entry], frame: ttk.Frame):
        """Add a new inflow step entry."""
        i = len(entries)
        row_frame = ttk.Frame(frame)
        row_frame.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(row_frame, text=f"Step {i+1}:").pack(side="left")
        entry = ttk.Entry(row_frame, width=15)
        entry.pack(side="left", padx=5)
        entry.insert(0, "0.0")
        entries.append(entry)
        
        for child in frame.winfo_children():
            if hasattr(child, 'winfo_children'):
                for subchild in child.winfo_children():
                    if isinstance(subchild, ttk.Button) and subchild['text'] in ('+', '-'):
                        subchild.destroy()
        
        last_row = frame.winfo_children()[-1]
        add_btn = ttk.Button(last_row, text="+", width=3, 
                            command=lambda: self.add_inflow_step(entries, frame))
        add_btn.pack(side="left", padx=2)
        
        remove_btn = ttk.Button(last_row, text="-", width=3,
                              command=lambda: self.remove_inflow_step(entries, frame))
        remove_btn.pack(side="left", padx=2)
    
    def remove_inflow_step(self, entries: List[ttk.Entry], frame: ttk.Frame):
        """Remove the last inflow step entry."""
        if len(entries) <= 1:
            messagebox.showerror("Error", "Must have at least one inflow step")
            return
            
        entries.pop()
        frame.winfo_children()[-1].destroy()
        
        last_row = frame.winfo_children()[-1]
        add_btn = ttk.Button(last_row, text="+", width=3, 
                            command=lambda: self.add_inflow_step(entries, frame))
        add_btn.pack(side="left", padx=2)
        
        if len(entries) > 1:
            remove_btn = ttk.Button(last_row, text="-", width=3,
                                  command=lambda: self.remove_inflow_step(entries, frame))
            remove_btn.pack(side="left", padx=2)
    
    def reset_to_default(self, entries: List[ttk.Entry]):
        """Reset inflow entries to default values."""
        for i, entry in enumerate(entries):
            entry.delete(0, tk.END)
            if i < len(DEFAULT_INFLOW):
                entry.insert(0, str(DEFAULT_INFLOW[i]))
            else:
                entry.insert(0, "0.0")
    
    def trace_downstream_muskingum(
        self,
        start_lon: float, 
        start_lat: float, 
        inflow_series: Union[List[float], float], 
        time_step: str, 
        transform: rasterio.Affine, 
        dem_data: np.ndarray, 
        K: float, 
        X: float, 
        geod: Geod
    ) -> Tuple[List[Tuple[int, int]], float, Dict[Tuple[int, int], List[float]]]:
        """Trace downstream path using Muskingum routing with evaporation and infiltration losses."""
        try:
            self.log_calculation(f"\n=== Starting downstream tracing for ({start_lon:.6f}, {start_lat:.6f}) ===")
            
            # Time step in seconds
            dt = 3600 if time_step == "hourly" else 86400
            self.log_calculation(f"Time step: {dt} seconds ({time_step})")
            
            # Convert K from days to seconds
            K_sec = K * 86400
            self.log_calculation(f"Muskingum K: {K} days = {K_sec} seconds")
            
            # Calculate Muskingum coefficients
            C0, C1, C2 = calculate_muskingum_coefficients(K_sec, X, dt)
            self.log_calculation(f"Muskingum Coefficients: C0={C0:.4f}, C1={C1:.4f}, C2={C2:.4f}")
            
            # Convert inflow series to numpy array
            if isinstance(inflow_series, (int, float)):
                inflow_series = [float(inflow_series)]
            current_inflow = np.array(inflow_series, dtype=np.float64)
            self.log_calculation(f"Initial inflow series: {current_inflow}")
            
            # Initialize tracking
            flow_history = defaultdict(list)
            x, y = geo_to_pixel(start_lon, start_lat, transform)
            flow_history[(x, y)] = current_inflow.tolist()
            path = [(x, y)]
            current_elev = dem_data[y, x]
            self.log_calculation(f"Starting at pixel ({x}, {y}) with elevation {current_elev:.2f} m")
            
            step = 0
            while True:
                step += 1
                self.log_calculation(f"\n--- Step {step} ---")
                
                # Find next downstream pixel
                min_elev = current_elev
                best_nx, best_ny = x, y

                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if not (0 <= nx < dem_data.shape[1] and 0 <= ny < dem_data.shape[0]):
                            continue
                        elev = dem_data[ny, nx]
                        if np.ma.is_masked(elev):
                            continue
                        if elev < min_elev:
                            min_elev, best_nx, best_ny = elev, nx, ny

                # Stop if no downhill path
                if (best_nx, best_ny) == (x, y):
                    self.log_calculation("No downhill path found - stopping tracing")
                    break

                # Calculate distance
                current_lon, current_lat = pixel_to_geo(x, y, transform)
                next_lon, next_lat = pixel_to_geo(best_nx, best_ny, transform)
                _, _, distance = geod.inv(current_lon, current_lat, next_lon, next_lat)
                self.log_calculation(f"Moving from ({x},{y}) to ({best_nx},{best_ny})")
                self.log_calculation(f"Distance between pixels: {distance:.2f} m")
                
                if distance <= 0:
                    self.log_calculation("Zero or negative distance - stopping tracing")
                    break

                # Calculate losses
                evaporation_loss = (EVAPORATION_RATE * 1000) * (CANAL_WIDTH * distance)
                infiltration_loss = (INFILTRATION_RATE * 1000) * (CANAL_WIDTH * distance)
                total_loss = evaporation_loss + infiltration_loss
                self.log_calculation(f"Losses - Evaporation: {evaporation_loss:.6f} m³/s, Infiltration: {infiltration_loss:.6f} m³/s")
                self.log_calculation(f"Total loss: {total_loss:.6f} m³/s")

                # Apply losses
                effective_inflow = current_inflow - total_loss
                effective_inflow[effective_inflow < 0] = 0
                self.log_calculation(f"Effective inflow after losses: {effective_inflow}")

                # Muskingum routing
                outflow = np.zeros_like(effective_inflow)
                outflow[0] = effective_inflow[0]
                for t in range(1, len(effective_inflow)):
                    outflow[t] = C0 * effective_inflow[t] + C1 * effective_inflow[t - 1] + C2 * outflow[t - 1]
                    self.log_calculation(f"Time {t}: Outflow = {C0:.4f}*{effective_inflow[t]:.4f} + {C1:.4f}*{effective_inflow[t-1]:.4f} + {C2:.4f}*{outflow[t-1]:.4f} = {outflow[t]:.4f}")
                
                self.log_calculation(f"Final outflow series: {outflow}")

                # Store and move to next pixel
                flow_history[(best_nx, best_ny)] = outflow.tolist()
                x, y = best_nx, best_ny
                current_elev = dem_data[y, x]
                current_inflow = outflow.copy()
                path.append((x, y))
                self.log_calculation(f"New elevation: {current_elev:.2f} m")

                # Stop if flow is below threshold
                if np.all(outflow < FLOW_THRESHOLD):
                    self.log_calculation(f"Outflow below threshold ({FLOW_THRESHOLD} m³/s) - stopping tracing")
                    break

            downstream_coords = [pixel_to_geo(x, y, transform) for (x, y) in path]
            stream_length = calculate_stream_length(downstream_coords, geod)
            self.log_calculation(f"\n=== Tracing complete ===")
            self.log_calculation(f"Total stream length: {stream_length:.2f} m")
            self.log_calculation(f"Number of pixels traced: {len(path)}")
            
            return path, stream_length, flow_history
        except Exception as e:
            self.log_calculation(f"ERROR in tracing: {str(e)}")
            logger.error(f"Error in trace_downstream_muskingum: {e}")
            raise
    
    def run_model(self):
        """Run the WWTP flow tracing model."""
        if self.processing:
            messagebox.showwarning("Warning", "Processing already in progress")
            return
            
        if not self.dem_file:
            messagebox.showerror("Error", "Please select a DEM file")
            return
        
        if not self.wwtp_data:
            messagebox.showerror("Error", "Please load WWTP locations")
            return
        
        try:
            K = float(self.K_entry.get())  # K in days
            X = float(self.X_entry.get())
            
            if K <= 0:
                raise ValueError("Muskingum K must be positive")
            if X < 0 or X > 0.5:
                raise ValueError("Muskingum X must be between 0 and 0.5")
                
            time_step = self.time_step_var.get()
            
            os.makedirs(self.output_dir, exist_ok=True)
            
            self.processing = True
            self.run_button.config(state="disabled")
            self.root.config(cursor="watch")
            self.status_label.config(text="Processing...")
            self.progress["value"] = 0
            self.clear_calculations()
            self.root.update()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tif") as tmp_dem:
                try:
                    shutil.copyfile(self.dem_file, tmp_dem.name)
                    dem_path = tmp_dem.name
                    
                    with rasterio.open(dem_path) as src:
                        dem_data = src.read(1, masked=True)
                        transform = src.transform
                        crs = src.crs
                        geod = Geod(ellps="WGS84")
                        
                        command_areas = np.zeros_like(dem_data.filled(0), dtype=np.int32)
                        wwtp_features = []
                        streamline_features = []
                        stream_info = []
                        
                        total_wwtps = len(self.wwtp_data)
                        processed = 0
                        
                        for idx, (lon, lat, name) in enumerate(self.wwtp_data):
                            try:
                                self.status_label.config(text=f"Processing {name} ({idx+1}/{total_wwtps})...")
                                self.progress["value"] = (idx / total_wwtps) * 100
                                self.root.update()
                                
                                # Validate coordinates first
                                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                                    logger.warning(f"Invalid coordinates for WWTP {name}: ({lon}, {lat})")
                                    continue
                                    
                                try:
                                    x_center, y_center = geo_to_pixel(lon, lat, transform)
                                except ValueError as e:
                                    logger.warning(f"Skipping WWTP {name}: {e}")
                                    continue
                                
                                if not (0 <= x_center < dem_data.shape[1] and 0 <= y_center < dem_data.shape[0]):
                                    logger.warning(f"WWTP {name} is outside DEM bounds")
                                    continue
                                
                                wwtp_elev = dem_data[y_center, x_center]
                                if np.ma.is_masked(wwtp_elev):
                                    logger.warning(f"WWTP {name} has no elevation data")
                                    continue
                                
                                inflow = self.inflow_series.get(idx, DEFAULT_INFLOW.copy())
                                
                                # Create circular command area
                                circular_pixels = get_circular_pixels(
                                    lon, lat, 
                                    COMMAND_AREA_RADIUS, 
                                    transform, 
                                    geod, 
                                    dem_data.shape, 
                                    dem_data, 
                                    wwtp_elev, 
                                    ELEVATION_THRESHOLD
                                )
                                
                                for (y, x) in circular_pixels:
                                    command_areas[y, x] = idx + 1
                                
                                # Trace downstream
                                downstream_path, stream_length, flow_history = self.trace_downstream_muskingum(
                                    lon, lat, 
                                    inflow,
                                    time_step,
                                    transform,
                                    dem_data,
                                    K,
                                    X,
                                    geod
                                )
                                
                                pixel_count = len(downstream_path)
                                stream_info.append((name, pixel_count, stream_length))
                                logger.info(f"WWTP: {name} | Pixels: {pixel_count} | Stream Length: {stream_length:.2f}m")
                                
                                if downstream_path and len(downstream_path) >= 2:
                                    downstream_coords = [pixel_to_geo(x, y, transform) for (x, y) in downstream_path]
                                    streamline_features.append({
                                        'geometry': LineString(downstream_coords),
                                        'properties': {
                                            'name': name, 
                                            'id': idx + 1,
                                            'pixel_count': pixel_count,
                                            'length_m': stream_length,
                                            'inflow': ','.join(map(str, inflow))
                                        }
                                    })
                                    
                                    for (x_p, y_p) in downstream_path:
                                        plon, plat = pixel_to_geo(x_p, y_p, transform)
                                        buffer_pixels = get_circular_pixels(
                                            plon, plat, 
                                            STREAM_BUFFER_RADIUS, 
                                            transform, 
                                            geod, 
                                            dem_data.shape, 
                                            dem_data
                                        )
                                        for (y_b, x_b) in buffer_pixels:
                                            command_areas[y_b, x_b] = idx + 1
                                
                                wwtp_features.append({
                                    'geometry': Point(lon, lat),
                                    'properties': {
                                        'name': name, 
                                        'id': idx + 1,
                                        'elevation': float(wwtp_elev),
                                        'inflow': ','.join(map(str, inflow))
                                    }
                                })
                                
                                processed += 1
                                
                            except Exception as e:
                                logger.error(f"Error processing WWTP {name}: {e}")
                                continue
                        
                        stream_info_file = os.path.join(self.output_dir, "stream_info.csv")
                        with open(stream_info_file, 'w') as f:
                            f.write("WWTP Name,Pixel Count,Stream Length (m)\n")
                            for name, pixels, length in stream_info:
                                f.write(f"{name},{pixels},{length:.2f}\n")
                        
                        self.progress["value"] = 90
                        self.status_label.config(text="Saving results...")
                        self.root.update()
                        
                        if np.any(command_areas > 0):
                            gdf_areas = gpd.GeoDataFrame.from_features(
                                [{'geometry': geom, 'properties': {'id': props}} 
                                 for geom, props in features.shapes(command_areas, transform=transform) 
                                 if props > 0],
                                crs=crs
                            )
                            gdf_areas = gdf_areas.dissolve(by='id')
                            gdf_areas = gdf_areas.to_crs(epsg=4326)
                            
                            wwtp_info = {idx + 1: name for idx, (_, _, name) in enumerate(self.wwtp_data)}
                            gdf_areas['wwtp_name'] = gdf_areas.index.map(wwtp_info)
                            
                            output_file = os.path.join(self.output_dir, "wwtp_command_areas.geojson")
                            gdf_areas.to_file(output_file, driver='GeoJSON')
                        
                        if wwtp_features:
                            gdf_points = gpd.GeoDataFrame.from_features(wwtp_features, crs=crs)
                            gdf_points = gdf_points.to_crs(epsg=4326)
                            output_file = os.path.join(self.output_dir, "wwtp_locations.geojson")
                            gdf_points.to_file(output_file, driver='GeoJSON')
                        
                        if streamline_features:
                            gdf_lines = gpd.GeoDataFrame.from_features(streamline_features, crs=crs)
                            gdf_lines = gdf_lines.to_crs(epsg=4326)
                            output_file = os.path.join(self.output_dir, "wwtp_streamlines.geojson")
                            gdf_lines.to_file(output_file, driver='GeoJSON')
                        
                        self.progress["value"] = 100
                        self.status_label.config(text=f"Processed {processed} of {total_wwtps} WWTPs successfully")
                        messagebox.showinfo(
                            "Success", 
                            f"Processing complete!\n\nResults saved to:\n- wwtp_command_areas.geojson\n- wwtp_locations.geojson\n- wwtp_streamlines.geojson\n- stream_info.csv\n\nOutput directory:\n{self.output_dir}"
                        )
                        
                finally:
                    try:
                        os.unlink(dem_path)
                    except:
                        pass
                    
        except ValueError as ve:
            messagebox.showerror("Input Error", f"Invalid parameter value: {ve}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred:\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}")
        finally:
            self.processing = False
            self.run_button.config(state="normal")
            self.root.config(cursor="")
            self.progress["value"] = 0

if __name__ == "__main__":
    try:
        root = tk.Tk()
        root.geometry("800x600+100+100")
        app = WWTPModelApp(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Application error: {e}")
        messagebox.showerror("Fatal Error", f"The application encountered a fatal error:\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}")