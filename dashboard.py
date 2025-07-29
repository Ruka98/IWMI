import os
import pandas as pd
from flask import Flask, render_template, request, jsonify
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import json
import geopandas as gpd
from datetime import datetime
import logging
from collections import defaultdict

app = Flask(__name__)
BASIN_DIR = "basin"
GEOJSON_DIR = "geojson"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define column mappings for CSV columns
COLUMN_MAPPINGS = {
    'precipitation': ['p', 'pr', 'precip', 'precipitation'],
    'storage_change': ['ds', 'storage', 'delta_s', 'storage_change'],
    'inflow': ['q_inflow'],
    'gross_inflow': ['q_gross_inflow'],
    'net_inflow': ['net_inflow'],
    'et_rain': ['et_rain'],
    'et_rain_natural': ['et_rain_nat', 'et_rain_natural'],
    'et_rain_urban': ['et_rain_urban'],
    'et_rain_agriculture': ['et_rain_ag', 'et_rain_agriculture'],
    'et_blue': ['et_blue'],
    'et_blue_natural': ['et_blue_nat', 'et_blue_natural'],
    'et_blue_urban': ['et_blue_urban'],
    'et_blue_agriculture': ['et_blue_ag', 'et_blue_agriculture'],
    'total_et': ['landscape_et', 'total_et', 'evapotranspiration'],
    'wastewater': ['q_tww', 'total_wastewater'],
    'natural_outflow': ['natural_surface_q'],
    'total_outflow': ['outflow'],
    'year': ['yr', 'year', 'yr_csv'],
    'sectorial_consumption': ['sect_w_con'],
    'manmade_consumption': ['consumtion_manmade'],
    'consumed_water': ['consumed_water']
}

# Available parameters for user selection grouped by category
PARAMETER_CATEGORIES = {
    'Water Inputs': ['precipitation', 'gross_inflow', 'net_inflow', 'inflow'],
    'Water Outputs': ['total_et', 'total_outflow', 'natural_outflow'],
    'ET Components': ['et_rain', 'et_blue', 'et_rain_natural', 'et_rain_urban', 
                     'et_rain_agriculture', 'et_blue_natural', 'et_blue_urban', 
                     'et_blue_agriculture'],
    'Storage': ['storage_change'],
    'Wastewater': ['wastewater'],
    'Consumption': ['sectorial_consumption', 'manmade_consumption', 'consumed_water']
}

# Categories for pie charts
ET_RAIN_CATEGORIES = ['et_rain_natural', 'et_rain_urban', 'et_rain_agriculture']
ET_BLUE_CATEGORIES = ['et_blue_natural', 'et_blue_urban', 'et_blue_agriculture']
INFLOW_CATEGORIES = ['inflow', 'wastewater']
INPUT_CATEGORIES = ['precipitation', 'inflow']
CONSUMPTION_CATEGORIES = ['sectorial_consumption', 'manmade_consumption']
OUTFLOW_CATEGORIES = ['natural_outflow', 'wastewater']
ET_TOTAL_CATEGORIES = ['et_rain', 'et_blue']

def get_basins():
    """Get list of available basins by checking BASIN_DIR"""
    try:
        basins = [name for name in os.listdir(BASIN_DIR) if os.path.isdir(os.path.join(BASIN_DIR, name))]
        logger.info(f"Found basins: {basins}")
        return basins
    except Exception as e:
        logger.error(f"Error getting basins: {str(e)}")
        return []

def get_geojson_path(basin_name):
    """Find the GeoJSON file for the basin"""
    try:
        geojson_dir = os.path.join(BASIN_DIR, basin_name, GEOJSON_DIR)
        if os.path.exists(geojson_dir):
            for file in os.listdir(geojson_dir):
                if file.endswith('.geojson') or file.endswith('.json'):
                    path = os.path.join(geojson_dir, file)
                    logger.info(f"Found GeoJSON for {basin_name}: {path}")
                    return path
        logger.warning(f"No GeoJSON file found for basin {basin_name}")
        return None
    except Exception as e:
        logger.error(f"Error finding GeoJSON for {basin_name}: {str(e)}")
        return None

def load_and_convert_to_geojson(basin_name):
    """Load and convert shapefile to GeoJSON if needed"""
    try:
        geojson_path = get_geojson_path(basin_name)
        if not geojson_path:
            return None
            
        gdf = gpd.read_file(geojson_path)
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        
        geojson = json.loads(gdf.to_json())
        logger.info(f"Successfully loaded GeoJSON for {basin_name}")
        return geojson
    except Exception as e:
        logger.error(f"Error processing GeoJSON for {basin_name}: {str(e)}")
        return None

