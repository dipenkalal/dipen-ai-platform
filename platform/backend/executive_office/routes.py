from fastapi import APIRouter, HTTPException, status

from executive_office.delegation_service import (
    executive_delegation_service,
)
from executive_office.execution_reservation_service import (
    executive_reservation_service,
)
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartRequest,
    ExecutiveExecutionStartResponse,
    ExecutiveExecutionStatusResponse,
)
from executive_office.execution_start_service import (
    executive_execution_start_service,
)
from executive_office.execution_status_service import (
    executive_execution_status_service,
)
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutiveDelegationResponse,
    ExecutiveExecutionRequest,
    ExecutiveExecutionResponse,
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
    return executive_execution_start_service.status()


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


@router.post(
    "/execute",
    response_model=ExecutiveExecutionResponse,
)
async def execute_executive_plan(
    request: ExecutiveExecutionRequest,
) -> ExecutiveExecutionResponse:
    try:
        return executive_reservation_service.admit(request)
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutiveExecutionStatusResponse,
)
async def get_executive_execution_status(
    execution_id: str,
) -> ExecutiveExecutionStatusResponse:
    try:
        return executive_execution_status_service.get(execution_id)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.post(
    "/executions/{execution_id}/start",
    response_model=ExecutiveExecutionStartResponse,
)
async def start_executive_execution(
    execution_id: str,
    request: ExecutiveExecutionStartRequest,
) -> ExecutiveExecutionStartResponse:
    try:
        return await executive_execution_start_service.start(
            execution_id=execution_id,
            request=request,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
