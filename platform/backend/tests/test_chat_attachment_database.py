import sqlite3
from pathlib import Path

import pytest

from history.database import HistoryDatabase


def make_database(
    tmp_path: Path,
) -> HistoryDatabase:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()

    return database


def create_conversation(
    connection: sqlite3.Connection,
    conversation_id: str = "conversation-1",
) -> None:
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
            "Attachment test",
            "auto",
            "{}",
            "2026-08-09T12:00:00+00:00",
            "2026-08-09T12:00:00+00:00",
            None,
        ),
    )


def create_message(
    connection: sqlite3.Connection,
    *,
    message_id: str = "message-1",
    conversation_id: str = "conversation-1",
) -> None:
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            conversation_id,
            1,
            "user",
            "Review the attachment.",
            "completed",
            "[]",
            "{}",
            "{}",
            "2026-08-09T12:00:00+00:00",
            "2026-08-09T12:00:00+00:00",
        ),
    )


def create_attachment(
    connection: sqlite3.Connection,
    *,
    attachment_id: str = "attachment-1",
    conversation_id: str = "conversation-1",
    message_id: str | None = None,
    knowledge_document_id: str | None = "document-1",
    ownership: str = "chat_owned",
    status: str = "indexed",
) -> None:
    connection.execute(
        """
        INSERT INTO chat_attachments (
            attachment_id,
            conversation_id,
            message_id,
            knowledge_document_id,
            filename,
            content_type,
            size_bytes,
            chunk_count,
            sha256,
            ownership,
            status,
            error,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attachment_id,
            conversation_id,
            message_id,
            knowledge_document_id,
            "example.pdf",
            "application/pdf",
            1234,
            3,
            "abc123",
            ownership,
            status,
            None,
            "2026-08-09T12:00:00+00:00",
            "2026-08-09T12:00:00+00:00",
        ),
    )


def test_attachment_table_initializes_idempotently(
    tmp_path: Path,
) -> None:
    database = make_database(
        tmp_path
    )

    database.initialize()

    with database.connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        indexes = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            )
        }

    assert "chat_attachments" in tables

    assert (
        "idx_chat_attachments_conversation_created"
        in indexes
    )

    assert (
        "idx_chat_attachments_message_id"
        in indexes
    )

    assert (
        "idx_chat_attachments_status"
        in indexes
    )


def test_attachment_accepts_unbound_pending_record(
    tmp_path: Path,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)

        create_attachment(
            connection,
            message_id=None,
            knowledge_document_id=None,
            status="pending",
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT
                message_id,
                ownership,
                status
            FROM chat_attachments
            WHERE attachment_id = ?
            """,
            ("attachment-1",),
        ).fetchone()

    assert row is not None
    assert row["message_id"] is None
    assert row["ownership"] == "chat_owned"
    assert row["status"] == "pending"


def test_multiple_pending_attachments_can_have_no_document_id(
    tmp_path: Path,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)

        create_attachment(
            connection,
            attachment_id="attachment-1",
            knowledge_document_id=None,
            status="pending",
        )

        create_attachment(
            connection,
            attachment_id="attachment-2",
            knowledge_document_id=None,
            status="pending",
        )

        connection.commit()

        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM chat_attachments
            WHERE knowledge_document_id IS NULL
            """
        ).fetchone()[0]

    assert count == 2


@pytest.mark.parametrize(
    "status",
    [
        "indexed",
        "deleting",
    ],
)
def test_indexed_or_deleting_attachment_requires_document_id(
    tmp_path: Path,
    status: str,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            create_attachment(
                connection,
                knowledge_document_id=None,
                status=status,
            )


def test_failed_attachment_can_have_no_document_id(
    tmp_path: Path,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)

        create_attachment(
            connection,
            knowledge_document_id=None,
            status="failed",
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT status, knowledge_document_id
            FROM chat_attachments
            WHERE attachment_id = ?
            """,
            ("attachment-1",),
        ).fetchone()

    assert row is not None
    assert row["status"] == "failed"
    assert row["knowledge_document_id"] is None


def test_attachment_knowledge_document_id_is_unique(
    tmp_path: Path,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)

        create_attachment(
            connection,
            attachment_id="attachment-1",
            knowledge_document_id="document-1",
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            create_attachment(
                connection,
                attachment_id="attachment-2",
                knowledge_document_id="document-1",
            )


def test_conversation_delete_cascades_attachment_metadata(
    tmp_path: Path,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)

        create_attachment(
            connection
        )

        connection.execute(
            """
            DELETE FROM chat_conversations
            WHERE conversation_id = ?
            """,
            ("conversation-1",),
        )

        connection.commit()

        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM chat_attachments
            """
        ).fetchone()[0]

    assert count == 0


def test_message_delete_unbinds_attachment(
    tmp_path: Path,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)
        create_message(connection)

        create_attachment(
            connection,
            message_id="message-1",
        )

        connection.execute(
            """
            DELETE FROM chat_messages
            WHERE message_id = ?
            """,
            ("message-1",),
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT message_id
            FROM chat_attachments
            WHERE attachment_id = ?
            """,
            ("attachment-1",),
        ).fetchone()

    assert row is not None
    assert row["message_id"] is None


@pytest.mark.parametrize(
    "ownership",
    [
        "global",
        "knowledge_reference",
        "unknown",
    ],
)
def test_attachment_rejects_non_chat_ownership(
    tmp_path: Path,
    ownership: str,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            create_attachment(
                connection,
                ownership=ownership,
            )


@pytest.mark.parametrize(
    "status",
    [
        "uploaded",
        "completed",
        "unknown",
    ],
)
def test_attachment_rejects_invalid_status(
    tmp_path: Path,
    status: str,
) -> None:
    database = make_database(
        tmp_path
    )

    with database.connection() as connection:
        create_conversation(connection)

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            create_attachment(
                connection,
                status=status,
            )
