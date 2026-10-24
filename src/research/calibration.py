"""
Research Pipeline — Phase 3: Uncertainty Calibration (RQ2)
Can prediction intervals hold their stated coverage for shallow and deep wells, every region and
every season — and keep holding as conditions drift?

All methods wrap the same point forecast: the Phase 2 M2 arm (memory + past forcing + ENSO/IOD),
trained on target years ≤ 2015. Calibration residuals come from 2016–2018; test = 2019–2025.

Static methods (calibrate once on 2016–2018)
  Gaussian            ŷ ± z·σ, σ = std of calibration residuals
  Split conformal     one pool of signed residuals for every well
  Mondrian D×S        separate pools per depth class × target season (the pilot method)
  Mondrian D×R        separate pools per depth class × region
  Normalised          residuals scaled by a cross-fitted σ̂(x) model, one pool
  CQR                 conformalised quantile regression (quantile XGBoost on M2 features)
Online methods (operational: use every reading already observed when the forecast is made)
  Mondrian D×R + recal      pools grow with test residuals whose target is ≤ T − h
  Mondrian D×R + recal + ACI  plus adaptive conformal inference (Gibbs & Candès 2021): each cell's
                              working α moves with its own observed miscoverage
  Mondrian D×R×S + recal + ACI    the same with target season added to the cells
  Normalised D×R×S + recal + ACI  the same on σ̂-scaled scores (sharper intervals for deep wells)

All conformal intervals are two-sided from signed residuals with finite-sample ranks, so a pool of
n residuals gives coverage ≥ 1 − α under exchangeability. Small cells fall back to coarser pools.
"""

import json
import warnings

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import stats

from src.research.benchmark import DEPTH_CLASS_NAMES
from src.research.config import DATA_PROCESSED_DIR, HORIZONS, NOMINAL_LEVELS, RANDOM_SEED, SKILL_REPORTS_DIR
from src.research.skill_decomposition import ARMS, BASE_PARAMS, load_dataset

CALIBRATION_REPORTS_DIR = SKILL_REPORTS_DIR.parent / "calibration"
POINT_ARM = "M2 + ENSO/IOD"
MIN_CELL = 50
ACI_GAMMA = 0.05  # fixed a priori; sensitivity over ACI_GAMMA_GRID is reported
ACI_GAMMA_GRID = [0.01, 0.02, 0.05, 0.1]
CRPS_TAUS = np.round(np.arange(0.025, 0.976, 0.025), 3)
TOLERANCE = 0.03  # exit check: every depth and region class within ±3 points
SEASONS = ["Jan", "May", "Aug", "Nov"]


# ── Conformal primitives ────────────────────────────────────────────────────

def signed_offsets(residuals: np.ndarray, alpha: float) -> tuple[float, float]:
    """
    Two-sided split-conformal offsets from signed residuals r = y − ŷ:
    lower = r_(⌊(n+1)·α/2⌋), upper = r_(⌈(n+1)·(1−α/2)⌉); ±inf when the rank falls outside 1…n.
    """
    r = np.sort(np.asarray(residuals, dtype=float))
    n = len(r)
    k_lo = int(np.floor((n + 1) * alpha / 2))
    k_hi = int(np.ceil((n + 1) * (1 - alpha / 2)))
    lo = r[k_lo - 1] if k_lo >= 1 else -np.inf
    hi = r[k_hi - 1] if k_hi <= n else np.inf
    return float(lo), float(hi)


def residual_quantile(residuals: np.ndarray, tau: float) -> float:
    """Conformal-style τ-quantile of signed residuals (rank ⌈(n+1)τ⌉, clipped to the sample)."""
    r = np.sort(np.asarray(residuals, dtype=float))
    k = int(np.clip(np.ceil((len(r) + 1) * tau), 1, len(r)))
    return float(r[k - 1])


def hierarchical_pools(pool: pd.DataFrame, keys: list[str], min_cell: int = MIN_CELL) -> dict:
    """
    Residual pools for every prefix of `keys` (finest first), so a cell with < min_cell residuals
    falls back to its parent, ending at the global pool under key ().
    """
    pools = {(): pool["score"].to_numpy()}
    for depth in range(1, len(keys) + 1):
        for cell, g in pool.groupby(keys[:depth]):
            cell = cell if isinstance(cell, tuple) else (cell,)
            if len(g) >= min_cell:
                pools[cell] = g["score"].to_numpy()
    return pools


def lookup(pools: dict, cell: tuple) -> np.ndarray:
    for depth in range(len(cell), -1, -1):
        if cell[:depth] in pools:
            return pools[cell[:depth]]
    raise KeyError(cell)


