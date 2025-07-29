# IWMI

This repository includes tools and dashboards developed during my work at the International Water Management Institute (IWMI). It contains branches and folders organized by project, along with resources and code used for hydrological modeling, water accounting, and spatial analysis.

## 🌊 Water Accounting Dashboard

An interactive Flask-based dashboard for visualizing basin-level water balance components. It allows users to explore annual data for selected basins using charts and maps.

### ✅ Features

- Basin selection with dynamic GeoJSON map loading
- Time-series plots for precipitation, inflow, evapotranspiration (ET), storage, and outflow
- Pie charts for:
  - Total ET (Green vs Blue water)
  - ET by land use (Natural, Urban, Agriculture)
  - Inflow/Outflow composition
  - Water consumption (sectoral vs manmade)
- Sankey diagram showing water flow balance
- Summary tables of water balance metrics
- Custom year range selection with average or single-year analysis

### 🛠️ Technologies Used

- Python (Flask, Pandas, GeoPandas)
- Plotly (Express + Graph Objects)
- HTML/CSS with Jinja2 templates
- File-based data (CSV for time series, GeoJSON for boundaries)

### 📁 Project Structure


