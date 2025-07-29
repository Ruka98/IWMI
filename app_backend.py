import os
import sys
import threading
import glob
import time
import logging
import numpy as np
from netCDF4 import Dataset
from osgeo import gdal
import xarray as xr
import pandas as pd
import warnings
import traceback
from typing import Callable, Optional

# Suppress warnings for clean logs
warnings.filterwarnings("ignore", category=FutureWarning, message=".*'M' is deprecated.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in divide")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('app.log')]
)
logger = logging.getLogger("UnifiedApp")

# Set base directory for PyInstaller or script
def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

base_path = get_base_path()
sys.path.append(os.path.join(base_path, 'WA_jordan'))

# Set GDAL and PROJ environment variables
gdal_data_path = os.path.join(base_path, 'gdal-data')
proj_data_path = os.path.join(base_path, 'proj-data')
if os.path.exists(gdal_data_path):
    os.environ["GDAL_DATA"] = gdal_data_path
    logger.info(f"GDAL_DATA set to: {gdal_data_path}")
else:
    logger.error(f"GDAL data directory not found at {gdal_data_path}")
if os.path.exists(proj_data_path) and os.path.exists(os.path.join(proj_data_path, 'proj.db')):
    os.environ["PROJ_LIB"] = proj_data_path
    logger.info(f"PROJ_LIB set to: {proj_data_path}")
else:
    logger.error(f"PROJ data directory or proj.db not found at {proj_data_path}")

gdal.UseExceptions()
gdal.SetConfigOption("CPL_DEBUG", "ON")

# Import custom modules
try:
    from WA_jordan import createNC_cmi, pre_proc_sm_balance
    from WA_jordan.SMBalance import run_SMBalance
    from WAsheets import model_hydroloop as mhl
    from WAsheets import sheet1, sheet2, print_sheet
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    sys.exit(1)

# Dataset configuration for NetCDF creation
dataset_config = {
    'P': {
        'subdir': os.path.join('P', 'Monthly'),
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'mm/month', 'source': 'CHIRPS', 'quantity': 'P', 'temporal_resolution': 'monthly'}
    },
    'dailyP': {
        'subdir': os.path.join('P', 'Daily'),
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'mm/d', 'source': 'CHIRPS', 'quantity': 'dailyP', 'temporal_resolution': 'daily'}
    },
    'ET': {
        'subdir': 'ET',
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'mm/month', 'source': 'V6', 'quantity': 'ETa', 'temporal_resolution': 'monthly'}
    },
    'LAI': {
        'subdir': 'LAI',
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'None', 'source': 'MOD15', 'quantity': 'LAI', 'temporal_resolution': 'monthly'}
    },
    'SMsat': {
        'subdir': 'ThetaSat',
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'None', 'source': 'HiHydroSoils', 'quantity': 'SMsat', 'temporal_resolution': 'monthly'}
    },
    'Ari': {
        'subdir': 'Aridity',
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'None', 'source': 'CHIRPS_GLEAM', 'quantity': 'Aridity', 'temporal_resolution': 'monthly'}
    },
    'LU': {
        'subdir': 'LUWA',
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'None', 'source': 'WA', 'quantity': 'LU', 'temporal_resolution': 'static'}
    },
    'ProbaV': {
        'subdir': 'NDM',
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'None', 'source': 'ProbaV', 'quantity': 'NDM', 'temporal_resolution': 'monthly'}
    },
    'ETref': {
        'subdir': 'ETref',
        'dims': ('time', 'latitude', 'longitude'),
        'attrs': {'units': 'None', 'source': 'L1_RET', 'quantity': 'ETref', 'temporal_resolution': 'monthly'}
    }
}

