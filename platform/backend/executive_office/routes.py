from fastapi import APIRouter

from executive_office.schemas import (
    ExecutiveOfficeStatusResponse,
    ExecutivePlanRequest,
    ExecutivePlanResponse,
)
from executive_office.service import executive_office_service

router = APIRouter(
    prefix="/api/v1/executive-office",
    tags=["Executive Office"],
)


@router.get(
    "/status",
    response_model=ExecutiveOfficeStatusResponse,
)
async def get_executive_office_status() -> ExecutiveOfficeStatusResponse:
    return executive_office_service.status()


@router.post(
    "/plan",
    response_model=ExecutivePlanResponse,
)
async def create_executive_plan(
    request: ExecutivePlanRequest,
) -> ExecutivePlanResponse:
    return executive_office_service.plan(request)