def load_csv_data(basin):
    """Load CSV data for a specific basin"""
    try:
        csv_folder = os.path.join(BASIN_DIR, basin, "csv")
        if not os.path.exists(csv_folder):
            logger.warning(f"CSV folder not found for basin {basin}")
            return pd.DataFrame()
            
        for file in os.listdir(csv_folder):
            if file.endswith(".csv"):
                file_path = os.path.join(csv_folder, file)
                try:
                    df = pd.read_csv(file_path)
                    df.columns = df.columns.str.lower()
                    logger.info(f"Loaded CSV data for {basin} with shape {df.shape}")
                    return df
                except Exception as e:
                    logger.error(f"Error loading CSV {file_path}: {str(e)}")
                    continue
        
        logger.warning(f"No valid CSV files found in {csv_folder}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading CSV data for {basin}: {str(e)}")
        return pd.DataFrame()

def map_column_names(df):
    """Map various column names to standard water balance components"""
    try:
        mapped_cols = {}
        for standard_name, possible_names in COLUMN_MAPPINGS.items():
            for name in possible_names:
                if name in df.columns:
                    mapped_cols[standard_name] = name
                    break
        
        logger.info(f"Mapped columns: {mapped_cols}")
        return mapped_cols
    except Exception as e:
        logger.error(f"Error mapping column names: {str(e)}")
        return {}

def calculate_water_balance(df, mapped_cols):
    """Calculate water balance components using mapped column names"""
    try:
        if not mapped_cols:
            return df
            
        for standard_name, original_name in mapped_cols.items():
            if standard_name not in df.columns:
                df[standard_name] = df[original_name]
        
        # Calculate aggregated ET components if individual components exist
        if all(c in mapped_cols for c in ET_RAIN_CATEGORIES) and 'et_rain' not in mapped_cols:
            df['et_rain'] = df[[mapped_cols[c] for c in ET_RAIN_CATEGORIES]].sum(axis=1)
        
        if all(c in mapped_cols for c in ET_BLUE_CATEGORIES) and 'et_blue' not in mapped_cols:
            df['et_blue'] = df[[mapped_cols[c] for c in ET_BLUE_CATEGORIES]].sum(axis=1)
        
        if 'et_rain' in mapped_cols and 'et_blue' in mapped_cols and 'total_et' not in mapped_cols:
            df['total_et'] = df[[mapped_cols['et_rain'], mapped_cols['et_blue']]].sum(axis=1)
        
        logger.info("Calculated water balance components")
        return df
    except Exception as e:
        logger.error(f"Error calculating water balance: {str(e)}")
        return df

def validate_year_range(df, year_start, year_end, mapped_cols):
    """Validate if the selected year range is within available data"""
    try:
        if not mapped_cols or 'year' not in mapped_cols:
            return False, "No year column found in data"
        
        year_col = mapped_cols['year']
        df[year_col] = pd.to_numeric(df[year_col], errors='coerce')
        available_years = df[year_col].dropna().astype(int).unique()
        
        if not available_years.size:
            return False, "No valid years found in data"
        
        try:
            year_start_int = int(year_start)
            year_end_int = int(year_end)
            if year_start_int > year_end_int:
                return False, "Start year cannot be greater than end year"
            
            min_year, max_year = min(available_years), max(available_years)
            if year_start_int < min_year or year_end_int > max_year:
                return False, f"Selected years ({year_start}-{year_end}) are out of range. Available years: {min_year}-{max_year}"
            
            return True, ""
        except ValueError:
            return False, "Invalid year format. Please enter numeric years"
    except Exception as e:
        logger.error(f"Error validating year range: {str(e)}")
        return False, f"Error validating year range: {str(e)}"

