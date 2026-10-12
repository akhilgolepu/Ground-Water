from typing import Optional

from fastapi import APIRouter, Query

from app.schemas import XAIResponse
from app.services import get_xai_metrics

router = APIRouter(prefix="/api", tags=["xai"])


@router.get("/xai", response_model=XAIResponse)
def xai_metrics(well_id: Optional[str] = Query(default=None)) -> XAIResponse:
    return get_xai_metrics(well_id=well_id)
