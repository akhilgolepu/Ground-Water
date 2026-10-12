from fastapi import APIRouter

from app.schemas import WellOverview
from app.services import get_all_wells_summary

router = APIRouter(prefix="/api", tags=["wells"])


@router.get("/wells", response_model=list[WellOverview])
def list_wells() -> list[WellOverview]:
    return get_all_wells_summary()