def create_time_series_chart(df, mapped_cols, selected_basin="", selected_parameters=None):
    """Create time series visualization of selected parameters"""
    try:
        if not mapped_cols or 'year' not in mapped_cols:
            logger.warning("No valid column mappings or year column not found")
            return None
        
        year_col = mapped_cols['year']
        
        # Flatten selected parameters from categories
        if selected_parameters and isinstance(selected_parameters, dict):
            selected_parameters = [param for category in selected_parameters.values() for param in category]
        
        available_components = [c for c in (selected_parameters or []) if c in mapped_cols]
        
        if not available_components:
            logger.warning(f"No available components found for selected parameters: {selected_parameters}")
            return None
        
        plot_df = df[[year_col] + available_components].copy()
        plot_df = plot_df.melt(id_vars=[year_col], var_name='component', value_name='value')
        
        if plot_df.empty or plot_df['value'].isna().all():
            logger.warning(f"Time series data is empty or contains only NaN values for {selected_basin}")
            return None
        
        color_map = {
            'precipitation': '#1f77b4',
            'gross_inflow': '#9467bd',
            'net_inflow': '#8c564b',
            'inflow': '#17becf',
            'total_et': '#ff7f0e',
            'total_outflow': '#2ca02c',
            'natural_outflow': '#d62728',
            'et_rain': '#e377c2',
            'et_blue': '#7f7f7f',
            'et_rain_natural': '#bcbd22',
            'et_rain_urban': '#17becf',
            'et_rain_agriculture': '#8c564b',
            'et_blue_natural': '#1f77b4',
            'et_blue_urban': '#ff7f0e',
            'et_blue_agriculture': '#2ca02c',
            'storage_change': '#d62728',
            'wastewater': '#ff9896',
            'sectorial_consumption': '#6b7280',
            'manmade_consumption': '#f87171',
            'consumed_water': '#4b5563'
        }
        
        label_map = {
            'precipitation': 'Precipitation (P)',
            'gross_inflow': 'Gross Inflow',
            'net_inflow': 'Net Inflow',
            'inflow': 'Natural Inflow',
            'total_et': 'Total ET',
            'total_outflow': 'Total Outflow',
            'natural_outflow': 'Natural Outflow',
            'et_rain': 'ET Rain (Green Water)',
            'et_blue': 'ET Blue (Blue Water)',
            'et_rain_natural': 'ET Rain - Natural',
            'et_rain_urban': 'ET Rain - Urban',
            'et_rain_agriculture': 'ET Rain - Agriculture',
            'et_blue_natural': 'ET Blue - Natural',
            'et_blue_urban': 'ET Blue - Urban',
            'et_blue_agriculture': 'ET Blue - Agriculture',
            'storage_change': 'Storage Change (ΔS)',
            'wastewater': 'Wastewater Inflow',
            'sectorial_consumption': 'Sectorial Consumption',
            'manmade_consumption': 'Manmade Consumption',
            'consumed_water': 'Total Consumed Water'
        }
        
        plot_df['component'] = plot_df['component'].map(label_map)
        
        fig = px.line(
            plot_df,
            x=year_col,
            y='value',
            color='component',
            color_discrete_map={label_map[k]: v for k, v in color_map.items() if k in available_components},
            title=f"{selected_basin} - Water Balance Components Over Time",
            labels={'value': 'Value (Mm³/year)', year_col: 'Year'},
            template="plotly_white"
        )
        
        fig.update_traces(
            mode='lines+markers', 
            marker=dict(size=8, line=dict(width=1, color='DarkSlateGrey')),
            line=dict(width=2)
        )
        
        fig.update_layout(
            hovermode="x unified",
            legend_title="Components",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10)
            ),
            yaxis_title="Water Balance Components (Mm³/year)",
            margin=dict(l=50, r=50, b=80, t=80),
            plot_bgcolor='rgba(240,240,240,0.9)',
            paper_bgcolor='rgba(240,240,240,0.5)',
            font=dict(size=12),
            showlegend=True,
            height=550,
            xaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                gridwidth=0.5
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='lightgray',
                gridwidth=0.5
            )
        )
        
        chart_json = fig.to_json()
        logger.info(f"Successfully created time series chart for {selected_basin}")
        return chart_json
    except Exception as e:
        logger.error(f"Error creating time series chart for {selected_basin}: {str(e)}")
        return None

def create_total_et_pie_chart(df, mapped_cols, selected_year=None, selected_basin="", is_range=False):
    """Create pie chart for total ET composition (Blue vs Green)"""
    try:
        if not mapped_cols:
            return None
            
        available_components = [c for c in ET_TOTAL_CATEGORIES if c in mapped_cols]
        
        if not available_components:
            return None
            
        title_suffix = f"({selected_year})" if selected_year and not is_range else "(Average)"
        
        if selected_year and not is_range:
            year_col = mapped_cols['year']
            year_df = df[df[year_col] == selected_year]
            if year_df.empty:
                return None
            data_source = year_df
        else:
            data_source = df
        
        if is_range:
            values = {comp: data_source[mapped_cols[comp]].mean() for comp in available_components}
        else:
            values = {comp: data_source[mapped_cols[comp]].values[0] for comp in available_components}
        
        labels_map = {
            'et_rain': 'Green Water (ET Rain)',
            'et_blue': 'Blue Water (ET Blue)'
        }
        
        labels = [labels_map[comp] for comp in available_components]
        values = [values[comp] for comp in available_components]
        
        if sum(values) <= 0:
            return None
            
        colors = ['#e377c2', '#7f7f7f']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker_colors=colors[:len(available_components)],
            textinfo='percent+label',
            textposition='inside'
        )])
        
        fig.update_layout(
            title_text=f"Total ET Composition - {selected_basin} {title_suffix}",
            showlegend=True,
            height=400,
            margin=dict(t=60, b=20, l=20, r=20)
        )
        
        return fig.to_json()
    except Exception as e:
        logger.error(f"Error creating total ET pie chart: {str(e)}")
        return None

