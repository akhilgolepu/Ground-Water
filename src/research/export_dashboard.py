"""
Research Pipeline — Phase 5.1–5.3: Dashboard export.

Writes every number the dashboard shows into frontend/public/data/, each file naming the report it
was taken from, so anything on screen can be traced to `reports/` (Phase 5 exit check).

  summary.json      network counts, trends, headline results, sources
  stations.json     one record per well: location, state, region, trend, operational warning probabilities
  wells/<b>.json    per-well detail, 64 buckets (bucket = sum of character codes mod 64): observed series,
                    2019–25 test forecasts of the memory-only (M0) and forcing (M2) models, per-well errors,
                    operational forecasts with 80 % intervals, warning probabilities and advisories
  skill.json        Phase 2 — skill by arm with CIs, gains by stratum, reference models, robustness
  calibration.json  Phase 3 — conditional coverage by method, drift series
  decision.json     Phase 4 — value curves, a fine trigger table, case study

Operational forecasts use the evaluated Phase 2 models unchanged (retrained here with the tuned
settings and checked to reproduce the Phase 2 test predictions), intervals from the depth × region
residual pools of every residual observed so far (Phase 3), and probabilities recalibrated with the
isotonic map of the 8 most recent observed campaigns (Phase 4). If India-WRIS updates exist
(src/research/wris_refresh.py), matching wells are extended with them before forecasting.
"""

import json
import warnings

import numpy as np
import pandas as pd
import xgboost as xgb

from src.research.benchmark import DEPTH_CLASS_NAMES, premonsoon_trends
from src.research.calibration import CALIBRATION_REPORTS_DIR, hierarchical_pools, lookup, signed_offsets
from src.research.config import DATA_PROCESSED_DIR, FRONTEND_DATA_DIR, HORIZONS, SKILL_REPORTS_DIR
from src.research.decision_value import (
    ALPHAS,
    DECISION_REPORTS_DIR,
    ROLLING_WINDOW,
    SUCTION_LIMIT_M,
    advisory,
    reference_thresholds,
    relative_value,
)
from src.research.ingest import build_campaign_series, remove_outliers
from src.research.skill_decomposition import ARMS, BASE_PARAMS, load_dataset
from src.research.states import station_states

ARMS_EXPORT = {"M0 memory": "m0", "M2 + ENSO/IOD": "m2"}
N_BUCKETS = 64
TRIGGER_GRID = ALPHAS  # same grid as the value curves, so every trigger has a value CI
SEASONS = ["Jan", "May", "Aug", "Nov"]
PRIMARY_INTERVAL = "Mondrian D×R + recal + ACI"


def label(idx: int) -> str:
    return f"{int(idx) // 4}-{SEASONS[int(idx) % 4]}"


def bucket(well_id: str) -> int:
    return sum(ord(c) for c in well_id) % N_BUCKETS


def r(x, n=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) or pd.isna(x) else round(float(x), n)


# ── Models ──────────────────────────────────────────────────────────────────

def fit_models(h: int) -> dict:
    """Refit M0 and M2 with the Phase 2 tuned settings and check they reproduce the Phase 2 test predictions."""
    with open(SKILL_REPORTS_DIR / "tuning.json") as f:
        tuning = json.load(f)[str(h)]
    df = load_dataset(h)
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]
    ref = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    ref = ref[(ref["h"] == h) & (ref["split"] == "test")].set_index(["well_id", "campaign_idx"])
    models = {}
    for arm in ARMS_EXPORT:
        t = tuning[arm]
        m = xgb.XGBRegressor(n_estimators=t["n_trees_final"], max_depth=t["best"]["max_depth"],
                             min_child_weight=t["best"]["min_child_weight"], **BASE_PARAMS)
        m.fit(train[ARMS[arm]], train["y_target"] - train["y_t"])
        pred = test["y_t"].to_numpy() + m.predict(test[ARMS[arm]])
        gap = np.abs(pred - ref.loc[list(zip(test["well_id"], test["campaign_idx"])), arm].to_numpy()).max()
        if gap > 1e-3:
            raise RuntimeError(f"Refitted {arm} (h={h}) differs from Phase 2 by {gap:.4f} m")
        models[arm] = m
    return models


# ── Operational data (snapshot + optional India-WRIS updates) ───────────────

