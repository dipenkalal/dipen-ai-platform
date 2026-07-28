from fastapi import (
    APIRouter,
    Query,
)

from history.analytics_schemas import (
    AgentAnalyticsResponse,
    AnalyticsDashboardResponse,
    AnalyticsOverview,
    RecentAnalyticsResponse,
)
from history.analytics_service import (
    agent_analytics_service,
)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Agent Analytics"],
)


@router.get(
    "/overview",
    response_model=AnalyticsOverview,
)
async def get_analytics_overview() -> AnalyticsOverview:
    return agent_analytics_service.get_overview()


@router.get(
    "/agents",
    response_model=AgentAnalyticsResponse,
)
async def get_agent_analytics(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
) -> AgentAnalyticsResponse:
    return agent_analytics_service.get_agents(
        limit=limit,
    )


@router.get(
    "/recent",
    response_model=RecentAnalyticsResponse,
)
async def get_recent_analytics_runs(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
) -> RecentAnalyticsResponse:
    return agent_analytics_service.get_recent(
        limit=limit,
    )


@router.get(
    "/dashboard",
    response_model=AnalyticsDashboardResponse,
)
async def get_analytics_dashboard(
    agent_limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    recent_limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
) -> AnalyticsDashboardResponse:
    return agent_analytics_service.get_dashboard(
        agent_limit=agent_limit,
        recent_limit=recent_limit,
    )
