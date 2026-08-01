from typing import Literal

from fastapi import (
    APIRouter,
    Query,
)

from history.orchestration_schemas import (
    OrchestrationRunClearResponse,
    OrchestrationRunDeleteResponse,
    OrchestrationRunListResponse,
    OrchestrationRunRecord,
)
from history.orchestration_service import (
    orchestration_history_service,
)

router = APIRouter(
    prefix="/api/v1/orchestrations",
    tags=["Orchestration History"],
)


@router.get(
    "",
    response_model=OrchestrationRunListResponse,
)
async def list_orchestration_runs(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    status: (
        Literal[
            "running",
            "completed",
            "failed",
        ]
        | None
    ) = None,
    execution_mode: (
        Literal[
            "sequential",
            "parallel",
        ]
        | None
    ) = None,
    lead_agent_id: str | None = None,
    validation_status: (
        Literal[
            "passed",
            "corrected",
            "warning",
            "failed",
        ]
        | None
    ) = None,
    search: str | None = None,
) -> OrchestrationRunListResponse:
    return orchestration_history_service.list_runs(
        limit=limit,
        offset=offset,
        status=status,
        execution_mode=execution_mode,
        lead_agent_id=lead_agent_id,
        validation_status=validation_status,
        search=search,
    )


@router.get(
    "/{run_id}",
    response_model=OrchestrationRunRecord,
)
async def get_orchestration_run(
    run_id: str,
) -> OrchestrationRunRecord:
    return orchestration_history_service.get(
        run_id,
    )


@router.delete(
    "/{run_id}",
    response_model=OrchestrationRunDeleteResponse,
)
async def delete_orchestration_run(
    run_id: str,
) -> OrchestrationRunDeleteResponse:
    return orchestration_history_service.delete(
        run_id,
    )


@router.delete(
    "",
    response_model=OrchestrationRunClearResponse,
)
async def clear_orchestration_runs() -> OrchestrationRunClearResponse:
    return orchestration_history_service.clear()
