from fastapi import APIRouter, HTTPException, status

from executive_office.delegation_service import (
    executive_delegation_service,
)
from executive_office.execution_cancellation_recovery import (
    executive_cancellation_aware_recovery_service,
)
from executive_office.execution_cancellation_repository import (
    CancellationStateConflictError,
)
from executive_office.execution_cancellation_schemas import (
    ExecutiveRunningCancellationRecord,
    ExecutiveRunningCancellationRequest,
)
from executive_office.execution_cancellation_service import (
    executive_execution_cancellation_service,
)
from executive_office.execution_recovery_schemas import (
    ExecutiveExecutionControlRequest,
    ExecutiveExecutionControlResponse,
)
from executive_office.execution_recovery_service import (
    executive_execution_recovery_service,
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

# Preserve the generic route dependency name while Phase 4 extends admission
# from validation into durable reservation. Tests and integrations may patch it.
executive_execution_service = executive_reservation_service

router = APIRouter(
    prefix="/api/v1/executive-office",
    tags=["Executive Office"],
)


@router.get(
    "/status",
    response_model=ExecutiveOfficeStatusResponse,
)
async def get_executive_office_status() -> ExecutiveOfficeStatusResponse:
    return executive_execution_recovery_service.status()


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
        return executive_execution_service.admit(request)
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


@router.post(
    "/executions/{execution_id}/request-cancellation",
    response_model=ExecutiveRunningCancellationRecord,
)
async def request_running_execution_cancellation(
    execution_id: str,
    request: ExecutiveRunningCancellationRequest,
) -> ExecutiveRunningCancellationRecord:
    try:
        return executive_execution_cancellation_service.request(
            execution_id=execution_id,
            request=request,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except CancellationStateConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=ExecutiveExecutionControlResponse,
)
async def cancel_executive_execution(
    execution_id: str,
    request: ExecutiveExecutionControlRequest,
) -> ExecutiveExecutionControlResponse:
    try:
        return executive_execution_recovery_service.cancel(
            execution_id=execution_id,
            request=request,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/executions/{execution_id}/recover",
    response_model=ExecutiveExecutionControlResponse,
)
async def recover_executive_execution(
    execution_id: str,
    request: ExecutiveExecutionControlRequest,
) -> ExecutiveExecutionControlResponse:
    try:
        return executive_cancellation_aware_recovery_service.recover(
            execution_id=execution_id,
            request=request,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