def create_et_pie_charts(df, mapped_cols, selected_year=None, selected_basin="", is_range=False):
    """Create pie charts for ET rain and ET blue categories"""
    try:
        if not mapped_cols:
            return {}
            
        charts = {}
        title_suffix = f"({selected_year})" if selected_year and not is_range else "(Average)"
        
        if selected_year and not is_range:
            year_col = mapped_cols['year']
            year_df = df[df[year_col] == selected_year]
            if year_df.empty:
                return {}
            data_source = year_df
        else:
            data_source = df
        
        # ET Rain Pie Chart
        available_et_rain = [c for c in ET_RAIN_CATEGORIES if c in mapped_cols]
        if available_et_rain:
            if is_range:
                et_rain_values = {cat: data_source[mapped_cols[cat]].mean() for cat in available_et_rain}
            else:
                et_rain_values = {cat: data_source[mapped_cols[cat]].values[0] for cat in available_et_rain}
            
            et_rain_total = sum(et_rain_values.values())
            
            if et_rain_total > 0:
                labels_map = {
                    'et_rain_natural': 'Natural',
                    'et_rain_urban': 'Urban',
                    'et_rain_agriculture': 'Agriculture'
                }
                
                labels = [labels_map[cat] for cat in available_et_rain]
                values = [et_rain_values[cat] for cat in available_et_rain]
                
                fig = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.4,
                    marker_colors=['#bcbd22', '#17becf', '#8c564b'],
                    textinfo='percent+label',
                    textposition='inside'
                )])
                
                fig.update_layout(
                    title_text=f"ET Rain Composition - {selected_basin} {title_suffix}",
                    showlegend=True,
                    height=400,
                    margin=dict(t=60, b=20, l=20, r=20)
                )
                
                charts['et_rain_pie'] = fig.to_json()
        
        # ET Blue Pie Chart
        available_et_blue = [c for c in ET_BLUE_CATEGORIES if c in mapped_cols]
        if available_et_blue:
            if is_range:
                et_blue_values = {cat: data_source[mapped_cols[cat]].mean() for cat in available_et_blue}
            else:
                et_blue_values = {cat: data_source[mapped_cols[cat]].values[0] for cat in available_et_blue}
            
            et_blue_total = sum(et_blue_values.values())
            
            if et_blue_total > 0:
                labels_map = {
                    'et_blue_natural': 'Natural',
                    'et_blue_urban': 'Urban',
                    'et_blue_agriculture': 'Agriculture'
                }
                
                labels = [labels_map[cat] for cat in available_et_blue]
                values = [et_blue_values[cat] for cat in available_et_blue]
                
                fig = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.4,
                    marker_colors=['#1f77b4', '#ff7f0e', '#2ca02c'],
                    textinfo='percent+label',
                    textposition='inside'
                )])
                
                fig.update_layout(
                    title_text=f"ET Blue Composition - {selected_basin} {title_suffix}",
                    showlegend=True,
                    height=400,
                    margin=dict(t=60, b=20, l=20, r=20)
                )
                
                charts['et_blue_pie'] = fig.to_json()
        
        return charts
    except Exception as e:
        logger.error(f"Error creating ET pie charts: {str(e)}")
        return {}

def create_input_pie_chart(df, mapped_cols, selected_year=None, selected_basin="", is_range=False):
    """Create pie chart of input components (precipitation and inflow)"""
    try:
        if not mapped_cols:
            return None
            
        available_components = [c for c in INPUT_CATEGORIES if c in mapped_cols]
        
        if not available_components:
            return None
            
        title_suffix = f"({selected_year})" if selected_year and not is_range else "(Average)"
        
        if selected_year and not is_range:
            year_col = mapped_cols['year']
            year_df = df[df[year_col] == selected_year]
            if year_df.empty:
                return None
            data_source = year_df
        else:
            data_source = df
        
        if is_range:
            input_values = {comp: data_source[mapped_cols[comp]].mean() for comp in available_components}
        else:
            input_values = {comp: data_source[mapped_cols[comp]].values[0] for comp in available_components}
        
        labels_map = {
            'precipitation': 'Precipitation',
            'inflow': 'Natural Inflow'
        }
        
        labels = [labels_map[comp] for comp in available_components]
        values = [input_values[comp] for comp in available_components]
        
        if sum(values) <= 0:
            return None
            
        colors = ['#1f77b4', '#17becf']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker_colors=colors[:len(available_components)],
            textinfo='percent+label',
            textposition='inside'
        )])
        
        fig.update_layout(
            title_text=f"Water Input Composition - {selected_basin} {title_suffix}",
            showlegend=True,
            height=400,
            margin=dict(t=60, b=20, l=20, r=20)
        )
        
        return fig.to_json()
    except Exception as e:
        logger.error(f"Error creating input pie chart: {str(e)}")
        return None

