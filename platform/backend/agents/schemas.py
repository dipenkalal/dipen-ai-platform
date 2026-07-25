from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AgentStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
]

AgentCategory = Literal[
    "system",
    "knowledge",
    "research",
    "devops",
    "coding",
    "documentation",
    "data",
    "general",
]

AgentAccent = Literal[
    "cyan",
    "violet",
    "emerald",
    "amber",
    "blue",
    "rose",
    "orange",
    "slate",
]


class AgentDefinition(BaseModel):
    id: str
    name: str
    description: str

    category: AgentCategory = "general"
    icon: str = "bot"
    accent: AgentAccent = "cyan"

    tools: list[str] = Field(
        default_factory=list
    )

    capabilities: list[str] = Field(
        default_factory=list
    )

    recommended_model: str | None = None

    safe: bool = True
    enabled: bool = True


class AgentListResponse(BaseModel):
    agents: list[AgentDefinition]


class ToolListResponse(BaseModel):
    tools: list[dict[str, Any]]


class AgentRunRequest(BaseModel):
    mode: Literal[
        "smart",
        "manual",
    ] = "manual"

    agent_id: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

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

    max_steps: int = Field(
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


class AgentStep(BaseModel):
    step_number: int

    type: Literal[
        "planning",
        "tool",
        "generation",
        "result",
    ]

    title: str
    tool_id: str | None = None
    success: bool = True

    input: dict[str, Any] | None = None
    output: Any = None
    error: str | None = None

    started_at: datetime
    completed_at: datetime


class AgentUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float = 0.0


class AgentRunResponse(BaseModel):
    run_id: str
    agent_id: str
    objective: str
    status: AgentStatus
    answer: str
    steps: list[AgentStep]

    sources: list[dict[str, Any]] = Field(
        default_factory=list
    )

    usage: AgentUsage
    started_at: datetime
    completed_at: datetime
