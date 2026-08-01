from fastapi import APIRouter

from monitoring.schemas import (
    MonitoringOverview,
)
from monitoring.service import (
    get_monitoring_overview,
)


router = APIRouter(
    prefix="/api/monitoring",
    tags=["monitoring"],
)


@router.get(
    "/overview",
    response_model=MonitoringOverview,
)
async def monitoring_overview() -> MonitoringOverview:
    return await get_monitoring_overview()
