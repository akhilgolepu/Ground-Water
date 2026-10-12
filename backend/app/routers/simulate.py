from fastapi import APIRouter

from app.schemas import SimulationRequest, SimulationResponse
from app.services import run_policy_simulation

router = APIRouter(prefix="/api", tags=["simulate"])


@router.post("/simulate", response_model=SimulationResponse)
def simulate_policy(request: SimulationRequest) -> SimulationResponse:
    return run_policy_simulation(request)
