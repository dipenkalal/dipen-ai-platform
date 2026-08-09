from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from history.chat_attachment_repository import (
    ChatAttachmentRepository,
)
from history.chat_attachment_schemas import (
    CreatePendingChatAttachmentInput,
)
from history.chat_repository import (
    ChatHistoryRepository,
    ChatMessageAttachmentBindingError,
)
from history.chat_schemas import (
    CreateChatConversationInput,
    CreateChatMessageInput,
)
from history.chat_service import (
    ChatHistoryService,
)
from history.database import HistoryDatabase


def make_database(
    tmp_path: Path,
) -> HistoryDatabase:
    database = HistoryDatabase(tmp_path / "history.db")

    database.initialize()

    return database


def create_conversation(
    repository: ChatHistoryRepository,
    title: str,
) -> str:
    record = repository.create_conversation(
        CreateChatConversationInput(
            title=title,
            preferred_role_id="auto",
        )
    )

    return record.conversation_id


def create_attachment(
    repository: ChatAttachmentRepository,
    conversation_id: str,
    *,
    indexed: bool = True,
):
    attachment = repository.create_pending(
        conversation_id,
        CreatePendingChatAttachmentInput(
            filename="phase94f.txt",
            content_type="text/plain",
            size_bytes=32,
            sha256="a" * 64,
        ),
    )

    assert attachment is not None

    if not indexed:
        return attachment

    indexed_attachment = repository.mark_indexed(
        attachment.attachment_id,
        knowledge_document_id=str(uuid4()),
        chunk_count=1,
    )

    assert indexed_attachment is not None

    return indexed_attachment


def message_count(
    database: HistoryDatabase,
    conversation_id: str,
) -> int:
    with database.connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM chat_messages
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        ).fetchone()

    return int(row["total"])


def test_user_message_atomically_binds_attachment(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)

    messages = ChatHistoryRepository(database)

    attachments = ChatAttachmentRepository(database)

    conversation_id = create_conversation(
        messages,
        "Atomic bind",
    )

    attachment = create_attachment(
        attachments,
        conversation_id,
    )

    message = messages.create_message(
        conversation_id,
        CreateChatMessageInput(
            role="user",
            content="Analyse this file.",
            attachment_ids=[
                attachment.attachment_id,
            ],
        ),
    )

    assert message is not None

    bound = attachments.get_attachment(attachment.attachment_id)

    assert bound is not None
    assert bound.message_id == message.message_id
    assert (
        message_count(
            database,
            conversation_id,
        )
        == 1
    )


def test_cross_conversation_attachment_rolls_back_message(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)

    messages = ChatHistoryRepository(database)

    attachments = ChatAttachmentRepository(database)

    first = create_conversation(
        messages,
        "First",
    )

    second = create_conversation(
        messages,
        "Second",
    )

    attachment = create_attachment(
        attachments,
        second,
    )

    with pytest.raises(
        ChatMessageAttachmentBindingError,
        match="does not belong",
    ):
        messages.create_message(
            first,
            CreateChatMessageInput(
                role="user",
                content="Invalid bind",
                attachment_ids=[
                    attachment.attachment_id,
                ],
            ),
        )

    assert (
        message_count(
            database,
            first,
        )
        == 0
    )

    unchanged = attachments.get_attachment(attachment.attachment_id)

    assert unchanged is not None
    assert unchanged.message_id is None


def test_pending_attachment_rolls_back_message(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)

    messages = ChatHistoryRepository(database)

    attachments = ChatAttachmentRepository(database)

    conversation_id = create_conversation(
        messages,
        "Pending",
    )

    attachment = create_attachment(
        attachments,
        conversation_id,
        indexed=False,
    )

    with pytest.raises(
        ChatMessageAttachmentBindingError,
        match="must be indexed",
    ):
        messages.create_message(
            conversation_id,
            CreateChatMessageInput(
                role="user",
                content="Too early",
                attachment_ids=[
                    attachment.attachment_id,
                ],
            ),
        )

    assert (
        message_count(
            database,
            conversation_id,
        )
        == 0
    )


def test_attachment_cannot_be_rebound(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)

    messages = ChatHistoryRepository(database)

    attachments = ChatAttachmentRepository(database)

    conversation_id = create_conversation(
        messages,
        "No rebind",
    )

    attachment = create_attachment(
        attachments,
        conversation_id,
    )

    first = messages.create_message(
        conversation_id,
        CreateChatMessageInput(
            role="user",
            content="First",
            attachment_ids=[
                attachment.attachment_id,
            ],
        ),
    )

    assert first is not None

    with pytest.raises(
        ChatMessageAttachmentBindingError,
        match="already bound",
    ):
        messages.create_message(
            conversation_id,
            CreateChatMessageInput(
                role="user",
                content="Second",
                attachment_ids=[
                    attachment.attachment_id,
                ],
            ),
        )

    assert (
        message_count(
            database,
            conversation_id,
        )
        == 1
    )


def test_duplicate_attachment_ids_roll_back_message(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)

    messages = ChatHistoryRepository(database)

    attachments = ChatAttachmentRepository(database)

    conversation_id = create_conversation(
        messages,
        "Duplicate",
    )

    attachment = create_attachment(
        attachments,
        conversation_id,
    )

    with pytest.raises(
        ChatMessageAttachmentBindingError,
        match="must be unique",
    ):
        messages.create_message(
            conversation_id,
            CreateChatMessageInput(
                role="user",
                content="Duplicate",
                attachment_ids=[
                    attachment.attachment_id,
                    attachment.attachment_id,
                ],
            ),
        )

    assert (
        message_count(
            database,
            conversation_id,
        )
        == 0
    )


def test_assistant_message_cannot_claim_attachment(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)

    messages = ChatHistoryRepository(database)

    attachments = ChatAttachmentRepository(database)

    conversation_id = create_conversation(
        messages,
        "Assistant",
    )

    attachment = create_attachment(
        attachments,
        conversation_id,
    )

    with pytest.raises(
        ChatMessageAttachmentBindingError,
        match="user messages",
    ):
        messages.create_message(
            conversation_id,
            CreateChatMessageInput(
                role="assistant",
                content="No",
                attachment_ids=[
                    attachment.attachment_id,
                ],
            ),
        )

    assert (
        message_count(
            database,
            conversation_id,
        )
        == 0
    )


def test_service_maps_binding_conflict_to_409(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)

    repository = ChatHistoryRepository(database)

    attachments = ChatAttachmentRepository(database)

    conversation_id = create_conversation(
        repository,
        "Service",
    )

    attachment = create_attachment(
        attachments,
        conversation_id,
        indexed=False,
    )

    service = ChatHistoryService(repository)

    with pytest.raises(HTTPException) as captured:
        service.create_message(
            conversation_id,
            CreateChatMessageInput(
                role="user",
                content="Conflict",
                attachment_ids=[
                    attachment.attachment_id,
                ],
            ),
        )

    assert captured.value.status_code == 409

    assert (
        message_count(
            database,
            conversation_id,
        )
        == 0
    )
