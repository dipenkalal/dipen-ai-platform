import sqlite3
from pathlib import Path

import pytest

from history.chat_attachment_repository import (
    ChatAttachmentRepository,
)
from history.chat_attachment_schemas import (
    CreatePendingChatAttachmentInput,
)
from history.database import HistoryDatabase


def make_repository(
    tmp_path: Path,
) -> tuple[
    HistoryDatabase,
    ChatAttachmentRepository,
]:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()

    return (
        database,
        ChatAttachmentRepository(
            database
        ),
    )


def insert_conversation(
    database: HistoryDatabase,
    conversation_id: str,
) -> None:
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_conversations (
                conversation_id,
                title,
                preferred_role_id,
                settings_json,
                created_at,
                updated_at,
                archived_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                "Attachment repository test",
                "auto",
                "{}",
                "2026-08-09T12:00:00+00:00",
                "2026-08-09T12:00:00+00:00",
                None,
            ),
        )

        connection.commit()


def insert_message(
    database: HistoryDatabase,
    *,
    conversation_id: str,
    message_id: str,
    sequence: int = 1,
) -> None:
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_messages (
                message_id,
                conversation_id,
                sequence,
                role,
                content,
                status,
                sources_json,
                usage_json,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                message_id,
                conversation_id,
                sequence,
                "user",
                "Review this attachment.",
                "completed",
                "[]",
                "{}",
                "{}",
                "2026-08-09T12:00:00+00:00",
                "2026-08-09T12:00:00+00:00",
            ),
        )

        connection.commit()


def pending_input(
    filename: str = "example.pdf",
) -> CreatePendingChatAttachmentInput:
    return CreatePendingChatAttachmentInput(
        filename=filename,
        content_type="application/pdf",
        size_bytes=1234,
        sha256="a" * 64,
    )


