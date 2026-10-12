"""
Phase 2: Resampling & Alignment Module
Standardizes time-series records per station to uniform monthly start ('MS') frequencies.
"""

import pandas as pd
import numpy as np


def resample_temporal_frequency(
    df: pd.DataFrame,
    group_col: str = 'well_id',
    time_col: str = 'timestamp',
    freq: str = 'MS'
) -> pd.DataFrame:
    """
    Resamples each well station's time series to uniform monthly intervals,
    preserving full historical sequence depth.
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if group_col in numeric_cols:
        numeric_cols.remove(group_col)

    resampled_groups = []
    
    for well_id, group in df.groupby(group_col):
        group = group.sort_values(time_col).set_index(time_col)
        # Resample time series to monthly frequency
        resampled = group[numeric_cols].resample(freq).mean()
        
        # Re-attach identifier and spatial coordinates
        resampled[group_col] = well_id
        for col in ['latitude', 'longitude', 'aquifer_elevation_m']:
            if col in group.columns:
                resampled[col] = group[col].iloc[0]
                
        resampled_groups.append(resampled.reset_index())

    df_resampled = pd.concat(resampled_groups, ignore_index=True)
    # Linear interpolation for small missing time gaps within station time series
    df_resampled[numeric_cols] = df_resampled.groupby(group_col)[numeric_cols].transform(
        lambda g: g.interpolate(method='linear', limit_direction='both')
    )
    return df_resampled.dropna(subset=['depth_to_water_m'])