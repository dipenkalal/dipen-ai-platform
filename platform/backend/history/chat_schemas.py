from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ChatMessageRole = Literal[
    "user",
    "assistant",
]

ChatMessageStatus = Literal[
    "routing",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class ChatMessageRecord(BaseModel):
    message_id: str
    conversation_id: str
    sequence: int
    role: ChatMessageRole
    content: str

    employee_role_id: str | None = None
    employee_title: str | None = None
    department_name: str | None = None
    machine_agent_id: str | None = None

    run_id: str | None = None
    model: str | None = None
    routing_confidence: float | None = None

    status: ChatMessageStatus = "completed"

    sources: list[dict[str, Any]] = Field(default_factory=list)

    usage: dict[str, Any] = Field(default_factory=dict)

    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime


class ChatConversationSummary(BaseModel):
    conversation_id: str
    title: str
    preferred_role_id: str | None = None

    message_count: int = 0
    last_message_preview: str = ""

    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class ChatConversationRecord(BaseModel):
    conversation_id: str
    title: str
    preferred_role_id: str | None = None

    settings: dict[str, Any] = Field(default_factory=dict)

    messages: list[ChatMessageRecord] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class ChatConversationListResponse(BaseModel):
    conversations: list[ChatConversationSummary]
    total: int
    limit: int
    offset: int


class ChatConversationDeleteResponse(BaseModel):
    deleted: bool
    conversation_id: str


class CreateChatConversationInput(BaseModel):
    title: str = Field(
        default="New chat",
        min_length=1,
        max_length=200,
    )

    preferred_role_id: str | None = "auto"

    settings: dict[str, Any] = Field(default_factory=dict)


class UpdateChatConversationInput(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    preferred_role_id: str | None = None

    settings: dict[str, Any] | None = None

    archived: bool | None = None


class CreateChatMessageInput(BaseModel):
    role: ChatMessageRole
    content: str = ""

    attachment_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    employee_role_id: str | None = None
    employee_title: str | None = None
    department_name: str | None = None
    machine_agent_id: str | None = None

    run_id: str | None = None
    model: str | None = None
    routing_confidence: float | None = None

    status: ChatMessageStatus = "completed"

    sources: list[dict[str, Any]] = Field(default_factory=list)

    usage: dict[str, Any] = Field(default_factory=dict)

    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateChatMessageInput(BaseModel):
    content: str | None = None

    employee_role_id: str | None = None
    employee_title: str | None = None
    department_name: str | None = None
    machine_agent_id: str | None = None

    run_id: str | None = None
    model: str | None = None
    routing_confidence: float | None = None

    status: ChatMessageStatus | None = None

    sources: list[dict[str, Any]] | None = None
    usage: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
