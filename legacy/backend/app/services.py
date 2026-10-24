"""Data loaders, TFT inference, XAI aggregation, and policy simulation."""

from __future__ import annotations

import sys
from datetime import datetime
from functools import lru_cache
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from app.config import (
    DEFAULT_FORECAST_HORIZON_MONTHS,
    EXCLUDE_FEATURE_COLS,
    FEATURE_MATRIX_CSV,
    FEATURE_MATRIX_PARQUET,
    HISTORY_MONTHS_IN_FORECAST,
    PROJECT_ROOT,
    SCALER_PATH,
    SHAP_IMPORTANCE_CSV,
    TARGET_COL,
    TFT_CHECKPOINT,
    VSN_IMPORTANCE_CSV,
)
from app.schemas import (
    FeatureImportance,
    ForecastPoint,
    SimulationRequest,
    SimulationResponse,
    WellOverview,
    XAIResponse,
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _format_feature_name(raw: str) -> str:
    return raw.replace("_", " ").title()


def _risk_level(current_depth_m: float, predicted_depth_m: float) -> str:
    delta = predicted_depth_m - current_depth_m
    if delta >= 1.5 or predicted_depth_m > 18.0:
        return "Critical"
    if delta >= 0.5:
        return "Moderate"
    return "Stable"


def _mock_wells() -> list[WellOverview]:
    now = datetime.utcnow().strftime("%Y-%m-%d")
    return [
        WellOverview(
            well_id="WELL_001",
            latitude=8.2486,
            longitude=77.3083,
            current_depth_m=48.2,
            predicted_depth_m=51.0,
            risk_level="Critical",
            last_updated=now,
        ),
        WellOverview(
            well_id="WELL_002",
            latitude=8.2500,
            longitude=77.5167,
            current_depth_m=32.5,
            predicted_depth_m=33.2,
            risk_level="Moderate",
            last_updated=now,
        ),
        WellOverview(
            well_id="WELL_003",
            latitude=8.2583,
            longitude=77.4528,
            current_depth_m=18.7,
            predicted_depth_m=18.1,
            risk_level="Stable",
            last_updated=now,
        ),
    ]


@lru_cache(maxsize=1)
def _load_feature_matrix() -> Optional[pd.DataFrame]:
    if FEATURE_MATRIX_PARQUET.exists():
        df = pd.read_parquet(FEATURE_MATRIX_PARQUET)
    elif FEATURE_MATRIX_CSV.exists():
        df = pd.read_csv(FEATURE_MATRIX_CSV, low_memory=False)
    else:
        return None

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["well_id"] = df["well_id"].astype(str)
    return df.sort_values(["well_id", "timestamp"]).reset_index(drop=True)


def _feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in EXCLUDE_FEATURE_COLS]


class _InferenceEngine:
    """Lazy-loaded TFT + scaler singleton."""

    def __init__(self) -> None:
        self._torch = None
        self._device = None
        self._model = None
        self._scaler = None
        self._feature_cols: Optional[list[str]] = None
        self._ready = False
        self._init_attempted = False

    def _torch_module(self):
        if self._torch is None:
            import torch as torch_mod

            self._torch = torch_mod
            self._device = torch_mod.device(
                "cuda" if torch_mod.cuda.is_available() else "cpu"
            )
        return self._torch

    def _initialize(self, feature_cols: list[str]) -> None:
        if self._init_attempted:
            return
        self._init_attempted = True
        self._feature_cols = feature_cols

        if not TFT_CHECKPOINT.exists() or not SCALER_PATH.exists():
            return

        try:
            from src.models.tft_model import TemporalFusionTransformer

            torch = self._torch_module()
            self._scaler = joblib.load(SCALER_PATH)
            self._model = TemporalFusionTransformer(
                num_features=len(feature_cols),
                hidden_dim=64,
            ).to(self._device)
            try:
                state = torch.load(
                    TFT_CHECKPOINT, map_location=self._device, weights_only=True
                )
            except TypeError:
                state = torch.load(TFT_CHECKPOINT, map_location=self._device)
            self._model.load_state_dict(state)
            self._model.eval()
            self._ready = True
        except Exception:
            self._model = None
            self._scaler = None
            self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def predict_quantiles(self, row: pd.Series, feature_cols: list[str]) -> tuple[float, float, float]:
        batch = self.predict_quantiles_batch(row.to_frame().T, feature_cols)
        return batch[0]

    def predict_quantiles_batch(
        self, rows: pd.DataFrame, feature_cols: list[str]
    ) -> list[tuple[float, float, float]]:
        self._initialize(feature_cols)
        n = len(rows)
        if n == 0:
            return []

        currents = rows[TARGET_COL].astype(float).values
        fallback_std = pd.to_numeric(
            rows.get("depth_to_water_m_roll_std_12", pd.Series([0.5] * n)),
            errors="coerce",
        ).fillna(0.5).to_numpy(dtype=float)

        if not self._ready or self._model is None or self._scaler is None:
            out: list[tuple[float, float, float]] = []
            for i in range(n):
                std = max(float(fallback_std[i]), 0.25)
                q50 = float(currents[i])
                out.append((q50 - 1.28 * std, q50, q50 + 1.28 * std))
            return out

        torch = self._torch_module()
        x = rows[feature_cols].fillna(0)
        x_scaled = self._scaler.transform(x)
        tensor = torch.tensor(x_scaled, dtype=torch.float32, device=self._device)

        with torch.no_grad():
            preds, _ = self._model(tensor)
            preds_np = preds.cpu().numpy()

        results: list[tuple[float, float, float]] = []
        for i in range(n):
            q10, q50, q90 = float(preds_np[i, 0]), float(preds_np[i, 1]), float(preds_np[i, 2])
            if q10 > q90:
                q10, q90 = q90, q10
            results.append((q10, q50, q90))
        return results


