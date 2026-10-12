"""
Phase 2: Feature Engineering Module
Computes Static Metadata, Known Future Inputs, and Observed Past Inputs (Lags, API, SPEI).
"""

import warnings
import numpy as np
import pandas as pd


def add_known_future_inputs(
    df: pd.DataFrame,
    time_col: str = 'timestamp'
) -> pd.DataFrame:
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])

    df['calendar_month'] = df[time_col].dt.month
    df['day_of_year'] = df[time_col].dt.dayofyear
    df['calendar_quarter'] = df[time_col].dt.quarter

    df['sin_month'] = np.sin(2 * np.pi * df['calendar_month'] / 12.0)
    df['cos_month'] = np.cos(2 * np.pi * df['calendar_month'] / 12.0)
    
    df['sin_day_of_year'] = np.sin(2 * np.pi * df['day_of_year'] / 365.25)
    df['cos_day_of_year'] = np.cos(2 * np.pi * df['day_of_year'] / 365.25)

    return df


def calculate_antecedent_precipitation_index(
    precipitation_series: pd.Series,
    decay_factor: float = 0.85
) -> pd.Series:
    p = precipitation_series.fillna(0).values
    api = np.zeros(len(p))
    for t in range(1, len(p)):
        api[t] = p[t] + decay_factor * api[t - 1]
    return pd.Series(api, index=precipitation_series.index)


def compute_thornthwaite_pet(
    temp_series: pd.Series,
    latitudes: pd.Series
) -> pd.Series:
    t_mean = np.maximum(temp_series.values, 0)
    i_m = (t_mean / 5.0) ** 1.514
    I_val = np.sum(i_m) if np.sum(i_m) > 0 else 1.0
    
    alpha = (6.75e-7 * I_val**3) - (7.71e-5 * I_val**2) + (1.792e-2 * I_val) + 0.49239
    pet = 16.0 * ((10.0 * t_mean / I_val) ** alpha)
    return pd.Series(pet, index=temp_series.index)


def calculate_spei(
    precipitation: pd.Series,
    temperature: pd.Series,
    latitudes: pd.Series,
    scale: int = 3
) -> pd.Series:
    pet = compute_thornthwaite_pet(temperature, latitudes)
    d = precipitation - pet
    d_rolling = d.rolling(window=scale, min_periods=1).sum()
    
    mean_d = d_rolling.mean()
    std_d = d_rolling.std()
    std_d = std_d if std_d > 0 else 1.0
    
    return (d_rolling - mean_d) / std_d


def add_observed_past_inputs(
    df: pd.DataFrame,
    group_col: str,
    time_col: str,
    target_col: str,
    precip_col: str = None,
    temp_col: str = None,
    lat_col: str = 'latitude',
    lags: list[int] = [1, 2, 3, 6, 12],
    rolling_windows: list[int] = [3, 6, 12]
) -> pd.DataFrame:
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values([group_col, time_col])

    def _engineer_group(group):
        for lag in lags:
            group[f'{target_col}_lag_{lag}'] = group[target_col].shift(lag)

        for w in rolling_windows:
            group[f'{target_col}_roll_mean_{w}'] = group[target_col].shift(1).rolling(w, min_periods=1).mean()
            group[f'{target_col}_roll_std_{w}'] = group[target_col].shift(1).rolling(w, min_periods=1).std()

        if precip_col in group.columns and group[precip_col].notnull().any():
            group['API'] = calculate_antecedent_precipitation_index(group[precip_col])
            
            if temp_col in group.columns and group[temp_col].notnull().any():
                group['SPEI_3'] = calculate_spei(group[precip_col], group[temp_col], group[lat_col], scale=3)
                group['SPEI_6'] = calculate_spei(group[precip_col], group[temp_col], group[lat_col], scale=6)

        return group

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, message=".*DataFrameGroupBy.apply.*")
        return df.groupby(group_col, group_keys=False).apply(_engineer_group)


def add_static_metadata_defaults(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    static_defaults = {
        'aquifer_elevation_m': 250.0,
        'soil_hydraulic_conductivity_m_d': 1.5,
        'soil_porosity': 0.25,
        'land_cover_type': 'Agricultural'
    }
    for col, default_val in static_defaults.items():
        if col not in df.columns:
            df[col] = default_val
    return df
