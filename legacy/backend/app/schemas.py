"""Pydantic V2 request/response contracts (aligned with AquaSense frontend types)."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class WellOverview(BaseModel):
    well_id: str
    latitude: float
    longitude: float
    current_depth_m: float
    predicted_depth_m: float
    risk_level: Literal["Critical", "Moderate", "Stable"]
    last_updated: str


class ForecastPoint(BaseModel):
    timestamp: str
    historical_m: Optional[float] = None
    q10_m: Optional[float] = None
    q50_m: Optional[float] = None
    q90_m: Optional[float] = None


class FeatureImportance(BaseModel):
    feature: str
    vsn_score: float
    shap_score: float


class XAIResponse(BaseModel):
    global_importance: List[FeatureImportance]
    attention_weights: List[Dict[str, Any]]
    policy_brief: str


class SimulationRequest(BaseModel):
    well_id: str
    pumping_reduction_pct: float = Field(ge=0.0, le=50.0)
    recharge_enhancement_pct: float = Field(ge=0.0, le=30.0)
    forecast_horizon_months: int = Field(default=12, ge=1, le=36)


class SimulationResponse(BaseModel):
    well_id: str
    baseline_q50: List[float]
    simulated_q50: List[float]
    water_saved_m3: float
    months: List[str]