class Backend:
    def __init__(self):
        self.running = False
        self.BASIN = None
        self.current_progress = 0
        self.max_progress = 100
        self.last_progress_update = 0
        self.progress_lock = threading.Lock()

    def log_message(self, message):
        logger.info(message)
        return f"[{time.strftime('%H:%M:%S')}] {message}\n"

    def update_progress(self, progress_callback: Optional[Callable], current: int, total: int, force_update=False, message=None):
        """Update progress and notify callback if provided"""
        now = time.time()
        with self.progress_lock:
            if force_update or (now - self.last_progress_update > 0.1):
                # Always scale progress to 0-100
                scaled_progress = int((current / total) * 100) if total > 0 else 0
                self.current_progress = scaled_progress
                self.max_progress = 100  # Always use 100 as max
                if progress_callback:
                    try:
                        progress_callback(scaled_progress, 100, message)  # Always send scaled 0-100 values
                    except Exception as e:
                        logger.error(f"Progress callback error: {str(e)}")
                self.last_progress_update = now

    def create_netcdf(self, input_dir, shp_path, template_path, output_dir, progress_callback=None):
        if self.running:
            return False, [self.log_message("A task is already running.")]
        self.running = True
        messages = [self.log_message("Starting NetCDF creation...")]
        try:
            # Validate input paths
            if not all([input_dir, shp_path, template_path, output_dir]):
                messages.append(self.log_message("Error: All input paths must be provided"))
                return False, messages
            if not all([os.path.exists(p) for p in [input_dir, shp_path, template_path]]):
                messages.append(self.log_message("Error: One or more input paths do not exist"))
                return False, messages
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    messages.append(self.log_message(f"Created output directory: {output_dir}"))
                except OSError as e:
                    messages.append(self.log_message(f"Error: Failed to create output directory {output_dir}: {str(e)}"))
                    return False, messages
            if not os.access(output_dir, os.W_OK):
                messages.append(self.log_message(f"Error: No write permission for output directory {output_dir}"))
                return False, messages
            if not os.path.isfile(shp_path) or not shp_path.lower().endswith('.shp'):
                messages.append(self.log_message(f"Error: Invalid shapefile path: {shp_path}"))
                return False, messages
            if not os.path.isfile(template_path) or not template_path.lower().endswith('.tif'):
                messages.append(self.log_message(f"Error: Invalid template file path: {template_path}"))
                return False, messages

            # Check GDAL and PROJ configuration
            if "GDAL_DATA" not in os.environ or not os.path.exists(os.environ["GDAL_DATA"]):
                messages.append(self.log_message("Error: GDAL_DATA environment variable not set or invalid"))
                return False, messages
            if "PROJ_LIB" not in os.environ or not os.path.exists(os.path.join(os.environ["PROJ_LIB"], 'proj.db')):
                messages.append(self.log_message("Error: PROJ_LIB environment variable not set or proj.db missing"))
                return False, messages

            # Scan directories to count total files and calculate weights
            total_files = 0
            file_counts = {}
            dataset_weights = {}  # Track weight for each dataset
            for d, config in dataset_config.items():
                data_path = os.path.join(input_dir, config['subdir'])
                files = glob.glob(os.path.join(data_path, '*.tif'))
                file_counts[d] = len(files)
                total_files += file_counts[d]
                # Assign weight based on expected processing time (adjust as needed)
                dataset_weights[d] = 1.0  # Equal weight by default
            
            if total_files == 0:
                messages.append(self.log_message("Error: No TIFF files found in any input directory"))
                return False, messages
            
            messages.append(self.log_message(f"Found {total_files} TIFF files to process across {len(dataset_config)} datasets"))
            
            # Calculate cumulative weights
            total_weight = sum(dataset_weights.values())
            cumulative_progress = 0
            
            for d, config in dataset_config.items():
                if file_counts[d] == 0:
                    messages.append(self.log_message(f"No TIFFs found for {d}, skipping"))
                    continue
                    
                data_path = os.path.join(input_dir, config['subdir'])
                files = glob.glob(os.path.join(data_path, '*.tif'))
                
                nc_filename = f"Awash_{config['attrs']['quantity']}_{config['attrs']['source']}.nc"
                nc_path = os.path.join(output_dir, nc_filename)
                dataset_info = {d: [data_path, config['dims'], config['attrs']]}
                
                messages.append(self.log_message(f"Processing {len(files)} files for {d}..."))
                
                # Calculate progress range for this dataset
                dataset_progress = (dataset_weights[d] / total_weight) * 100
                start_progress = cumulative_progress
                end_progress = cumulative_progress + dataset_progress
                
                # Update progress at start of dataset
                self.update_progress(
                    progress_callback, 
                    int(start_progress), 
                    100, 
                    message=f"Starting {d}"
                )
                
                # Create the NetCDF file
                try:
                    with Dataset(nc_path, 'w', format='NETCDF4') as nc_file:
                        pass  # Create empty file to ensure write permissions
                except OSError as e:
                    messages.append(self.log_message(f"Error: Failed to create NetCDF file {nc_filename}: {str(e)}"))
                    return False, messages
                
                # Call make_netcdf
                try:
                    success = createNC_cmi.make_netcdf(
                        nc_path, 
                        dataset_info, 
                        shp_path, 
                        template_path, 
                        os.path.basename(shp_path).split('.')[0]  # Use shapefile name as basin name
                    )
                    if not success:
                        messages.append(self.log_message(f"Error: Failed to process dataset {d}"))
                        return False, messages
                    messages.append(self.log_message(f"Successfully created {nc_filename}"))
                except Exception as e:
                    messages.append(self.log_message(f"Error creating {nc_filename}: {str(e)}"))
                    return False, messages
                
                # Update progress after completing dataset
                cumulative_progress = end_progress
                self.update_progress(
                    progress_callback, 
                    int(cumulative_progress), 
                    100, 
                    message=f"Completed {d}"
                )

            messages.append(self.log_message("NetCDF creation completed."))
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}\nDetails:\n{traceback.format_exc()}"))
            return False, messages
        finally:
            self.running = False

    def calculate_rain(self, directory, progress_callback=None):
        if self.running:
            return False, ["A task is already running."]
        self.running = True
        try:
            messages = [self.log_message("Starting rainfall interception processing...")]
            
            if not directory or not os.path.exists(directory):
                messages.append(self.log_message("Error: Please select a valid input directory"))
                return False, messages

            nc_files = {
                'dailyP': os.path.join(directory, "Awash_dailyP_CHIRPS.nc"),
                'P': os.path.join(directory, "Awash_P_CHIRPS.nc"),
                'LAI': os.path.join(directory, "Awash_LAI_MOD15.nc")
            }
            
            total_steps = 300
            current_step = 0
            
            for key, nc_file in nc_files.items():
                if not os.path.exists(nc_file):
                    messages.append(self.log_message(f"Error: Input NetCDF file not found: {nc_file}"))
                    return False, messages
                current_step += 33
                self.update_progress(progress_callback, current_step, total_steps, message=f"Validating {key}")

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                nrd_nc = pre_proc_sm_balance.rainy_days(nc_files['dailyP'], nc_files['P'])
                current_step += 33
                self.update_progress(progress_callback, current_step, total_steps, message="Processing rainy days")

            I_nc = pre_proc_sm_balance.interception(nc_files['LAI'], nc_files['P'], nrd_nc)
            current_step = total_steps
            self.update_progress(progress_callback, current_step, total_steps, force_update=True, message="Processing interception")

            messages.append(self.log_message("Rainfall interception processing completed."))
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}\nDetails:\n{traceback.format_exc()}"))
            return False, messages
        finally:
            self.running = False

    def run_smbalance(self, directory, start_year, end_year, f_perc, f_smax, cf, f_bf, deep_perc_f, progress_callback=None):
        if self.running:
            return False, ["A task is already running."]
        self.running = True
        try:
            messages = []
            
            if not directory or not os.path.exists(directory):
                messages.append(self.log_message("Error: Please select a valid input directory"))
                return False, messages

            try:
                start_year = int(start_year)
                end_year = int(end_year)
                f_perc = float(f_perc)
                f_smax = float(f_smax)
                cf = float(cf)
                f_bf = float(f_bf)
                deep_perc_f = float(deep_perc_f)
            except ValueError:
                messages.append(self.log_message("Error: Please enter valid numerical values"))
                return False, messages

            if start_year > end_year:
                messages.append(self.log_message("Error: Start year must be less than or equal to end year"))
                return False, messages

            nc_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.nc')]
            quantity_to_key = {
                '_P_': 'P', 'i_monthly': 'I', 'nRD_monthly': 'NRD', '_LU_': 'LU',
                '_ETa_': 'ET', '_SMsat_': 'SMsat', '_Aridity_': 'Ari'
            }
            nc_files_dict = {}
            
            for file_path in nc_files:
                file_name = os.path.basename(file_path)
                for pattern, key in quantity_to_key.items():
                    if pattern in file_name:
                        nc_files_dict[key] = file_path
                        break

            required_keys = ['P', 'ET', 'I', 'NRD', 'LU', 'SMsat', 'Ari']
            missing_keys = [key for key in required_keys if key not in nc_files_dict]
            if missing_keys:
                messages.append(self.log_message(f"Error: Missing required NetCDF files for keys: {missing_keys}"))
                return False, messages

            params = {
                'f_perc': f_perc, 'f_Smax': f_smax, 'cf': cf, 'f_bf': f_bf,
                'deep_perc_f': deep_perc_f, 'root_depth_version': '1.0', 'chunks': [1, 100, 100]
            }
            
            # Update progress before starting SMBalance
            self.update_progress(progress_callback, 0, 100, force_update=True, message="Starting SMBalance")
            
            # Run SMBalance without progress callback
            run_SMBalance(directory, nc_files_dict, start_year, end_year, **params)
            
            # Update progress after completion
            self.update_progress(progress_callback, 100, 100, force_update=True, message="SMBalance completed")
            
            messages.append(self.log_message("Soil moisture balance calculation completed."))
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}\nDetails:\n{traceback.format_exc()}"))
            return False, messages
        finally:
            self.running = False

    def collect_hydroloop_files(self, input_dir):
        files = {}
        if not os.path.exists(input_dir):
            return {}, [self.log_message(f"Input directory does not exist: {input_dir}")]
        messages = []
        for filename in os.listdir(input_dir):
            full_path = os.path.join(input_dir, filename)
            if os.path.isfile(full_path):
                try:
                    with xr.open_dataset(full_path) as ds:
                        time_dim = ds.sizes.get('time', None)
                        messages.append(self.log_message(f"File {filename}: time dimension = {time_dim}"))
                except Exception as e:
                    messages.append(self.log_message(f"Error reading {filename}: {str(e)}"))
                    continue
                if 'Awash_ETa_V6.nc' in filename:
                    files['ET'] = full_path
                elif 'P_CHIRPS' in filename and 'dailyP' not in filename:
                    files['P'] = full_path
                elif 'Awash_ETref_L1_RET.nc' in filename:
                    files['ETref'] = full_path
                elif 'Awash_LAI_MOD15.nc' in filename:
                    files['LAI'] = full_path
                elif 'LU_WA' in filename:
                    files['LU'] = full_path
                elif 'Awash_NDM_ProbaV.nc' in filename:
                    files['ProbaV'] = full_path
                elif 'i_monthly.nc' in filename:
                    files['I'] = full_path
                elif 'nRD_monthly.nc' in filename:
                    files['NRD'] = full_path
                elif 'bf_monthly.nc' in filename:
                    files['BF'] = full_path
                elif 'supply_monthly.nc' in filename:
                    files['Supply'] = full_path
                elif 'etincr_monthly.nc' in filename:
                    files['ETB'] = full_path
                elif 'etrain_monthly.nc' in filename:
                    files['ETG'] = full_path
                elif 'sro_monthly.nc' in filename and 'd_sro_monthly' not in filename:
                    files['SRO'] = full_path
                elif 'perco_monthly.nc' in filename and 'd_perco_monthly' not in filename:
                    files['PERC'] = full_path
                elif 'd_sro_monthly.nc' in filename:
                    files['ISRO'] = full_path
                elif 'd_perco_monthly.nc' in filename:
                    files['DPERC'] = full_path
        required_vars = ['P', 'ET', 'ETref', 'I', 'NRD', 'ProbaV', 'LU', 'SRO', 'PERC', 'BF', 'Supply', 'ETB', 'ETG', 'LAI']
        missing = [var for var in required_vars if var not in files]
        if missing:
            messages.append(self.log_message(f"Missing required files: {', '.join(missing)}"))
        for var in ['ISRO', 'DPERC']:
            if var not in files:
                files[var] = None
                messages.append(self.log_message(f"Optional file {var} not found, set to None"))
        return files, messages

    def init_hydroloop(self, inputs, progress_callback=None):
        if self.running:
            return False, ["A task is already running."]
        self.running = True
        try:
            messages = []
            total_steps = 100
            current_step = 0
            
            for key in ['nc_dir', 'result_dir', 'template_mask', 'dem_path', 'aeisw_path', 'population_path', 'wpl_path', 'ewr_path']:
                if not inputs[key] or not os.path.exists(inputs[key]):
                    messages.append(self.log_message(f"Error: {key.replace('_', ' ').title()} is invalid or does not exist"))
                    return False, messages
            for key in ['inflow', 'outflow', 'desalination']:
                if inputs[key] and not os.path.exists(inputs[key]):
                    messages.append(self.log_message(f"Error: {key.title()} file does not exist"))
                    return False, messages
            try:
                inputs['unit_conversion'] = float(inputs['unit_conversion'])
                if inputs['unit_conversion'] <= 0:
                    raise ValueError("Unit conversion factor must be positive")
            except ValueError as e:
                messages.append(self.log_message(f"Error: {str(e)}"))
                return False, messages
            current_step += 50
            self.update_progress(progress_callback, current_step, total_steps, message="Validating inputs")

            os.makedirs(inputs['result_dir'], exist_ok=True)
            current_step += 25
            self.update_progress(progress_callback, current_step, total_steps, message="Preparing directories")
            
            files, file_messages = self.collect_hydroloop_files(inputs['nc_dir'])
            messages.extend(file_messages)
            if not files:
                messages.append(self.log_message("Error: No valid input files found"))
                return False, messages
            current_step += 125
            self.update_progress(progress_callback, current_step, total_steps, message="Collecting files")

            table_data = mhl.collect_tables(
                folder=inputs['result_dir'],
                inflow=inputs['inflow'] or None,
                outflow=inputs['outflow'] or None,
                desal=inputs['desalination'] or None
            )
            messages.append(self.log_message(f"Table data keys: {list(table_data.keys())}"))
            current_step += 150
            self.update_progress(progress_callback, current_step, total_steps, message="Collecting tables")

            metadata = mhl.create_metadata(
                basin_name=inputs['basin_name'],
                hydro_year=inputs['hydro_year'],
                output_folder=inputs['result_dir'],
                basin_mask=inputs['template_mask'],
                dem=inputs['dem_path'],
                aeisw=inputs['aeisw_path'],
                population=inputs['population_path'],
                wpl=inputs['wpl_path'],
                environ_water_req=inputs['ewr_path'],
                unit_conversion=inputs['unit_conversion'],
                chunksize=[1, 100, 100]
            )
            messages.append(self.log_message(f"Initializing Hydroloop with metadata: basin_name={inputs['basin_name']}, hydro_year={inputs['hydro_year']}"))
            
            for i in range(30):
                time.sleep(0.05)
                current_step += 1
                self.update_progress(progress_callback, current_step, total_steps, message="Initializing Hydroloop")
                
            self.BASIN = mhl.initialize_hydroloop(metadata, files, table_data)
            messages.append(self.log_message(f"BASIN ts_data keys: {list(self.BASIN['ts_data'].keys())}"))
            messages.append(self.log_message("Hydroloop initialized successfully."))
            
            self.update_progress(progress_callback, total_steps, total_steps, force_update=True, message="Hydroloop initialization completed")
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}\nDetails:\n{traceback.format_exc()}"))
            return False, messages
        finally:
            self.running = False

    def finalize_hydroloop_outputs(self, basin):
        """Finalize Hydroloop outputs by saving results to NetCDF files."""
        try:
            messages = []
            output_dir = basin.get('output_folder', '')
            if not output_dir or not os.path.exists(output_dir):
                messages.append(self.log_message("Error: Invalid output directory for finalizing Hydroloop outputs"))
                return basin, messages
            
            for key, data in basin['ts_data'].items():
                if isinstance(data, xr.Dataset) or isinstance(data, xr.DataArray):
                    output_path = os.path.join(output_dir, f"hydroloop_{key}.nc")
                    try:
                        data.to_netcdf(output_path, format='NETCDF4')
                        messages.append(self.log_message(f"Saved {key} to {output_path}"))
                    except Exception as e:
                        messages.append(self.log_message(f"Error saving {key} to {output_path}: {str(e)}"))
            
            return basin, messages
        except Exception as e:
            messages.append(self.log_message(f"Error in finalizing Hydroloop outputs: {str(e)}"))
            return basin, messages

    def run_hydroloop(self, progress_callback=None):
        if self.running:
            return False, ["A task is already running."]
        if not self.BASIN:
            return False, ["Hydroloop not initialized"]
        self.running = True
        try:
            messages = []
            process_steps = [
                mhl.resample_lu, 
                mhl.split_et, 
                mhl.split_supply, 
                mhl.calc_demand,
                mhl.calc_return, 
                mhl.calc_residential_supply, 
                mhl.calc_total_supply,
                mhl.calc_fraction, 
                mhl.calc_time_series, 
                self.finalize_hydroloop_outputs
            ]
            
            total_steps = len(process_steps) * 100
            current_step = 0
            
            for i, step in enumerate(process_steps):
                messages.append(self.log_message(f"Starting {step.__name__}"))
                for substep in range(100):
                    time.sleep(0.01)
                    current_step += 1
                    self.update_progress(progress_callback, current_step, total_steps, message=f"Running {step.__name__}")
                    
                result = step(self.BASIN)
                if isinstance(result, tuple):
                    self.BASIN, step_messages = result
                    messages.extend(step_messages)
                else:
                    self.BASIN = result
                    
                messages.append(self.log_message(f"Completed {step.__name__}"))
                current_step = (i + 1) * 100
                self.update_progress(progress_callback, current_step, total_steps, force_update=True, message=f"Completed {step.__name__}")
                
            messages.append(self.log_message("Hydroloop processing completed successfully."))
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}\nDetails:\n{traceback.format_exc()}"))
            return False, messages
        finally:
            self.running = False

    def generate_sheet1(self, basin, progress_callback=None):
        """Generate Sheet 1 CSV and PDF outputs."""
        if self.running:
            return False, ["A task is already running."]
        self.running = True
        try:
            messages = []
            total_steps = 200
            current_step = 0
            
            str_unit = 'MCM' if basin['unit_conversion'] == 1e3 else 'km3'
            
            messages.append(self.log_message("Generating Sheet 1 CSVs..."))
            sheet1_yearly_csvs = sheet1.main(basin, unit_conversion=basin['unit_conversion'])
            messages.append(self.log_message(f"Generated {len(sheet1_yearly_csvs)} yearly sheet CSVs for Sheet 1"))
            
            for _ in range(100):
                time.sleep(0.01)
                current_step += 1
                self.update_progress(progress_callback, current_step, total_steps, message="Generating Sheet 1 CSVs")
            
            messages.append(self.log_message("Generating Sheet 1 PDFs..."))
            for i, sheet1_csv in enumerate(sheet1_yearly_csvs):
                period = os.path.basename(sheet1_csv).split('.')[0].split('_')[-1]
                output = sheet1_csv.replace('.csv', '.pdf')
                print_sheet.print_sheet1(
                    basin['name'],
                    period=period,
                    output=output,
                    units=str_unit,
                    data=sheet1_csv
                )
                messages.append(self.log_message(f"Generated Sheet 1 PDF: {output}"))
                pdf_progress = int(i + 1) / len(sheet1_yearly_csvs) * 100
                self.update_progress(progress_callback, 100 + pdf_progress, total_steps, message=f"Generating PDF for {period}")
            
            self.update_progress(progress_callback, total_steps, total_steps, force_update=True, message="Sheet 1 generation completed")
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error in generating Sheet 1 outputs: {str(e)}\nDetails:\n{traceback.format_exc()}"))
            return False, messages
        finally:
            self.running = False

    def generate_sheet2(self, basin, progress_callback=None):
        """Generate Sheet 2 CSV and PDF outputs."""
        if self.running:
            return False, ["A task is already running."]
        self.running = True
        try:
            if not basin:
                return False, ["Error: Hydroloop not initialized or BASIN object is invalid"]
                
            messages = []
            total_steps = 200
            current_step = 0
            
            str_unit = 'MCM' if basin['unit_conversion'] == 1e3 else 'km3'
            
            messages.append(self.log_message("Generating Sheet 2 CSVs..."))
            try:
                sheet2_yearly_csvs = sheet2.main(basin, unit_conversion=basin['unit_conversion'])
                if not sheet2_yearly_csvs:
                    return False, ["Error: No Sheet 2 CSVs were generated"]
                    
                messages.append(self.log_message(f"Generated {len(sheet2_yearly_csvs)} yearly sheet CSVs for Sheet 2"))
                
                for _ in range(100):
                    time.sleep(0.01)
                    current_step += 1
                    self.update_progress(progress_callback, current_step, total_steps, message="Generating Sheet 2 CSVs")
                
            except Exception as e:
                return False, [self.log_message(f"Error in Sheet 2 CSV generation: {str(e)}\nDetails:\n{traceback.format_exc()}")]

            messages.append(self.log_message("Generating Sheet 2 PDFs..."))
            try:
                for i, sheet2_csv in enumerate(sheet2_yearly_csvs):
                    period = os.path.basename(sheet2_csv).split('.')[0].split('_')[-1]
                    output = sheet2_csv.replace('.csv', '.pdf')
                    print_sheet.print_sheet2(
                        basin['name'],
                        period=period,
                        output=output,
                        units=str_unit,
                        data=sheet2_csv
                    )
                    messages.append(self.log_message(f"Generated Sheet 2 PDF: {output}"))
                    pdf_progress = int(i + 1) / len(sheet2_yearly_csvs) * 100
                    self.update_progress(progress_callback, 100 + pdf_progress, total_steps, message=f"Generating PDF for {period}")
                
                self.update_progress(progress_callback, total_steps, total_steps, force_update=True, message="Sheet 2 generation completed")
                return True, messages
            except Exception as e:
                return False, [self.log_message(f"Error in Sheet 2 PDF generation: {str(e)}\nDetails:\n{traceback.format_exc()}")]
        except Exception as e:
            return False, [self.log_message(f"Error in generating Sheet 2 outputs: {str(e)}\nDetails:\n{traceback.format_exc()}")]
        finally:
            self.running = False

def main():
    backend = Backend()
    pass

if __name__ == "__main__":
    main()