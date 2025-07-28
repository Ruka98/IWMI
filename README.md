# IWMI

This repository contains tools and scripts developed for delineating **command areas** around wastewater treatment plants (WWTPs) and reservoirs using hydrological and spatial analysis methods.

## 🧭 Command Area Delineation Options

The repository includes three distinct methods for delineating command areas:

### ✅ Option 1: Fixed Stream Length + Buffer
- Considers a **fixed stream length** of **5 km** downstream from the WWTP outlet.
- Applies a **500 m buffer** around the traced stream.
- Suitable for quick estimates in small basins.

### ✅ Option 2: Stream Length Based on Discharge + Buffer
- Dynamically traces the stream length based on the **discharge rate**.
- Applies a **500 m buffer** to account for lateral spread.
- More accurate for varying flow conditions.

### ✅ Option 3: Full Downslope Area (Reservoir Method)
- Available under the `reservoir` folder.
- Identifies **all possible downslope areas** where water can naturally drain.
- Suitable for identifying maximum potential command areas.

## 📁 Folder Structure