def aci_update(alpha_t: float, alpha: float, miscoverage: float, gamma: float) -> float:
    """Adaptive conformal inference step: α_{t+1} = α_t + γ·(α − err_t), clipped to (0, 1)."""
    return float(np.clip(alpha_t + gamma * (alpha - miscoverage), 1e-4, 0.999))


# ── Scores ──────────────────────────────────────────────────────────────────

def winkler(y, lo, hi, alpha):
    width = hi - lo
    return width + (2 / alpha) * np.clip(lo - y, 0, None) + (2 / alpha) * np.clip(y - hi, 0, None)


def crps_from_quantiles(y: np.ndarray, q: np.ndarray, taus: np.ndarray = CRPS_TAUS) -> np.ndarray:
    """CRPS ≈ 2 × mean pinball loss over a uniform τ grid. q: [n, len(taus)]."""
    diff = y[:, None] - q
    pinball = np.maximum(taus * diff, (taus - 1) * diff)
    return 2 * pinball.mean(axis=1)


# ── Data ────────────────────────────────────────────────────────────────────

def load_frame(h: int) -> pd.DataFrame:
    """Phase 2 M2 forecasts for calibration and test rows, joined with the model features."""
    preds = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    preds = preds[(preds["h"] == h) & preds["split"].isin(["cal", "test"])]
    feats = load_dataset(h)
    keep = ["well_id", "campaign_idx"] + [c for c in ARMS[POINT_ARM] if c not in preds.columns]
    df = preds.merge(feats[keep], on=["well_id", "campaign_idx"], how="left")
    df["yhat"] = df[POINT_ARM]
    df["score"] = df["y_target"] - df["yhat"]
    df["depth_name"] = df["depth_class"].map(lambda v: DEPTH_CLASS_NAMES[int(v)])
    df["season_name"] = df["target_season"].map(lambda v: SEASONS[int(v)])
    return df.reset_index(drop=True)


# ── Normalised conformal: cross-fitted σ̂(x) ─────────────────────────────────

SIGMA_FEATURES = ["y_t", "d1", "d4", "anom_t", "n_past", "target_season", "clim_target", "latitude", "longitude",
                  "well_depth_m", "rain_since_prev", "spi_6"]


