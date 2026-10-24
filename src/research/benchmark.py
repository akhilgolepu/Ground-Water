"""
Research Pipeline — Step 2: Honest Benchmark & Calibrated Uncertainty (pilot)
Forecasts CGWB manual-network depth to water `h` campaigns ahead (h=1 ≈ 3 months,
h=2 ≈ 6 months, h=4 ≈ 12 months) and evaluates:

  * naive baselines  — persistence, seasonal naive, expanding climatology, anomaly persistence
  * a global XGBoost — trained on groundwater memory only (no meteorology yet)
  * uncertainty      — split conformal, Mondrian conformal (season × depth class) and
                       conformalised quantile regression (CQR), checked for empirical coverage
  * early warning    — conformal predictive probability that depth exceeds the well's
                       seasonal 80th percentile, scored with the Brier skill score

Time-blocked split by *target* year (no per-well random or percentage splits):
train ≤ 2015 · calibration 2016–2018 · test 2019–2025.

All features are computed from information available at the forecast origin.
"""

import json
import numpy as np
import pandas as pd
import xgboost as xgb

from src.research.config import (
    CAL_END_YEAR,
    DATA_PROCESSED_DIR,
    EXCEEDANCE_PERCENTILE,
    HORIZONS,
    NOMINAL_LEVELS,
    RANDOM_SEED,
    REPORTS_DIR,
    TRAIN_END_YEAR,
)

DEPTH_CLASS_EDGES = [-np.inf, 5.0, 15.0, 40.0, np.inf]
DEPTH_CLASS_NAMES = ["< 5 m", "5–15 m", "15–40 m", "≥ 40 m"]

FEATURE_COLS = [
    "y_t", "y_lag1", "y_lag2", "y_lag3", "y_lag4", "d1", "d4",
    "origin_season", "target_season", "clim_target", "clim_origin", "anom_t",
    "n_past", "latitude", "longitude", "well_depth_m",
]
FEATURE_LABELS = {
    "y_t": "Current depth", "y_lag1": "Depth 1 campaign ago", "y_lag2": "Depth 2 campaigns ago",
    "y_lag3": "Depth 3 campaigns ago", "y_lag4": "Depth 1 year ago", "d1": "Change since last campaign",
    "d4": "Change over past year", "origin_season": "Origin season", "target_season": "Target season",
    "clim_target": "Target-season climatology", "clim_origin": "Origin-season climatology",
    "anom_t": "Current anomaly", "n_past": "Record length", "latitude": "Latitude",
    "longitude": "Longitude", "well_depth_m": "Borehole depth",
}


# ── Feature construction ────────────────────────────────────────────────────

def complete_grid(campaigns: pd.DataFrame) -> pd.DataFrame:
    """Expands every well onto a gap-free quarterly campaign grid (missing campaigns = NaN)."""
    span = campaigns.groupby("well_id")["campaign_idx"].agg(["min", "max"])
    lengths = (span["max"] - span["min"] + 1).values
    well_ids = np.repeat(span.index.values, lengths)
    idx = np.concatenate([np.arange(a, b + 1) for a, b in zip(span["min"], span["max"])])
    grid = pd.DataFrame({"well_id": well_ids, "campaign_idx": idx})
    grid = grid.merge(campaigns[["well_id", "campaign_idx", "depth_mbgl"]], how="left")
    grid["season"] = grid["campaign_idx"] % 4
    grid["year"] = grid["campaign_idx"] // 4
    return grid.sort_values(["well_id", "campaign_idx"]).reset_index(drop=True)


def add_expanding_climatology(grid: pd.DataFrame) -> pd.DataFrame:
    """Per-well, per-season mean of all values observed up to (and including) each campaign."""
    g = grid.copy()
    for s in range(4):
        vals = g["depth_mbgl"].where(g["season"] == s)
        csum = vals.fillna(0.0).groupby(g["well_id"]).cumsum()
        ccount = vals.notna().astype(int).groupby(g["well_id"]).cumsum()
        g[f"clim_s{s}"] = (csum / ccount.replace(0, np.nan)).where(ccount >= 2)
    return g


