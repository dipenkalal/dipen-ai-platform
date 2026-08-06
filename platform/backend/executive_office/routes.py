from fastapi import APIRouter, HTTPException, status

from executive_office.delegation_service import (
    executive_delegation_service,
)
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutiveDelegationResponse,
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
    return executive_delegation_service.status()


@router.post(
    "/plan",
    response_model=ExecutivePlanResponse,
)
async def create_executive_plan(
    request: ExecutivePlanRequest,
) -> ExecutivePlanResponse:
    return executive_office_service.plan(request)


@router.post(
    "/delegate",
    response_model=ExecutiveDelegationResponse,
)
async def delegate_executive_plan(
    request: ExecutiveDelegationRequest,
) -> ExecutiveDelegationResponse:
    try:
        return executive_delegation_service.delegate(request)
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
