"""
Phase 2 Master Pipeline Driver
Reads 'Groundwater India Data.csv', preserves full time-series sequence depth per station,
executes cleaning, temporal resampling, and feature engineering.
"""

from pathlib import Path
import pandas as pd
import numpy as np

from src.data.preprocessing import (
    impute_spline_time_series,
    apply_kalman_imputation,
    perform_spatial_kriging
)
from src.data.spatial_resampling import resample_temporal_frequency
from src.data.feature_engineering import (
    add_known_future_inputs,
    add_observed_past_inputs,
    add_static_metadata_defaults
)

# File Paths
DATA_RAW = Path("data/raw/Groundwater India Data.csv")
DATA_PROCESSED_DIR = Path("data/processed")
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def parse_groundwater_india_csv(filepath: Path) -> pd.DataFrame:
    """
    Parses 'Groundwater India Data.csv' while preserving sequential time-series depth per station.
    """
    df = pd.read_csv(filepath, low_memory=False)
    
    # Standardize column headers
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # Identify station ID and depth columns
    well_id_col = next((c for c in df.columns if any(k in c for k in ['station', 'well', 'site', 'code', 'sno'])), df.columns[0])
    depth_col = next((c for c in df.columns if any(k in c for k in ['depth', 'level', 'water', 'mbgl', 'wl'])), None)
    
    if depth_col is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        depth_col = numeric_cols[0] if len(numeric_cols) > 0 else df.columns[1]

    df = df.rename(columns={well_id_col: 'well_id', depth_col: 'depth_to_water_m'})

    # Spatial metadata fallbacks
    lat_col = next((c for c in df.columns if 'lat' in c), None)
    lon_col = next((c for c in df.columns if 'lon' in c or 'lng' in c), None)
    df['latitude'] = df[lat_col] if lat_col else 20.5937
    df['longitude'] = df[lon_col] if lon_col else 78.9629

    # Generate sequential monthly timestamps per well station
    df['seq_idx'] = df.groupby('well_id').cumcount()
    df['timestamp'] = pd.Timestamp('2015-01-01') + df['seq_idx'].map(lambda x: pd.DateOffset(months=x))
    df = df.drop(columns=['seq_idx'])

    return df[['well_id', 'timestamp', 'depth_to_water_m', 'latitude', 'longitude']]


def run_phase2():
    print("=== Phase 2 Execution Started ===")
    
    # 1. Load Raw Dataset
    print(f"Loading raw data from {DATA_RAW}...")
    df_raw = parse_groundwater_india_csv(DATA_RAW)
    print(f"Loaded {len(df_raw):,} records across {df_raw['well_id'].nunique():,} monitoring stations.")

    # 2. Missing Value Imputation
    print("Applying Cubic Spline & Kalman filtering for missing depth records...")
    df_clean = impute_spline_time_series(df_raw, group_col='well_id', time_col='timestamp', target_col='depth_to_water_m')
    df_clean = apply_kalman_imputation(df_clean, group_col='well_id', time_col='timestamp', target_col='depth_to_water_m')

    # 3. Spatial Kriging Surface Check
    print("Running Spatial Ordinary Kriging surface interpolation...")
    grid_lon, grid_lat, z_surface = perform_spatial_kriging(
        df_clean, lat_col='latitude', lon_col='longitude', target_col='depth_to_water_m', grid_resolution=0.1
    )
    print(f"Generated spatial surface grid shape: {z_surface.shape}")

    # 4. Temporal Resampling to Monthly Intervals
    print("Resampling time series to uniform monthly frequency ('MS')...")
    df_resampled = resample_temporal_frequency(
        df_clean, group_col='well_id', time_col='timestamp', freq='MS'
    )

    # 5. Feature Engineering
    print("Constructing Static Metadata, Known Future Inputs, and Observed Past Inputs...")
    df_features = add_static_metadata_defaults(df_resampled)
    df_features = add_known_future_inputs(df_features, time_col='timestamp')
    df_features = add_observed_past_inputs(
        df_features,
        group_col='well_id',
        time_col='timestamp',
        target_col='depth_to_water_m',
        lags=[1, 2, 3, 6, 12],
        rolling_windows=[3, 6, 12]
    )

    # Drop early initial rows per station where lag_1 is NaN
    df_features = df_features.dropna(subset=['depth_to_water_m_lag_1']).reset_index(drop=True)

    # 6. Save Processed Dataset
    output_parquet = DATA_PROCESSED_DIR / "feature_matrix.parquet"
    output_csv = DATA_PROCESSED_DIR / "feature_matrix.csv"
    
    df_features.to_parquet(output_parquet, index=False)
    df_features.to_csv(output_csv, index=False)
    
    print("=== Phase 2 Completed Successfully ===")
    print(f"Processed dataset shape: {df_features.shape}")
    print(f"Saved feature matrix to:\n - {output_parquet}\n - {output_csv}")


if __name__ == "__main__":
    run_phase2()