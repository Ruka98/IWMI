import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import rasterio
import numpy as np
from pyproj import Geod
import geopandas as gpd
from rasterio import features
import pandas as pd
from shapely.geometry import Point, LineString
import os
import tempfile

# Coordinate conversion functions
def geo_to_pixel(lon, lat, transform):
    col, row = ~transform * (lon, lat)
    return int(col), int(row)

def pixel_to_geo(x, y, transform):
    lon, lat = rasterio.transform.xy(transform, y, x, offset='center')
    return lon, lat

def get_circular_pixels(lon, lat, radius_m, transform, geod, dem_shape, dem_data, wwtp_elev=None, elevation_threshold=None):
    x_center, y_center = geo_to_pixel(lon, lat, transform)
    if (x_center < 0 or x_center >= dem_shape[1] or 
        y_center < 0 or y_center >= dem_shape[0]):
        return []
    
    circular_pixels = []
    clon, clat = pixel_to_geo(x_center, y_center, transform)
    east_x = x_center + 1
    east_lon, east_lat = pixel_to_geo(east_x, y_center, transform)
    _, _, dist_east = geod.inv(clon, clat, east_lon, east_lat)
    
    max_dx = int(np.ceil(radius_m / dist_east)) if dist_east != 0 else 0
    
    for dx in range(-max_dx, max_dx + 1):
        for dy in range(-max_dx, max_dx + 1):
            x = x_center + dx
            y = y_center + dy
            if 0 <= x < dem_shape[1] and 0 <= y < dem_shape[0]:
                plon, plat = pixel_to_geo(x, y, transform)
                _, _, distance = geod.inv(lon, lat, plon, plat)
                if distance <= radius_m:
                    pixel_elev = dem_data[y, x]
                    elev_condition = True
                    if wwtp_elev is not None and elevation_threshold is not None:
                        elev_condition = (pixel_elev <= wwtp_elev + elevation_threshold)
                    if not np.ma.is_masked(pixel_elev) and elev_condition:
                        circular_pixels.append((y, x))
    
    return circular_pixels

def trace_downstream_fixed_distance(start_lon, start_lat, transform, dem_data, geod, distance_limit=5000):
    x, y = geo_to_pixel(start_lon, start_lat, transform)
    if x < 0 or x >= dem_data.shape[1] or y < 0 or y >= dem_data.shape[0]:
        return []
    current_elev = dem_data[y, x]
    if np.ma.is_masked(current_elev):
        return []
    
    path = [(x, y)]
    current_lon, current_lat = pixel_to_geo(x, y, transform)
    total_distance = 0.0
    
    while total_distance < distance_limit:
        min_elev = current_elev
        best_nx, best_ny = x, y
        # Find steepest downhill neighbor
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if nx < 0 or nx >= dem_data.shape[1] or ny < 0 or ny >= dem_data.shape[0]:
                    continue
                elev = dem_data[ny, nx]
                if np.ma.is_masked(elev):
                    continue
                if elev < min_elev:
                    min_elev = elev
                    best_nx, best_ny = nx, ny
                    
        if (best_nx, best_ny) == (x, y):
            break  # No downhill neighbor (reached a sink)
        
        # Calculate distance to next pixel
        next_lon, next_lat = pixel_to_geo(best_nx, best_ny, transform)
        _, _, segment_distance = geod.inv(current_lon, current_lat, next_lon, next_lat)
        
        # Check if adding this segment would exceed the distance limit
        if total_distance + segment_distance > distance_limit:
            # Calculate how far we can go in this direction to exactly reach distance_limit
            fraction = (distance_limit - total_distance) / segment_distance
            # We could interpolate a point here, but for simplicity, just add the next point
            # if we've gone at least halfway there
            if fraction >= 0.5:
                path.append((best_nx, best_ny))
            break
        
        # Update current position and elevation
        x, y = best_nx, best_ny
        current_elev = dem_data[y, x]
        current_lon, current_lat = next_lon, next_lat
        path.append((x, y))
        
        # Update total distance
        total_distance += segment_distance
    
    return path

class WWTPModelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WWTP Model Interface")
        
        self.dem_file = None
        self.excel_file = None
        self.output_dir = "output"
        
        self.create_widgets()
    
    def create_widgets(self):
        ttk.Label(self.root, text="DEM File:").grid(row=0, column=0, padx=10, pady=10)
        self.dem_entry = ttk.Entry(self.root, width=50)
        self.dem_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Button(self.root, text="Browse", command=self.browse_dem).grid(row=0, column=2, padx=10, pady=10)
        
        ttk.Label(self.root, text="Excel File:").grid(row=1, column=0, padx=10, pady=10)
        self.excel_entry = ttk.Entry(self.root, width=50)
        self.excel_entry.grid(row=1, column=1, padx=10, pady=10)
        ttk.Button(self.root, text="Browse", command=self.browse_excel).grid(row=1, column=2, padx=10, pady=10)
        
        ttk.Label(self.root, text="Output Directory:").grid(row=2, column=0, padx=10, pady=10)
        self.output_entry = ttk.Entry(self.root, width=50)
        self.output_entry.grid(row=2, column=1, padx=10, pady=10)
        self.output_entry.insert(0, self.output_dir)
        ttk.Button(self.root, text="Browse", command=self.browse_output).grid(row=2, column=2, padx=10, pady=10)
        
        ttk.Button(self.root, text="Run Model", command=self.run_model).grid(row=3, column=1, padx=10, pady=20)
    
    def browse_dem(self):
        self.dem_file = filedialog.askopenfilename(filetypes=[("TIF files", "*.tif")])
        self.dem_entry.delete(0, tk.END)
        self.dem_entry.insert(0, self.dem_file)
    
    def browse_excel(self):
        self.excel_file = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        self.excel_entry.delete(0, tk.END)
        self.excel_entry.insert(0, self.excel_file)
    
    def browse_output(self):
        self.output_dir = filedialog.askdirectory()
        self.output_entry.delete(0, tk.END)
        self.output_entry.insert(0, self.output_dir)
    
    def run_model(self):
        if not self.dem_file or not self.excel_file:
            messagebox.showerror("Error", "Please upload both DEM and Excel files.")
            return

        os.makedirs(self.output_dir, exist_ok=True)

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tif") as tmp_dem:
                with open(self.dem_file, 'rb') as f:
                    tmp_dem.write(f.read())
                dem_path = tmp_dem.name

            df = pd.read_excel(self.excel_file)
            # Updated to handle with or without volume column
            if 'Volume' in df.columns:
                wwtp_locations = df[['Longitude', 'Latitude']].values.tolist()
            else:
                wwtp_locations = df[['Longitude', 'Latitude']].values.tolist()

            with rasterio.open(dem_path) as src:
                dem_data = src.read(1, masked=True)
                transform = src.transform
                crs = src.crs
                
                geod = Geod(ellps="WGS84")
                command_areas = np.zeros_like(dem_data.filled(0), dtype=np.int32)
                wwtp_points = []
                streamlines = []

                for idx, (lon, lat) in enumerate(wwtp_locations, 1):
                    try:
                        x_center, y_center = geo_to_pixel(lon, lat, transform)
                        if not (0 <= x_center < dem_data.shape[1] and 0 <= y_center < dem_data.shape[0]):
                            messagebox.showwarning("Warning", f"WWTP {idx} is outside DEM bounds.")
                            continue
                        
                        wwtp_elev = dem_data[y_center, x_center]
                        if np.ma.is_masked(wwtp_elev):
                            messagebox.showwarning("Warning", f"WWTP {idx} has no elevation data.")
                            continue
                        
                        # Part 1: 5km circular buffer with elevation up to 50m higher than WWTP
                        circular_pixels = get_circular_pixels(lon, lat, 500, transform, geod, dem_data.shape, dem_data, wwtp_elev, elevation_threshold=50)
                        for (y, x) in circular_pixels:
                            command_areas[y, x] = idx
                        
                        # Part 2: Trace downstream for fixed 5km distance and buffer 1km around path
                        downstream_path = trace_downstream_fixed_distance(lon, lat, transform, dem_data, geod, distance_limit=5000)
                        if downstream_path and len(downstream_path) >= 2:  # Ensure at least 2 points
                            # Convert downstream path to geographic coordinates
                            downstream_coords = [pixel_to_geo(x, y, transform) for (x, y) in downstream_path]
                            streamlines.append(downstream_coords)
                            # Create 1km buffer around downstream path (no elevation check)
                            for (x_p, y_p) in downstream_path:
                                plon, plat = pixel_to_geo(x_p, y_p, transform)
                                buffer_pixels = get_circular_pixels(plon, plat, 500, transform, geod, dem_data.shape, dem_data)
                                for (y_b, x_b) in buffer_pixels:
                                    command_areas[y_b, x_b] = idx
                        
                        # Save WWTP location as a point
                        wwtp_points.append(Point(lon, lat))
                    except Exception as e:
                        messagebox.showerror("Error", f"Error processing WWTP {idx}: {e}")
                
                mask = command_areas > 0
                features_list = []
                wwtp_names = df['WWTP'].tolist() if 'WWTP' in df.columns else [f"WWTP_{i}" for i in range(1, len(wwtp_locations)+1)]
                
                for geom, value in features.shapes(command_areas, mask=mask, transform=transform):
                    if value == 0:
                        continue
                    wwtp_index = int(value)
                    if 1 <= wwtp_index <= len(wwtp_names):
                        features_list.append({
                            'geometry': geom,
                            'properties': {'name': wwtp_names[wwtp_index-1], 'id': wwtp_index}
                        })
                
                if features_list:
                    gdf = gpd.GeoDataFrame.from_features(features_list, crs=crs)
                    gdf = gdf.dissolve(by='id').reset_index()
                    gdf = gdf.to_crs(epsg=4326)
                    output_file = os.path.join(self.output_dir, "OP2wwtp_command_areas.geojson")
                    gdf.to_file(output_file, driver='GeoJSON')
                    messagebox.showinfo("Success", f"Command areas saved to {output_file}")
                
                if wwtp_points:
                    wwtp_gdf = gpd.GeoDataFrame(geometry=wwtp_points, crs='EPSG:4326')
                    if 'WWTP' in df.columns:
                        wwtp_gdf['name'] = df['WWTP']
                    else:
                        wwtp_gdf['name'] = [f"WWTP_{i}" for i in range(1, len(wwtp_points)+1)]
                    output_file = os.path.join(self.output_dir, "OP2wwtp_locations.geojson")
                    wwtp_gdf.to_file(output_file, driver='GeoJSON')
                    messagebox.showinfo("Success", f"WWTP locations saved to {output_file}")
                
                if streamlines:
                    streamline_geometries = [LineString(coords) for coords in streamlines if len(coords) >= 2]  # Ensure valid LineString
                    if streamline_geometries:
                        streamline_gdf = gpd.GeoDataFrame(geometry=streamline_geometries, crs=crs)
                        streamline_gdf = streamline_gdf.to_crs(epsg=4326)
                        output_file = os.path.join(self.output_dir, "OP2streamlines.geojson")
                        streamline_gdf.to_file(output_file, driver='GeoJSON')
                        messagebox.showinfo("Success", f"Streamlines saved to {output_file}")
                    else:
                        messagebox.showwarning("Warning", "No valid streamlines to save.")
                
            os.unlink(dem_path)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = WWTPModelApp(root)
    root.mainloop()