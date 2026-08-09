from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ChatAttachmentOwnership = Literal[
    "chat_owned",
]

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

    ownership: ChatAttachmentOwnership = (
        "chat_owned"
    )

    status: ChatAttachmentStatus = (
        "pending"
    )

    error: str | None = None

    created_at: datetime
    updated_at: datetime


class CreatePendingChatAttachmentInput(
    BaseModel
):
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
