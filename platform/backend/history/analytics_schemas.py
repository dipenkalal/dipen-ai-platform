from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AnalyticsRunStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class AnalyticsOverview(BaseModel):
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    running_runs: int = 0
    cancelled_runs: int = 0
    success_rate: float = 0.0
    average_latency_ms: float = 0.0
    total_tokens: int = 0
    runs_today: int = 0
    most_used_agent: str | None = None


class AgentAnalyticsItem(BaseModel):
    agent_id: str
    runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    average_latency_ms: float = 0.0
    total_tokens: int = 0
    last_used_at: datetime


class AgentAnalyticsResponse(BaseModel):
    agents: list[AgentAnalyticsItem] = Field(default_factory=list)
    total: int = 0


class RecentAnalyticsRun(BaseModel):
    run_id: str
    agent_id: str
    objective: str
    model: str | None = None
    provider: str = "auto"
    status: AnalyticsRunStatus
    total_tokens: int | None = None
    latency_ms: float = 0.0
    started_at: datetime
    completed_at: datetime


class RecentAnalyticsResponse(BaseModel):
    runs: list[RecentAnalyticsRun] = Field(default_factory=list)
    total: int = 0
    limit: int = 10


class RoutingMatchedTerm(BaseModel):
    term: str
    count: int


class RoutingAnalytics(BaseModel):
    smart_runs: int = 0
    manual_runs: int = 0
    smart_routing_percentage: float = 0.0
    average_confidence: float = 0.0
    average_routing_latency_ms: float = 0.0
    most_selected_agent: str | None = None
    agent_selection_distribution: dict[str, int] = Field(default_factory=dict)
    top_matched_terms: list[RoutingMatchedTerm] = Field(default_factory=list)


class AnalyticsDashboardResponse(BaseModel):
    overview: AnalyticsOverview
    routing: RoutingAnalytics
    agents: list[AgentAnalyticsItem] = Field(default_factory=list)
    recent_runs: list[RecentAnalyticsRun] = Field(default_factory=list)
