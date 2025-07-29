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
    logger.warning(f"GDAL data directory not found at {gdal_data_path}")
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

    def log_message(self, message):
        logger.info(message)
        return f"[{time.strftime('%H:%M:%S')}] {message}\n"

    def create_netcdf(self, input_dir, shp_path, template_path, output_dir, progress_callback=None):
        if self.running:
            return False, "A task is already running."
        self.running = True
        try:
            messages = [self.log_message("Starting NetCDF creation...")]
            if not all([input_dir, shp_path, template_path, output_dir]):
                messages.append(self.log_message("Error: Please select all required directories and files"))
                return False, "Please select all required directories and files"
            
            os.makedirs(output_dir, exist_ok=True)
            for i, (d, config) in enumerate(dataset_config.items()):
                data_path = os.path.join(input_dir, config['subdir'])
                files = glob.glob(os.path.join(data_path, '*.tif'))
                if not files:
                    messages.append(self.log_message(f"No TIFFs found in {data_path}, skipping {d}"))
                    continue

                nc_filename = f"Awash_{config['attrs']['quantity']}_{config['attrs']['source']}.nc"
                nc_path = os.path.join(output_dir, nc_filename)
                dataset_info = {d: [data_path, config['dims'], config['attrs']]}

                messages.append(self.log_message(f"Creating {nc_filename}..."))
                success = createNC_cmi.make_netcdf(nc_path, dataset_info, shp_path, template_path, "")
                messages.append(self.log_message(f"{'Successfully created' if success else 'Failed to create'} {nc_filename}"))
                
                if progress_callback:
                    progress_callback(i + 1, len(dataset_config))

            messages.append(self.log_message("NetCDF creation completed."))
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}"))
            return False, messages
        finally:
            self.running = False

    def calculate_rain(self, directory):
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
            for key, nc_file in nc_files.items():
                if not os.path.exists(nc_file):
                    messages.append(self.log_message(f"Error: Input NetCDF file not found: {nc_file}"))
                    return False, messages

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                nrd_nc = pre_proc_sm_balance.rainy_days(nc_files['dailyP'], nc_files['P'])
                I_nc = pre_proc_sm_balance.interception(nc_files['LAI'], nc_files['P'], nrd_nc)

            messages.append(self.log_message("Rainfall interception processing completed."))
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}"))
            return False, messages
        finally:
            self.running = False

    def run_smbalance(self, directory, start_year, end_year, f_perc, f_smax, cf, f_bf, deep_perc_f):
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
            run_SMBalance(directory, nc_files_dict, start_year, end_year, **params)
            messages.append(self.log_message("Soil moisture balance calculation completed."))
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}"))
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
                if 'ETa_V6' in filename:
                    files['ET'] = full_path
                elif 'P_CHIRPS' in filename and 'dailyP' not in filename:
                    files['P'] = full_path
                elif 'ETref' in filename:
                    files['ETref'] = full_path
                elif 'LAI' in filename:
                    files['LAI'] = full_path
                elif 'LU' in filename:
                    files['LU'] = full_path
                elif 'NDM' in filename:
                    files['ProbaV'] = full_path
                elif 'i_monthly' in filename:
                    files['I'] = full_path
                elif 'nRD' in filename:
                    files['NRD'] = full_path
                elif 'bf_monthly' in filename:
                    files['BF'] = full_path
                elif 'supply_monthly' in filename:
                    files['Supply'] = full_path
                elif 'etincr_monthly' in filename:
                    files['ETB'] = full_path
                elif 'etrain_monthly' in filename:
                    files['ETG'] = full_path
                elif 'sro_monthly' in filename and 'd_sro_monthly' not in filename:
                    files['SRO'] = full_path
                elif 'perco_monthly' in filename and 'd_perco_monthly' not in filename:
                    files['PERC'] = full_path
                elif 'd_sro_monthly' in filename:
                    files['ISRO'] = full_path
                elif 'd_perco_monthly' in filename:
                    files['DPERC'] = full_path
        required_vars = ['P', 'ET', 'ETref', 'I', 'NRD', 'ProbaV', 'LU', 'SRO', 'PERC', 'BF', 'Supply', 'ETB', 'ETG', 'LAI']
        missing = [var for var in required_vars if var not in files]
        if missing:
            messages.append(self.log_message(f"Missing required files: {', '.join(missing)}"))
            return {}, messages
        for var in ['ISRO', 'DPERC']:
            if var not in files:
                files[var] = None
                messages.append(self.log_message(f"Optional file {var} not found, set to None"))
        return files, messages

    def init_hydroloop(self, inputs):
        if self.running:
            return False, ["A task is already running."]
        self.running = True
        try:
            messages = []
            for key in ['nc_dir', 'static_data_dir', 'result_dir', 'mask_path', 'dem_path', 'aeisw_path', 'population_path', 'wpl_path', 'ewr_path']:
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

            os.makedirs(inputs['result_dir'], exist_ok=True)
            files, file_messages = self.collect_hydroloop_files(inputs['nc_dir'])
            messages.extend(file_messages)
            if not files:
                messages.append(self.log_message("Error: No valid input files found"))
                return False, messages

            table_data = mhl.collect_tables(
                folder=inputs['static_data_dir'],
                inflow=inputs['inflow'] or None,
                outflow=inputs['outflow'] or None,
                desal=inputs['desalination'] or None
            )
            messages.append(self.log_message(f"Table data keys: {list(table_data.keys())}"))

            metadata = mhl.create_metadata(
                basin_name=inputs['basin_name'],
                hydro_year=inputs['hydro_year'],
                output_folder=inputs['result_dir'],
                basin_mask=inputs['mask_path'],
                dem=inputs['dem_path'],
                aeisw=inputs['aeisw_path'],
                population=inputs['population_path'],
                wpl=inputs['wpl_path'],
                environ_water_req=inputs['ewr_path'],
                unit_conversion=inputs['unit_conversion'],
                chunksize=[1, 100, 100]
            )
            messages.append(self.log_message(f"Initializing Hydroloop with metadata: basin_name={inputs['basin_name']}, hydro_year={inputs['hydro_year']}"))
            self.BASIN = mhl.initialize_hydroloop(metadata, files, table_data)
            messages.append(self.log_message(f"BASIN ts_data keys: {list(self.BASIN['ts_data'].keys())}"))
            messages.append(self.log_message("Hydroloop initialized successfully."))
            return True, messages
        except Exception as e:
            error_details = traceback.format_exc()
            messages.append(self.log_message(f"Error: {str(e)}\nDetails:\n{error_details}"))
            return False, messages
        finally:
            self.running = False

    def run_hydroloop(self):
        if self.running:
            return False, ["A task is already running."]
        if not self.BASIN:
            return False, ["Hydroloop not initialized"]
        self.running = True
        try:
            messages = []
            process_steps = [
                mhl.resample_lu, mhl.split_et, mhl.split_supply, mhl.calc_demand,
                mhl.calc_return, mhl.calc_residential_supply, mhl.calc_total_supply,
                mhl.calc_fraction, mhl.calc_time_series, self.finalize_hydroloop_outputs
            ]
            for step in process_steps:
                messages.append(self.log_message(f"Starting {step.__name__}"))
                self.BASIN = step(self.BASIN)
                messages.append(self.log_message(f"Completed {step.__name__}"))

            messages.append(self.log_message("Hydroloop processing completed successfully."))
            return True, messages
        except Exception as e:
            messages.append(self.log_message(f"Error: {str(e)}"))
            return False, messages
        finally:
            self.running = False

    def finalize_hydroloop_outputs(self, basin):
        """Final processing step for hydroloop outputs"""
        try:
            # Generate output sheets
            sheet1.generate_sheet1(basin)
            sheet2.generate_sheet2(basin)
            print_sheet.generate_print_sheet(basin)
            return basin
        except Exception as e:
            logger.error(f"Error in finalizing outputs: {str(e)}")
            raise

def main():
    backend = Backend()
    # Example usage or CLI interface could be added here
    # For now, this serves as a placeholder for backend instantiation
    pass

if __name__ == "__main__":
    main()