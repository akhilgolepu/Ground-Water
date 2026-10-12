"""
Phase 2: Preprocessing Module
Handles time-series missing value imputation (Cubic Spline & Kalman Smoother)
and spatial interpolation across unmonitored zones via Ordinary Kriging.
"""

import warnings
import numpy as np
import pandas as pd
from scipy.interpolate import Rbf

try:
    from pykrige.ok import OrdinaryKriging
    HAS_PYKRIGE = True
except ImportError:
    HAS_PYKRIGE = False


def impute_spline_time_series(
    df: pd.DataFrame,
    group_col: str,
    time_col: str,
    target_col: str,
    order: int = 3
) -> pd.DataFrame:
    """
    Applies Cubic Spline Interpolation per well group along the time axis.
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values([group_col, time_col])

    def _spline_group(group):
        s = group.set_index(time_col)[target_col]
        s = s.interpolate(method='spline', order=order, limit_direction='both')
        s = s.interpolate(method='linear', limit_direction='both')
        group[target_col] = s.values
        return group

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, message=".*DataFrameGroupBy.apply.*")
        return df.groupby(group_col, group_keys=False).apply(_spline_group)


def impute_kalman_filter_1d(
    series: pd.Series,
    process_variance: float = 1e-4,
    measurement_variance: float = 1e-2
) -> np.ndarray:
    """
    Applies 1D Kalman Filter and Smoother to impute missing observations in a sequence.
    """
    x = series.values.copy()
    n = len(x)
    
    x_hat = np.zeros(n)
    P = np.zeros(n)
    
    initial_val = x[~np.isnan(x)][0] if np.any(~np.isnan(x)) else 0.0
    x_hat_minus = initial_val
    P_minus = 1.0

    for t in range(n):
        if not np.isnan(x[t]):
            K = P_minus / (P_minus + measurement_variance)
            x_hat[t] = x_hat_minus + K * (x[t] - x_hat_minus)
            P[t] = (1 - K) * P_minus
        else:
            x_hat[t] = x_hat_minus
            P[t] = P_minus + process_variance
            
        x_hat_minus = x_hat[t]
        P_minus = P[t] + process_variance

    x_smooth = x_hat.copy()
    for t in range(n - 2, -1, -1):
        if np.isnan(x[t + 1]):
            x_smooth[t] = x_smooth[t + 1]

    return x_smooth


def apply_kalman_imputation(
    df: pd.DataFrame,
    group_col: str,
    time_col: str,
    target_col: str
) -> pd.DataFrame:
    """
    Applies Kalman smoothing per well time series.
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values([group_col, time_col])

    def _kalman_group(group):
        if group[target_col].isnull().any():
            smoothed_vals = impute_kalman_filter_1d(group[target_col])
            group[target_col] = np.where(group[target_col].isnull(), smoothed_vals, group[target_col])
        return group

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, message=".*DataFrameGroupBy.apply.*")
        return df.groupby(group_col, group_keys=False).apply(_kalman_group)


def perform_spatial_kriging(
    df: pd.DataFrame,
    lat_col: str = 'latitude',
    lon_col: str = 'longitude',
    target_col: str = 'depth_to_water_m',
    grid_resolution: float = 0.1,
    variogram_model: str = 'spherical'
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Performs Ordinary Kriging / RBF spatial interpolation across unique station locations.
    Returns (grid_lon, grid_lat, interpolated_surface).
    """
    valid_data = df.dropna(subset=[lat_col, lon_col, target_col])
    spatial_stations = valid_data.groupby([lat_col, lon_col])[target_col].mean().reset_index()
    
    lons = spatial_stations[lon_col].values
    lats = spatial_stations[lat_col].values
    values = spatial_stations[target_col].values

    grid_lon = np.arange(lons.min(), lons.max() + grid_resolution, grid_resolution)
    grid_lat = np.arange(lats.min(), lats.max() + grid_resolution, grid_resolution)
    grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)

    if HAS_PYKRIGE:
        OK = OrdinaryKriging(
            lons, lats, values,
            variogram_model=variogram_model,
            verbose=False,
            enable_plotting=False
        )
        z_surface, ss = OK.execute('grid', grid_lon, grid_lat)
    else:
        # Adding smooth=0.1 conditions the distance matrix to eliminate LinAlgWarning
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*ill-conditioned matrix.*")
            rbf = Rbf(lons, lats, values, function='multiquadric', smooth=0.1)
            z_surface = rbf(grid_lon_mesh, grid_lat_mesh)

    return grid_lon_mesh, grid_lat_mesh, z_surface