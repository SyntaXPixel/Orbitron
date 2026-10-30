from fastapi import APIRouter
from app.schemas.public import HealthResponse
from app.adapters.scheduler import SchedulerAdapter
from app.adapters.security import SecurityAdapter

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def get_health():
    is_ready = SchedulerAdapter.is_available() and SecurityAdapter.is_available()
    return HealthResponse(
        service="orbitron-backend",
        contract_version="orbitron.v1",
        status="ready" if is_ready else "degraded"
    )
