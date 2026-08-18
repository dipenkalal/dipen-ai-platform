from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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

    tools: list[str] = Field(default_factory=list)

    capabilities: list[str] = Field(default_factory=list)

    recommended_model: str | None = None

    safe: bool = True
    enabled: bool = True


class AgentListResponse(BaseModel):
    agents: list[AgentDefinition]


class ToolListResponse(BaseModel):
    tools: list[dict[str, Any]]


class AgentRoutingMetadata(BaseModel):
    mode: Literal[
        "smart",
        "manual",
    ]

    selected_agent_id: str
    confidence: float | None = None
    reason: str | None = None

    matched_terms: list[str] = Field(default_factory=list)

    candidate_scores: dict[str, int] = Field(default_factory=dict)

    routing_latency_ms: float | None = None


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

    supplemental_context: str | None = Field(
        default=None,
        max_length=12000,
    )

    research_urls: tuple[str, ...] = Field(
        default=(),
        max_length=3,
    )

    research_search_query: str | None = Field(
        default=None,
        min_length=1,
        max_length=400,
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
    routing: AgentRoutingMetadata | None = None

    @field_validator("research_urls")
    @classmethod
    def normalize_research_urls(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("research URLs must not contain empty values")
        if len(set(normalized)) != len(normalized):
            raise ValueError("research URLs must be unique")
        return normalized

    @field_validator("research_search_query")
    @classmethod
    def normalize_research_search_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("research search query must not be empty")
        if len(normalized.split()) > 50:
            raise ValueError("research search query must contain at most 50 words")
        return normalized

    @model_validator(mode="after")
    def validate_research_source_mode(self) -> "AgentRunRequest":
        if self.research_urls and self.research_search_query:
            raise ValueError(
                "research_urls and research_search_query are mutually exclusive"
            )
        return self


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

    sources: list[dict[str, Any]] = Field(default_factory=list)

    usage: AgentUsage
    started_at: datetime
    completed_at: datetime
