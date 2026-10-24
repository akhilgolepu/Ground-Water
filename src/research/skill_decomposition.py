"""
Research Pipeline — Phase 2: Skill Decomposition (RQ1)
How much skill does monsoon forcing add over groundwater memory, and how far ahead?

Nested arms, all trained and evaluated on identical rows:
  M0  memory       groundwater history, season, climatology, location (the pilot model)
  M1  + forcing    + past rainfall windows, last monsoon, SPI, temperature anomaly
  M2  + climate    + Niño 3.4 and DMI (IOD) at 0/3/6-month lags
  M3  + oracle     + rainfall that actually fell between origin and target (hindsight upper bound)
  C   control      M0 + the source file's snapshot rainfall (prior work's construction)

Each arm gets the same hyper-parameter search: fit on target years ≤ 2012, early-stop on
2013–2015, then refit on all training years (≤ 2015). Test = 2019–2025 on the pilot's common rows.
Uncertainty: well-clustered bootstrap CIs and a panel Diebold–Mariano test (HAC) on
campaign-averaged loss differentials.
"""

import json
import warnings
from itertools import product
from math import erf, sqrt

import numpy as np
import pandas as pd
import xgboost as xgb

from src.research.benchmark import (
    DEPTH_CLASS_NAMES,
    FEATURE_COLS,
    add_expanding_climatology,
    assign_split,
    build_supervised,
    complete_grid,
    depth_class,
)
from src.research.config import DATA_PROCESSED_DIR, HORIZONS, RANDOM_SEED, SKILL_REPORTS_DIR
from src.research.regions import assign_region

INNER_FIT_END_YEAR = 2012  # inner validation = 2013 … TRAIN_END_YEAR
N_BOOT = 1000
JUMP_SENSITIVITY_M = 20.0  # sensitivity analysis: drop readings that move > 20 m in one step

PAST_FORCING = ["rain_since_prev", "rain_3m", "rain_6m", "rain_12m", "jjas_last_mm", "jjas_last_ratio",
                "spi_3", "spi_6", "spi_12", "tmean_anom_3m"]
TELECONNECTION = [f"{i}_lag{l}" for i in ("nino34", "dmi") for l in (0, 3, 6)]
ORACLE = ["oracle_rain", "oracle_rain_ratio"]
SNAPSHOT = ["snap_cum2", "snap_cum4", "snap_cum8"]

ARMS = {
    "M0 memory": FEATURE_COLS,
    "M1 + past forcing": FEATURE_COLS + PAST_FORCING,
    "M2 + ENSO/IOD": FEATURE_COLS + PAST_FORCING + TELECONNECTION,
    "M3 + oracle rain": FEATURE_COLS + PAST_FORCING + TELECONNECTION + ORACLE,
    "C snapshot control": FEATURE_COLS + SNAPSHOT,
}
NESTED_PAIRS = [("M0 memory", "M1 + past forcing"), ("M1 + past forcing", "M2 + ENSO/IOD"),
                ("M2 + ENSO/IOD", "M3 + oracle rain"), ("M0 memory", "C snapshot control"),
                ("M0 memory", "M2 + ENSO/IOD")]

FEATURE_GROUPS = {
    "Groundwater memory": ["y_t", "y_lag1", "y_lag2", "y_lag3", "y_lag4", "d1", "d4", "anom_t", "n_past"],
    "Season & climatology": ["origin_season", "target_season", "clim_target", "clim_origin"],
    "Location & borehole": ["latitude", "longitude", "well_depth_m"],
    "Past rainfall & temperature": PAST_FORCING,
    "ENSO/IOD": TELECONNECTION,
    "Future rainfall (oracle)": ORACLE,
    "Snapshot rainfall": SNAPSHOT,
}

PARAM_GRID = [{"max_depth": d, "min_child_weight": m} for d, m in product([4, 6, 8], [5, 20])]
BASE_PARAMS = dict(learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, tree_method="hist",
                   random_state=RANDOM_SEED, n_jobs=-1)