def build_supervised(grid: pd.DataFrame, catalog: pd.DataFrame, h: int) -> pd.DataFrame:
    """One row per (well, origin campaign) with features at the origin and the target h ahead."""
    g = grid
    by_well = g.groupby("well_id")["depth_mbgl"]
    df = g[["well_id", "campaign_idx", "season", "year"]].copy()
    df["y_t"] = g["depth_mbgl"]
    for k in range(1, 5):
        df[f"y_lag{k}"] = by_well.shift(k)
    df["y_target"] = by_well.shift(-h)
    df["d1"] = df["y_t"] - df["y_lag1"]
    df["d4"] = df["y_t"] - df["y_lag4"]
    df["n_past"] = g["depth_mbgl"].notna().astype(int).groupby(g["well_id"]).cumsum()

    df["origin_season"] = df["season"]
    df["target_season"] = (df["season"] + h) % 4
    df["target_idx"] = df["campaign_idx"] + h
    df["target_year"] = df["target_idx"] // 4

    clim = g[[f"clim_s{s}" for s in range(4)]].to_numpy()
    rows = np.arange(len(df))
    df["clim_target"] = clim[rows, df["target_season"].to_numpy()]
    df["clim_origin"] = clim[rows, df["origin_season"].to_numpy()]
    df["anom_t"] = df["y_t"] - df["clim_origin"]

    # Seasonal naive: the value observed in the target season one year before the target
    df["seasonal_naive"] = by_well.shift(4 - h) if h < 4 else df["y_t"]

    meta = catalog.set_index("well_id")[["latitude", "longitude", "well_depth_m"]]
    df = df.join(meta, on="well_id")
    df = df[df["y_t"].notna()].reset_index(drop=True)
    return df


def assign_split(df: pd.DataFrame) -> pd.Series:
    return pd.Series(
        np.select(
            [df["target_year"] <= TRAIN_END_YEAR, df["target_year"] <= CAL_END_YEAR],
            ["train", "cal"],
            default="test",
        ),
        index=df.index,
    )


def depth_class(values: pd.Series) -> pd.Series:
    """Left-closed classes [0, 5), [5, 15), [15, 40), [40, ∞) to match the labels."""
    return pd.cut(values, DEPTH_CLASS_EDGES, labels=False, right=False).astype("Int64")


# ── Metrics ─────────────────────────────────────────────────────────────────

def point_metrics(y: np.ndarray, pred: np.ndarray, ref_mse: float) -> dict:
    err = pred - y
    mse = float(np.mean(err ** 2))
    return {
        "rmse": float(np.sqrt(mse)),
        "mae": float(np.mean(np.abs(err))),
        "bias": float(np.mean(err)),
        "skill_vs_persistence": float(1.0 - mse / ref_mse),
    }


def conformal_quantile(scores: np.ndarray, level: float) -> float:
    """Split-conformal quantile: the ⌈(n+1)·level⌉-th smallest score (the maximum if that exceeds n)."""
    n = len(scores)
    k = min(n, int(np.ceil((n + 1) * level)))
    return float(np.partition(np.asarray(scores, dtype=float), k - 1)[k - 1])


def station_skill(df: pd.DataFrame, pred_col: str, min_rows: int = 6) -> np.ndarray:
    def _skill(gp):
        mse_m = np.mean((gp[pred_col] - gp["y_target"]) ** 2)
        mse_p = np.mean((gp["y_t"] - gp["y_target"]) ** 2)
        return np.nan if mse_p == 0 else 1.0 - mse_m / mse_p
    counts = df.groupby("well_id").size()
    keep = counts[counts >= min_rows].index
    sk = df[df["well_id"].isin(keep)].groupby("well_id").apply(_skill, include_groups=False)
    return sk.dropna().to_numpy()


# ── Trend analysis (Sen's slope + Mann–Kendall on pre-monsoon depth) ────────