def create_inflow_pie_chart(df, mapped_cols, selected_year=None, selected_basin="", is_range=False):
    """Create pie chart of inflow components (natural inflow and wastewater)"""
    try:
        if not mapped_cols:
            return None
            
        available_components = [c for c in INFLOW_CATEGORIES if c in mapped_cols]
        
        if not available_components:
            return None
            
        title_suffix = f"({selected_year})" if selected_year and not is_range else "(Average)"
        
        if selected_year and not is_range:
            year_col = mapped_cols['year']
            year_df = df[df[year_col] == selected_year]
            if year_df.empty:
                return None
            data_source = year_df
        else:
            data_source = df
        
        if is_range:
            inflow_values = {comp: data_source[mapped_cols[comp]].mean() for comp in available_components}
        else:
            inflow_values = {comp: data_source[mapped_cols[comp]].values[0] for comp in available_components}
        
        labels_map = {
            'inflow': 'Natural Inflow',
            'wastewater': 'Wastewater Inflow'
        }
        
        labels = [labels_map[comp] for comp in available_components]
        values = [inflow_values[comp] for comp in available_components]
        
        if sum(values) <= 0:
            return None
            
        colors = ['#17becf', '#ff9896']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker_colors=colors[:len(available_components)],
            textinfo='percent+label',
            textposition='inside'
        )])
        
        fig.update_layout(
            title_text=f"Inflow Composition - {selected_basin} {title_suffix}",
            showlegend=True,
            height=400,
            margin=dict(t=60, b=20, l=20, r=20)
        )
        
        return fig.to_json()
    except Exception as e:
        logger.error(f"Error creating inflow pie chart: {str(e)}")
        return None

def create_outflow_pie_chart(df, mapped_cols, selected_year=None, selected_basin="", is_range=False):
    """Create pie chart of outflow components (natural outflow and wastewater)"""
    try:
        if not mapped_cols:
            return None
            
        available_components = [c for c in OUTFLOW_CATEGORIES if c in mapped_cols]
        
        if not available_components:
            return None
            
        title_suffix = f"({selected_year})" if selected_year and not is_range else "(Average)"
        
        if selected_year and not is_range:
            year_col = mapped_cols['year']
            year_df = df[df[year_col] == selected_year]
            if year_df.empty:
                return None
            data_source = year_df
        else:
            data_source = df
        
        if is_range:
            outflow_values = {comp: data_source[mapped_cols[comp]].mean() for comp in available_components}
        else:
            outflow_values = {comp: data_source[mapped_cols[comp]].values[0] for comp in available_components}
        
        labels_map = {
            'natural_outflow': 'Natural Outflow',
            'wastewater': 'Wastewater Outflow'
        }
        
        labels = [labels_map[comp] for comp in available_components]
        values = [outflow_values[comp] for comp in available_components]
        
        if sum(values) <= 0:
            return None
            
        colors = ['#d62728', '#ff9896']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker_colors=colors[:len(available_components)],
            textinfo='percent+label',
            textposition='inside'
        )])
        
        fig.update_layout(
            title_text=f"Outflow Composition - {selected_basin} {title_suffix}",
            showlegend=True,
            height=400,
            margin=dict(t=60, b=20, l=20, r=20)
        )
        
        return fig.to_json()
    except Exception as e:
        logger.error(f"Error creating outflow pie chart: {str(e)}")
        return None

def create_consumption_bar_chart(df, mapped_cols, selected_basin="", selected_year=None, is_range=False):
    """Create bar chart for consumption components"""
    try:
        if not mapped_cols:
            return None
            
        available_components = [c for c in CONSUMPTION_CATEGORIES if c in mapped_cols]
        
        if not available_components:
            return None
            
        title_suffix = f"({selected_year})" if selected_year and not is_range else "(Average)"
        
        if selected_year and not is_range:
            year_col = mapped_cols['year']
            year_df = df[df[year_col] == selected_year]
            if year_df.empty:
                return None
            data_source = year_df
        else:
            data_source = df
        
        if is_range:
            values = [data_source[mapped_cols[comp]].mean() for comp in available_components]
        else:
            values = [data_source[mapped_cols[comp]].values[0] for comp in available_components]
        
        labels_map = {
            'sectorial_consumption': 'Sectorial Non-Irrigated',
            'manmade_consumption': 'Manmade Consumption'
        }
        
        labels = [labels_map[comp] for comp in available_components]
        
        fig = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color=['#6b7280', '#f87171'],
                text=[f"{v:.1f}" for v in values],
                textposition='auto'
            )
        ])
        
        fig.update_layout(
            title_text=f"Water Consumption - {selected_basin} {title_suffix}",
            yaxis_title="Consumption (Mm³/year)",
            showlegend=False,
            height=400,
            margin=dict(t=60, b=20, l=20, r=20),
            plot_bgcolor='rgba(240,240,240,0.9)',
            paper_bgcolor='rgba(240,240,240,0.5)'
        )
        
        return fig.to_json()
    except Exception as e:
        logger.error(f"Error creating consumption bar chart: {str(e)}")
        return None

