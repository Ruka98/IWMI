import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import glob
import logging
from pathlib import Path
from osgeo import gdal, osr
import shutil

# Enable GDAL exceptions
gdal.UseExceptions()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set working directory to the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Add WA_jordan folder to sys.path to import WA module
wa_jordan_dir = os.path.join(script_dir, 'WA_jordan')
sys.path.append(wa_jordan_dir)
from WA import AWAS_to_LUWA as LtL

def check_crs_compatibility(raster_path, shapefile_path):
    """Check if the CRS of the raster and shapefile are compatible."""
    try:
        raster_ds = gdal.Open(raster_path)
        if not raster_ds:
            raise ValueError(f"Failed to open raster: {raster_path}")
        raster_srs = osr.SpatialReference()
        raster_srs.ImportFromWkt(raster_ds.GetProjection())
        raster_crs = raster_srs.GetAuthorityCode("PROJCS") or raster_srs.GetAuthorityCode("GEOGCS")

        shapefile_ds = gdal.OpenEx(shapefile_path, gdal.OF_VECTOR)
        if not shapefile_ds:
            raise ValueError(f"Failed to open shapefile: {shapefile_path}")
        layer = shapefile_ds.GetLayer()
        shapefile_srs = layer.GetSpatialRef()
        shapefile_crs = shapefile_srs.GetAuthorityCode("PROJCS") or shapefile_srs.GetAuthorityCode("GEOGCS")

        if raster_crs != shapefile_crs:
            logger.warning(f"CRS mismatch: Raster CRS={raster_crs}, Shapefile CRS={shapefile_crs}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking CRS: {str(e)}")
        return False

def rasterize_shapefile(shapefile_path, template_raster_path, output_path, burn_value=1):
    """Alternative rasterization function using GDAL Python bindings"""
    try:
        # Get template raster info
        template = gdal.Open(template_raster_path)
        if template is None:
            raise ValueError(f"Could not open template raster: {template_raster_path}")
        
        # Create output raster
        driver = gdal.GetDriverByName('GTiff')
        out_raster = driver.Create(
            output_path,
            template.RasterXSize,
            template.RasterYSize,
            1,
            gdal.GDT_Byte,
            options=['COMPRESS=LZW', 'TILED=YES']
        )
        out_raster.SetGeoTransform(template.GetGeoTransform())
        out_raster.SetProjection(template.GetProjection())
        
        # Initialize with 0 and set no data value
        band = out_raster.GetRasterBand(1)
        band.Fill(0)
        band.SetNoDataValue(0)
        
        # Rasterize the shapefile
        shapefile = gdal.OpenEx(shapefile_path, gdal.OF_VECTOR)
        if shapefile is None:
            raise ValueError(f"Could not open shapefile: {shapefile_path}")
        
        gdal.RasterizeLayer(
            out_raster,
            [1],
            shapefile.GetLayer(),
            burn_values=[burn_value],
            options=["ALL_TOUCHED=TRUE"]
        )
        
        # Close datasets
        out_raster = None
        shapefile = None
        template = None
        
        if not os.path.exists(output_path):
            raise RuntimeError(f"Output file was not created: {output_path}")
            
        return True
    except Exception as e:
        logger.error(f"Error in rasterize_shapefile: {str(e)}")
        # Clean up if output was partially created
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        return False

class LUWAProcessingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LUWA Processing Interface")
        self.root.geometry("600x400")

        # Variables to store input and output paths
        self.lcc_folder = tk.StringVar(value="")
        self.grand_reservoir = tk.StringVar(value="")
        self.wdpa = tk.StringVar(value="")
        self.luwa_output_dir = tk.StringVar(value=os.path.join(script_dir, 'luwa'))

        # Create GUI elements
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self.root, text="LCC Folder (WaPOR LCC GeoTIFFs):").pack(pady=5)
        tk.Entry(self.root, textvariable=self.lcc_folder, width=50).pack()
        tk.Button(self.root, text="Browse", command=self.browse_lcc_folder).pack()

        tk.Label(self.root, text="GRanD Reservoir Shapefile:").pack(pady=5)
        tk.Entry(self.root, textvariable=self.grand_reservoir, width=50).pack()
        tk.Button(self.root, text="Browse", command=self.browse_grand_reservoir).pack()

        tk.Label(self.root, text="WDPA Shapefile:").pack(pady=5)
        tk.Entry(self.root, textvariable=self.wdpa, width=50).pack()
        tk.Button(self.root, text="Browse", command=self.browse_wdpa).pack()

        tk.Label(self.root, text="LUWA Output Directory:").pack(pady=5)
        tk.Entry(self.root, textvariable=self.luwa_output_dir, width=50).pack()
        tk.Button(self.root, text="Browse", command=self.browse_luwa_output_dir).pack()

        tk.Button(self.root, text="Run Processing", command=self.run_processing, bg="green", fg="white").pack(pady=20)

    def browse_lcc_folder(self):
        directory = filedialog.askdirectory()
        if directory:
            self.lcc_folder.set(directory)

    def browse_grand_reservoir(self):
        file = filedialog.askopenfilename(filetypes=[("Shapefiles", "*.shp")])
        if file:
            self.grand_reservoir.set(file)

    def browse_wdpa(self):
        file = filedialog.askopenfilename(filetypes=[("Shapefiles", "*.shp")])
        if file:
            self.wdpa.set(file)

    def browse_luwa_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.luwa_output_dir.set(directory)

    def run_processing(self):
        try:
            # Validate inputs
            if not all([self.lcc_folder.get(), self.grand_reservoir.get(), self.wdpa.get(), self.luwa_output_dir.get()]):
                messagebox.showerror("Error", "Please specify all required paths!")
                return

            # Normalize paths and ensure they are absolute
            lcc_folder = str(Path(self.lcc_folder.get()).resolve())
            grand_reservoir = str(Path(self.grand_reservoir.get()).resolve())
            wdpa = str(Path(self.wdpa.get()).resolve())
            main_dir = str(Path(self.luwa_output_dir.get()).resolve())

            # Validate input files
            if not os.path.exists(lcc_folder):
                messagebox.showerror("Error", f"LCC folder does not exist: {lcc_folder}")
                return
            if not os.path.exists(grand_reservoir):
                messagebox.showerror("Error", f"GRanD Reservoir shapefile does not exist: {grand_reservoir}")
                return
            if not os.path.exists(wdpa):
                messagebox.showerror("Error", f"WDPA shapefile does not exist: {wdpa}")
                return

            # Create main output directory
            os.makedirs(main_dir, exist_ok=True)
            logger.info(f"Main output directory: {main_dir}")

            # Get all yearly WaPOR LCC maps
            lcc_fhs = glob.glob(os.path.join(lcc_folder, '*.tif'))
            if not lcc_fhs:
                messagebox.showerror("Error", "No .tif files found in LCC folder!")
                return
            
            # Use the first LCC file as template
            wapor_lcc = lcc_fhs[0]
            logger.info(f"Using template LCC file: {wapor_lcc}")

            # Check CRS compatibility
            if not check_crs_compatibility(wapor_lcc, grand_reservoir):
                messagebox.showwarning("Warning", "CRS mismatch between LCC raster and GRanD shapefile. Processing may fail.")
            if not check_crs_compatibility(wapor_lcc, wdpa):
                messagebox.showwarning("Warning", "CRS mismatch between LCC raster and WDPA shapefile. Processing may fail.")

            # Create Reservoir raster map for basin
            reservoir_dir = os.path.join(main_dir, 'static_datasets', 'Reservoir')
            os.makedirs(reservoir_dir, exist_ok=True)
            basin_reservoir_tif = os.path.join(reservoir_dir, 'Reservoir_basin.tif')
            
            logger.info(f"Creating reservoir raster: {basin_reservoir_tif}")
            if not rasterize_shapefile(grand_reservoir, wapor_lcc, basin_reservoir_tif):
                messagebox.showerror("Error", "Failed to create reservoir raster")
                return
            logger.info("Successfully created reservoir raster")

            # Create Protected Area raster map for basin
            protected_dir = os.path.join(main_dir, 'static_datasets', 'Protected')
            os.makedirs(protected_dir, exist_ok=True)
            protected_area_tif = os.path.join(protected_dir, 'ProtectedArea_basin.tif')
            
            logger.info(f"Creating protected area raster: {protected_area_tif}")
            if not rasterize_shapefile(wdpa, wapor_lcc, protected_area_tif):
                messagebox.showerror("Error", "Failed to create protected area raster")
                return
            logger.info("Successfully created protected area raster")

            # Reclassify LCC to LUWA
            luwa_output_dir = os.path.join(main_dir, 'luwa_output')
            os.makedirs(luwa_output_dir, exist_ok=True)
            logger.info(f"Reclassifying LCC to LUWA in: {luwa_output_dir}")
            
            for fh in lcc_fhs:
                try:
                    logger.info(f"Processing {os.path.basename(fh)}")
                    LtL.Reclass_LCC_to_LUWA(fh, luwa_output_dir, protected_area_tif, basin_reservoir_tif)
                    logger.info(f"Successfully processed {os.path.basename(fh)}")
                except Exception as e:
                    logger.error(f"Error processing {fh}: {str(e)}")
                    messagebox.showerror("Error", f"Error processing {os.path.basename(fh)}:\n{str(e)}")
                    return

            messagebox.showinfo("Success", "Processing completed successfully!")
            logger.info("Processing completed successfully")
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"An unexpected error occurred:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = LUWAProcessingGUI(root)
    root.mainloop()