def operational_campaigns() -> tuple[pd.DataFrame, dict]:
    campaigns = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    path = DATA_PROCESSED_DIR / "wris_manual_updates.parquet"
    info = {"wris_used": False}
    if not path.exists():
        return campaigns, info
    upd = pd.read_parquet(path)
    upd = upd[upd["in_research_snapshot"]]
    obs = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_observations_clean.parquet")
    obs = obs[obs["well_id"].isin(upd["well_id"].unique())]
    # Same sign rule as ingest: a station whose readings are mostly negative reports level, not depth
    neg = upd.groupby("well_id")["water_level_raw"].transform(lambda x: (x < 0).mean() > 0.5)
    upd = upd.assign(depth_mbgl=np.where(neg, -upd["water_level_raw"], upd["water_level_raw"]))
    new = upd[["well_id", "timestamp", "depth_mbgl"]]
    combined = pd.concat([obs[["well_id", "timestamp", "depth_mbgl"]], new], ignore_index=True)
    combined = combined.drop_duplicates(["well_id", "timestamp"])
    combined, _ = remove_outliers(combined)
    extra = build_campaign_series(combined)
    last = campaigns.groupby("well_id")["campaign_idx"].max()
    extra = extra[extra["campaign_idx"] > extra["well_id"].map(last).fillna(-1)]
    info = {"wris_used": True, "wells_extended": int(extra["well_id"].nunique()),
            "campaigns_added": int(len(extra)), "latest_campaign": label(extra["campaign_idx"].max()) if len(extra) else None}
    return pd.concat([campaigns, extra[campaigns.columns]], ignore_index=True), info