def sen_mann_kendall(years: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    n = len(values)
    i, j = np.triu_indices(n, k=1)
    dy, dx = values[j] - values[i], years[j] - years[i]
    slope = float(np.median(dy[dx != 0] / dx[dx != 0]))
    s = np.sign(dy).sum()
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    z = (s - np.sign(s)) / np.sqrt(var_s) if s != 0 else 0.0
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    return slope, float(p)


def premonsoon_trends(campaigns: pd.DataFrame, min_years: int = 8) -> pd.DataFrame:
    may = campaigns[campaigns["season"] == 1]
    out = []
    for well_id, gp in may.groupby("well_id"):
        if gp["year"].nunique() < min_years:
            continue
        slope, p = sen_mann_kendall(gp["year"].to_numpy(float), gp["depth_mbgl"].to_numpy(float))
        out.append((well_id, slope, p))
    return pd.DataFrame(out, columns=["well_id", "trend_m_per_yr", "trend_p"])


# ── Main benchmark ──────────────────────────────────────────────────────────

def run_benchmark():
    print("=== Research Step 2: Honest Benchmark (pilot) ===")
    campaigns = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    catalog = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")

    grid = add_expanding_climatology(complete_grid(campaigns))
    print(f"Campaign grid: {len(grid):,} cells, {grid['depth_mbgl'].notna().sum():,} observed.")

    benchmark = {"horizons": {}, "split": {"train_end_year": TRAIN_END_YEAR, "cal_end_year": CAL_END_YEAR}}
    coverage_rows, importance = [], {}

    for h in HORIZONS:
        df = build_supervised(grid, catalog, h)
        df["split"] = assign_split(df)
        labelled = df[df["y_target"].notna()].copy()
        labelled["depth_class"] = depth_class(labelled["y_t"])

        tr = labelled[labelled["split"] == "train"]
        ca = labelled[labelled["split"] == "cal"].copy()
        te = labelled[labelled["split"] == "test"].copy()

        # Point model: predict the change, add it back to current depth
        model = xgb.XGBRegressor(n_estimators=600, max_depth=6, learning_rate=0.05, subsample=0.8,
                                 colsample_bytree=0.8, min_child_weight=5, random_state=RANDOM_SEED, n_jobs=-1)
        model.fit(tr[FEATURE_COLS], tr["y_target"] - tr["y_t"])
        qmodel = xgb.XGBRegressor(objective="reg:quantileerror", quantile_alpha=np.array([0.1, 0.5, 0.9]),
                                  n_estimators=600, max_depth=6, learning_rate=0.05, subsample=0.8,
                                  colsample_bytree=0.8, min_child_weight=5, random_state=RANDOM_SEED, n_jobs=-1)
        qmodel.fit(tr[FEATURE_COLS], tr["y_target"] - tr["y_t"])

        for part in (ca, te):
            part["xgb"] = part["y_t"] + model.predict(part[FEATURE_COLS])
            q = qmodel.predict(part[FEATURE_COLS])
            part["q10"], part["q90"] = part["y_t"] + q[:, 0], part["y_t"] + q[:, 2]
            part["persistence"] = part["y_t"]
            part["climatology"] = part["clim_target"]
            part["anomaly_persistence"] = part["anom_t"] + part["clim_target"]

        # Common evaluation set: every baseline must be defined
        base_cols = ["seasonal_naive", "climatology", "anomaly_persistence"]
        te_c = te.dropna(subset=base_cols)
        ref_mse = float(np.mean((te_c["persistence"] - te_c["y_target"]) ** 2))
        models = {"Persistence": "persistence", "Seasonal naive": "seasonal_naive",
                  "Climatology": "climatology", "Anomaly persistence": "anomaly_persistence",
                  "XGBoost (memory-only)": "xgb"}
        metrics = {name: point_metrics(te_c["y_target"].to_numpy(), te_c[col].to_numpy(), ref_mse)
                   for name, col in models.items()}
        skills = station_skill(te_c, "xgb")
        benchmark["horizons"][str(h)] = {
            "months_ahead": 3 * h,
            "n_train": int(len(tr)), "n_cal": int(len(ca)), "n_test": int(len(te_c)),
            "n_test_wells": int(te_c["well_id"].nunique()),
            "metrics": metrics,
            "station_skill": {
                "n_wells": int(len(skills)),
                "median": float(np.median(skills)),
                "share_positive": float(np.mean(skills > 0)),
                "histogram": np.histogram(np.clip(skills, -1, 1), bins=20, range=(-1, 1))[0].tolist(),
            },
        }
        print(f"\n[h={h} | {3*h} months] train={len(tr):,} cal={len(ca):,} test={len(te_c):,}")
        for name, m in metrics.items():
            print(f"  {name:<24} RMSE {m['rmse']:.3f}  MAE {m['mae']:.3f}  skill {m['skill_vs_persistence']:+.3f}")

        # ── Uncertainty: coverage of each interval method on the test set ──
        abs_res_cal = np.abs(ca["y_target"] - ca["xgb"]).to_numpy()
        group_cal = ca["target_season"].astype(str) + "|" + ca["depth_class"].astype(str)
        group_te = te["target_season"].astype(str) + "|" + te["depth_class"].astype(str)
        cqr_scores = np.maximum(ca["q10"] - ca["y_target"], ca["y_target"] - ca["q90"]).to_numpy()
        gauss_sigma = float(np.std(tr["y_target"] - tr["y_t"] - model.predict(tr[FEATURE_COLS])))
        from statistics import NormalDist

        for level in NOMINAL_LEVELS:
            z = NormalDist().inv_cdf(0.5 + level / 2)
            methods = {}
            methods["Gaussian (train residuals)"] = (te["xgb"] - z * gauss_sigma, te["xgb"] + z * gauss_sigma)
            qg = conformal_quantile(abs_res_cal, level)
            methods["Split conformal"] = (te["xgb"] - qg, te["xgb"] + qg)
            qmap = {k: conformal_quantile(np.abs(gp["y_target"] - gp["xgb"]).to_numpy(), level)
                    for k, gp in ca.groupby(group_cal) if len(gp) >= 50}
            q_te = group_te.map(qmap).fillna(qg)
            methods["Mondrian conformal"] = (te["xgb"] - q_te, te["xgb"] + q_te)
            if level == 0.8:
                methods["Quantile XGBoost (raw)"] = (te["q10"], te["q90"])
                qc = conformal_quantile(cqr_scores, level)
                methods["CQR"] = (te["q10"] - qc, te["q90"] + qc)
                te["lo80"], te["hi80"] = methods["Mondrian conformal"]

            for mname, (lo, hi) in methods.items():
                covered = (te["y_target"] >= lo) & (te["y_target"] <= hi)
                width = (hi - lo)
                coverage_rows.append({"h": h, "nominal": level, "method": mname,
                                      "coverage": float(covered.mean()), "median_width_m": float(width.median()),
                                      "group": "All"})
                if mname == "Mondrian conformal" or mname == "Split conformal":
                    for dc, sub in covered.groupby(te["depth_class"]):
                        coverage_rows.append({"h": h, "nominal": level, "method": mname,
                                              "coverage": float(sub.mean()),
                                              "median_width_m": float(width[sub.index].median()),
                                              "group": DEPTH_CLASS_NAMES[int(dc)]})

        # ── Early warning: P(depth > seasonal 80th pct) from the conformal predictive distribution ──
        signed_res = (ca["y_target"] - ca["xgb"]).to_numpy()
        hist = campaigns[campaigns["year"] <= CAL_END_YEAR]
        thr = hist.groupby(["well_id", "season"])["depth_mbgl"].agg(
            lambda s: s.quantile(EXCEEDANCE_PERCENTILE) if len(s) >= 4 else np.nan)
        te["threshold"] = pd.MultiIndex.from_arrays([te["well_id"], te["target_season"]]).map(thr)
        ew = te.dropna(subset=["threshold"])
        res_sorted = np.sort(signed_res)
        p_exceed = 1.0 - np.searchsorted(res_sorted, (ew["threshold"] - ew["xgb"]).to_numpy(), side="right") / len(res_sorted)
        event = (ew["y_target"] > ew["threshold"]).astype(float).to_numpy()
        brier = float(np.mean((p_exceed - event) ** 2))
        base_rate = 1.0 - EXCEEDANCE_PERCENTILE
        brier_clim = float(np.mean((base_rate - event) ** 2))
        bins = np.linspace(0, 1, 11)
        which = np.clip(np.digitize(p_exceed, bins) - 1, 0, 9)
        reliability = [{"p_mean": float(p_exceed[which == b].mean()), "obs_freq": float(event[which == b].mean()),
                        "n": int((which == b).sum())} for b in range(10) if (which == b).sum() >= 30]
        benchmark["horizons"][str(h)]["early_warning"] = {
            "event": f"depth deeper than the well's {int(EXCEEDANCE_PERCENTILE*100)}th percentile for the target season",
            "n": int(len(ew)), "event_rate": float(event.mean()),
            "brier": brier, "brier_climatology": brier_clim,
            "brier_skill": float(1 - brier / brier_clim), "reliability": reliability,
        }
        print(f"  Early warning: Brier {brier:.4f} vs climatology {brier_clim:.4f} → BSS {1 - brier / brier_clim:+.3f}")

        # ── Explainability: TreeSHAP contributions (XGBoost native) ──
        sample = te_c.sample(min(20000, len(te_c)), random_state=RANDOM_SEED)
        contribs = model.get_booster().predict(xgb.DMatrix(sample[FEATURE_COLS]), pred_contribs=True)
        mean_abs = np.abs(contribs[:, :-1]).mean(axis=0)
        importance[str(h)] = sorted(
            [{"feature": FEATURE_LABELS[f], "key": f, "mean_abs_shap_m": float(v)} for f, v in zip(FEATURE_COLS, mean_abs)],
            key=lambda d: -d["mean_abs_shap_m"])


    # ── Persist research artefacts ──
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(REPORTS_DIR / "coverage.csv", index=False)
    with open(REPORTS_DIR / "benchmark_metrics.json", "w") as f:
        json.dump(benchmark, f, indent=2)
    with open(REPORTS_DIR / "shap_importance.json", "w") as f:
        json.dump(importance, f, indent=2)
    print(f"\nSaved benchmark artefacts to {REPORTS_DIR}/")


if __name__ == "__main__":
    run_benchmark()
