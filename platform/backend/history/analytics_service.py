from history.analytics_repository import (
    agent_analytics_repository,
)
from history.analytics_schemas import (
    AgentAnalyticsResponse,
    AnalyticsDashboardResponse,
    AnalyticsOverview,
    RecentAnalyticsResponse,
)


class AgentAnalyticsService:
    def get_overview(
        self,
    ) -> AnalyticsOverview:
        return (
            agent_analytics_repository
            .get_overview()
        )

    def get_agents(
        self,
        *,
        limit: int,
    ) -> AgentAnalyticsResponse:
        agents = (
            agent_analytics_repository
            .get_agents(
                limit=limit,
            )
        )

        return AgentAnalyticsResponse(
            agents=agents,
            total=len(agents),
        )

    def get_recent(
        self,
        *,
        limit: int,
    ) -> RecentAnalyticsResponse:
        runs = (
            agent_analytics_repository
            .get_recent(
                limit=limit,
            )
        )

        return RecentAnalyticsResponse(
            runs=runs,
            total=len(runs),
            limit=limit,
        )

    def get_dashboard(
        self,
        *,
        agent_limit: int,
        recent_limit: int,
    ) -> AnalyticsDashboardResponse:
        overview = (
            agent_analytics_repository
            .get_overview()
        )

        agents = (
            agent_analytics_repository
            .get_agents(
                limit=agent_limit,
            )
        )

        recent_runs = (
            agent_analytics_repository
            .get_recent(
                limit=recent_limit,
            )
        )

        return AnalyticsDashboardResponse(
            overview=overview,
            agents=agents,
            recent_runs=recent_runs,
        )


agent_analytics_service = (
    AgentAnalyticsService()
)
