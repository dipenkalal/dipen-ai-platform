from pathlib import Path

import pytest
from fastapi import HTTPException

from history.chat_repository import (
    ChatHistoryRepository,
)
from history.chat_schemas import (
    CreateChatConversationInput,
)
from history.chat_service import (
    ChatHistoryService,
)
from history.database import HistoryDatabase


class FakeAttachmentCleanupService:
    def __init__(
        self,
    ) -> None:
        self.cleaned: list[str] = []
        self.error: Exception | None = None

    async def cleanup_conversation_attachments(
        self,
        conversation_id: str,
    ) -> None:
        self.cleaned.append(
            conversation_id
        )

        if self.error is not None:
            raise self.error


def make_service(
    tmp_path: Path,
) -> tuple[
    ChatHistoryRepository,
    FakeAttachmentCleanupService,
    ChatHistoryService,
]:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()

    repository = ChatHistoryRepository(
        database
    )

    cleanup = (
        FakeAttachmentCleanupService()
    )

    service = ChatHistoryService(
        repository,
        attachment_service=cleanup,
    )

    return (
        repository,
        cleanup,
        service,
    )


@pytest.mark.asyncio
async def test_conversation_delete_runs_external_cleanup_first(
    tmp_path: Path,
) -> None:
    (
        repository,
        cleanup,
        service,
    ) = make_service(
        tmp_path
    )

    conversation = (
        repository.create_conversation(
            CreateChatConversationInput(
                title="Delete lifecycle",
            )
        )
    )

    result = (
        await service.delete_conversation(
            conversation.conversation_id
        )
    )

    assert result.deleted

    assert cleanup.cleaned == [
        conversation.conversation_id
    ]

    assert (
        repository.get_conversation(
            conversation.conversation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_cleanup_failure_preserves_conversation(
    tmp_path: Path,
) -> None:
    (
        repository,
        cleanup,
        service,
    ) = make_service(
        tmp_path
    )

    conversation = (
        repository.create_conversation(
            CreateChatConversationInput(
                title="Preserve on failure",
            )
        )
    )

    cleanup.error = HTTPException(
        status_code=502,
        detail="Knowledge unavailable",
    )

    with pytest.raises(
        HTTPException
    ):
        await service.delete_conversation(
            conversation.conversation_id
        )

    assert (
        repository.get_conversation(
            conversation.conversation_id
        )
        is not None
    )


@pytest.mark.asyncio
async def test_missing_conversation_does_not_run_cleanup(
    tmp_path: Path,
) -> None:
    (
        _,
        cleanup,
        service,
    ) = make_service(
        tmp_path
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.delete_conversation(
            "missing"
        )

    assert (
        exc_info.value.status_code
        == 404
    )

    assert cleanup.cleaned == []