def test_create_pending_attachment(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    attachment = repository.create_pending(
        "conversation-1",
        pending_input(),
    )

    assert attachment is not None
    assert (
        attachment.conversation_id
        == "conversation-1"
    )
    assert attachment.message_id is None

    assert (
        attachment.knowledge_document_id
        is None
    )

    assert attachment.status == "pending"
    assert (
        attachment.ownership
        == "chat_owned"
    )
    assert attachment.chunk_count == 0
    assert attachment.sha256 == "a" * 64


def test_create_pending_requires_existing_conversation(
    tmp_path: Path,
) -> None:
    _, repository = (
        make_repository(tmp_path)
    )

    attachment = repository.create_pending(
        "missing",
        pending_input(),
    )

    assert attachment is None


def test_get_and_list_conversation_attachments(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    first = repository.create_pending(
        "conversation-1",
        pending_input(
            "first.pdf"
        ),
    )

    second = repository.create_pending(
        "conversation-1",
        pending_input(
            "second.pdf"
        ),
    )

    assert first is not None
    assert second is not None

    loaded = repository.get_attachment(
        first.attachment_id
    )

    assert loaded is not None
    assert loaded.filename == "first.pdf"

    records = (
        repository
        .list_conversation_attachments(
            "conversation-1"
        )
    )

    assert len(records) == 2

    assert {
        record.filename
        for record in records
    } == {
        "first.pdf",
        "second.pdf",
    }


def test_bind_to_message_same_conversation(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    insert_message(
        database,
        conversation_id="conversation-1",
        message_id="message-1",
    )

    attachment = repository.create_pending(
        "conversation-1",
        pending_input(),
    )

    assert attachment is not None

    bound = repository.bind_to_message(
        attachment.attachment_id,
        "message-1",
    )

    assert bound is not None
    assert (
        bound.message_id
        == "message-1"
    )


def test_bind_rejects_message_from_other_conversation(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    insert_conversation(
        database,
        "conversation-2",
    )

    insert_message(
        database,
        conversation_id="conversation-2",
        message_id="message-2",
    )

    attachment = repository.create_pending(
        "conversation-1",
        pending_input(),
    )

    assert attachment is not None

    bound = repository.bind_to_message(
        attachment.attachment_id,
        "message-2",
    )

    assert bound is None

    unchanged = repository.get_attachment(
        attachment.attachment_id
    )

    assert unchanged is not None
    assert unchanged.message_id is None


def test_mark_indexed(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    attachment = repository.create_pending(
        "conversation-1",
        pending_input(),
    )

    assert attachment is not None

    indexed = repository.mark_indexed(
        attachment.attachment_id,
        knowledge_document_id=(
            "document-1"
        ),
        chunk_count=7,
    )

    assert indexed is not None

    assert (
        indexed.knowledge_document_id
        == "document-1"
    )

    assert indexed.chunk_count == 7
    assert indexed.status == "indexed"
    assert indexed.error is None


def test_mark_indexed_requires_pending_state(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    attachment = repository.create_pending(
        "conversation-1",
        pending_input(),
    )

    assert attachment is not None

    failed = repository.mark_failed(
        attachment.attachment_id,
        "Upload failed",
    )

    assert failed is not None

    indexed = repository.mark_indexed(
        attachment.attachment_id,
        knowledge_document_id=(
            "document-1"
        ),
        chunk_count=1,
    )

    assert indexed is None


def test_knowledge_document_id_remains_unique(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    first = repository.create_pending(
        "conversation-1",
        pending_input(
            "first.pdf"
        ),
    )

    second = repository.create_pending(
        "conversation-1",
        pending_input(
            "second.pdf"
        ),
    )

    assert first is not None
    assert second is not None

    indexed = repository.mark_indexed(
        first.attachment_id,
        knowledge_document_id=(
            "document-1"
        ),
        chunk_count=1,
    )

    assert indexed is not None

    with pytest.raises(
        sqlite3.IntegrityError
    ):
        repository.mark_indexed(
            second.attachment_id,
            knowledge_document_id=(
                "document-1"
            ),
            chunk_count=1,
        )


def test_mark_failed(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    attachment = repository.create_pending(
        "conversation-1",
        pending_input(),
    )

    assert attachment is not None

    failed = repository.mark_failed(
        attachment.attachment_id,
        "Embedding service unavailable",
    )

    assert failed is not None
    assert failed.status == "failed"

    assert (
        failed.error
        == "Embedding service unavailable"
    )

    assert (
        failed.knowledge_document_id
        is None
    )


def test_mark_deleting_requires_indexed_attachment(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    attachment = repository.create_pending(
        "conversation-1",
        pending_input(),
    )

    assert attachment is not None

    assert (
        repository.mark_deleting(
            attachment.attachment_id
        )
        is None
    )

    indexed = repository.mark_indexed(
        attachment.attachment_id,
        knowledge_document_id=(
            "document-1"
        ),
        chunk_count=3,
    )

    assert indexed is not None

    deleting = repository.mark_deleting(
        attachment.attachment_id
    )

    assert deleting is not None
    assert deleting.status == "deleting"

    assert (
        deleting.knowledge_document_id
        == "document-1"
    )


def test_cleanup_targets_only_include_document_backed_records(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    indexed = repository.create_pending(
        "conversation-1",
        pending_input(
            "indexed.pdf"
        ),
    )

    pending = repository.create_pending(
        "conversation-1",
        pending_input(
            "pending.pdf"
        ),
    )

    assert indexed is not None
    assert pending is not None

    indexed_record = (
        repository.mark_indexed(
            indexed.attachment_id,
            knowledge_document_id=(
                "document-1"
            ),
            chunk_count=4,
        )
    )

    assert indexed_record is not None

    targets = (
        repository
        .list_cleanup_targets(
            "conversation-1"
        )
    )

    assert len(targets) == 1

    assert (
        targets[0].attachment_id
        == indexed.attachment_id
    )

    assert (
        targets[0].knowledge_document_id
        == "document-1"
    )


def test_delete_metadata(
    tmp_path: Path,
) -> None:
    database, repository = (
        make_repository(tmp_path)
    )

    insert_conversation(
        database,
        "conversation-1",
    )

    attachment = repository.create_pending(
        "conversation-1",
        pending_input(),
    )

    assert attachment is not None

    assert repository.delete_metadata(
        attachment.attachment_id
    )

    assert (
        repository.get_attachment(
            attachment.attachment_id
        )
        is None
    )

    assert not repository.delete_metadata(
        attachment.attachment_id
    )
