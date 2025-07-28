import rasterio
import numpy as np
from collections import deque
from rasterio.features import shapes
import geopandas as gpd
import os
import tkinter as tk
from tkinter import filedialog, simpledialog
from time import time

def main():
    # === INPUTS ===
    dem_path = r"E:\MY APP\Reservoir\0.01.tif"  # Path to your DEM
    outlet_lonlat = (80.692317, 6.258161)  # (longitude, latitude) of the outlet 

    print("\n=== Watershed Delineation with Flood Level Adjustment ===")
    print(f"DEM Path: {dem_path}")
    print(f"Outlet Coordinates (lon,lat): {outlet_lonlat}")

    # === GET USER INPUTS ===
    root = tk.Tk()
    root.withdraw()

    # Ask for flood level
    flood_level = simpledialog.askfloat("Flood Level", 
                                      "Enter flood level in meters (0 for default command area):",
                                      minvalue=0, maxvalue=10)
    if flood_level is None:
        print("\nOperation cancelled by user")
        return

    print(f"\nSelected flood level: {flood_level}m")

    # Ask for output directory
    output_dir = filedialog.askdirectory(title="Select directory to save results")
    if not output_dir:
        print("\nOperation cancelled by user")
        return

    print(f"\nOutput directory: {output_dir}")

    # === OUTPUT PATHS ===
    raster_output_path = os.path.join(output_dir, f"command_area_flood_{flood_level}m.tif")
    geojson_output_path = os.path.join(output_dir, f"command_area_flood_{flood_level}m.geojson")

    # === LOAD DEM ===
    print("\nLoading DEM...")
    start_time = time()
    
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        transform = src.transform
        crs = src.crs
        height, width = dem.shape
        nodata = src.nodata

        print(f"DEM loaded in {time()-start_time:.2f} seconds")
        print(f"CRS: {crs}")
        print(f"Dimensions: {width} cols x {height} rows")
        print(f"Pixel size: {transform.a:.6f} x {-transform.e:.6f} units")
        print(f"NoData value: {nodata}")

        # Convert outlet coordinates
        x, y = outlet_lonlat
        outlet_col, outlet_row = ~transform * (x, y)
        outlet_row, outlet_col = int(outlet_row), int(outlet_col)
        outlet_elev = dem[outlet_row, outlet_col]

        print(f"\nOutlet at (row,col): {outlet_row},{outlet_col}")
        print(f"Outlet elevation: {outlet_elev:.2f}m")

        # Validate outlet position
        if not (0 <= outlet_row < height and 0 <= outlet_col < width):
            raise ValueError("Outlet coordinates are outside DEM bounds!")
        if nodata is not None and dem[outlet_row, outlet_col] == nodata:
            raise ValueError("Outlet is in NoData area!")

    # === STEP 1: DELINEATE DEFAULT COMMAND AREA ===
    print("\nDelineating default command area (0m flood level)...")
    start_time = time()

    command_mask = np.zeros(dem.shape, dtype=np.uint8)
    queue = deque([(outlet_row, outlet_col)])
    command_mask[outlet_row, outlet_col] = 1
    cells_processed = 1

    # 8-directional neighbors
    neighbors = [(-1, -1), (-1, 0), (-1, 1),
                 (0, -1),           (0, 1),
                 (1, -1),  (1, 0), (1, 1)]

    while queue:
        r, c = queue.popleft()
        for dr, dc in neighbors:
            nr, nc = r + dr, c + dc
            if 0 <= nr < height and 0 <= nc < width and command_mask[nr, nc] == 0:
                if (nodata is None or dem[nr, nc] != nodata) and dem[nr, nc] <= dem[r, c]:
                    command_mask[nr, nc] = 1
                    queue.append((nr, nc))
                    cells_processed += 1

    default_area = np.sum(command_mask == 1)
    print(f"Completed in {time()-start_time:.2f} seconds")
    print(f"Default command area: {default_area} pixels")

    # === STEP 2: FLOOD LEVEL EXPANSION ===
    if flood_level > 0:
        print(f"\nExpanding command area with {flood_level}m flood level...")
        start_time = time()

        # Find boundary cells (cells adjacent to non-command area)
        boundary_cells = set()
        for r in range(height):
            for c in range(width):
                if command_mask[r, c] == 1:  # Only look at default command area
                    for dr, dc in neighbors:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < height and 0 <= nc < width and command_mask[nr, nc] == 0:
                            boundary_cells.add((r, c))
                            break

        print(f"Found {len(boundary_cells)} boundary cells")

        # First pass: expand based on flood level
        new_additions = set()
        for r, c in boundary_cells:
            current_elev = dem[r, c]
            
            for dr, dc in neighbors:
                nr, nc = r + dr, c + dc
                if (0 <= nr < height and 0 <= nc < width 
                    and command_mask[nr, nc] == 0 
                    and (nodata is None or dem[nr, nc] != nodata)):
                    
                    neighbor_elev = dem[nr, nc]
                    if neighbor_elev <= (current_elev + flood_level):
                        command_mask[nr, nc] = 2
                        new_additions.add((nr, nc))

        # Second pass: apply default logic to new additions
        expansion_queue = deque(new_additions)
        while expansion_queue:
            r, c = expansion_queue.popleft()
            current_elev = dem[r, c]
            
            for dr, dc in neighbors:
                nr, nc = r + dr, c + dc
                if (0 <= nr < height and 0 <= nc < width 
                    and command_mask[nr, nc] == 0 
                    and (nodata is None or dem[nr, nc] != nodata)):
                    
                    neighbor_elev = dem[nr, nc]
                    # Now apply default logic (must be equal or lower)
                    if neighbor_elev <= current_elev:
                        command_mask[nr, nc] = 2
                        expansion_queue.append((nr, nc))
                        new_additions.add((nr, nc))

        expansion_cells = len(new_additions)
        print(f"Expansion completed in {time()-start_time:.2f} seconds")
        print(f"Added {expansion_cells} pixels in flood expansion")

    # === CALCULATE STATISTICS ===
    pixel_area = abs(transform.a * transform.e)
    total_pixels = np.sum(command_mask > 0)
    total_area = total_pixels * pixel_area

    print("\n=== RESULTS ===")
    print(f"Default command area (0m): {default_area} pixels")
    if flood_level > 0:
        print(f"Flood expansion area (+{flood_level}m): {total_pixels - default_area} pixels")
    print(f"Total command area: {total_pixels} pixels")
    print(f"Total area: {total_area:.2f} square units")

    # === SAVE RASTER ===
    print("\nSaving raster output...")
    with rasterio.open(
        raster_output_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=command_mask.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(command_mask, 1)
    print(f"Raster saved to: {raster_output_path}")

    # === SAVE GEOJSON ===
    print("\nConverting to GeoJSON...")
    start_time = time()
    
    results = (
        {"properties": {
            "value": v,
            "flood_level": flood_level,
            "area_sq_units": total_area,
            "type": "default" if v == 1 else "flood_expansion"
        }, 
        "geometry": s}
        for s, v in shapes(command_mask, mask=command_mask > 0, transform=transform)
    )
    
    gdf = gpd.GeoDataFrame.from_features(list(results))
    gdf.crs = crs
    gdf.to_file(geojson_output_path, driver='GeoJSON')
    
    print(f"GeoJSON conversion completed in {time()-start_time:.2f} seconds")
    print(f"GeoJSON saved to: {geojson_output_path}")

    print("\nProcessing complete!")

if __name__ == "__main__":
    main()
