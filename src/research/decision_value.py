"""
Research Pipeline — Phase 4: Decision Value (RQ3)
Are the calibrated forecasts worth acting on, for whom, and at what trigger?

Events (thresholds from each well's own readings up to CAL_END_YEAR, per target season)
  E1  deeper than usual       depth > the well's 80th percentile for that season
  E2  groundwater drought      standardised groundwater index (SGI) < −1, i.e. depth above the
                               Φ(1) = 84.1 % normal-score position of the reference readings
  E3  below the suction limit  depth > 8 m bgl, for wells currently at ≤ 8 m (centrifugal pumps
                               lose suction around 7–8 m and farmers must switch to submersibles)

Probabilities come from the Phase 3 primary scheme (rolling depth × region residual pools, using
only residuals observed before each forecast), computed separately for each Phase 2 arm.

Raw probabilities are also recalibrated two ways, both added after the raw reliability diagram showed
over-confidence at mid probabilities: a static isotonic map fitted on calibration-period (2016–18)
probabilities computed leave-one-campaign-out, and a rolling isotonic map refitted for each forecast
on the 8 most recent campaigns observable at issue time.

Scores: Brier skill vs the well's own climatological frequency, ROC AUC, reliability, and
relative economic value V(α) (Richardson 2000) for cost–loss ratio α = C/L under the rule
"act when p ≥ α", plus the potential value when the trigger is chosen optimally.
CIs: well-clustered bootstrap.
"""

import json
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

from src.research.benchmark import DEPTH_CLASS_NAMES
from src.research.calibration import hierarchical_pools, lookup
from src.research.config import CAL_END_YEAR, DATA_PROCESSED_DIR, HORIZONS, RANDOM_SEED, SKILL_REPORTS_DIR
from src.research.states import station_states

DECISION_REPORTS_DIR = SKILL_REPORTS_DIR.parent / "decision"
ARMS_DV = ["M0 memory", "M1 + past forcing", "M2 + ENSO/IOD", "M3 + oracle rain"]
POOL_KEYS = ["depth_name", "region"]
SUCTION_LIMIT_M = 8.0
SGI_DROUGHT_P = float(stats.norm.cdf(1.0))  # 0.8413
ALPHAS = np.round(np.arange(0.02, 0.981, 0.02), 2)
TRIGGERS = [0.2, 0.3, 0.4, 0.5, 0.6]
N_BOOT = 500
EVENTS = {"E1": "Deeper than usual (80th percentile)", "E2": "Groundwater drought (SGI < −1)",
          "E3": f"Below the {SUCTION_LIMIT_M:.0f} m suction limit"}


# ── Thresholds and climatology ──────────────────────────────────────────────

def plotting_position_quantile(values: np.ndarray, p: float) -> float:
    """Quantile on Weibull plotting positions i/(n+1), as used for SGI normal scores."""
    x = np.sort(values)
    pos = np.arange(1, len(x) + 1) / (len(x) + 1)
    if p > pos[-1] or p < pos[0]:
        return np.nan
    return float(np.interp(p, pos, x))


def reference_thresholds(campaigns: pd.DataFrame) -> pd.DataFrame:
    """Per (well, season): E1/E2 thresholds and the climatological event frequencies for E1–E3."""
    ref = campaigns[campaigns["year"] <= CAL_END_YEAR]
    rows = []
    for (well, season), g in ref.groupby(["well_id", "season"]):
        v = g["depth_mbgl"].to_numpy()
        thr1 = float(np.quantile(v, 0.8)) if len(v) >= 4 else np.nan
        thr2 = plotting_position_quantile(v, SGI_DROUGHT_P) if len(v) >= 8 else np.nan
        rows.append({"well_id": well, "target_season": season, "thr_E1": thr1, "thr_E2": thr2,
                     "clim_E1": float(np.mean(v > thr1)) if np.isfinite(thr1) else np.nan,
                     "clim_E2": float(np.mean(v > thr2)) if np.isfinite(thr2) else np.nan,
                     "clim_E3": float(np.mean(v > SUCTION_LIMIT_M)), "n_ref": len(v)})
    return pd.DataFrame(rows)


