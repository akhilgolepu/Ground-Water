"""
Research Pipeline — Phase 2.3: Reference Models
Puts the skill-decomposition arms next to models used in prior work, on the same test rows:

  RF M0 / RF M2         Random Forest on the memory-only and memory + forcing + ENSO/IOD features
  Chronos-2 (zero-shot) pretrained time-series foundation model, water level only
  Chronos-2 + past rain the same, with rain between campaigns as a past-only covariate
  Chronos-2 + future rain  also given the rain that will fall before the target (oracle upper bound)

Chronos-2 sees each well's campaign series up to the origin (gaps left as NaN) and forecasts four
campaigns ahead; steps 1, 2 and 4 are scored. Requires `skill_predictions.parquet` from Phase 2.
"""

import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from src.research.config import DATA_PROCESSED_DIR, HORIZONS, RANDOM_SEED, SKILL_REPORTS_DIR
from src.research.skill_decomposition import ARMS, load_dataset

CHRONOS_MODEL = "amazon/chronos-2"
MAX_CONTEXT = 128  # campaigns (32 years)
PRED_STEPS = max(HORIZONS)


def random_forest_predictions() -> pd.DataFrame:
    out = []
    for h in HORIZONS:
        df = load_dataset(h)
        train = df[df["split"] == "train"]
        test = df[df["split"] == "test"].copy()
        for arm in ("M0 memory", "M2 + ENSO/IOD"):
            feats = ARMS[arm]
            rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=0.33,
                                       n_jobs=-1, random_state=RANDOM_SEED)
            rf.fit(train[feats], train["y_target"] - train["y_t"])
            test[f"RF {arm.split()[0]}"] = test["y_t"] + rf.predict(test[feats])
            print(f"[h={h}] RF {arm} fitted on {len(train):,} rows")
        out.append(test[["well_id", "campaign_idx", "RF M0", "RF M2"]].assign(h=h))
    return pd.concat(out)


def chronos_predictions(origins: pd.DataFrame) -> pd.DataFrame:
    """Forecasts PRED_STEPS campaigns from every (well, origin) in `origins` with three Chronos-2 variants."""
    import torch
    from chronos import Chronos2Pipeline

    campaigns = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    forcing = pd.read_parquet(DATA_PROCESSED_DIR / "forcing_features.parquet")[["well_id", "campaign_idx", "rain_since_prev"]]
    series = {w: g.set_index("campaign_idx")["depth_mbgl"] for w, g in campaigns.groupby("well_id")}
    rain = {w: g.set_index("campaign_idx")["rain_since_prev"] for w, g in forcing.groupby("well_id")}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = Chronos2Pipeline.from_pretrained(CHRONOS_MODEL, device_map=device)
    print(f"Chronos-2 loaded on {device}")

    def build(row, with_past: bool, with_future: bool):
        s = series[row.well_id]
        idx = np.arange(max(s.index.min(), row.campaign_idx - MAX_CONTEXT + 1), row.campaign_idx + 1)
        target = s.reindex(idx).to_numpy(dtype=float)
        item = {"target": target}
        if with_past:
            r = rain[row.well_id]
            past = r.reindex(idx).to_numpy(dtype=float)
            item["past_covariates"] = {"rain": past}
            if with_future:
                fut = r.reindex(np.arange(row.campaign_idx + 1, row.campaign_idx + 1 + PRED_STEPS)).to_numpy(dtype=float)
                item["future_covariates"] = {"rain": fut}
        return item

    rows = list(origins.itertuples(index=False))
    result = origins[["well_id", "campaign_idx"]].copy()
    variants = {"Chronos-2 zero-shot": (False, False), "Chronos-2 + past rain": (True, False),
                "Chronos-2 + future rain (oracle)": (True, True)}
    for name, (past, future) in variants.items():
        preds = []
        batch = 1024
        for i in range(0, len(rows), batch):
            inputs = [build(r, past, future) for r in rows[i:i + batch]]
            _, means = pipe.predict_quantiles(inputs, prediction_length=PRED_STEPS, quantile_levels=[0.5], batch_size=256)
            preds.append(np.stack([m.squeeze(0).cpu().numpy() for m in means]))
        arr = np.concatenate(preds)  # [n, PRED_STEPS]
        for h in HORIZONS:
            result[f"{name}|h{h}"] = arr[:, h - 1]
        print(f"  {name}: {len(rows):,} origins forecast")
    return result


def score(pred: pd.DataFrame) -> pd.DataFrame:
    """Metrics on the Phase 2 common test rows, next to the skill-decomposition arms."""
    base = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    rows = []
    for h in HORIZONS:
        b = base[(base["h"] == h) & (base["split"] == "test")].dropna(subset=["anomaly_persistence"])
        m = b.merge(pred[pred["h"] == h], on=["well_id", "campaign_idx"], how="left")
        cols = [c for c in pred.columns if c not in ("well_id", "campaign_idx", "h")]
        m = m.dropna(subset=cols)
        mse_p = np.mean((m["persistence"] - m["y_target"]) ** 2)
        for col in ["M0 memory", "M2 + ENSO/IOD", "M3 + oracle rain"] + cols:
            err = m[col] - m["y_target"]
            rows.append({"h": h, "model": col, "n": len(m), "rmse": float(np.sqrt(np.mean(err ** 2))),
                         "mae": float(np.mean(np.abs(err))),
                         "skill_vs_persistence": float(1 - np.mean(err ** 2) / mse_p)})
    return pd.DataFrame(rows)


def run_reference_models():
    print("=== Phase 2.3: Reference Models ===")
    rf = random_forest_predictions()

    base = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    test = base[(base["split"] == "test")].dropna(subset=["anomaly_persistence"])
    origins = test[["well_id", "campaign_idx"]].drop_duplicates().reset_index(drop=True)
    print(f"Chronos-2 origins: {len(origins):,}")
    ch = chronos_predictions(origins)
    long = []
    for h in HORIZONS:
        cols = {c: c.split("|")[0] for c in ch.columns if c.endswith(f"|h{h}")}
        long.append(ch[["well_id", "campaign_idx", *cols]].rename(columns=cols).assign(h=h))
    ch_long = pd.concat(long)

    pred = rf.merge(ch_long, on=["well_id", "campaign_idx", "h"], how="outer")
    pred.to_parquet(DATA_PROCESSED_DIR / "reference_predictions.parquet", index=False)
    metrics = score(pred)
    metrics.to_csv(SKILL_REPORTS_DIR / "reference_metrics.csv", index=False)
    print(metrics.pivot_table(index="model", columns="h", values="skill_vs_persistence").round(3).to_string())


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        run_reference_models()
