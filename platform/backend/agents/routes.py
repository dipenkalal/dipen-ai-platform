from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agents.orchestration.schemas import (
    OrchestrationPlanRequest,
    OrchestrationPlanResponse,
    OrchestrationRunResponse,
)
from agents.orchestration.service import (
    orchestration_service,
)
from agents.schemas import (
    AgentListResponse,
    AgentRunRequest,
    AgentRunResponse,
    ToolListResponse,
)
from agents.service import agent_service

router = APIRouter(
    prefix="/api/v1",
    tags=["AI Agents"],
)


@router.get(
    "/agents",
    response_model=AgentListResponse,
)
async def list_agents() -> AgentListResponse:
    return AgentListResponse(
        agents=agent_service.list_agents(),
    )


@router.get(
    "/tools",
    response_model=ToolListResponse,
)
async def list_tools() -> ToolListResponse:
    return ToolListResponse(
        tools=agent_service.list_tools(),
    )


@router.post(
    "/agents/orchestration/plan",
    response_model=OrchestrationPlanResponse,
)
async def create_orchestration_plan(
    request: OrchestrationPlanRequest,
) -> OrchestrationPlanResponse:
    return OrchestrationPlanResponse(
        plan=orchestration_service.create_plan(
            request,
        ),
    )


@router.post(
    "/agents/orchestration/run",
    response_model=OrchestrationRunResponse,
)
async def run_orchestration(
    request: OrchestrationPlanRequest,
) -> OrchestrationRunResponse:
    return await orchestration_service.run(
        request,
    )


@router.post(
    "/agents/run",
    response_model=AgentRunResponse,
)
async def run_agent(
    request: AgentRunRequest,
) -> AgentRunResponse:
    return await agent_service.run(
        request,
    )


@router.post(
    "/agents/run/stream",
    response_class=StreamingResponse,
)
async def stream_agent(
    request: AgentRunRequest,
) -> StreamingResponse:
    return StreamingResponse(
        agent_service.stream(request),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