# ── Exceedance probabilities from rolling residual pools ────────────────────

def online_exceedance(cal: pd.DataFrame, test: pd.DataFrame, h: int, thr: np.ndarray) -> np.ndarray:
    """
    P(y > thr) = share of pool residuals r with ŷ + r > thr. The pool for target campaign T holds
    calibration residuals plus test residuals with target ≤ T − h (observed at issue time).
    """
    p = np.full(len(test), np.nan)
    cells = test[POOL_KEYS].apply(tuple, axis=1).to_numpy()
    t_idx = test["target_idx"].to_numpy()
    for T in np.unique(t_idx):
        seen = test[t_idx <= T - h]
        pools = hierarchical_pools(pd.concat([cal[POOL_KEYS + ["score"]], seen[POOL_KEYS + ["score"]]]), POOL_KEYS)
        at_T = np.flatnonzero(t_idx == T)
        for cell in pd.unique(cells[at_T]):
            idx = at_T[np.array([c == cell for c in cells[at_T]])]
            r = np.sort(lookup(pools, cell))
            gap = thr[idx] - test["yhat"].to_numpy()[idx]
            p[idx] = 1 - np.searchsorted(r, gap, side="right") / len(r)
    return p


# ── Economic value ──────────────────────────────────────────────────────────

def contingency(p: np.ndarray, o: np.ndarray, trigger: float) -> tuple[int, int, int, int]:
    warn = p >= trigger
    return (int(np.sum(warn & o)), int(np.sum(warn & ~o)), int(np.sum(~warn & o)), int(np.sum(~warn & ~o)))


def relative_value(a, b, c, d, alpha):
    """
    Richardson (2000) relative economic value with loss L = 1 and cost C = α:
    V = (E_clim − E_fc) / (E_clim − E_perfect); E_fc = ((a + b)·α + c) / N, E_clim = min(α, s),
    E_perfect = s·α, s = (a + c) / N. Works elementwise on arrays.
    """
    a, b, c, d = (np.asarray(x, float) for x in (a, b, c, d))
    n = a + b + c + d
    s = (a + c) / n
    e_fc = ((a + b) * alpha + c) / n
    e_clim = np.minimum(alpha, s)
    e_perf = s * alpha
    with np.errstate(divide="ignore", invalid="ignore"):
        return (e_clim - e_fc) / (e_clim - e_perf)