def fit_sigma(cal: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    σ̂(x) = predicted |residual|. Two-fold cross-fit by well on the calibration rows (each fold
    scored by the model fitted on the other), test σ̂ = mean of the two fold models.
    """
    wells = cal["well_id"].unique()
    rng = np.random.default_rng(RANDOM_SEED)
    fold_of = dict(zip(wells, rng.permutation(len(wells)) % 2))
    fold = cal["well_id"].map(fold_of).to_numpy()
    sigma_cal = np.zeros(len(cal))
    sigma_test = np.zeros(len(test))
    for k in (0, 1):
        tr = cal[fold != k]
        m = xgb.XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
                             colsample_bytree=0.8, min_child_weight=20, random_state=RANDOM_SEED, n_jobs=-1)
        m.fit(tr[SIGMA_FEATURES], np.log(np.abs(tr["score"]) + 0.05))
        sigma_cal[fold == k] = np.exp(m.predict(cal.loc[fold == k, SIGMA_FEATURES]))
        sigma_test += np.exp(m.predict(test[SIGMA_FEATURES])) / 2
    return sigma_cal, sigma_test


# ── CQR ─────────────────────────────────────────────────────────────────────

def cqr_quantiles(h: int, levels: list[float]) -> pd.DataFrame:
    """Quantile XGBoost on the M2 features (trained ≤ 2015, M2's tuned depth) for every α/2, 1 − α/2."""
    df = load_dataset(h)
    with open(SKILL_REPORTS_DIR / "tuning.json") as f:
        best = json.load(f)[str(h)][POINT_ARM]
    taus = sorted({round(t, 4) for a in levels for t in ((1 - a) / 2, 1 - (1 - a) / 2)})
    params = {k: v for k, v in BASE_PARAMS.items()}
    m = xgb.XGBRegressor(objective="reg:quantileerror", quantile_alpha=np.array(taus),
                         n_estimators=best["n_trees_final"], max_depth=best["best"]["max_depth"],
                         min_child_weight=best["best"]["min_child_weight"], **params)
    train = df[df["split"] == "train"]
    feats = ARMS[POINT_ARM]
    m.fit(train[feats], train["y_target"] - train["y_t"])
    ev = df[df["split"].isin(["cal", "test"])]
    q = np.sort(m.predict(ev[feats]), axis=1) + ev["y_t"].to_numpy()[:, None]
    out = ev[["well_id", "campaign_idx"]].copy()
    for j, t in enumerate(taus):
        out[f"q{t}"] = q[:, j]
    return out


# ── Interval construction ───────────────────────────────────────────────────

def static_mondrian(cal: pd.DataFrame, test: pd.DataFrame, keys: list[str], alpha: float,
                    scale_cal=None, scale_test=None) -> tuple[np.ndarray, np.ndarray]:
    pool = cal.assign(score=cal["score"] / (scale_cal if scale_cal is not None else 1.0))
    pools = hierarchical_pools(pool, keys)
    cells = test[keys].apply(tuple, axis=1) if keys else pd.Series([()] * len(test), index=test.index)
    offs = {c: signed_offsets(lookup(pools, c), alpha) for c in cells.unique()}
    lo_off = cells.map(lambda c: offs[c][0]).to_numpy()
    hi_off = cells.map(lambda c: offs[c][1]).to_numpy()
    s = scale_test if scale_test is not None else 1.0
    return test["yhat"].to_numpy() + lo_off * s, test["yhat"].to_numpy() + hi_off * s


def online_mondrian(cal: pd.DataFrame, test: pd.DataFrame, keys: list[str], alpha: float, h: int,
                    gamma: float | None = None, scale_cal=None, scale_test=None) -> tuple[np.ndarray, np.ndarray]:
    """
    Campaign-by-campaign: the pool for target campaign T holds calibration residuals plus test
    residuals whose target_idx ≤ T − h (already observed when the forecast was issued). With
    `gamma`, each cell's working α follows ACI using miscoverage observed with the same lag.
    With `scale_cal`/`scale_test` (σ̂), scores are residual / σ̂ and offsets are multiplied back by σ̂.
    """
    lo = np.full(len(test), np.nan)
    hi = np.full(len(test), np.nan)
    cal = cal.assign(score=cal["score"] / (scale_cal if scale_cal is not None else 1.0))
    test = test.assign(score=test["score"] / (scale_test if scale_test is not None else 1.0),
                       sigma=scale_test if scale_test is not None else 1.0)
    test["cell"] = test[keys].apply(tuple, axis=1)
    alpha_t: dict[tuple, float] = {}
    history: dict[int, pd.DataFrame] = {}  # target_idx → that campaign's rows with interval outcome
    pending_updates: list[int] = []
    for T in sorted(test["target_idx"].unique()):
        # ACI: absorb outcomes of campaigns that became observable before issuing forecasts for T
        if gamma is not None:
            for t in [t for t in pending_updates if t <= T - h]:
                g = history[t]
                for cell, gc in g.groupby("cell"):
                    a = alpha_t.get(cell, alpha)
                    alpha_t[cell] = aci_update(a, alpha, float(gc["miss"].mean()), gamma)
                pending_updates.remove(t)
        seen = test[test["target_idx"] <= T - h]
        pools = hierarchical_pools(pd.concat([cal[keys + ["score"]], seen[keys + ["score"]]]), keys)
        idx = np.flatnonzero(test["target_idx"].to_numpy() == T)
        rows = test.iloc[idx]
        for cell, gc in rows.groupby("cell"):
            a = alpha_t.get(cell, alpha) if gamma is not None else alpha
            o_lo, o_hi = signed_offsets(lookup(pools, cell), a)
            pos = idx[np.isin(rows.index, gc.index)]
            lo[pos] = gc["yhat"].to_numpy() + o_lo * gc["sigma"].to_numpy()
            hi[pos] = gc["yhat"].to_numpy() + o_hi * gc["sigma"].to_numpy()
        if gamma is not None:
            done = rows.assign(miss=~((rows["y_target"] >= lo[idx]) & (rows["y_target"] <= hi[idx])))
            history[T] = done[["cell", "miss"]]
            pending_updates.append(T)
    return lo, hi


# ── Evaluation ──────────────────────────────────────────────────────────────

GROUP_VARS = {"depth_name": "Depth", "region": "Region", "season_name": "Target season", "record": "Record length"}


def evaluate(test: pd.DataFrame, lo, hi, method: str, level: float, h: int) -> list[dict]:
    y = test["y_target"].to_numpy()
    inside = (y >= lo) & (y <= hi)
    width = hi - lo
    ws = winkler(y, lo, hi, 1 - level)
    rows = [{"h": h, "method": method, "nominal": level, "group_var": "All", "group": "All", "n": len(y),
             "coverage": float(inside.mean()), "median_width": float(np.median(width)),
             "mean_width": float(np.mean(width[np.isfinite(width)])), "winkler": float(np.mean(ws[np.isfinite(ws)])),
             "infinite_share": float(np.mean(~np.isfinite(width)))}]
    for var, label in GROUP_VARS.items():
        for g, idx in test.groupby(var).indices.items():
            cov = float(inside[idx].mean())
            p = stats.binomtest(int(inside[idx].sum()), len(idx), level).pvalue
            rows.append({"h": h, "method": method, "nominal": level, "group_var": label, "group": str(g),
                         "n": len(idx), "coverage": cov, "median_width": float(np.median(width[idx])),
                         "mean_width": float(np.mean(width[idx][np.isfinite(width[idx])])) if np.isfinite(width[idx]).any() else np.inf,
                         "winkler": float(np.mean(ws[idx][np.isfinite(ws[idx])])) if np.isfinite(ws[idx]).any() else np.inf,
                         "infinite_share": float(np.mean(~np.isfinite(width[idx]))), "binom_p": float(p)})
    return rows


def holm(pvals: pd.Series) -> pd.Series:
    order = pvals.sort_values().index
    m = len(pvals)
    adj, running = pd.Series(index=pvals.index, dtype=float), 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvals[k]))
        adj[k] = running
    return adj