def create_sankey_diagram(df, mapped_cols, selected_basin="", selected_year=None, is_range=False):
    """Create a sankey diagram for water balance flows"""
    try:
        if not mapped_cols:
            return None
            
        required_cols = ['precipitation', 'inflow', 'total_et', 'total_outflow', 'storage_change']
        available_cols = [c for c in required_cols if c in mapped_cols]
        
        if len(available_cols) < 2:
            return None
            
        title_suffix = f"({selected_year})" if selected_year and not is_range else "(Average)"
        
        if selected_year and not is_range:
            year_col = mapped_cols['year']
            year_df = df[df[year_col] == selected_year]
            if year_df.empty:
                return None
            data_source = year_df
        else:
            data_source = df
        
        if is_range:
            values = {comp: data_source[mapped_cols[comp]].mean() for comp in available_cols}
        else:
            values = {comp: data_source[mapped_cols[comp]].values[0] for comp in available_cols}
        
        nodes = ['Precipitation', 'Inflow', 'Total Inflow', 'ET', 'Outflow', 'Storage Change']
        node_indices = {n: i for i, n in enumerate(nodes)}
        
        links = []
        values_list = []
        
        if 'precipitation' in values:
            links.append([node_indices['Precipitation'], node_indices['Total Inflow']])
            values_list.append(values['precipitation'])
        
        if 'inflow' in values:
            links.append([node_indices['Inflow'], node_indices['Total Inflow']])
            values_list.append(values['inflow'])
        
        if 'total_et' in values:
            links.append([node_indices['Total Inflow'], node_indices['ET']])
            values_list.append(values['total_et'])
        
        if 'total_outflow' in values:
            links.append([node_indices['Total Inflow'], node_indices['Outflow']])
            values_list.append(values['total_outflow'])
        
        if 'storage_change' in values and values['storage_change'] > 0:
            links.append([node_indices['Total Inflow'], node_indices['Storage Change']])
            values_list.append(values['storage_change'])
        elif 'storage_change' in values and values['storage_change'] < 0:
            links.append([node_indices['Storage Change'], node_indices['Total Inflow']])
            values_list.append(abs(values['storage_change']))
        
        if not links:
            return None
            
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=nodes,
                color=['#1f77b4', '#17becf', '#9ca3af', '#ff7f0e', '#2ca02c', '#d62728']
            ),
            link=dict(
                source=[link[0] for link in links],
                target=[link[1] for link in links],
                value=values_list,
                color=['rgba(31,119,180,0.5)', 'rgba(23,190,207,0.5)', 
                       'rgba(255,127,14,0.5)', 'rgba(44,160,44,0.5)', 'rgba(214,39,40,0.5)'][:len(links)]
            )
        )])
        
        fig.update_layout(
            title_text=f"Water Flow - {selected_basin} {title_suffix}",
            height=500,
            margin=dict(t=60, b=20, l=20, r=20),
            font=dict(size=12)
        )
        
        return fig.to_json()
    except Exception as e:
        logger.error(f"Error creating sankey diagram: {str(e)}")
        return None

def create_water_balance_summary(df, mapped_cols, selected_basin="", selected_year=None, is_range=False):
    """Create an interactive water balance summary as an HTML table"""
    try:
        if not mapped_cols:
            return None
        
        title_suffix = f"({selected_year})" if selected_year and not is_range else "(Average)"
        
        if selected_year and not is_range:
            year_col = mapped_cols['year']
            year_df = df[df[year_col] == selected_year]
            if year_df.empty:
                return None
            data_source = year_df
        else:
            data_source = df
        
        summary_data = {}
        for key in ['gross_inflow', 'precipitation', 'inflow', 'total_et', 
                    'wastewater', 'sectorial_consumption', 'manmade_consumption', 'storage_change']:
            if key in mapped_cols:
                summary_data[key] = data_source[mapped_cols[key]].mean() if is_range else data_source[mapped_cols[key]].values[0]
        
        precipitation_percentage = (summary_data['precipitation'] / summary_data['gross_inflow'] * 100) if 'precipitation' in summary_data and 'gross_inflow' in summary_data and summary_data['gross_inflow'] > 0 else 0
        
        summary_html = f"""
        <div class="summary-table-container">
            <h3>Water Balance Summary - {selected_basin} {title_suffix}</h3>
            <table class="summary-table">
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Total Water Inflows</td>
                    <td>{summary_data.get('gross_inflow', 0):.1f} Mm³/year</td>
                </tr>
                <tr>
                    <td>Precipitation Contribution</td>
                    <td>{precipitation_percentage:.1f}% of gross inflows</td>
                </tr>
                <tr>
                    <td>Imported Water (Inflow)</td>
                    <td>{summary_data.get('inflow', 0):.1f} Mm³/year</td>
                </tr>
                <tr>
                    <td>Landscape Water Consumption</td>
                    <td>{summary_data.get('total_et', 0):.1f} Mm³/year</td>
                </tr>
                <tr>
                    <td>Manmade Water Consumption</td>
                    <td>{summary_data.get('manmade_consumption', 0):.1f} Mm³/year</td>
                </tr>
                <tr>
                    <td>Treated Wastewater Discharge</td>
                    <td>{summary_data.get('wastewater', 0):.1f} Mm³/year</td>
                </tr>
                <tr>
                    <td>Non-Irrigated Water Consumption</td>
                    <td>{summary_data.get('sectorial_consumption', 0):.1f} Mm³/year</td>
                </tr>
                <tr>
                    <td>Basin Recharge</td>
                    <td>{summary_data.get('storage_change', 0):.1f} Mm³/year</td>
                </tr>
            </table>
            <style>
                .summary-table-container {{
                    margin: 20px;
                    padding: 15px;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .summary-table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 14px;
                }}
                .summary-table th, .summary-table td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #dee2e6;
                }}
                .summary-table th {{
                    background-color: #e9ecef;
                    font-weight: bold;
                }}
                .summary-table tr:hover {{
                    background-color: #f1f3f5;
                }}
            </style>
        </div>
        """
        
        logger.info(f"Created water balance summary for {selected_basin}")
        return {'html': summary_html}
    except Exception as e:
        logger.error(f"Error creating water balance summary: {str(e)}")
        return None