def well_counts(df: pd.DataFrame, p_col: str, triggers: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-well contingency counts [wells, len(triggers), 4] for the rule p ≥ trigger."""
    wells, inv = np.unique(df["well_id"].to_numpy(), return_inverse=True)
    o = df["event"].to_numpy(bool)
    p = df[p_col].to_numpy()
    out = np.zeros((len(wells), len(triggers), 4))
    for j, t in enumerate(triggers):
        warn = p >= t
        for k, m in enumerate((warn & o, warn & ~o, ~warn & o, ~warn & ~o)):
            out[:, j, k] = np.bincount(inv, weights=m.astype(float), minlength=len(wells))
    return wells, out


def bootstrap_weights(n_wells: int, n_boot: int = N_BOOT, seed: int = RANDOM_SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.stack([np.bincount(rng.integers(0, n_wells, n_wells), minlength=n_wells) for _ in range(n_boot)]).astype(float)


# ── Plain-language advisory (template only; every number comes from the forecast record) ──

SEASON_LONG = {0: "January", 1: "May (pre-monsoon)", 2: "August (monsoon)", 3: "November (post-monsoon)"}


def advisory(well_id: str, target_idx: int, q50: float, lo80: float, hi80: float, p_e1: float, thr_e1: float,
             trigger: float) -> str:
    when = f"{SEASON_LONG[int(target_idx) % 4]} {int(target_idx) // 4}"
    action = ("Warning: plan for a deeper-than-usual water level." if p_e1 >= trigger
              else "No warning: a deeper-than-usual level is not likely enough to act on.")
    return (f"Well {well_id}, forecast for {when}: water about {q50:.1f} m below ground "
            f"(80% range {lo80:.1f}–{hi80:.1f} m). Chance it is deeper than this well's usual "
            f"level for the season ({thr_e1:.1f} m): {p_e1 * 100:.0f}%. {action}")


# ── Main ────────────────────────────────────────────────────────────────────

def loco_exceedance(cal: pd.DataFrame, thr: np.ndarray) -> np.ndarray:
    """Calibration-period probabilities with each target campaign's own residuals left out of the pool."""
    p = np.full(len(cal), np.nan)
    cells = cal[POOL_KEYS].apply(tuple, axis=1).to_numpy()
    t_idx = cal["target_idx"].to_numpy()
    for T in np.unique(t_idx):
        pools = hierarchical_pools(cal[t_idx != T][POOL_KEYS + ["score"]], POOL_KEYS)
        at_T = np.flatnonzero(t_idx == T)
        for cell in pd.unique(cells[at_T]):
            idx = at_T[np.array([c == cell for c in cells[at_T]])]
            r = np.sort(lookup(pools, cell))
            p[idx] = 1 - np.searchsorted(r, thr[idx] - cal["yhat"].to_numpy()[idx], side="right") / len(r)
    return p


ROLLING_WINDOW = 8  # campaigns (two years), fixed before the rolling variant was run


def rolling_isotonic(cal: pd.DataFrame, test: pd.DataFrame, h: int, window: int = ROLLING_WINDOW) -> np.ndarray:
    """
    For each test target campaign T, fit an isotonic map on the (p, outcome) pairs of the `window`
    most recent campaigns observable at issue time (target ≤ T − h; calibration pairs are LOCO),
    and apply it to the raw probabilities at T.
    """
    from sklearn.isotonic import IsotonicRegression

    hist = pd.concat([cal, test], ignore_index=True)
    out = np.full(len(test), np.nan)
    for T in np.unique(test["target_idx"]):
        known = hist[hist["target_idx"] <= T - h]
        recent = known[known["target_idx"] > known["target_idx"].max() - window]
        idx = np.flatnonzero(test["target_idx"].to_numpy() == T)
        if recent["o"].nunique() < 2:
            out[idx] = test["p"].to_numpy()[idx]
            continue
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(recent["p"], recent["o"])
        out[idx] = iso.predict(test["p"].to_numpy()[idx])
    return out


def event_subset(df: pd.DataFrame, ev: str) -> tuple[pd.DataFrame, np.ndarray]:
    if ev == "E3":
        sub = df[df["y_t"] <= SUCTION_LIMIT_M].reset_index(drop=True)
        return sub, np.full(len(sub), SUCTION_LIMIT_M)
    sub = df[df[f"thr_{ev}"].notna()].reset_index(drop=True)
    return sub, sub[f"thr_{ev}"].to_numpy()


def build_event_frame(h: int, thresholds: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (test row, arm, event): raw probability from the rolling pools, a recalibrated
    probability (isotonic map fitted on leave-one-campaign-out calibration-period probabilities),
    the outcome and the well's climatological probability.
    """
    from sklearn.isotonic import IsotonicRegression

    preds = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    preds = preds[(preds["h"] == h) & preds["split"].isin(["cal", "test"])].copy()
    preds["depth_name"] = preds["depth_class"].map(lambda v: DEPTH_CLASS_NAMES[int(v)])
    preds = preds.merge(thresholds, on=["well_id", "target_season"], how="left")
    cal = preds[preds["split"] == "cal"].reset_index(drop=True)
    test = preds[preds["split"] == "test"].reset_index(drop=True)
    parts = []
    for arm in ARMS_DV:
        c = cal.assign(yhat=cal[arm], score=cal["y_target"] - cal[arm])
        t = test.assign(yhat=test[arm], score=test["y_target"] - test[arm])
        for ev in EVENTS:
            c_sub, c_thr = event_subset(c, ev)
            p_cal = loco_exceedance(c_sub, c_thr)
            o_cal = c_sub["y_target"].to_numpy() > c_thr
            iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(p_cal, o_cal)
            sub, thr = event_subset(t, ev)
            prob = online_exceedance(c, sub, h, thr)
            rolling = rolling_isotonic(
                pd.DataFrame({"target_idx": c_sub["target_idx"], "p": p_cal, "o": o_cal}),
                pd.DataFrame({"target_idx": sub["target_idx"], "p": prob, "o": sub["y_target"].to_numpy() > thr}), h)
            parts.append(pd.DataFrame({
                "h": h, "arm": arm, "event_id": ev, "well_id": sub["well_id"], "target_idx": sub["target_idx"],
                "region": sub["region"], "depth_name": sub["depth_name"], "p": prob, "p_recal": iso.predict(prob),
                "p_rolling": rolling,
                "event": sub["y_target"].to_numpy() > thr, "clim": sub[f"clim_{ev}"].to_numpy(),
                "threshold": thr, "q50": sub["yhat"].to_numpy()}))
    return pd.concat(parts, ignore_index=True)


def score_group(g: pd.DataFrame, p_col: str, W: np.ndarray):
    """Brier/AUC/reliability, value curves with bootstrap draws, and the trigger table for one group."""
    o = g["event"].to_numpy(bool)
    p, clim = g[p_col].to_numpy(), g["clim"].to_numpy()
    wells, inv = np.unique(g["well_id"].to_numpy(), return_inverse=True)
    se_f = np.bincount(inv, weights=(p - o) ** 2, minlength=len(wells))
    se_c = np.bincount(inv, weights=(clim - o) ** 2, minlength=len(wells))
    bss_boot = 1 - (W @ se_f) / (W @ se_c)
    score = {"n": len(g), "n_wells": len(wells), "event_rate": float(o.mean()),
             "brier": float(np.mean((p - o) ** 2)), "brier_clim": float(np.mean((clim - o) ** 2)),
             "bss": float(1 - se_f.sum() / se_c.sum()),
             "bss_ci": [float(np.percentile(bss_boot, 2.5)), float(np.percentile(bss_boot, 97.5))],
             "roc_auc": float(roc_auc_score(o, p)), "roc_auc_clim": float(roc_auc_score(o, clim))}
    _, counts = well_counts(g, p_col, ALPHAS)
    tot = counts.sum(axis=0)
    v_rule = relative_value(*(tot[:, k] for k in range(4)), ALPHAS)
    v_boot = relative_value(*(np.einsum("bw,wtk->btk", W, counts)[:, :, k] for k in range(4)), ALPHAS[None, :])
    env = np.array([np.nanmax(relative_value(*(tot[:, k] for k in range(4)), a)) for a in ALPHAS])
    trig = []
    for t in TRIGGERS:
        a_, b_, c_, d_ = contingency(p, o, t)
        trig.append({"trigger": t, "hits": a_, "false_alarms": b_, "misses": c_, "correct_negatives": d_,
                     "warning_rate": (a_ + b_) / len(g), "hit_rate": a_ / max(a_ + c_, 1),
                     "false_alarm_rate": b_ / max(b_ + d_, 1), "false_alarm_ratio": b_ / max(a_ + b_, 1),
                     "value_at_alpha_eq_trigger": float(relative_value(a_, b_, c_, d_, t))})
    bins = np.minimum((p * 10).astype(int), 9)
    rel = [{"bin": b, "p_mean": float(p[bins == b].mean()), "obs_freq": float(o[bins == b].mean()),
            "n": int((bins == b).sum())} for b in range(10) if (bins == b).any()]
    return score, v_rule, v_boot, env, trig, rel


VALUE_PAIRS = [("M0 memory", "M2 + ENSO/IOD"), ("M2 + ENSO/IOD", "M3 + oracle rain")]
PROB_VARIANTS = {"p": "raw", "p_recal": "static isotonic", "p_rolling": "rolling isotonic"}
PRIMARY_P = "p_rolling"  # best-calibrated variant; used for the case study, triggers and advisories


def run_decision_value():
    print("=== Phase 4: Decision Value ===")
    DECISION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    campaigns = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    thresholds = reference_thresholds(campaigns)
    ev = pd.concat([build_event_frame(h, thresholds) for h in HORIZONS], ignore_index=True).dropna(subset=["p", "clim"])
    ev = ev.merge(station_states(), on="well_id", how="left")
    ev.to_parquet(DATA_PROCESSED_DIR / "event_probabilities.parquet", index=False)

    scores, value_rows, trigger_rows, rel_rows, diff_rows = [], [], [], [], []
    for (h, ev_id), g_ev in ev.groupby(["h", "event_id"]):
        n_wells = g_ev["well_id"].nunique()
        W = bootstrap_weights(n_wells)  # same draws for every arm → paired differences
        for p_col, variant in PROB_VARIANTS.items():
            boots = {}
            for arm, g in g_ev.groupby("arm"):
                score, v_rule, v_boot, env, trig, rel = score_group(g, p_col, W)
                boots[arm] = v_boot
                key = {"h": h, "event_id": ev_id, "arm": arm, "probability": variant}
                scores.append({**key, **score})
                for j, a in enumerate(ALPHAS):
                    value_rows.append({**key, "alpha": float(a), "value": float(v_rule[j]),
                                       "value_lo": float(np.nanpercentile(v_boot[:, j], 2.5)),
                                       "value_hi": float(np.nanpercentile(v_boot[:, j], 97.5)),
                                       "value_envelope": float(env[j])})
                trigger_rows += [{**key, **t} for t in trig]
                rel_rows += [{**key, **r} for r in rel]
            for a, b in VALUE_PAIRS:
                d = boots[b] - boots[a]
                for j, alpha in enumerate(ALPHAS):
                    if alpha in (0.1, 0.2, 0.3, 0.4, 0.5):
                        diff_rows.append({"h": h, "event_id": ev_id, "probability": variant, "comparison": f"{b} − {a}",
                                          "alpha": float(alpha), "diff_median": float(np.nanmedian(d[:, j])),
                                          "diff_lo": float(np.nanpercentile(d[:, j], 2.5)),
                                          "diff_hi": float(np.nanpercentile(d[:, j], 97.5))})

    pd.DataFrame(scores).to_json(DECISION_REPORTS_DIR / "scores.json", orient="records", indent=2)
    value_df = pd.DataFrame(value_rows)
    value_df.to_csv(DECISION_REPORTS_DIR / "value_curves.csv", index=False)
    pd.DataFrame(trigger_rows).to_csv(DECISION_REPORTS_DIR / "triggers.csv", index=False)
    pd.DataFrame(rel_rows).to_csv(DECISION_REPORTS_DIR / "reliability.csv", index=False)
    diffs = pd.DataFrame(diff_rows)
    diffs.to_csv(DECISION_REPORTS_DIR / "value_differences.csv", index=False)
    case_study(ev).to_csv(DECISION_REPORTS_DIR / "case_study_2023.csv", index=False)
    with open(DECISION_REPORTS_DIR / "advisory_examples.json", "w") as f:
        json.dump(advisory_examples(ev), f, indent=2, ensure_ascii=False)

    sc = pd.DataFrame(scores)
    print("\nBrier skill vs each well's own climatology, by probability variant:")
    print(sc.pivot_table(index=["event_id", "arm"], columns=["h", "probability"], values="bss").round(3).to_string())
    vmax = value_df.groupby(["h", "event_id", "arm", "probability"])["value"].max().unstack(["h", "probability"])
    print("\nMaximum relative economic value under the rule 'act when p ≥ C/L':")
    print(vmax.round(3).to_string())
    print(f"\nPaired value differences ({PROB_VARIANTS[PRIMARY_P]} probabilities), 95% CI:")
    d = diffs[diffs["probability"] == PROB_VARIANTS[PRIMARY_P]]
    for r in d.itertuples():
        print(f"  h={r.h} {r.event_id} α={r.alpha:.1f} {r.comparison:<34} {r.diff_median:+.3f} [{r.diff_lo:+.3f}, {r.diff_hi:+.3f}]")
    print(f"\nSaved reports to {DECISION_REPORTS_DIR}/")


WATER_YEARS = {  # targets Aug → May; JJAS departures from docs/07
    "2022–23 (wet, JJAS +9 %)": [2022 * 4 + 2, 2022 * 4 + 3, 2023 * 4 + 0, 2023 * 4 + 1],
    "2023–24 (dry, JJAS −5 %)": [2023 * 4 + 2, 2023 * 4 + 3, 2024 * 4 + 0, 2024 * 4 + 1],
}


def case_study(ev: pd.DataFrame, trigger: float = 0.3) -> pd.DataFrame:
    """
    Warnings for event E1 over the 2023–24 dry water year vs the 2022–23 wet one, Atal Bhujal states
    vs the rest (primary probabilities, trigger 0.3). District-level selection awaits the official list.
    """
    rows = []
    for year, targets in WATER_YEARS.items():
        g = ev[ev["target_idx"].isin(targets) & (ev["event_id"] == "E1")]
        for (h, arm), ga in g.groupby(["h", "arm"]):
            for label, gs in [("Atal Bhujal states", ga[ga["atal_bhujal_state"] == True]),  # noqa: E712
                              ("Other states", ga[ga["atal_bhujal_state"] == False])]:  # noqa: E712
                if len(gs) < 30:
                    continue
                a, b, c, d = contingency(gs[PRIMARY_P].to_numpy(), gs["event"].to_numpy(bool), trigger)
                rows.append({"water_year": year, "h": h, "arm": arm, "area": label, "n": len(gs),
                             "n_wells": gs["well_id"].nunique(), "event_rate": (a + c) / len(gs),
                             "mean_p": float(gs[PRIMARY_P].mean()), "mean_p_raw": float(gs["p"].mean()),
                             "warning_rate": (a + b) / len(gs),
                             "hits": a, "misses": c, "false_alarms": b,
                             "hit_rate": a / max(a + c, 1), "false_alarm_ratio": b / max(a + b, 1)})
    return pd.DataFrame(rows)


def advisory_examples(ev: pd.DataFrame, trigger: float = 0.3, n: int = 6) -> list[dict]:
    """Template advisories for a few M2 test forecasts, with the source record next to each text."""
    iv = pd.read_parquet(DATA_PROCESSED_DIR / "intervals_80.parquet")
    iv = iv[(iv["method"] == "Mondrian D×R + recal + ACI") & (iv["h"] == 2)]
    g = ev[(ev["arm"] == "M2 + ENSO/IOD") & (ev["event_id"] == "E1") & (ev["h"] == 2)]
    g = g.merge(iv[["well_id", "target_idx", "lo", "hi"]], on=["well_id", "target_idx"])
    picks = pd.concat([g[g[PRIMARY_P] >= 0.7].sample(n // 2, random_state=RANDOM_SEED),
                       g[g[PRIMARY_P] < 0.1].sample(n - n // 2, random_state=RANDOM_SEED)])
    out = []
    for r in picks.itertuples():
        rec = {"well_id": r.well_id, "target_idx": int(r.target_idx), "q50": round(float(r.q50), 2),
               "lo80": round(float(r.lo), 2), "hi80": round(float(r.hi), 2), "p_e1": round(float(getattr(r, PRIMARY_P)), 3),
               "thr_e1": round(float(r.threshold), 2), "trigger": trigger, "observed_event": bool(r.event)}
        rec["text"] = advisory(r.well_id, r.target_idx, r.q50, r.lo, r.hi, getattr(r, PRIMARY_P), r.threshold, trigger)
        out.append(rec)
    return out


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        run_decision_value()
