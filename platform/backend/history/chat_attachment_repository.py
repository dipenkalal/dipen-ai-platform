import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from history.chat_attachment_schemas import (
    ChatAttachmentRecord,
    CreatePendingChatAttachmentInput,
)
from history.database import (
    HistoryDatabase,
    history_database,
)


class ChatAttachmentRepository:
    def __init__(
        self,
        database: HistoryDatabase,
    ) -> None:
        self.database = database

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def conversation_exists(
        self,
        conversation_id: str,
    ) -> bool:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM chat_conversations
                WHERE conversation_id = ?
                LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()

        return row is not None

    def create_pending(
        self,
        conversation_id: str,
        data: CreatePendingChatAttachmentInput,
    ) -> ChatAttachmentRecord | None:
        attachment_id = str(uuid4())

        now = self._now()

        with self.database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            conversation = connection.execute(
                """
                SELECT conversation_id
                FROM chat_conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()

            if conversation is None:
                connection.rollback()
                return None

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
                VALUES (
                    ?, ?, NULL, NULL,
                    ?, ?, ?, 0, ?,
                    'chat_owned',
                    'pending',
                    NULL,
                    ?, ?
                )
                """,
                (
                    attachment_id,
                    conversation_id,
                    data.filename,
                    data.content_type,
                    data.size_bytes,
                    data.sha256,
                    now,
                    now,
                ),
            )

            connection.commit()

        return self.get_attachment(attachment_id)

    def get_attachment(
        self,
        attachment_id: str,
    ) -> ChatAttachmentRecord | None:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM chat_attachments
                WHERE attachment_id = ?
                """,
                (attachment_id,),
            ).fetchone()

        if row is None:
            return None

        return self._attachment_from_row(row)

    def list_conversation_attachments(
        self,
        conversation_id: str,
    ) -> list[ChatAttachmentRecord]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM chat_attachments
                WHERE conversation_id = ?
                ORDER BY
                    created_at ASC,
                    attachment_id ASC
                """,
                (conversation_id,),
            ).fetchall()

        return [self._attachment_from_row(row) for row in rows]

    def list_message_attachments(
        self,
        conversation_id: str,
        message_id: str,
    ) -> list[ChatAttachmentRecord]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT attachment.*
                FROM chat_attachments AS attachment
                JOIN chat_messages AS message
                  ON message.message_id =
                     attachment.message_id
                 AND message.conversation_id =
                     attachment.conversation_id
                WHERE attachment.conversation_id = ?
                  AND attachment.message_id = ?
                  AND message.role = 'user'
                  AND attachment.status = 'indexed'
                  AND attachment.knowledge_document_id
                      IS NOT NULL
                ORDER BY
                    attachment.created_at ASC,
                    attachment.attachment_id ASC
                """,
                (
                    conversation_id,
                    message_id,
                ),
            ).fetchall()

        return [self._attachment_from_row(row) for row in rows]

    def bind_to_message(
        self,
        attachment_id: str,
        message_id: str,
    ) -> ChatAttachmentRecord | None:
        now = self._now()

        with self.database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            attachment = connection.execute(
                """
                SELECT
                    attachment_id,
                    conversation_id
                FROM chat_attachments
                WHERE attachment_id = ?
                """,
                (attachment_id,),
            ).fetchone()

            if attachment is None:
                connection.rollback()
                return None

            message = connection.execute(
                """
                SELECT
                    message_id,
                    conversation_id
                FROM chat_messages
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()

            if (
                message is None
                or message["conversation_id"] != attachment["conversation_id"]
            ):
                connection.rollback()
                return None

            connection.execute(
                """
                UPDATE chat_attachments
                SET
                    message_id = ?,
                    updated_at = ?
                WHERE attachment_id = ?
                """,
                (
                    message_id,
                    now,
                    attachment_id,
                ),
            )

            connection.commit()

        return self.get_attachment(attachment_id)

    def mark_indexed(
        self,
        attachment_id: str,
        *,
        knowledge_document_id: str,
        chunk_count: int,
    ) -> ChatAttachmentRecord | None:
        if not knowledge_document_id.strip():
            raise ValueError("knowledge_document_id is required")

        if chunk_count < 0:
            raise ValueError("chunk_count cannot be negative")

        now = self._now()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE chat_attachments
                SET
                    knowledge_document_id = ?,
                    chunk_count = ?,
                    status = 'indexed',
                    error = NULL,
                    updated_at = ?
                WHERE attachment_id = ?
                  AND status = 'pending'
                """,
                (
                    knowledge_document_id,
                    chunk_count,
                    now,
                    attachment_id,
                ),
            )

            connection.commit()

        if cursor.rowcount <= 0:
            return None

        return self.get_attachment(attachment_id)

    def mark_failed(
        self,
        attachment_id: str,
        error: str,
    ) -> ChatAttachmentRecord | None:
        now = self._now()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE chat_attachments
                SET
                    status = 'failed',
                    error = ?,
                    updated_at = ?
                WHERE attachment_id = ?
                  AND status = 'pending'
                """,
                (
                    error,
                    now,
                    attachment_id,
                ),
            )

            connection.commit()

        if cursor.rowcount <= 0:
            return None

        return self.get_attachment(attachment_id)

    def mark_cleanup_required(
        self,
        attachment_id: str,
        *,
        knowledge_document_id: str,
        error: str,
    ) -> ChatAttachmentRecord | None:
        if not knowledge_document_id.strip():
            raise ValueError("knowledge_document_id is required")

        now = self._now()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE chat_attachments
                SET
                    knowledge_document_id = ?,
                    status = 'deleting',
                    error = ?,
                    updated_at = ?
                WHERE attachment_id = ?
                  AND status = 'pending'
                """,
                (
                    knowledge_document_id,
                    error,
                    now,
                    attachment_id,
                ),
            )

            connection.commit()

        if cursor.rowcount <= 0:
            return None

        return self.get_attachment(attachment_id)

    def mark_deleting(
        self,
        attachment_id: str,
    ) -> ChatAttachmentRecord | None:
        now = self._now()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE chat_attachments
                SET
                    status = 'deleting',
                    error = NULL,
                    updated_at = ?
                WHERE attachment_id = ?
                  AND status = 'indexed'
                  AND knowledge_document_id
                      IS NOT NULL
                """,
                (
                    now,
                    attachment_id,
                ),
            )

            connection.commit()

        if cursor.rowcount > 0:
            return self.get_attachment(attachment_id)

        existing = self.get_attachment(attachment_id)

        if (
            existing is not None
            and existing.status == "deleting"
            and existing.knowledge_document_id is not None
        ):
            return existing

        return None

    def record_delete_error(
        self,
        attachment_id: str,
        error: str,
    ) -> ChatAttachmentRecord | None:
        now = self._now()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE chat_attachments
                SET
                    error = ?,
                    updated_at = ?
                WHERE attachment_id = ?
                  AND status = 'deleting'
                  AND knowledge_document_id
                      IS NOT NULL
                """,
                (
                    error,
                    now,
                    attachment_id,
                ),
            )

            connection.commit()

        if cursor.rowcount <= 0:
            return None

        return self.get_attachment(attachment_id)

    def delete_metadata(
        self,
        attachment_id: str,
    ) -> bool:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM chat_attachments
                WHERE attachment_id = ?
                """,
                (attachment_id,),
            )

            connection.commit()

        return cursor.rowcount > 0

    def list_cleanup_targets(
        self,
        conversation_id: str,
    ) -> list[ChatAttachmentRecord]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM chat_attachments
                WHERE conversation_id = ?
                  AND knowledge_document_id
                      IS NOT NULL
                ORDER BY
                    created_at ASC,
                    attachment_id ASC
                """,
                (conversation_id,),
            ).fetchall()

        return [self._attachment_from_row(row) for row in rows]

    @staticmethod
    def _attachment_from_row(
        row: sqlite3.Row,
    ) -> ChatAttachmentRecord:
        return ChatAttachmentRecord(
            attachment_id=(row["attachment_id"]),
            conversation_id=(row["conversation_id"]),
            message_id=(row["message_id"]),
            knowledge_document_id=(row["knowledge_document_id"]),
            filename=(row["filename"]),
            content_type=(row["content_type"]),
            size_bytes=int(row["size_bytes"]),
            chunk_count=int(row["chunk_count"]),
            sha256=(row["sha256"]),
            ownership=(row["ownership"]),
            status=(row["status"]),
            error=(row["error"]),
            created_at=(row["created_at"]),
            updated_at=(row["updated_at"]),
        )


chat_attachment_repository = ChatAttachmentRepository(history_database)
