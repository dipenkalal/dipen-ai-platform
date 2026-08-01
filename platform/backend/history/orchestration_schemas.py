from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.orchestration.schemas import (
    EvidenceValidationResult,
    OrchestrationExecutionMode,
    OrchestrationPlan,
    OrchestrationRunResponse,
    OrchestrationSynthesisResult,
    OrchestrationTaskResult,
)
from agents.schemas import AgentUsage

OrchestrationHistoryStatus = Literal[
    "running",
    "completed",
    "failed",
]


class OrchestrationTaskRunRecord(BaseModel):
    id: int

    orchestration_run_id: str

    task_id: str
    sequence: int

    agent_id: str
    agent_name: str
    role: Literal[
        "lead",
        "specialist",
        "formatter",
    ]

    status: Literal[
        "completed",
        "failed",
    ]

    depends_on: list[str] = Field(
        default_factory=list,
    )

    answer: str = ""

    steps: list[dict[str, Any]] = Field(
        default_factory=list,
    )

    sources: list[dict[str, Any]] = Field(
        default_factory=list,
    )

    usage: AgentUsage = Field(
        default_factory=AgentUsage,
    )

    error: str | None = None

    started_at: datetime
    completed_at: datetime
    created_at: datetime


class OrchestrationRunRecord(BaseModel):
    run_id: str
    plan_id: str

    objective: str

    status: OrchestrationHistoryStatus

    execution_mode: OrchestrationExecutionMode

    lead_agent_id: str

    selected_agent_ids: list[str] = Field(
        default_factory=list,
    )

    plan: OrchestrationPlan

    synthesis: OrchestrationSynthesisResult | None = None

    validation: EvidenceValidationResult | None = None

    final_answer: str = ""

    usage: AgentUsage = Field(
        default_factory=AgentUsage,
    )

    error: str | None = None

    task_runs: list[OrchestrationTaskRunRecord] = Field(
        default_factory=list,
    )

    started_at: datetime
    completed_at: datetime
    created_at: datetime
    updated_at: datetime


class OrchestrationRunSummary(BaseModel):
    run_id: str
    plan_id: str

    objective: str

    status: OrchestrationHistoryStatus

    execution_mode: OrchestrationExecutionMode

    lead_agent_id: str

    selected_agent_ids: list[str] = Field(
        default_factory=list,
    )

    task_count: int = 0

    completed_task_count: int = 0

    failed_task_count: int = 0

    final_answer_preview: str = ""

    validation_status: (
        Literal[
            "passed",
            "corrected",
            "warning",
            "failed",
        ]
        | None
    ) = None

    validation_passed: bool | None = None

    total_tokens: int | None = None

    latency_ms: float = 0.0

    error: str | None = None

    started_at: datetime
    completed_at: datetime
    created_at: datetime


class OrchestrationRunListResponse(BaseModel):
    runs: list[OrchestrationRunSummary] = Field(
        default_factory=list,
    )

    total: int = 0
    limit: int = 100
    offset: int = 0


class OrchestrationRunDeleteResponse(BaseModel):
    deleted: bool
    run_id: str


class OrchestrationRunClearResponse(BaseModel):
    deleted_count: int


class SaveOrchestrationRunInput(BaseModel):
    response: OrchestrationRunResponse


class OrchestrationHistoryFilters(BaseModel):
    limit: int = Field(
        default=100,
        ge=1,
        le=500,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )

    status: OrchestrationHistoryStatus | None = None

    execution_mode: OrchestrationExecutionMode | None = None

    lead_agent_id: str | None = None

    validation_status: (
        Literal[
            "passed",
            "corrected",
            "warning",
            "failed",
        ]
        | None
    ) = None

    search: str | None = None


class OrchestrationTaskSaveInput(BaseModel):
    orchestration_run_id: str

    task: OrchestrationTaskResult

    depends_on: list[str] = Field(
        default_factory=list,
    )
