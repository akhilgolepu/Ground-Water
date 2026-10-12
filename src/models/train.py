"""
Phase 3 Master Training Driver
Executes chronological dataset splitting, model training (XGBoost, LSTM, TFT),
multi-quantile evaluation, and artifact checkpointing.
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import joblib

from sklearn.preprocessing import StandardScaler
from torch.utils.data import TensorDataset, DataLoader

from src.models.baselines import XGBoostBaseline, LSTMBaseline
from src.models.tft_model import TemporalFusionTransformer, QuantileLoss, calculate_picp

# File Paths
DATA_PATH = Path("data/processed/feature_matrix.parquet")
CSV_FALLBACK_PATH = Path("data/processed/feature_matrix.csv")
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def load_and_preprocess_data() -> tuple[pd.DataFrame, list, str]:
    if DATA_PATH.exists():
        print(f"Loading dataset from {DATA_PATH}...")
        df = pd.read_parquet(DATA_PATH)
    elif CSV_FALLBACK_PATH.exists():
        print(f"Loading CSV fallback dataset from {CSV_FALLBACK_PATH}...")
        df = pd.read_csv(CSV_FALLBACK_PATH, low_memory=False)
    else:
        raise FileNotFoundError(f"Feature matrix not found at {DATA_PATH} or {CSV_FALLBACK_PATH}")

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(['well_id', 'timestamp'])

    target_col = 'depth_to_water_m'
    exclude_cols = ['well_id', 'timestamp', 'land_cover_type', target_col]
    feature_cols = [c for c in df.columns if c not in exclude_cols]

    return df, feature_cols, target_col


def chronological_train_val_test_split(
    df: pd.DataFrame,
    feature_cols: list,
    target_col: str,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15
):
    """
    Splits time series chronologically per well station (70% Train, 15% Val, 15% Test).
    """
    df = df.sort_values(['well_id', 'timestamp']).reset_index(drop=True)
    train_list, val_list, test_list = [], [], []

    for _, group in df.groupby('well_id'):
        n = len(group)
        if n < 5:
            train_list.append(group)
            continue

        n_tr = int(n * train_ratio)
        n_va = int(n * val_ratio)

        train_list.append(group.iloc[:n_tr])
        val_list.append(group.iloc[n_tr : n_tr + n_va])
        test_list.append(group.iloc[n_tr + n_va :])

    df_tr = pd.concat(train_list, ignore_index=True)
    df_va = pd.concat(val_list, ignore_index=True)
    df_te = pd.concat(test_list, ignore_index=True)

    print(f"Dataset Split — Train: {len(df_tr):,} rows | Val: {len(df_va):,} rows | Test: {len(df_te):,} rows")

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(df_tr[feature_cols].fillna(0))
    X_va = scaler.transform(df_va[feature_cols].fillna(0))
    X_te = scaler.transform(df_te[feature_cols].fillna(0))

    y_tr = df_tr[target_col].values
    y_va = df_va[target_col].values
    y_te = df_te[target_col].values

    joblib.dump(scaler, MODELS_DIR / "scaler.pkl")

    return X_tr, y_tr, X_va, y_va, X_te, y_te, df_te


def train_and_evaluate():
    print("==================================================")
    print(" STARTING PHASE 3: PREDICTIVE MODELING (TFT) ")
    print("==================================================")

    # 1. Load Data
    print("[Step 1/5] Loading processed dataset...")
    df, feature_cols, target_col = load_and_preprocess_data()
    print(f"Loaded dataset: {df.shape[0]} rows across {len(feature_cols)} predictor features.")

    # 2. Chronological Split
    print("[Step 2/5] Splitting dataset chronologically (70% Train, 15% Val, 15% Test)...")
    X_tr, y_tr, X_va, y_va, X_te, y_te = chronological_train_val_test_split(df, feature_cols, target_col)
    print(f"Train samples: {X_tr.shape[0]} | Val samples: {X_va.shape[0]} | Test samples: {X_te.shape[0]}")

    results = {}

    # 3. XGBoost Baseline
    print("\n[Step 3/5] Training XGBoost Baseline...")
    xgb_base = XGBoostBaseline()
    xgb_base.fit(pd.DataFrame(X_tr, columns=feature_cols), pd.Series(y_tr))
    xgb_metrics = xgb_base.evaluate(pd.DataFrame(X_te, columns=feature_cols), pd.Series(y_te))
    results["XGBoost"] = xgb_metrics
    joblib.dump(xgb_base.model, MODELS_DIR / "xgboost_baseline.joblib")
    print(f"  XGBoost -> RMSE: {xgb_metrics['RMSE']:.4f}, MAE: {xgb_metrics['MAE']:.4f}, R2: {xgb_metrics['R2']:.4f}")

    # 4. LSTM Baseline
    print("\n[Step 4/5] Training LSTM Baseline...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_ds = TensorDataset(torch.tensor(X_tr, dtype=torch.float32), torch.tensor(y_tr, dtype=torch.float32))
    test_ds = TensorDataset(torch.tensor(X_te, dtype=torch.float32), torch.tensor(y_te, dtype=torch.float32))
    train_loader = DataLoader(train_ds, batch_size=min(256, len(train_ds)), shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=min(256, len(test_ds)), shuffle=False)

    lstm_model = LSTMBaseline(input_dim=X_tr.shape[1]).to(device)
    lstm_criterion = nn.MSELoss()
    lstm_optimizer = torch.optim.Adam(lstm_model.parameters(), lr=0.001)

    for epoch in range(1, 11):
        lstm_model.train()
        for x_b, y_b in train_loader:
            x_b, y_b = x_b.to(device), y_b.to(device)
            lstm_optimizer.zero_grad()
            preds = lstm_model(x_b)
            loss = lstm_criterion(preds, y_b)
            loss.backward()
            lstm_optimizer.step()

    lstm_model.eval()
    all_lstm_preds = []
    with torch.no_grad():
        for x_b, _ in test_loader:
            x_b = x_b.to(device)
            preds = lstm_model(x_b)
            all_lstm_preds.append(preds.cpu().numpy())

    lstm_preds = np.concatenate(all_lstm_preds)
    lstm_rmse = float(np.sqrt(np.mean((y_te - lstm_preds) ** 2)))
    lstm_mae = float(np.mean(np.abs(y_te - lstm_preds)))
    lstm_r2 = float(1.0 - (np.sum((y_te - lstm_preds) ** 2) / np.sum((y_te - np.mean(y_te)) ** 2)))
    results["LSTM"] = {"RMSE": lstm_rmse, "MAE": lstm_mae, "R2": lstm_r2}
    print(f"  LSTM -> RMSE: {lstm_rmse:.4f}, MAE: {lstm_mae:.4f}, R2: {lstm_r2:.4f}")

    # 5. Temporal Fusion Transformer
    print("\n[Step 5/5] Training Temporal Fusion Transformer (TFT)...")
    model = TemporalFusionTransformer(num_features=X_tr.shape[1], hidden_dim=64).to(device)
    criterion = QuantileLoss(quantiles=[0.1, 0.5, 0.9])
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    tft_train_loader = DataLoader(train_ds, batch_size=min(256, len(train_ds)), shuffle=True)
    tft_test_loader = DataLoader(test_ds, batch_size=min(256, len(test_ds)), shuffle=False)

    for epoch in range(1, 16):
        model.train()
        train_loss = 0.0
        for x_b, y_b in tft_train_loader:
            x_b, y_b = x_b.to(device), y_b.to(device)
            optimizer.zero_grad()
            preds, _ = model(x_b)
            loss = criterion(preds, y_b)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(y_b)
        train_loss /= len(tft_train_loader.dataset)
        if epoch % 5 == 0 or epoch == 15:
            print(f"  Epoch {epoch:02d}/15 - Quantile Loss: {train_loss:.4f}")

    torch.save(model.state_dict(), MODELS_DIR / "tft_checkpoint.pth")

    model.eval()
    all_q_preds = []
    with torch.no_grad():
        for x_b, _ in tft_test_loader:
            x_b = x_b.to(device)
            preds, _ = model(x_b)
            all_q_preds.append(preds.cpu().numpy())

    q_preds = np.vstack(all_q_preds)
    q10, q50, q90 = q_preds[:, 0], q_preds[:, 1], q_preds[:, 2]

    tft_rmse = float(np.sqrt(np.mean((y_te - q50) ** 2)))
    tft_mae = float(np.mean(np.abs(y_te - q50)))
    tft_r2 = float(1.0 - (np.sum((y_te - q50) ** 2) / np.sum((y_te - np.mean(y_te)) ** 2)))
    tft_picp = calculate_picp(y_te, q10, q90)

    results["TFT"] = {"RMSE": tft_rmse, "MAE": tft_mae, "R2": tft_r2, "PICP_80": tft_picp}
    print(f"  TFT -> RMSE: {tft_rmse:.4f}, MAE: {tft_mae:.4f}, R2: {tft_r2:.4f}, PICP (80%): {tft_picp:.2f}%")

    with open(MODELS_DIR / "phase3_benchmark_metrics.json", "w") as f:
        json.dump(results, f, indent=4)

    print("\n=== Phase 3 Training Completed Successfully ===")
    print(pd.DataFrame(results).T.to_string())


if __name__ == "__main__":
    train_and_evaluate()