def predictive_quantiles(cal: pd.DataFrame, test: pd.DataFrame, keys: list[str], scale_cal=None, scale_test=None):
    """Quantiles of the conformal predictive distribution on the CRPS grid, plus PIT values."""
    pool = cal.assign(score=cal["score"] / (scale_cal if scale_cal is not None else 1.0))
    pools = hierarchical_pools(pool, keys)
    cells = test[keys].apply(tuple, axis=1) if keys else pd.Series([()] * len(test), index=test.index)
    s = scale_test if scale_test is not None else np.ones(len(test))
    q = np.zeros((len(test), len(CRPS_TAUS)))
    pit = np.zeros(len(test))
    z = (test["score"].to_numpy()) / s
    cell_arr = cells.to_numpy()
    for c in pd.unique(cell_arr):
        idx = np.flatnonzero(np.array([x == c for x in cell_arr]))
        r = np.sort(lookup(pools, c))
        qs = np.array([residual_quantile(r, t) for t in CRPS_TAUS])
        q[idx] = test["yhat"].to_numpy()[idx, None] + qs[None, :] * s[idx, None]
        pit[idx] = (np.searchsorted(r, z[idx], side="right") + 0.5) / (len(r) + 1)
    return q, pit


def run_calibration():
    print("=== Phase 3: Uncertainty Calibration ===")
    CALIBRATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rows, prob_rows, pit_rows, aci_rows, interval_store = [], [], [], [], []

    for h in HORIZONS:
        df = load_frame(h)
        cal, test = df[df["split"] == "cal"].reset_index(drop=True), df[df["split"] == "test"].reset_index(drop=True)
        sigma_cal, sigma_test = fit_sigma(cal, test)
        cqr = cqr_quantiles(h, NOMINAL_LEVELS)
        cal_q = cal[["well_id", "campaign_idx"]].merge(cqr, how="left")
        test_q = test[["well_id", "campaign_idx"]].merge(cqr, how="left")
        sd = cal["score"].std()
        print(f"[h={h}] cal {len(cal):,} rows, test {len(test):,} rows, σ̂ range {sigma_test.min():.2f}–{sigma_test.max():.2f} m")

        for level in NOMINAL_LEVELS:
            a = 1 - level
            methods = {}
            z = stats.norm.ppf(1 - a / 2)
            methods["Gaussian"] = (test["yhat"] - z * sd, test["yhat"] + z * sd)
            methods["Split conformal"] = static_mondrian(cal, test, [], a)
            methods["Mondrian D×S"] = static_mondrian(cal, test, ["depth_name", "season_name"], a)
            methods["Mondrian D×R"] = static_mondrian(cal, test, ["depth_name", "region"], a)
            methods["Normalised"] = static_mondrian(cal, test, [], a, sigma_cal, sigma_test)
            t_lo, t_hi = round(a / 2, 4), round(1 - a / 2, 4)
            e_lo = cal_q[f"q{t_lo}"].to_numpy() - cal["y_target"].to_numpy()
            e_hi = cal["y_target"].to_numpy() - cal_q[f"q{t_hi}"].to_numpy()
            n = len(cal)
            k = int(np.ceil((n + 1) * (1 - a)))
            e = np.sort(np.maximum(e_lo, e_hi))[min(k, n) - 1]
            methods["CQR"] = (test_q[f"q{t_lo}"].to_numpy() - e, test_q[f"q{t_hi}"].to_numpy() + e)
            methods["Mondrian D×R + recal"] = online_mondrian(cal, test, ["depth_name", "region"], a, h)
            methods["Mondrian D×R + recal + ACI"] = online_mondrian(cal, test, ["depth_name", "region"], a, h, ACI_GAMMA)
            methods["Mondrian D×R×S + recal + ACI"] = online_mondrian(
                cal, test, ["depth_name", "region", "season_name"], a, h, ACI_GAMMA)
            methods["Normalised D×R×S + recal + ACI"] = online_mondrian(
                cal, test, ["depth_name", "region", "season_name"], a, h, ACI_GAMMA, sigma_cal, sigma_test)
            for name, (lo, hi) in methods.items():
                rows += evaluate(test, np.asarray(lo, float), np.asarray(hi, float), name, level, h)
                if level == 0.8:
                    interval_store.append(pd.DataFrame({"h": h, "method": name, "well_id": test["well_id"],
                                                        "target_idx": test["target_idx"], "y": test["y_target"],
                                                        "lo": np.asarray(lo, float), "hi": np.asarray(hi, float)}))
            if level in (0.8, 0.9):
                for gamma in ACI_GAMMA_GRID:
                    lo, hi = online_mondrian(cal, test, ["depth_name", "region"], a, h, gamma)
                    ev = evaluate(test, lo, hi, "ACI", level, h)
                    for r in ev:
                        if r["group_var"] in ("All", "Depth", "Region"):
                            aci_rows.append({**r, "gamma": gamma})

        # Probabilistic scores (CRPS, PIT) for the distribution-based methods
        variants = {"Gaussian": None, "Split conformal": ([], None), "Mondrian D×S": (["depth_name", "season_name"], None),
                    "Mondrian D×R": (["depth_name", "region"], None), "Normalised": ([], (sigma_cal, sigma_test))}
        for name, spec in variants.items():
            if spec is None:
                q = test["yhat"].to_numpy()[:, None] + stats.norm.ppf(CRPS_TAUS)[None, :] * sd
                pit = stats.norm.cdf(test["score"].to_numpy() / sd)
            else:
                keys, sc = spec
                q, pit = predictive_quantiles(cal, test, keys, *(sc if sc else (None, None)))
            crps = crps_from_quantiles(test["y_target"].to_numpy(), q)
            prob_rows.append({"h": h, "method": name, "crps": float(crps.mean())})
            for gvar in ("depth_name", "region"):
                for g, idx in test.groupby(gvar).indices.items():
                    prob_rows.append({"h": h, "method": name, "group_var": gvar, "group": g, "crps": float(crps[idx].mean())})
            hist, _ = np.histogram(pit, bins=10, range=(0, 1))
            pit_rows.append({"h": h, "method": name, "pit_hist": (hist / hist.sum()).round(4).tolist()})

    res = pd.DataFrame(rows)
    grp = res["group_var"] != "All"
    res.loc[grp, "binom_p_holm"] = res[grp].groupby(["h", "method", "nominal"])["binom_p"].transform(
        lambda s: holm(s))
    res.to_csv(CALIBRATION_REPORTS_DIR / "coverage.csv", index=False)
    pd.DataFrame(prob_rows).to_csv(CALIBRATION_REPORTS_DIR / "probabilistic.csv", index=False)
    pd.DataFrame(aci_rows).to_csv(CALIBRATION_REPORTS_DIR / "aci_gamma_sensitivity.csv", index=False)
    with open(CALIBRATION_REPORTS_DIR / "pit.json", "w") as f:
        json.dump(pit_rows, f, indent=2)
    pd.concat(interval_store).to_parquet(DATA_PROCESSED_DIR / "intervals_80.parquet", index=False)

    # Exit check: worst deviation over depth and region classes at 80 % and 90 %
    chk = res[res["group_var"].isin(["Depth", "Region"]) & res["nominal"].isin([0.8, 0.9])].copy()
    chk["dev"] = (chk["coverage"] - chk["nominal"]).abs()
    worst = chk.groupby(["method", "h"])["dev"].max().unstack()
    print("\nWorst |coverage − nominal| over depth and region classes at 80 % and 90 % (points):")
    print((worst * 100).round(1).to_string())
    summary = res[(res["group_var"] == "All") & (res["nominal"] == 0.8)].pivot_table(
        index="method", columns="h", values=["coverage", "median_width"])
    print("\nOverall at 80 %:")
    print(summary.round(3).to_string())
    print(f"\nSaved reports to {CALIBRATION_REPORTS_DIR}/")


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        run_calibration()
