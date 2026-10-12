"""
Phase 4: Explainable AI (XAI) & Natural Language Generation (NLG) Module
Extracts feature attributions (SHAP & TFT VSN weights) and converts numerical
predictions into policy-ready natural language explanations.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import joblib
import shap

from src.models.tft_model import TemporalFusionTransformer
from src.models.train import load_and_preprocess_data, chronological_train_val_test_split

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def extract_tft_feature_importance(model: torch.nn.Module, X_sample: np.ndarray, feature_names: list) -> pd.DataFrame:
    """
    Extracts global variable importance from the TFT Variable Selection Network (VSN).
    """
    device = next(model.parameters()).device
    model.eval()
    
    with torch.no_grad():
        x_tensor = torch.tensor(X_sample, dtype=torch.float32).to(device)
        weights = model.vsn.weight_grn(x_tensor)
        weights = torch.softmax(weights, dim=-1).cpu().numpy()

    mean_weights = weights.mean(axis=0)
    importance_df = pd.DataFrame({
        "Feature": feature_names,
        "VSN_Importance": mean_weights
    }).sort_values("VSN_Importance", ascending=False).reset_index(drop=True)
    
    return importance_df


def compute_tree_shap_values(model_path: Path, X_sample: np.ndarray, feature_names: list) -> tuple[np.ndarray, shap.Explainer]:
    """
    Computes TreeSHAP feature attributions using the trained XGBoost baseline.
    """
    xgb_model = joblib.load(model_path)
    explainer = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(X_sample)
    return shap_values, explainer


def generate_natural_language_explanation(
    well_id: str,
    current_depth: float,
    predicted_q10: float,
    predicted_q50: float,
    predicted_q90: float,
    top_features: list[tuple[str, float]]
) -> str:
    """
    Translates numerical point forecasts, quantile ranges, and top SHAP features
    into a plain-language policy summary for water managers.
    """
    delta = predicted_q50 - current_depth  # Positive delta = deeper water table (drawdown)
    abs_delta = abs(delta)

    if delta > 0:
        trend_str = f"drop (drawdown) of {abs_delta:.2f} meters"
    else:
        trend_str = f"increase (recharge) of {abs_delta:.2f} meters"

    driver_texts = []
    for feat, impact in top_features[:3]:
        if delta > 0:
            direction = "increasing drawdown risk" if impact > 0 else "mitigating drawdown"
        else:
            direction = "supporting recharge" if impact < 0 else "limiting recharge"
            
        clean_name = feat.replace("_", " ").title()
        driver_texts.append(f"{clean_name} ({direction})")

    drivers_sentence = ", ".join(driver_texts)

    explanation = (
        f"POLICY BRIEF FOR MONITORING WELL [{well_id}]:\n"
        f"• Current Water Depth : {current_depth:.2f} m bgl\n"
        f"• Predicted Forecast  : {predicted_q50:.2f} m bgl (Median)\n"
        f"• Projected Change    : Expected {trend_str} over the next horizon.\n"
        f"• Confidence Interval : 80% probability depth remains between {predicted_q10:.2f} m and {predicted_q90:.2f} m bgl.\n"
        f"• Primary Drivers     : {drivers_sentence}.\n"
        f"• Advisory Action     : "
    )

    if delta >= 2.0:
        explanation += "CRITICAL DRAWDOWN ALERT — Issue immediate extraction restrictions for nearby agricultural pumps."
    elif delta >= 0.5:
        explanation += "MODERATE RISK — Monitor local abstraction rates weekly and prepare supplemental recharge protocols."
    elif delta <= -2.0:
        explanation += "SIGNIFICANT RECHARGE — Safe capacity available for seasonal agricultural pumping."
    else:
        explanation += "STABLE CONDITIONS — Maintain standard seasonal extraction quotas."

    return explanation


def run_phase4():
    print("==================================================")
    print(" STARTING PHASE 4: MODEL INTERPRETABILITY & XAI  ")
    print("==================================================")

    # 1. Load Data
    print("[Step 1/4] Loading feature matrix and trained model checkpoints...")
    df, feature_cols, target_col = load_and_preprocess_data()
    X_tr, y_tr, X_va, y_va, X_te, y_te, df_te = chronological_train_val_test_split(df, feature_cols, target_col)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tft_model = TemporalFusionTransformer(num_features=X_tr.shape[1], hidden_dim=64).to(device)
    tft_model.load_state_dict(torch.load(MODELS_DIR / "tft_checkpoint.pth", map_location=device))

    # 2. Extract VSN Weights
    print("\n[Step 2/4] Extracting TFT Variable Selection Network (VSN) Importance...")
    np.random.seed(42)
    sample_indices = np.random.choice(len(X_te), size=min(1000, len(X_te)), replace=False)
    X_sample = X_te[sample_indices]
    
    vsn_df = extract_tft_feature_importance(tft_model, X_sample, feature_cols)
    print("\nTop 5 Driver Variables (TFT VSN):")
    print(vsn_df.head(5).to_string(index=False))

    # 3. Compute SHAP Values
    print("\n[Step 3/4] Computing TreeSHAP Attributions...")
    shap_values, _ = compute_tree_shap_values(MODELS_DIR / "xgboost_baseline.joblib", X_sample, feature_cols)
    
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    shap_df = pd.DataFrame({"Feature": feature_cols, "Mean_SHAP": mean_abs_shap}).sort_values("Mean_SHAP", ascending=False).reset_index(drop=True)
    
    print("\nTop 5 Driver Variables (TreeSHAP):")
    print(shap_df.head(5).to_string(index=False))

    # 4. Generate Natural Language Summaries (NLG)
    print("\n[Step 4/4] Generating Sample Natural Language Policy Briefs...")
    
    with torch.no_grad():
        sample_tensor = torch.tensor(X_sample[:3], dtype=torch.float32).to(device)
        preds, _ = tft_model(sample_tensor)
        preds = preds.cpu().numpy()

    for i in range(3):
        # EXACT INDEX MATCH: Extract metadata directly from df_te using sample_indices[i]
        matched_row = df_te.iloc[sample_indices[i]]
        well_id = matched_row["well_id"]
        current_val = float(matched_row[target_col])
        q10, q50, q90 = float(preds[i, 0]), float(preds[i, 1]), float(preds[i, 2])
        
        station_shap = list(zip(feature_cols, shap_values[i]))
        station_shap.sort(key=lambda x: abs(x[1]), reverse=True)
        
        brief = generate_natural_language_explanation(well_id, current_val, q10, q50, q90, station_shap)
        print("\n" + "=" * 60)
        print(brief)

    vsn_df.to_csv(REPORTS_DIR / "vsn_feature_importance.csv", index=False)
    shap_df.to_csv(REPORTS_DIR / "shap_feature_importance.csv", index=False)
    print(f"\nSaved XAI importance tables to {REPORTS_DIR}/")


if __name__ == "__main__":
    run_phase4()