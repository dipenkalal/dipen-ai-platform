from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from agents.truth_schemas import (
    AgentFleetStateResponse,
    AgentRuntimeState,
    TaskLedgerListResponse,
    TaskLedgerRecord,
    TaskLedgerStatus,
)
from agents.truth_service import agent_truth_service


router = APIRouter(
    prefix="/api/v1/truth",
    tags=["Guardian Truth Foundation"],
)


@router.get(
    "/agents",
    response_model=AgentFleetStateResponse,
)
async def list_agent_truth() -> AgentFleetStateResponse:
    return agent_truth_service.list_agent_states()


@router.get(
    "/agents/{agent_id}",
    response_model=AgentRuntimeState,
)
async def get_agent_truth(
    agent_id: str,
) -> AgentRuntimeState:
    try:
        return agent_truth_service.get_agent_state(
            agent_id
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@router.get(
    "/tasks",
    response_model=TaskLedgerListResponse,
)
async def list_truth_tasks(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    status: TaskLedgerStatus | None = None,
) -> TaskLedgerListResponse:
    return agent_truth_service.list_tasks(
        limit=limit,
        offset=offset,
        status=status,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskLedgerRecord,
)
async def get_truth_task(
    task_id: str,
) -> TaskLedgerRecord:
    try:
        return agent_truth_service.get_task(task_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
