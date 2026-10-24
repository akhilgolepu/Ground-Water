"""
Phase 3: Dataset Preparation & Sequence Generator
Performs chronological splitting (70% train, 15% val, 15% test) per well station
and builds sliding-window sequence tensors for multi-horizon forecasting.
"""

from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader


class GroundwaterSequenceDataset(Dataset):
    """
    PyTorch Dataset for multi-horizon groundwater forecasting.
    Constructs past observation windows and future target sequences per well station.
    """
    def __init__(
        self,
        df: pd.DataFrame,
        past_lookback: int = 12,
        future_horizon: int = 12,
        target_col: str = 'depth_to_water_m',
        feature_cols: List[str] = None
    ):
        self.past_lookback = past_lookback
        self.future_horizon = future_horizon
        self.target_col = target_col
        
        if feature_cols is None:
            # Exclude non-feature identifier columns
            exclude_cols = {'well_id', 'timestamp', 'land_cover_type'}
            feature_cols = [c for c in df.columns if c not in exclude_cols]
            
        self.feature_cols = feature_cols
        
        self.X_past_list = []
        self.Y_future_list = []
        self.well_ids = []
        
        # Build sliding windows per station to preserve temporal integrity
        for well_id, group in df.groupby('well_id'):
            group = group.sort_values('timestamp').reset_index(drop=True)
            n_samples = len(group)
            total_window = past_lookback + future_horizon
            
            if n_samples < total_window:
                continue
                
            features = group[feature_cols].values.astype(np.float32)
            targets = group[target_col].values.astype(np.float32)
            
            for i in range(n_samples - total_window + 1):
                x_window = features[i : i + past_lookback]
                y_window = targets[i + past_lookback : i + total_window]
                
                self.X_past_list.append(x_window)
                self.Y_future_list.append(y_window)
                self.well_ids.append(well_id)
                
        self.X_past = torch.tensor(np.array(self.X_past_list), dtype=torch.float32)
        self.Y_future = torch.tensor(np.array(self.Y_future_list), dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.X_past)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.X_past[idx], self.Y_future[idx]


def split_chronological_dataset(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Splits well time series chronologically into Train (70%), Validation (15%), and Test (15%) sets.
    """
    train_dfs, val_dfs, test_dfs = [], [], []
    
    for well_id, group in df.groupby('well_id'):
        group = group.sort_values('timestamp').reset_index(drop=True)
        n = len(group)
        
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        
        train_dfs.append(group.iloc[:train_end])
        val_dfs.append(group.iloc[train_end:val_end])
        test_dfs.append(group.iloc[val_end:])
        
    train_df = pd.concat(train_dfs, ignore_index=True)
    val_df = pd.concat(val_dfs, ignore_index=True)
    test_df = pd.concat(test_dfs, ignore_index=True)
    
    return train_df, val_df, test_df