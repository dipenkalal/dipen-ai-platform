from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ChatAttachmentOwnership = Literal["chat_owned",]

ChatAttachmentStatus = Literal[
    "pending",
    "indexed",
    "failed",
    "deleting",
]


ChatAttachmentCleanupResult = Literal[
    "not_required",
    "deleted",
    "already_missing",
]


class ChatAttachmentDeleteResponse(BaseModel):
    deleted: bool
    attachment_id: str
    knowledge_document_id: str | None = None
    cleanup_result: ChatAttachmentCleanupResult


class ChatAttachmentRecord(BaseModel):
    attachment_id: str
    conversation_id: str
    message_id: str | None = None

    knowledge_document_id: str | None = None

    filename: str
    content_type: str
    size_bytes: int
    chunk_count: int = 0

    sha256: str | None = None

    ownership: ChatAttachmentOwnership = "chat_owned"

    status: ChatAttachmentStatus = "pending"

    error: str | None = None

    created_at: datetime
    updated_at: datetime


class CreatePendingChatAttachmentInput(BaseModel):
    filename: str = Field(
        min_length=1,
        max_length=512,
    )

    content_type: str = Field(
        min_length=1,
        max_length=255,
    )

    size_bytes: int = Field(
        ge=0,
    )

    sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )


class ChatAttachmentListResponse(BaseModel):
    attachments: list[ChatAttachmentRecord]
    total: int


class ChatAttachmentContextRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=4000,
    )

    per_document_limit: int = Field(
        default=3,
        ge=1,
        le=10,
    )

    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    max_sources: int = Field(
        default=6,
        ge=1,
        le=20,
    )

    max_context_chars: int = Field(
        default=6000,
        ge=500,
        le=12000,
    )


class ChatAttachmentContextSource(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    chunk_index: int
    score: float
    excerpt: str


class ChatAttachmentContextResponse(BaseModel):
    context: str
    sources: list[ChatAttachmentContextSource]
    total: int