# ── Data ────────────────────────────────────────────────────────────────────

def load_dataset(h: int, campaigns: pd.DataFrame | None = None, keep_unlabelled: bool = False,
                 forcing: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Supervised rows for horizon h. `campaigns` overrides the research snapshot (the dashboard passes
    the snapshot merged with India-WRIS updates); `keep_unlabelled` keeps origins whose target has not
    been observed yet (operational forecasts); `forcing` overrides the forcing table. Defaults
    reproduce the Phase 2 dataset exactly.
    """
    if campaigns is None:
        campaigns = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    catalog = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")
    if forcing is None:
        forcing = pd.read_parquet(DATA_PROCESSED_DIR / "forcing_features.parquet")

    grid = add_expanding_climatology(complete_grid(campaigns))
    df = build_supervised(grid, catalog, h)
    if not keep_unlabelled:
        df = df[df["y_target"].notna()].copy()
    keep = ["well_id", "campaign_idx"] + PAST_FORCING + TELECONNECTION + SNAPSHOT + [f"oracle_rain_h{h}", f"oracle_rain_ratio_h{h}"]
    df = df.merge(forcing[keep], on=["well_id", "campaign_idx"], how="left")
    df = df.rename(columns={f"oracle_rain_h{h}": "oracle_rain", f"oracle_rain_ratio_h{h}": "oracle_rain_ratio"})

    df["split"] = assign_split(df)
    df["depth_class"] = depth_class(df["y_t"])
    df["region"] = assign_region(df["latitude"], df["longitude"]).to_numpy()
    df["record"] = pd.cut(df["n_past"], [0, 16, 48, np.inf], right=False,
                          labels=["< 4 years", "4–12 years", "≥ 12 years"]).astype(str)
    df["persistence"] = df["y_t"]
    df["anomaly_persistence"] = df["anom_t"] + df["clim_target"]
    return df


# ── Model fitting ───────────────────────────────────────────────────────────

def tune_and_fit(train: pd.DataFrame, features: list[str],
                 inner_fit_end_year: int = INNER_FIT_END_YEAR) -> tuple[xgb.XGBRegressor, dict]:
    """Inner-validation search (fit ≤ 2012, early-stop on 2013–2015 by default), then refit on all training rows."""
    inner_fit = train[train["target_year"] <= inner_fit_end_year]
    inner_val = train[train["target_year"] > inner_fit_end_year]
    y_fit = inner_fit["y_target"] - inner_fit["y_t"]
    y_val = inner_val["y_target"] - inner_val["y_t"]
    trials = []
    for params in PARAM_GRID:
        m = xgb.XGBRegressor(n_estimators=3000, early_stopping_rounds=50, eval_metric="rmse", **BASE_PARAMS, **params)
        m.fit(inner_fit[features], y_fit, eval_set=[(inner_val[features], y_val)], verbose=False)
        trials.append({**params, "best_iteration": int(m.best_iteration), "val_rmse": float(m.best_score)})
    best = min(trials, key=lambda t: t["val_rmse"])
    n_trees = int(np.ceil((best["best_iteration"] + 1) * len(train) / len(inner_fit)))
    params = {k: best[k] for k in ("max_depth", "min_child_weight")}
    model = xgb.XGBRegressor(n_estimators=n_trees, **BASE_PARAMS, **params)
    model.fit(train[features], train["y_target"] - train["y_t"])
    return model, {"best": best, "n_trees_final": n_trees, "trials": trials}


# ── Statistics ──────────────────────────────────────────────────────────────

def nse_median(df: pd.DataFrame, col: str, min_rows: int = 6) -> float:
    def _nse(g):
        ss = ((g["y_target"] - g["y_target"].mean()) ** 2).sum()
        return np.nan if ss == 0 else 1 - ((g[col] - g["y_target"]) ** 2).sum() / ss
    counts = df.groupby("well_id").size()
    sub = df[df["well_id"].isin(counts[counts >= min_rows].index)]
    return float(sub.groupby("well_id").apply(_nse, include_groups=False).median())


def cluster_bootstrap(df: pd.DataFrame, cols: list[str], n_boot: int = N_BOOT, seed: int = RANDOM_SEED) -> dict:
    """Resamples wells with replacement; returns bootstrap MSE draws per column (incl. persistence)."""
    wells, inv = np.unique(df["well_id"].to_numpy(), return_inverse=True)
    sq = {c: np.bincount(inv, weights=(df[c].to_numpy() - df["y_target"].to_numpy()) ** 2, minlength=len(wells))
          for c in cols + ["persistence"]}
    n = np.bincount(inv, minlength=len(wells)).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(wells), size=(n_boot, len(wells)))
    w = np.stack([np.bincount(d, minlength=len(wells)) for d in draws]).astype(float)
    denom = w @ n
    return {c: (w @ v) / denom for c, v in sq.items()}


def ci(values: np.ndarray) -> list[float]:
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def panel_dm(df: pd.DataFrame, a: str, b: str, loss: str = "squared") -> dict:
    """
    Diebold–Mariano on the campaign-averaged loss differential (a − b), Newey–West variance.
    loss="squared" (MSE) or "absolute" (MAE). Absolute loss is the primary test: squared-error
    differentials are dominated by a handful of datum-jump readings (docs/08 §3).
    """
    err_a, err_b = df[a] - df["y_target"], df[b] - df["y_target"]
    diff = err_a ** 2 - err_b ** 2 if loss == "squared" else err_a.abs() - err_b.abs()
    d = diff.groupby(df["target_idx"]).mean().sort_index()
    x = d.to_numpy() - d.mean()
    T = len(x)
    lag = max(1, int(np.floor(4 * (T / 100) ** (2 / 9))))
    var = x @ x / T + 2 * sum((1 - k / (lag + 1)) * (x[k:] @ x[:-k]) / T for k in range(1, lag + 1))
    stat = float(d.mean() / np.sqrt(var / T))
    p = 2 * (1 - 0.5 * (1 + erf(abs(stat) / sqrt(2))))
    return {"T_campaigns": T, "mean_diff": float(d.mean()), "dm_stat": stat, "p_value": float(p)}


def campaign_sign_test(df: pd.DataFrame, a: str, b: str) -> dict:
    """Two-sided binomial sign test: in how many target campaigns does b have lower MAE than a?"""
    from scipy.stats import binomtest

    err_a, err_b = (df[a] - df["y_target"]).abs(), (df[b] - df["y_target"]).abs()
    d = (err_a - err_b).groupby(df["target_idx"]).mean()
    wins, n = int((d > 0).sum()), int((d != 0).sum())
    return {"campaigns_b_better": wins, "campaigns": n, "sign_p_value": float(binomtest(wins, n).pvalue)}


def mae_bootstrap(df: pd.DataFrame, a: str, b: str, n_boot: int = N_BOOT, seed: int = RANDOM_SEED) -> list[float]:
    """Well-clustered bootstrap CI of the MAE reduction 1 − MAE_b / MAE_a."""
    wells, inv = np.unique(df["well_id"].to_numpy(), return_inverse=True)
    sa = np.bincount(inv, weights=(df[a] - df["y_target"]).abs().to_numpy(), minlength=len(wells))
    sb = np.bincount(inv, weights=(df[b] - df["y_target"]).abs().to_numpy(), minlength=len(wells))
    rng = np.random.default_rng(seed)
    w = np.stack([np.bincount(d, minlength=len(wells)) for d in rng.integers(0, len(wells), (n_boot, len(wells)))])
    return ci(1 - (w @ sb) / (w @ sa))


# ── Main ────────────────────────────────────────────────────────────────────

def run_skill_decomposition():
    print("=== Phase 2: Skill Decomposition ===")
    SKILL_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics, strata_rows, boot_rows, dm_rows, shap_rows, tuning = [], [], [], [], [], {}
    preds_out = []

    for h in HORIZONS:
        df = load_dataset(h)
        train = df[df["split"] == "train"]
        evalset = df[df["split"].isin(["cal", "test"])].copy()
        tuning[str(h)] = {}
        for arm, feats in ARMS.items():
            model, info = tune_and_fit(train, feats)
            tuning[str(h)][arm] = info
            evalset[arm] = evalset["y_t"] + model.predict(evalset[feats])
            print(f"[h={h}] {arm:<20} depth={info['best']['max_depth']} mcw={info['best']['min_child_weight']} "
                  f"trees={info['n_trees_final']} inner-val RMSE={info['best']['val_rmse']:.3f}")
            if arm in ("M2 + ENSO/IOD", "M3 + oracle rain"):
                te_s = evalset[evalset["split"] == "test"].sample(min(20000, (evalset["split"] == "test").sum()), random_state=RANDOM_SEED)
                contrib = model.get_booster().predict(xgb.DMatrix(te_s[feats]), pred_contribs=True)[:, :-1]
                share = np.abs(contrib).mean(axis=0)
                for group, cols in FEATURE_GROUPS.items():
                    idx = [feats.index(c) for c in cols if c in feats]
                    if idx:
                        shap_rows.append({"h": h, "arm": arm, "group": group, "mean_abs_shap_m": float(share[idx].sum())})

        test = evalset[evalset["split"] == "test"].dropna(subset=["seasonal_naive", "clim_target", "anomaly_persistence"])
        cols = list(ARMS) + ["anomaly_persistence"]
        mse_p = float(np.mean((test["persistence"] - test["y_target"]) ** 2))
        mse_ap = float(np.mean((test["anomaly_persistence"] - test["y_target"]) ** 2))
        for col in ["persistence"] + cols:
            err = test[col] - test["y_target"]
            mse = float(np.mean(err ** 2))
            metrics.append({"h": h, "months_ahead": 3 * h, "model": col, "n": len(test), "n_wells": test["well_id"].nunique(),
                            "rmse": float(np.sqrt(mse)), "mae": float(np.mean(np.abs(err))), "bias": float(np.mean(err)),
                            "skill_vs_persistence": 1 - mse / mse_p, "skill_vs_anomaly_persistence": 1 - mse / mse_ap,
                            "nse_median": nse_median(test, col)})

        boot = cluster_bootstrap(test, cols)
        for col in cols:
            boot_rows.append({"h": h, "model": col, "stat": "skill_vs_persistence",
                              "estimate": float(1 - np.mean((test[col] - test["y_target"]) ** 2) / mse_p),
                              "ci": ci(1 - boot[col] / boot["persistence"])})
        for a, b in NESTED_PAIRS:
            est = 1 - np.mean((test[b] - test["y_target"]) ** 2) / np.mean((test[a] - test["y_target"]) ** 2)
            boot_rows.append({"h": h, "model": f"{b} vs {a}", "stat": "mse_reduction", "estimate": float(est),
                              "ci": ci(1 - boot[b] / boot[a])})
            mae_a = np.mean(np.abs(test[a] - test["y_target"]))
            mae_b = np.mean(np.abs(test[b] - test["y_target"]))
            mse_dm = panel_dm(test, a, b, "squared")
            mae_dm = panel_dm(test, a, b, "absolute")
            stable = test[(test["y_target"] - test["y_t"]).abs() <= JUMP_SENSITIVITY_M]
            se = lambda c: np.mean((stable[c] - stable["y_target"]) ** 2)
            dm_rows.append({"h": h, "a": a, "b": b,
                            "mse_reduction": float(est), "mae_reduction": float(1 - mae_b / mae_a),
                            "mae_reduction_ci": mae_bootstrap(test, a, b),
                            "dm_mae_stat": mae_dm["dm_stat"], "dm_mae_p": mae_dm["p_value"],
                            "dm_mse_stat": mse_dm["dm_stat"], "dm_mse_p": mse_dm["p_value"],
                            **campaign_sign_test(test, a, b), "T_campaigns": mae_dm["T_campaigns"],
                            "mse_reduction_without_jumps": float(1 - se(b) / se(a)),
                            "n_jump_rows_excluded": int(len(test) - len(stable))})

        for var in ["depth_class", "region", "record", "target_season"]:
            for value, g in test.groupby(var):
                mp = np.mean((g["persistence"] - g["y_target"]) ** 2)
                m0 = np.mean((g["M0 memory"] - g["y_target"]) ** 2)
                label = DEPTH_CLASS_NAMES[int(value)] if var == "depth_class" else (
                    ["Jan", "May", "Aug", "Nov"][int(value)] if var == "target_season" else str(value))
                for arm in ARMS:
                    ma = np.mean((g[arm] - g["y_target"]) ** 2)
                    strata_rows.append({"h": h, "stratum": var, "value": label, "arm": arm, "n": len(g),
                                        "n_wells": g["well_id"].nunique(), "rmse": float(np.sqrt(ma)),
                                        "skill_vs_persistence": float(1 - ma / mp) if mp > 0 else np.nan,
                                        "mse_reduction_vs_M0": float(1 - ma / m0) if m0 > 0 else np.nan})

        keep = ["well_id", "campaign_idx", "target_idx", "split", "y_t", "y_target", "target_season", "depth_class",
                "region", "record", "persistence", "anomaly_persistence"] + list(ARMS)
        preds_out.append(evalset[keep].assign(h=h))

    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv(SKILL_REPORTS_DIR / "metrics.csv", index=False)
    pd.DataFrame(strata_rows).to_csv(SKILL_REPORTS_DIR / "strata.csv", index=False)
    pd.DataFrame(dm_rows).to_csv(SKILL_REPORTS_DIR / "diebold_mariano.csv", index=False)
    pd.DataFrame(shap_rows).to_csv(SKILL_REPORTS_DIR / "shap_groups.csv", index=False)
    with open(SKILL_REPORTS_DIR / "bootstrap.json", "w") as f:
        json.dump(boot_rows, f, indent=2)
    with open(SKILL_REPORTS_DIR / "tuning.json", "w") as f:
        json.dump(tuning, f, indent=2)
    pd.concat(preds_out).to_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet", index=False)

    print("\nSkill vs persistence on common test rows (95% well-clustered bootstrap CI):")
    for r in boot_rows:
        if r["stat"] == "skill_vs_persistence":
            print(f"  h={r['h']} {r['model']:<22} {r['estimate']:+.3f}  [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}]")
    print("\nBetween arms: MSE and MAE reduction (95% CI), DM on absolute loss, campaign sign test:")
    for r, d in zip([r for r in boot_rows if r["stat"] == "mse_reduction"], dm_rows):
        print(f"  h={r['h']} {r['model']:<44} MSE {r['estimate']:+.1%} [{r['ci'][0]:+.1%}, {r['ci'][1]:+.1%}]  "
              f"MAE {d['mae_reduction']:+.1%} [{d['mae_reduction_ci'][0]:+.1%}, {d['mae_reduction_ci'][1]:+.1%}]  "
              f"DM-MAE p={d['dm_mae_p']:.3g}  sign {d['campaigns_b_better']}/{d['campaigns']} p={d['sign_p_value']:.3g}  "
              f"MSE w/o jumps {d['mse_reduction_without_jumps']:+.1%}")
    print(f"\nSaved reports to {SKILL_REPORTS_DIR}/")


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        run_skill_decomposition()
