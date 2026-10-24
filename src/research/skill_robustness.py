"""
Research Pipeline — Phase 2.7: Robustness of the skill decomposition.

  A. Alternative split   train ≤ 2017, test 2020–2025 (inner validation 2015–2017)
  B. Spatial blocks      wells grouped into 2° × 2° blocks, 5 folds; each fold trains on the other
                         blocks (target years ≤ 2015) and tests on its own blocks (2019–2025),
                         i.e. forecasting in regions the model has never seen

For each setting it reports M0 → M1 → M2 → M3 gains (MSE and MAE reduction) and the campaign
sign test, using the same tuning procedure as the main experiment.
"""

import json
import warnings

import numpy as np
import pandas as pd

from src.research.config import HORIZONS, RANDOM_SEED, SKILL_REPORTS_DIR
from src.research.skill_decomposition import ARMS, campaign_sign_test, load_dataset, tune_and_fit

ROBUST_ARMS = ["M0 memory", "M1 + past forcing", "M2 + ENSO/IOD", "M3 + oracle rain"]
PAIRS = [("M0 memory", "M1 + past forcing"), ("M0 memory", "M2 + ENSO/IOD"), ("M2 + ENSO/IOD", "M3 + oracle rain")]
N_FOLDS = 5
BLOCK_DEG = 2.0


def gains(test: pd.DataFrame, setting: str, h: int) -> list[dict]:
    test = test.dropna(subset=["anomaly_persistence"])
    out = []
    mse_p = np.mean((test["persistence"] - test["y_target"]) ** 2)
    for a, b in PAIRS:
        mse = lambda c: np.mean((test[c] - test["y_target"]) ** 2)
        mae = lambda c: np.mean(np.abs(test[c] - test["y_target"]))
        out.append({"setting": setting, "h": h, "a": a, "b": b, "n": len(test), "n_wells": test["well_id"].nunique(),
                    "skill_a": float(1 - mse(a) / mse_p), "skill_b": float(1 - mse(b) / mse_p),
                    "mse_reduction": float(1 - mse(b) / mse(a)), "mae_reduction": float(1 - mae(b) / mae(a)),
                    **campaign_sign_test(test, a, b)})
    return out


def alternative_split(h: int) -> pd.DataFrame:
    df = load_dataset(h)
    train = df[df["target_year"] <= 2017]
    test = df[df["target_year"] >= 2020].copy()
    for arm in ROBUST_ARMS:
        model, _ = tune_and_fit(train, ARMS[arm], inner_fit_end_year=2014)
        test[arm] = test["y_t"] + model.predict(test[ARMS[arm]])
    return test


def spatial_blocks(h: int) -> pd.DataFrame:
    df = load_dataset(h)
    block = (np.floor(df["latitude"] / BLOCK_DEG).astype(int).astype(str) + "_"
             + np.floor(df["longitude"] / BLOCK_DEG).astype(int).astype(str))
    blocks = np.array(sorted(block.unique()))
    rng = np.random.default_rng(RANDOM_SEED)
    fold_of = dict(zip(blocks, rng.permutation(len(blocks)) % N_FOLDS))
    df["fold"] = block.map(fold_of)
    parts = []
    for k in range(N_FOLDS):
        train = df[(df["fold"] != k) & (df["split"] == "train")]
        test = df[(df["fold"] == k) & (df["split"] == "test")].copy()
        for arm in ROBUST_ARMS:
            model, _ = tune_and_fit(train, ARMS[arm])
            test[arm] = test["y_t"] + model.predict(test[ARMS[arm]])
        parts.append(test)
        print(f"  [h={h}] spatial fold {k + 1}/{N_FOLDS}: {test['well_id'].nunique()} unseen wells")
    return pd.concat(parts)


def run_robustness():
    print("=== Phase 2.7: Robustness ===")
    rows = []
    for h in HORIZONS:
        print(f"[h={h}] alternative split (train ≤ 2017, test 2020–2025)")
        rows += gains(alternative_split(h), "Split: train ≤2017, test 2020–25", h)
        print(f"[h={h}] spatially blocked CV ({BLOCK_DEG:.0f}° blocks, {N_FOLDS} folds)")
        rows += gains(spatial_blocks(h), "Spatial blocks (unseen regions)", h)
    out = pd.DataFrame(rows)
    out.to_csv(SKILL_REPORTS_DIR / "robustness.csv", index=False)
    for r in rows:
        print(f"  {r['setting']:<34} h={r['h']} {r['b']:<18} vs {r['a']:<18} MSE {r['mse_reduction']:+.1%}  "
              f"MAE {r['mae_reduction']:+.1%}  sign {r['campaigns_b_better']}/{r['campaigns']} p={r['sign_p_value']:.3g}  "
              f"(skill {r['skill_a']:.3f} → {r['skill_b']:.3f})")
    print(f"Saved {SKILL_REPORTS_DIR / 'robustness.csv'}")


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        run_robustness()
