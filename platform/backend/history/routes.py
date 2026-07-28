from fastapi import (
    APIRouter,
    Query,
)

from history.schemas import (
    AgentRunClearResponse,
    AgentRunDeleteResponse,
    AgentRunListResponse,
    AgentRunRecord,
)
from history.service import (
    agent_run_history_service,
)

router = APIRouter(
    prefix="/api/v1/agent-runs",
    tags=["Agent Run History"],
)


@router.get(
    "",
    response_model=AgentRunListResponse,
)
async def list_agent_runs(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    agent_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    search: str | None = None,
) -> AgentRunListResponse:
    return agent_run_history_service.list(
        limit=limit,
        offset=offset,
        agent_id=agent_id,
        status=status,
        model=model,
        search=search,
    )


@router.get(
    "/{run_id}",
    response_model=AgentRunRecord,
)
async def get_agent_run(
    run_id: str,
) -> AgentRunRecord:
    return agent_run_history_service.get(run_id)


@router.delete(
    "/{run_id}",
    response_model=AgentRunDeleteResponse,
)
async def delete_agent_run(
    run_id: str,
) -> AgentRunDeleteResponse:
    return agent_run_history_service.delete(run_id)


@router.delete(
    "",
    response_model=AgentRunClearResponse,
)
async def clear_agent_runs() -> AgentRunClearResponse:
    return agent_run_history_service.clear()