@app.route("/get_shapefile/<basin>")
def get_shapefile(basin):
    """Serve GeoJSON for the requested basin"""
    try:
        geojson_data = load_and_convert_to_geojson(basin)
        if geojson_data:
            logger.info(f"Successfully loaded GeoJSON for {basin}")
            return jsonify({"geojson": geojson_data, "basin_name": basin})
        return jsonify({"geojson": None, "error": "GeoJSON not found"}), 404
    except Exception as e:
        logger.error(f"Error in get_shapefile for {basin}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/get_all_basins")
def get_all_basins():
    """Serve GeoJSON for all basins with names"""
    try:
        basins = get_basins()
        logger.info(f"Processing basins: {basins}")
        all_features = []
        
        for basin in basins:
            geojson_data = load_and_convert_to_geojson(basin)
            if geojson_data and 'features' in geojson_data:
                for feature in geojson_data['features']:
                    feature['properties']['basin_name'] = basin
                all_features.extend(geojson_data['features'])
                logger.info(f"Added {len(geojson_data['features'])} features for {basin}")
        
        combined_geojson = {
            "type": "FeatureCollection",
            "features": all_features
        }
        
        logger.info(f"Returning {len(all_features)} total features")
        return jsonify({"geojson": combined_geojson})
    except Exception as e:
        logger.error(f"Error in get_all_basins: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/get_chart_data", methods=["POST"])
def get_chart_data():
    """Serve chart data for the requested basin and parameters"""
    try:
        data = request.get_json()
        logger.info(f"Received chart data request: {data}")
        
        basin = data.get("basin")
        if not basin:
            return jsonify({"error": "Basin parameter is required"}), 400
            
        year_start = data.get("year_start", "2018")
        year_end = data.get("year_end", "2021")
        selected_parameters = data.get("parameters", PARAMETER_CATEGORIES)
        
        df = load_csv_data(basin)
        if df.empty:
            return jsonify({"error": f"No data found for basin {basin}"}), 404
        
        mapped_columns = map_column_names(df)
        if not mapped_columns or 'year' not in mapped_columns:
            return jsonify({"error": "Required columns not found in data"}), 404
        
        # Validate year range
        is_valid, error_message = validate_year_range(df, year_start, year_end, mapped_columns)
        if not is_valid:
            return jsonify({"error": error_message}), 400
        
        year_col = mapped_columns['year']
        df[year_col] = pd.to_numeric(df[year_col], errors='coerce')
        df = df.dropna(subset=[year_col])
        
        try:
            year_start_int = int(year_start)
            year_end_int = int(year_end)
            df = df[(df[year_col] >= year_start_int) & (df[year_col] <= year_end_int)].sort_values(year_col)
        except ValueError as e:
            logger.warning(f"Invalid year range: {year_start}-{year_end}, using all data")
        
        df = calculate_water_balance(df, mapped_columns)
        
        graphs_json = {}
        is_single_year = year_start == year_end
        selected_year = int(year_start) if is_single_year else None
        
        # Time series chart
        time_series_fig = create_time_series_chart(df, mapped_columns, basin, selected_parameters)
        if time_series_fig:
            graphs_json['time_series'] = time_series_fig
        
        # Total ET pie chart
        total_et_pie_fig = create_total_et_pie_chart(df, mapped_columns, selected_year, basin, is_range=not is_single_year)
        if total_et_pie_fig:
            graphs_json['total_et_pie'] = total_et_pie_fig
        
        # ET component pie charts
        et_pie_charts = create_et_pie_charts(df, mapped_columns, selected_year, basin, is_range=not is_single_year)
        graphs_json.update(et_pie_charts)
        
        # Input pie chart
        input_pie_fig = create_input_pie_chart(df, mapped_columns, selected_year, basin, is_range=not is_single_year)
        if input_pie_fig:
            graphs_json['input_pie'] = input_pie_fig
        
        # Inflow pie chart
        inflow_pie_fig = create_inflow_pie_chart(df, mapped_columns, selected_year, basin, is_range=not is_single_year)
        if inflow_pie_fig:
            graphs_json['inflow_pie'] = inflow_pie_fig
        
        # Outflow pie chart
        outflow_pie_fig = create_outflow_pie_chart(df, mapped_columns, selected_year, basin, is_range=not is_single_year)
        if outflow_pie_fig:
            graphs_json['outflow_pie'] = outflow_pie_fig
        
        # Consumption bar chart
        consumption_bar_fig = create_consumption_bar_chart(df, mapped_columns, basin, selected_year, is_range=not is_single_year)
        if consumption_bar_fig:
            graphs_json['consumption_bar'] = consumption_bar_fig
        
        # Sankey diagram
        sankey_fig = create_sankey_diagram(df, mapped_columns, basin, selected_year, is_range=not is_single_year)
        if sankey_fig:
            graphs_json['sankey'] = sankey_fig
        
        water_balance_summary = create_water_balance_summary(df, mapped_columns, basin, selected_year, is_range=not is_single_year)
        
        response_data = {
            "graphs_json": graphs_json,
            "water_balance_summary": water_balance_summary,
            "basin": basin,
            "is_single_year": is_single_year
        }
        
        logger.info(f"Successfully processed data for {basin}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_chart_data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET", "POST"])