_ENGINE = _InferenceEngine()


def _month_label(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m")


def _well_history(df: pd.DataFrame, well_id: str) -> pd.DataFrame:
    subset = df[df["well_id"] == str(well_id)].copy()
    return subset.sort_values("timestamp")


def _trend_per_month(history: pd.DataFrame) -> float:
    if len(history) < 2:
        return 0.0
    tail = history.tail(min(12, len(history)))
    y = tail[TARGET_COL].astype(float).values
    if len(y) < 2:
        return 0.0
    return float((y[-1] - y[0]) / max(len(y) - 1, 1))


def _historical_std(history: pd.DataFrame) -> float:
    if len(history) < 3:
        return 0.75
    diffs = history[TARGET_COL].astype(float).diff().dropna()
    if diffs.empty:
        return 0.75
    return float(max(diffs.std(), 0.25))


def get_all_wells_summary() -> list[WellOverview]:
    df = _load_feature_matrix()
    if df is None or df.empty:
        return _mock_wells()

    feature_cols = _feature_columns(df)
    latest_df = df.groupby("well_id", sort=False).tail(1).reset_index(drop=True)
    quantiles = _ENGINE.predict_quantiles_batch(latest_df, feature_cols)

    summaries: list[WellOverview] = []
    for idx, (_, row) in enumerate(latest_df.iterrows()):
        _, q50, _ = quantiles[idx]
        current = float(row[TARGET_COL])
        predicted = float(q50)
        ts = row["timestamp"]
        last_updated = ts.strftime("%Y-%m-%d") if isinstance(ts, pd.Timestamp) else str(ts)

        summaries.append(
            WellOverview(
                well_id=str(row["well_id"]),
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                current_depth_m=round(current, 2),
                predicted_depth_m=round(predicted, 2),
                risk_level=_risk_level(current, predicted),
                last_updated=last_updated,
            )
        )

    summaries.sort(key=lambda w: w.well_id)
    return summaries


def get_well_forecast(well_id: str) -> Optional[list[ForecastPoint]]:
    df = _load_feature_matrix()
    if df is None:
        return None

    history = _well_history(df, well_id)
    if history.empty:
        return None

    feature_cols = _feature_columns(df)
    latest = history.iloc[-1]
    q10_base, q50_base, q90_base = _ENGINE.predict_quantiles(latest, feature_cols)
    band_half = max((q90_base - q10_base) / 2.0, _historical_std(history))

    trend = _trend_per_month(history)
    hist_tail = history.tail(HISTORY_MONTHS_IN_FORECAST)
    points: list[ForecastPoint] = []

    for _, row in hist_tail.iterrows():
        ts = row["timestamp"]
        points.append(
            ForecastPoint(
                timestamp=_month_label(ts),
                historical_m=round(float(row[TARGET_COL]), 2),
            )
        )

    last_ts: pd.Timestamp = pd.Timestamp(history.iloc[-1]["timestamp"])
    last_depth = float(history.iloc[-1][TARGET_COL])

    for step in range(1, DEFAULT_FORECAST_HORIZON_MONTHS + 1):
        future_ts = last_ts + pd.DateOffset(months=step)
        q50 = last_depth + trend * step
        if _ENGINE.ready:
            q50 = q50_base + trend * (step - 1)
        spread = band_half * (1.0 + 0.08 * step)
        q10 = q50 - spread
        q90 = q50 + spread
        points.append(
            ForecastPoint(
                timestamp=_month_label(future_ts),
                q10_m=round(q10, 2),
                q50_m=round(q50, 2),
                q90_m=round(q90, 2),
            )
        )

    return points


def _load_importance_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    vsn = pd.read_csv(VSN_IMPORTANCE_CSV) if VSN_IMPORTANCE_CSV.exists() else pd.DataFrame(
        columns=["Feature", "VSN_Importance"]
    )
    shap = pd.read_csv(SHAP_IMPORTANCE_CSV) if SHAP_IMPORTANCE_CSV.exists() else pd.DataFrame(
        columns=["Feature", "Mean_SHAP"]
    )
    return vsn, shap


def _build_attention_weights(vsn: pd.DataFrame) -> list[dict[str, Any]]:
    weights: list[dict[str, Any]] = []
    if vsn.empty:
        for lag in range(1, 13):
            weights.append({"lag_month": lag, "attention_weight": round(1.0 / 12, 4)})
        return weights

    lag_map: dict[int, float] = {}
    for _, row in vsn.iterrows():
        name = str(row["Feature"])
        if "lag_" in name:
            try:
                lag_num = int(name.split("lag_")[-1])
                lag_map[lag_num] = float(row.get("VSN_Importance", 0.0))
            except ValueError:
                continue

    for lag in range(1, 13):
        w = lag_map.get(lag, 0.0)
        if w == 0.0 and lag in (3, 6, 12):
            w = lag_map.get(lag, 0.05)
        weights.append({"lag_month": lag, "attention_weight": round(float(w), 6)})

    total = sum(item["attention_weight"] for item in weights) or 1.0
    for item in weights:
        item["attention_weight"] = round(item["attention_weight"] / total, 6)
    return weights


def _generate_policy_brief(
    well_id: Optional[str],
    top_features: list[FeatureImportance],
    current_depth: Optional[float] = None,
    predicted_q50: Optional[float] = None,
    q10: Optional[float] = None,
    q90: Optional[float] = None,
) -> str:
    wid = well_id or "REGIONAL_OVERVIEW"
    current = current_depth if current_depth is not None else 10.0
    q50 = predicted_q50 if predicted_q50 is not None else current
    low = q10 if q10 is not None else q50 - 0.5
    high = q90 if q90 is not None else q50 + 0.5

    delta = q50 - current
    abs_delta = abs(delta)
    trend_str = (
        f"drop (drawdown) of {abs_delta:.2f} meters"
        if delta > 0
        else f"increase (recharge) of {abs_delta:.2f} meters"
    )

    drivers = []
    for feat in top_features[:3]:
        name = feat.feature
        if delta > 0:
            direction = "increasing drawdown risk"
        else:
            direction = "supporting recharge"
        drivers.append(f"{name} ({direction})")

    drivers_sentence = ", ".join(drivers) if drivers else "Seasonal rainfall lag, Spei 3M, Agricultural extraction"

    brief = (
        f"POLICY BRIEF FOR MONITORING WELL [{wid}]:\n"
        f"• Current Water Depth : {current:.2f} m bgl\n"
        f"• Predicted Forecast  : {q50:.2f} m bgl (Median)\n"
        f"• Projected Change    : Expected {trend_str} over the next horizon.\n"
        f"• Confidence Interval : 80% probability depth remains between {low:.2f} m and {high:.2f} m bgl.\n"
        f"• Primary Drivers     : {drivers_sentence}.\n"
        f"• Advisory Action     : "
    )

    if delta >= 2.0:
        brief += "CRITICAL DRAWDOWN ALERT — Issue immediate extraction restrictions for nearby agricultural pumps."
    elif delta >= 0.5:
        brief += "MODERATE RISK — Monitor local abstraction rates weekly and prepare supplemental recharge protocols."
    elif delta <= -2.0:
        brief += "SIGNIFICANT RECHARGE — Safe capacity available for seasonal agricultural pumping."
    else:
        brief += "STABLE CONDITIONS — Maintain standard seasonal extraction quotas."

    return brief


def get_xai_metrics(well_id: Optional[str] = None) -> XAIResponse:
    vsn_df, shap_df = _load_importance_tables()

    if vsn_df.empty and shap_df.empty:
        defaults = [
            FeatureImportance(feature="Depth To Water M Lag 3", vsn_score=0.35, shap_score=0.10),
            FeatureImportance(feature="Depth To Water M Roll Mean 12", vsn_score=0.29, shap_score=0.01),
            FeatureImportance(feature="Depth To Water M Lag 1", vsn_score=0.06, shap_score=38.76),
        ]
        return XAIResponse(
            global_importance=defaults,
            attention_weights=_build_attention_weights(vsn_df),
            policy_brief=_generate_policy_brief(well_id, defaults),
        )

    merged = pd.merge(
        vsn_df,
        shap_df,
        on="Feature",
        how="outer",
    ).fillna(0.0)

    merged = merged.sort_values("VSN_Importance", ascending=False).head(15)
    global_importance = [
        FeatureImportance(
            feature=_format_feature_name(str(row["Feature"])),
            vsn_score=round(float(row.get("VSN_Importance", 0.0)), 6),
            shap_score=round(float(row.get("Mean_SHAP", 0.0)), 6),
        )
        for _, row in merged.iterrows()
    ]

    current_depth: Optional[float] = None
    predicted_q50: Optional[float] = None
    q10: Optional[float] = None
    q90: Optional[float] = None

    if well_id:
        df = _load_feature_matrix()
        if df is not None:
            history = _well_history(df, well_id)
            if not history.empty:
                feature_cols = _feature_columns(df)
                latest = history.iloc[-1]
                current_depth = float(latest[TARGET_COL])
                q10, predicted_q50, q90 = _ENGINE.predict_quantiles(latest, feature_cols)

    policy_brief = _generate_policy_brief(
        well_id,
        global_importance,
        current_depth=current_depth,
        predicted_q50=predicted_q50,
        q10=q10,
        q90=q90,
    )

    return XAIResponse(
        global_importance=global_importance,
        attention_weights=_build_attention_weights(vsn_df),
        policy_brief=policy_brief,
    )


def run_policy_simulation(request: SimulationRequest) -> SimulationResponse:
    df = _load_feature_matrix()
    horizon = request.forecast_horizon_months

    if df is not None and not _well_history(df, request.well_id).empty:
        forecast = get_well_forecast(request.well_id)
        if forecast:
            future = [p for p in forecast if p.q50_m is not None][-horizon:]
            baseline_q50 = [p.q50_m for p in future][:horizon]
            months = [p.timestamp for p in future][:horizon]
        else:
            baseline_q50 = [12.0 + 0.3 * i for i in range(horizon)]
            months = _future_month_labels(horizon)
    else:
        baseline_q50 = [12.0 + 0.3 * i for i in range(horizon)]
        months = _future_month_labels(horizon)

    if len(baseline_q50) < horizon:
        pad = horizon - len(baseline_q50)
        last = baseline_q50[-1] if baseline_q50 else 12.0
        baseline_q50.extend([last + 0.2 * (i + 1) for i in range(pad)])
        months = (months + _future_month_labels(pad))[:horizon]

    pumping_factor = (request.pumping_reduction_pct / 100.0) * 0.05
    recharge_factor = (request.recharge_enhancement_pct / 100.0) * 0.03
    mitigation = pumping_factor + recharge_factor

    simulated_q50: list[float] = []
    for step, base in enumerate(baseline_q50):
        depth = max(5.0, base - mitigation * step)
        simulated_q50.append(round(depth, 2))

    water_saved_m3 = (request.pumping_reduction_pct * 12500.0) + (
        request.recharge_enhancement_pct * 4500.0
    )

    return SimulationResponse(
        well_id=request.well_id,
        baseline_q50=[round(v, 2) for v in baseline_q50[:horizon]],
        simulated_q50=simulated_q50,
        water_saved_m3=round(water_saved_m3, 2),
        months=months[:horizon],
    )


def _future_month_labels(count: int) -> list[str]:
    start = pd.Timestamp.utcnow().normalize().replace(day=1)
    return [_month_label(start + pd.DateOffset(months=i)) for i in range(count)]