def operational_forcing(campaigns: pd.DataFrame) -> pd.DataFrame:
    """Forcing table extended to any origin campaign the snapshot table lacks (WRIS-extended wells)."""
    from src.research.forcing_features import compute_origin_features, load_forcing_inputs

    forcing = pd.read_parquet(DATA_PROCESSED_DIR / "forcing_features.parquet")
    have = set(zip(forcing["well_id"], forcing["campaign_idx"]))
    keys = campaigns[["well_id", "campaign_idx"]].drop_duplicates()
    missing = keys[[k not in have for k in zip(keys["well_id"], keys["campaign_idx"])]]
    if missing.empty:
        return forcing
    inp = load_forcing_inputs(pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet"), verbose=False)
    extra = compute_origin_features(missing, inp["well_row"], inp["rain"], inp["tmean"], inp["well_row_t"], inp["indices"])
    return pd.concat([forcing, extra], ignore_index=True)


def operational_forecasts(campaigns, forcing, models, h, event_probs) -> pd.DataFrame:
    """Forecast from each well's latest observed campaign (origins from 2019 on)."""
    df = load_dataset(h, campaigns=campaigns, keep_unlabelled=True, forcing=forcing)
    latest = df.sort_values("campaign_idx").groupby("well_id").tail(1)
    latest = latest[latest["year"] >= 2019].copy()
    latest["depth_name"] = latest["depth_class"].map(lambda v: DEPTH_CLASS_NAMES[int(v)])
    for arm, key in ARMS_EXPORT.items():
        latest[key] = latest["y_t"] + models[arm].predict(latest[ARMS[arm]])

    # 80 % interval from every M2 residual observed so far (calibration + test), depth × region pools
    preds = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    preds = preds[(preds["h"] == h) & preds["split"].isin(["cal", "test"])].copy()
    preds["depth_name"] = preds["depth_class"].map(lambda v: DEPTH_CLASS_NAMES[int(v)])
    preds["score"] = preds["y_target"] - preds["M2 + ENSO/IOD"]
    pools = hierarchical_pools(preds[["depth_name", "region", "score"]], ["depth_name", "region"])
    cells = list(zip(latest["depth_name"], latest["region"]))
    offs = [signed_offsets(lookup(pools, c), 0.2) for c in cells]
    latest["lo"] = latest["m2"].to_numpy() + np.array([o[0] for o in offs])
    latest["hi"] = latest["m2"].to_numpy() + np.array([o[1] for o in offs])

    # Warning probabilities: raw from the pools, then the rolling isotonic map of the latest window
    from sklearn.isotonic import IsotonicRegression

    thr = reference_thresholds(pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet"))
    latest = latest.merge(thr[["well_id", "target_season", "thr_E1"]], on=["well_id", "target_season"], how="left")
    for ev, thr_col in (("E1", "thr_E1"), ("E3", None)):
        g = event_probs[(event_probs["h"] == h) & (event_probs["event_id"] == ev) & (event_probs["arm"] == "M2 + ENSO/IOD")]
        recent = g[g["target_idx"] > g["target_idx"].max() - ROLLING_WINDOW]
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(recent["p"], recent["event"])
        threshold = latest[thr_col].to_numpy() if thr_col else np.full(len(latest), SUCTION_LIMIT_M)
        p_raw = np.array([1 - np.searchsorted(np.sort(lookup(pools, c)), t - y, side="right") / len(lookup(pools, c))
                          if np.isfinite(t) else np.nan for c, t, y in zip(cells, threshold, latest["m2"])])
        p = iso.predict(np.nan_to_num(p_raw))
        p[~np.isfinite(p_raw)] = np.nan
        if ev == "E3":
            p[latest["y_t"].to_numpy() > SUCTION_LIMIT_M] = np.nan  # E3 applies to wells currently at ≤ 8 m
        latest[f"p_{ev}"] = p
    return latest


# ── Per-well detail ─────────────────────────────────────────────────────────

def well_details(campaigns, ops: dict[int, pd.DataFrame]) -> dict[str, dict]:
    preds = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    test = preds[preds["split"] == "test"]
    iv = pd.read_parquet(DATA_PROCESSED_DIR / "intervals_80.parquet")
    iv = iv[(iv["method"] == PRIMARY_INTERVAL) & (iv["h"] == 1)].set_index(["well_id", "target_idx"])
    snapshot_last = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet").groupby("well_id")["campaign_idx"].max()

    out: dict[str, dict] = {}
    for well, g in campaigns.sort_values("campaign_idx").groupby("well_id"):
        last_snap = snapshot_last.get(well, np.inf)
        out[well] = {"obs": [[label(i), r(v), 1 if i > last_snap else 0] for i, v in zip(g["campaign_idx"], g["depth_mbgl"])]}
    t1 = test[test["h"] == 1].sort_values("target_idx")
    for well, g in t1.groupby("well_id"):
        rows = []
        for t_idx, m0, m2 in zip(g["target_idx"], g["M0 memory"], g["M2 + ENSO/IOD"]):
            key = (well, t_idx)
            lo, hi = (iv.at[key, "lo"], iv.at[key, "hi"]) if key in iv.index else (np.nan, np.nan)
            rows.append([label(t_idx), r(m0), r(m2), r(lo), r(hi)])
        out.setdefault(well, {"obs": []})["test"] = rows  # [target, M0, M2, lo80, hi80]
    for well, g in test.groupby("well_id"):
        err = {}
        for h, gh in g.groupby("h"):
            if len(gh) >= 3:
                err[str(h)] = {"n": len(gh), "m0": r(np.mean(np.abs(gh["M0 memory"] - gh["y_target"]))),
                               "m2": r(np.mean(np.abs(gh["M2 + ENSO/IOD"] - gh["y_target"])))}
        if err:
            out.setdefault(well, {"obs": []})["mae"] = err
    for h, latest in ops.items():
        for row in latest.itertuples():
            text = None
            if pd.notna(row.p_E1) and pd.notna(row.thr_E1):
                text = advisory(row.well_id, row.target_idx, row.m2, row.lo, row.hi, row.p_E1, row.thr_E1, 0.3)
            out.setdefault(row.well_id, {"obs": []}).setdefault("ops", {})[str(h)] = {
                "origin": label(row.campaign_idx), "target": label(row.target_idx), "now": r(row.y_t),
                "m0": r(row.m0), "m2": r(row.m2), "lo": r(row.lo), "hi": r(row.hi),
                "thrE1": r(row.thr_E1), "pE1": r(row.p_E1, 3), "pE3": r(row.p_E3, 3), "advisory": text}
    return out


# ── Report summaries ────────────────────────────────────────────────────────

def skill_payload() -> dict:
    boot = json.load(open(SKILL_REPORTS_DIR / "bootstrap.json"))
    strata = pd.read_csv(SKILL_REPORTS_DIR / "strata.csv")
    dm = pd.read_csv(SKILL_REPORTS_DIR / "diebold_mariano.csv")
    ref = pd.read_csv(SKILL_REPORTS_DIR / "reference_metrics.csv")
    rob = pd.read_csv(SKILL_REPORTS_DIR / "robustness.csv")
    metrics = pd.read_csv(SKILL_REPORTS_DIR / "metrics.csv")
    return {
        "source": "reports/skill/{bootstrap.json,metrics.csv,strata.csv,diebold_mariano.csv,reference_metrics.csv,robustness.csv}",
        "skill": [{"h": b["h"], "arm": b["model"], "skill": r(b["estimate"], 3), "lo": r(b["ci"][0], 3), "hi": r(b["ci"][1], 3)}
                  for b in boot if b["stat"] == "skill_vs_persistence"],
        "metrics": metrics[["h", "model", "n", "n_wells", "rmse", "mae", "nse_median"]].round(3).to_dict("records"),
        "gains": dm[["h", "a", "b", "mse_reduction", "mae_reduction", "campaigns_b_better", "campaigns", "sign_p_value"]]
                 .round(4).to_dict("records"),
        "strata": strata[strata["arm"].isin(["M1 + past forcing", "M2 + ENSO/IOD", "M3 + oracle rain"])]
                  [["h", "stratum", "value", "arm", "n", "mse_reduction_vs_M0"]].round(4).to_dict("records"),
        "reference": ref.round(3).to_dict("records"),
        "robustness": rob[["setting", "h", "a", "b", "mse_reduction", "mae_reduction", "campaigns_b_better", "campaigns"]]
                      .round(4).to_dict("records"),
    }


def calibration_payload() -> dict:
    cov = pd.read_csv(CALIBRATION_REPORTS_DIR / "coverage.csv")
    keep = ["Split conformal", "Mondrian D×R", "Mondrian D×R + recal + ACI", "Normalised D×R×S + recal + ACI", "CQR"]
    cov = cov[cov["method"].isin(keep) & cov["nominal"].isin([0.8, 0.9])]
    preds = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    preds = preds[preds["split"].isin(["cal", "test"])].copy()
    preds["year"] = preds["target_idx"] // 4
    preds["r"] = preds["y_target"] - preds["M2 + ENSO/IOD"]
    drift = preds[preds["year"] <= 2024].groupby(["h", "year"])["r"].agg(["median", "size"]).reset_index()
    jjas = json.load(open(DATA_PROCESSED_DIR.parent.parent / "reports" / "forcing" / "sanity.json"))["all_india_jjas_mm"]
    base = np.mean([v for y, v in jjas.items() if 1994 <= int(y) <= 2015])
    return {
        "source": "reports/calibration/coverage.csv; drift from data/processed/skill_predictions.parquet; JJAS from reports/forcing/sanity.json",
        "coverage": cov[["h", "method", "nominal", "group_var", "group", "n", "coverage", "median_width", "winkler"]]
                    .round(4).to_dict("records"),
        "drift": drift.rename(columns={"median": "median_residual", "size": "n"}).round(3).to_dict("records"),
        "jjas_anomaly_pct": {int(y): r((v / base - 1) * 100, 1) for y, v in jjas.items() if int(y) >= 2014},
    }


def decision_payload(event_probs: pd.DataFrame) -> dict:
    v = pd.read_csv(DECISION_REPORTS_DIR / "value_curves.csv")
    v = v[(v["probability"] == "rolling isotonic") & v["arm"].isin(["M0 memory", "M2 + ENSO/IOD", "M3 + oracle rain"])]
    g = event_probs[event_probs["arm"] == "M2 + ENSO/IOD"]
    trig = []
    for (h, ev), gg in g.groupby(["h", "event_id"]):
        o = gg["event"].to_numpy(bool)
        p = gg["p_rolling"].to_numpy()
        for t in TRIGGER_GRID:
            w = p >= t
            a, b, c, d = int((w & o).sum()), int((w & ~o).sum()), int((~w & o).sum()), int((~w & ~o).sum())
            trig.append({"h": int(h), "event": ev, "trigger": float(t), "warning_rate": r(w.mean(), 4),
                         "hit_rate": r(a / max(a + c, 1), 4), "false_alarm_rate": r(b / max(b + d, 1), 4),
                         "false_alarm_ratio": r(b / max(a + b, 1), 4), "value": r(relative_value(a, b, c, d, t), 4),
                         "n": len(gg)})
    case = pd.read_csv(DECISION_REPORTS_DIR / "case_study_2023.csv")
    scores = pd.read_json(DECISION_REPORTS_DIR / "scores.json")
    scores = scores[scores["probability"] == "rolling isotonic"]
    return {
        "source": "reports/decision/{value_curves.csv,scores.json,case_study_2023.csv}; trigger table from data/processed/event_probabilities.parquet",
        "value": v[["h", "event_id", "arm", "alpha", "value", "value_lo", "value_hi"]].round(4).to_dict("records"),
        "triggers": trig,
        "scores": scores[["h", "event_id", "arm", "bss", "roc_auc", "event_rate", "n"]].round(4).to_dict("records"),
        "case_study": case[case["arm"] == "M2 + ENSO/IOD"].round(4).to_dict("records"),
    }


# ── Driver ──────────────────────────────────────────────────────────────────

def run_export():
    print("=== Phase 5: Dashboard export ===")
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    catalog = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")
    campaigns, wris = operational_campaigns()
    print(f"India-WRIS updates: {wris}")
    forcing = operational_forcing(campaigns) if wris["wris_used"] else None
    event_probs = pd.read_parquet(DATA_PROCESSED_DIR / "event_probabilities.parquet")

    ops = {}
    for h in HORIZONS:
        models = fit_models(h)
        ops[h] = operational_forecasts(campaigns, forcing, models, h, event_probs)
        print(f"[h={h}] models reproduce Phase 2; {len(ops[h]):,} operational forecasts "
              f"(origins {label(ops[h]['campaign_idx'].min())} → {label(ops[h]['campaign_idx'].max())})")

    trends = premonsoon_trends(pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")).set_index("well_id")
    states = station_states().set_index("well_id")
    from src.research.regions import assign_region
    regions = pd.Series(assign_region(catalog["latitude"], catalog["longitude"]).to_numpy(), index=catalog["well_id"])
    stations = []
    for row in catalog.itertuples():
        rec = {"id": row.well_id, "lat": round(row.latitude, 4), "lon": round(row.longitude, 4), "net": row.network,
               "n": int(row.n_obs), "yrs": round(float(row.record_years), 1), "first": row.first_obs.strftime("%Y-%m"),
               "last": row.last_obs.strftime("%Y-%m"), "median": round(float(row.median_depth_m), 2),
               "state": states.at[row.well_id, "state"] if row.well_id in states.index else None,
               "region": regions.get(row.well_id), "b": bucket(row.well_id)}
        if row.well_id in trends.index:
            rec["trend"] = r(trends.at[row.well_id, "trend_m_per_yr"], 3)
            rec["trendP"] = r(trends.at[row.well_id, "trend_p"], 4)
        o = {}
        for h, latest in ops.items():
            hit = latest[latest["well_id"] == row.well_id]
            if len(hit):
                x = hit.iloc[0]
                o[str(h)] = {"t": label(x["target_idx"]), "e1": r(x["p_E1"], 3), "e3": r(x["p_E3"], 3)}
        if o:
            rec["ops"] = o
        stations.append(rec)

    details = well_details(campaigns, ops)
    wells_dir = FRONTEND_DATA_DIR / "wells"
    wells_dir.mkdir(exist_ok=True)
    buckets: dict[int, dict] = {}
    for well, d in details.items():
        buckets.setdefault(bucket(well), {})[well] = d
    for b in range(N_BUCKETS):
        with open(wells_dir / f"{b}.json", "w") as f:
            json.dump(buckets.get(b, {}), f, separators=(",", ":"))

    skill, calib, decision = skill_payload(), calibration_payload(), decision_payload(event_probs)
    with_trend = [s for s in stations if "trend" in s and s["trend"] is not None]
    ops_all = pd.concat(ops.values())
    summary = {
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "n_stations": len(catalog), "n_manual": int((catalog["network"] == "manual").sum()),
        "n_dwlr": int((catalog["network"] == "DWLR").sum()), "n_obs": int(catalog["n_obs"].sum()),
        "first_year": int(catalog["first_obs"].min().year), "last_year": int(catalog["last_obs"].max().year),
        "n_campaign_values": int(len(campaigns)),
        "trend": {"n_wells": len(with_trend),
                  "sig_deepening": sum(1 for s in with_trend if s["trend"] > 0 and s["trendP"] < 0.05),
                  "sig_rising": sum(1 for s in with_trend if s["trend"] < 0 and s["trendP"] < 0.05)},
        "operational": {"n_wells": int(ops[1]["well_id"].nunique()),
                        "latest_origin": label(ops_all["campaign_idx"].max()),
                        "origin_years": {str(k): int(v) for k, v in (ops[1]["campaign_idx"] // 4).value_counts().sort_index().items()}},
        "wris": wris,
        "sources": {"stations": "data/processed/station_catalog.parquet, gwl_campaigns.parquet, station_states.parquet",
                    "skill": skill["source"], "calibration": calib["source"], "decision": decision["source"],
                    "wris": "reports/wris_refresh.json"},
    }

    def dump(name, obj):
        with open(FRONTEND_DATA_DIR / name, "w") as f:
            json.dump(obj, f, separators=(",", ":"), default=lambda x: None)

    dump("summary.json", summary)
    dump("stations.json", stations)
    dump("skill.json", skill)
    dump("calibration.json", calib)
    dump("decision.json", decision)
    for stale in ("benchmark.json", "series.json"):
        (FRONTEND_DATA_DIR / stale).unlink(missing_ok=True)
    print(f"Exported {len(stations):,} stations, {len(details):,} well records in {N_BUCKETS} buckets to {FRONTEND_DATA_DIR}/")


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        run_export()