def dashboard():
    try:
        year_start = request.form.get("year_start", "2018")
        year_end = request.form.get("year_end", "2021")
        selected_basin = request.form.get("basin", "")
        
        if request.method == "POST" and "map_click_basin" in request.form:
            selected_basin = request.form.get("map_click_basin", selected_basin)
        
        selected_parameters = defaultdict(list)
        for category, params in PARAMETER_CATEGORIES.items():
            selected_params = request.form.getlist(f"parameters_{category.lower().replace(' ', '_')}")
            selected_parameters[category] = selected_params if selected_params else params
        
        logger.info(f"Dashboard request - basin: {selected_basin}, years: {year_start}-{year_end}, params: {selected_parameters}")
        
        graphs_json = {}
        water_balance_summary = None
        is_single_year = year_start == year_end
        error_message = None
        
        if selected_basin:
            df = load_csv_data(selected_basin)
            if not df.empty:
                mapped_columns = map_column_names(df)
                if mapped_columns and 'year' in mapped_columns:
                    year_col = mapped_columns['year']
                    df[year_col] = pd.to_numeric(df[year_col], errors='coerce')
                    df = df.dropna(subset=[year_col])
                    
                    # Validate year range
                    is_valid, error_message = validate_year_range(df, year_start, year_end, mapped_columns)
                    if is_valid:
                        try:
                            year_start_int = int(year_start)
                            year_end_int = int(year_end)
                            df = df[(df[year_col] >= year_start_int) & (df[year_col] <= year_end_int)].sort_values(year_col)
                        except ValueError:
                            logger.warning("Invalid year range, using all available data")
                        
                        df = calculate_water_balance(df, mapped_columns)
                        
                        time_series_fig = create_time_series_chart(df, mapped_columns, selected_basin, selected_parameters)
                        if time_series_fig:
                            graphs_json['time_series'] = time_series_fig
                        
                        selected_year = int(year_start) if is_single_year else None
                        total_et_pie_fig = create_total_et_pie_chart(df, mapped_columns, selected_year, selected_basin, is_range=not is_single_year)
                        if total_et_pie_fig:
                            graphs_json['total_et_pie'] = total_et_pie_fig
                        
                        et_pie_charts = create_et_pie_charts(df, mapped_columns, selected_year, selected_basin, is_range=not is_single_year)
                        graphs_json.update(et_pie_charts)
                        
                        input_pie_fig = create_input_pie_chart(df, mapped_columns, selected_year, selected_basin, is_range=not is_single_year)
                        if input_pie_fig:
                            graphs_json['input_pie'] = input_pie_fig
                        
                        inflow_pie_fig = create_inflow_pie_chart(df, mapped_columns, selected_year, selected_basin, is_range=not is_single_year)
                        if inflow_pie_fig:
                            graphs_json['inflow_pie'] = inflow_pie_fig
                        
                        outflow_pie_fig = create_outflow_pie_chart(df, mapped_columns, selected_year, selected_basin, is_range=not is_single_year)
                        if outflow_pie_fig:
                            graphs_json['outflow_pie'] = outflow_pie_fig
                        
                        consumption_bar_fig = create_consumption_bar_chart(df, mapped_columns, selected_basin, selected_year, is_range=not is_single_year)
                        if consumption_bar_fig:
                            graphs_json['consumption_bar'] = consumption_bar_fig
                        
                        sankey_fig = create_sankey_diagram(df, mapped_columns, selected_basin, selected_year, is_range=not is_single_year)
                        if sankey_fig:
                            graphs_json['sankey'] = sankey_fig
                        
                        water_balance_summary = create_water_balance_summary(df, mapped_columns, selected_basin, selected_year, is_range=not is_single_year)
        
        return render_template(
            "index.html",
            year_start=year_start,
            year_end=year_end,
            graphs_json=graphs_json,
            selected_basin=selected_basin,
            basins=get_basins(),
            water_balance_summary=water_balance_summary,
            parameter_categories=PARAMETER_CATEGORIES,
            selected_parameters=selected_parameters,
            current_year=datetime.now().year,
            is_single_year=is_single_year,
            error_message=error_message
        )
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}")
        return render_template("error.html", error=str(e)), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)