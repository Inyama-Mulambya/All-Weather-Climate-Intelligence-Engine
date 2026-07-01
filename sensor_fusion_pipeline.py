"""
STARi Sensor Fusion Core Pipeline
Author: [Inyama C. Mulambya / STARi Command]
Description: Open-source precision agriculture data processing engine.
             Blends Sentinel-2 Optical (NDVI/NDRE) and Sentinel-1 SAR Radar 
             arrays to extract zonal statistics and phone-ready GPS perimeters.
"""

import ee
from datetime import datetime, timedelta

class ClimateIntelligenceEngine:
    def __init__(self, project_name: str):
        """Initializes the Earth Engine environment wrapper."""
        self.project_name = project_name
        # Note: Users must authorize their own local ee environment credentials before initialization

    def process_field_telemetry(self, coordinates: list) -> dict:
        """Runs multi-spectral index analysis and radar structural profiling over a boundary box."""
        geometry = ee.Geometry.Polygon(coordinates)
        
        # 1. Establish Chronological Monitoring Windows
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        end_str = end_date.strftime('%Y-%m-%d')
        start_str = start_date.strftime('%Y-%m-%d')

        # 2. Pipeline Track A: Optical Imagery Parsing (Sentinel-2)
        def mask_clouds(image):
            scl = image.select('SCL')
            mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            return image.updateMask(mask)

        def add_ag_indices(image):
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
            ndwi = image.normalizedDifference(['B8', 'B11']).rename('NDWI')
            return image.addBands([ndvi, ndre, ndwi])

        opt_collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                          .filterBounds(geometry)
                          .filterDate(start_str, end_str)
                          .map(mask_clouds)
                          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                          .sort('system:time_start', False))

        # Cloud Gap Time-Travel Safe Fallback
        if opt_collection.size().getInfo() == 0:
            opt_collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                              .filterBounds(geometry)
                              .filterDate(start_str, end_str)
                              .map(mask_clouds)
                              .sort('system:time_start', False))

        latest_opt_image = opt_collection.first()
        processed_image = add_ag_indices(latest_opt_image).clip(geometry)
        
        # Calculate Zonal Statistics Distributions
        total_pixels = processed_image.reduceRegion(reducer=ee.Reducer.count(), geometry=geometry, scale=10).get('NDVI')
        low_nitrogen = processed_image.updateMask(processed_image.select('NDRE').lt(0.25)).reduceRegion(reducer=ee.Reducer.count(), geometry=geometry, scale=10).get('NDRE')
        water_stressed = processed_image.updateMask(processed_image.select('NDWI').lt(0.1)).reduceRegion(reducer=ee.Reducer.count(), geometry=geometry, scale=10).get('NDWI')
        pest_risk = processed_image.updateMask(processed_image.select('NDVI').lt(0.35)).reduceRegion(reducer=ee.Reducer.count(), geometry=geometry, scale=10).get('NDVI')

        try:
            total_val = total_pixels.getInfo() or 1
            nitrogen_deficit_pct = round(((low_nitrogen.getInfo() or 0) / total_val) * 100, 1)
            water_stress_pct = round(((water_stressed.getInfo() or 0) / total_val) * 100, 1)
            pest_risk_pct = round(((pest_risk.getInfo() or 0) / total_val) * 100, 1)
        except Exception:
            nitrogen_deficit_pct, water_stress_pct, pest_risk_pct = 0.0, 0.0, 0.0

        # 3. Pipeline Track B: Radar Surface Scattering (Sentinel-1 SAR)
        radar_collection = (ee.ImageCollection('COPERNICUS/S1_GRD')
                            .filterBounds(geometry)
                            .filterDate(start_str, end_str)
                            .filter(ee.Filter.eq('instrumentMode', 'IW'))
                            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
                            .sort('system:time_start', False))

        latest_radar = radar_collection.first().clip(geometry)
        biomass_indicator = latest_radar.select('VH')
        r_total = biomass_indicator.reduceRegion(reducer=ee.Reducer.count(), geometry=geometry, scale=10).get('VH')
        r_high = biomass_indicator.updateMask(biomass_indicator.gt(-14)).reduceRegion(reducer=ee.Reducer.count(), geometry=geometry, scale=10).get('VH')

        try:
            r_total_val = r_total.getInfo() or 1
            asset_presence_pct = round(((r_high.getInfo() or 0) / r_total_val) * 100, 1)
        except Exception:
            asset_presence_pct = 0.0

        # 4. Pipeline Track C: Algorithmic Field Perimeter Waypoint Generator
        navigation_url = "https://google.com"
        try:
            raw_list = coordinates[0] if isinstance(coordinates[0], list) and isinstance(coordinates[0][0], list) else coordinates
            path_points = [f"{float(vertex[1])},{float(vertex[0])}" for vertex in raw_list if isinstance(vertex, list) and len(vertex) >= 2]
            if path_points:
                path_string = "|".join(path_points)
                anchor_lat, anchor_lng = path_points[0].split(',')
                navigation_url = f"https://google.com/dir/?api=1&destination={anchor_lat},{anchor_lng}&travelmode=walking&waypoints={path_string}"
        except Exception as e:
            pass

        return {
            "metrics": {
                "nitrogen_deficit_proportion": nitrogen_deficit_pct,
                "canopy_water_stress_proportion": water_stress_pct,
                "cellular_tissue_degradation_proportion": pest_risk_pct,
                "radar_biomass_asset_verification": asset_presence_pct
            },
            "geospatial_escort_url": navigation_url
        }
