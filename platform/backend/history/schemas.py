from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStep,
    AgentUsage,
)


HistoryRunStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class AgentRunRecord(BaseModel):
    run_id: str
    agent_id: str
    objective: str
    model: str | None = None
    provider: str = "auto"
    status: HistoryRunStatus
    answer: str = ""
    error: str | None = None

    steps: list[AgentStep] = Field(
        default_factory=list
    )
    sources: list[dict[str, Any]] = Field(
        default_factory=list
    )
    usage: AgentUsage = Field(
        default_factory=AgentUsage
    )

    request: dict[str, Any] = Field(
        default_factory=dict
    )

    started_at: datetime
    completed_at: datetime
    created_at: datetime
    updated_at: datetime


class AgentRunSummary(BaseModel):
    run_id: str
    agent_id: str
    objective: str
    model: str | None = None
    provider: str = "auto"
    status: HistoryRunStatus
    answer_preview: str = ""
    error: str | None = None
    step_count: int = 0
    source_count: int = 0
    total_tokens: int | None = None
    latency_ms: float = 0.0
    started_at: datetime
    completed_at: datetime
    created_at: datetime


class AgentRunListResponse(BaseModel):
    runs: list[AgentRunSummary]
    total: int
    limit: int
    offset: int


class AgentRunDeleteResponse(BaseModel):
    deleted: bool
    run_id: str


class AgentRunClearResponse(BaseModel):
    deleted_count: int


class SaveAgentRunInput(BaseModel):
    request: AgentRunRequest
    response: AgentRunResponse
    error: str | None = None
