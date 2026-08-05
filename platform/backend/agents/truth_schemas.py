from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.schemas import AgentDefinition

AgentRuntimeStatus = Literal[
    "unreported",
    "available",
    "busy",
    "degraded",
    "offline",
    "disabled",
]

HeartbeatStatus = Literal[
    "available",
    "busy",
    "degraded",
    "offline",
]

TaskLedgerStatus = Literal[
    "created",
    "planned",
    "queued",
    "assigned",
    "running",
    "waiting",
    "completed",
    "failed",
    "cancelled",
    "manual_review",
]

TaskPriority = Literal[
    "critical",
    "high",
    "normal",
    "background",
    "maintenance",
]

TaskType = Literal[
    "agent",
    "orchestration",
    "system",
    "personal",
]

EvidenceSource = Literal[
    "agent-registry",
    "backend-runtime",
    "runtime-heartbeat",
    "task-ledger",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TruthEvidence(BaseModel):
    source: EvidenceSource
    observed_at: datetime | None = None
    detail: str


class AgentHeartbeat(BaseModel):
    agent_id: str = Field(min_length=2, max_length=100)
    worker_id: str = Field(min_length=2, max_length=160)
    status: HeartbeatStatus
    current_task_id: str | None = Field(
        default=None,
        max_length=160,
    )
    model: str | None = Field(
        default=None,
        max_length=160,
    )
    process_id: int | None = Field(
        default=None,
        ge=1,
    )
    container_id: str | None = Field(
        default=None,
        max_length=160,
    )
    details: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=utc_now)


class AgentRuntimeState(BaseModel):
    agent: AgentDefinition
    runtime_status: AgentRuntimeStatus
    worker_id: str | None = None
    current_task_id: str | None = None
    model: str | None = None
    process_id: int | None = None
    container_id: str | None = None
    last_heartbeat_at: datetime | None = None
    heartbeat_age_seconds: float | None = None
    evidence: list[TruthEvidence] = Field(default_factory=list)


class AgentFleetSummary(BaseModel):
    registered: int
    enabled: int
    available: int
    busy: int
    degraded: int
    offline: int
    unreported: int
    disabled: int


class AgentFleetStateResponse(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    summary: AgentFleetSummary
    agents: list[AgentRuntimeState]


class TaskLedgerRecord(BaseModel):
    task_id: str = Field(min_length=2, max_length=160)
    task_type: TaskType
    objective: str = Field(min_length=2, max_length=8000)
    status: TaskLedgerStatus
    priority: TaskPriority = "normal"
    requested_by: str = Field(min_length=2, max_length=160)
    assigned_agent_ids: list[str] = Field(default_factory=list)
    source_run_id: str | None = Field(
        default=None,
        max_length=160,
    )
    parent_task_id: str | None = Field(
        default=None,
        max_length=160,
    )
    current_step: str | None = Field(
        default=None,
        max_length=1000,
    )
    progress_percent: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
    )
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TaskLedgerListResponse(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    tasks: list[TaskLedgerRecord]
    total: int
    limit: int
    offset: int
