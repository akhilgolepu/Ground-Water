from fastapi import APIRouter, HTTPException

from app.schemas import ForecastPoint
from app.services import get_well_forecast

router = APIRouter(prefix="/api", tags=["forecast"])


@router.get("/forecast/{well_id}", response_model=list[ForecastPoint])
def well_forecast(well_id: str) -> list[ForecastPoint]:
    points = get_well_forecast(well_id)
    if points is None:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found")
    return points
