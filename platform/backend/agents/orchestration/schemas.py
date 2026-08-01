from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.schemas import (
    AgentStep,
    AgentUsage,
)

OrchestrationExecutionMode = Literal[
    "sequential",
    "parallel",
]

OrchestrationTaskRole = Literal[
    "lead",
    "specialist",
    "formatter",
]

OrchestrationRunStatus = Literal[
    "running",
    "completed",
    "failed",
]

SynthesisStatus = Literal[
    "completed",
    "failed",
]

EvidenceValidationStatus = Literal[
    "passed",
    "corrected",
    "warning",
    "failed",
]

EvidenceIssueSeverity = Literal[
    "info",
    "warning",
    "error",
]


class OrchestrationPlanRequest(BaseModel):
    objective: str = Field(
        min_length=2,
        max_length=8000,
    )

    model: str | None = None

    provider: Literal[
        "auto",
        "ollama",
    ] = "auto"

    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
    )

    max_tokens: int = Field(
        default=700,
        ge=1,
        le=8192,
    )

    max_agents: int = Field(
        default=4,
        ge=1,
        le=6,
    )

    max_steps_per_agent: int = Field(
        default=4,
        ge=1,
        le=10,
    )

    retrieval_limit: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    score_threshold: float | None = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
    )

    document_id: str | None = None

    include_documentation: bool = True


class OrchestrationTask(BaseModel):
    task_id: str
    sequence: int

    agent_id: str
    agent_name: str

    role: OrchestrationTaskRole

    objective: str
    instructions: str

    model: str | None = None

    tools: list[str] = Field(
        default_factory=list,
    )

    capabilities: list[str] = Field(
        default_factory=list,
    )

    depends_on: list[str] = Field(
        default_factory=list,
    )

    confidence: float = 0.0
    score: int = 0
    reason: str


class OrchestrationPlan(BaseModel):
    plan_id: str
    objective: str

    execution_mode: OrchestrationExecutionMode

    lead_agent_id: str

    selected_agent_ids: list[str] = Field(
        default_factory=list,
    )

    tasks: list[OrchestrationTask] = Field(
        default_factory=list,
    )

    candidate_scores: dict[str, int] = Field(
        default_factory=dict,
    )

    matched_terms: list[str] = Field(
        default_factory=list,
    )

    confidence: float = 0.0
    reason: str

    estimated_agent_runs: int = 0
    max_steps_per_agent: int = 4


class OrchestrationPlanResponse(BaseModel):
    plan: OrchestrationPlan


class OrchestrationTaskResult(BaseModel):
    task_id: str
    sequence: int

    agent_id: str
    agent_name: str
    role: OrchestrationTaskRole

    status: Literal[
        "completed",
        "failed",
    ]

    answer: str = ""

    steps: list[AgentStep] = Field(
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


class EvidenceValidationIssue(BaseModel):
    code: str

    severity: EvidenceIssueSeverity

    message: str

    claim: str | None = None

    topic: str | None = None


class EvidenceSnapshot(BaseModel):
    inspected_tools: list[str] = Field(
        default_factory=list,
    )

    inspected_topics: list[str] = Field(
        default_factory=list,
    )

    unavailable_topics: list[str] = Field(
        default_factory=list,
    )

    normalized_facts: dict[str, Any] = Field(
        default_factory=dict,
    )

    normalized_summary: str = ""

    direct_evidence_count: int = 0


class EvidenceValidationResult(BaseModel):
    status: EvidenceValidationStatus

    passed: bool = False

    corrected: bool = False

    confidence: float = 0.0

    issues: list[EvidenceValidationIssue] = Field(
        default_factory=list,
    )

    snapshot: EvidenceSnapshot = Field(
        default_factory=EvidenceSnapshot,
    )

    original_answer: str | None = None

    validated_answer: str | None = None


class OrchestrationSynthesisResult(BaseModel):
    status: SynthesisStatus

    answer: str = ""

    provider: str | None = None
    model: str | None = None

    usage: AgentUsage = Field(
        default_factory=AgentUsage,
    )

    validation: EvidenceValidationResult | None = None

    error: str | None = None

    started_at: datetime
    completed_at: datetime


class OrchestrationRunResponse(BaseModel):
    orchestration_run_id: str

    objective: str
    status: OrchestrationRunStatus

    plan: OrchestrationPlan

    task_results: list[OrchestrationTaskResult] = Field(
        default_factory=list,
    )

    synthesis: OrchestrationSynthesisResult | None = None

    final_answer: str = ""

    usage: AgentUsage = Field(
        default_factory=AgentUsage,
    )

    error: str | None = None

    started_at: datetime
    completed_at: datetime
