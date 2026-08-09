import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from history.chat_schemas import (
    ChatConversationRecord,
    ChatConversationSummary,
    ChatMessageRecord,
    CreateChatConversationInput,
    CreateChatMessageInput,
    UpdateChatConversationInput,
    UpdateChatMessageInput,
)
from history.database import (
    HistoryDatabase,
    history_database,
)


class ChatHistoryRepository:
    def __init__(
        self,
        database: HistoryDatabase,
    ) -> None:
        self.database = database

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def create_conversation(
        self,
        data: CreateChatConversationInput,
    ) -> ChatConversationRecord:
        conversation_id = str(uuid4())
        now = self._now()

        title = data.title.strip() or "New chat"

        with self.database.connection() as connection:
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
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    conversation_id,
                    title,
                    data.preferred_role_id,
                    json.dumps(
                        data.settings,
                        ensure_ascii=False,
                    ),
                    now,
                    now,
                ),
            )

            connection.commit()

        record = self.get_conversation(
            conversation_id
        )

        if record is None:
            raise RuntimeError(
                "Created chat conversation "
                "could not be read."
            )

        return record

    def get_conversation(
        self,
        conversation_id: str,
    ) -> ChatConversationRecord | None:
        with self.database.connection() as connection:
            conversation_row = connection.execute(
                """
                SELECT *
                FROM chat_conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()

            if conversation_row is None:
                return None

            message_rows = connection.execute(
                """
                SELECT *
                FROM chat_messages
                WHERE conversation_id = ?
                ORDER BY sequence ASC
                """,
                (conversation_id,),
            ).fetchall()

        return self._row_to_conversation(
            conversation_row,
            message_rows,
        )

    def list_conversations(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        include_archived: bool = False,
    ) -> tuple[
        list[ChatConversationSummary],
        int,
    ]:
        conditions: list[str] = []
        parameters: list[Any] = []

        if not include_archived:
            conditions.append(
                "c.archived_at IS NULL"
            )

        if search:
            conditions.append(
                "c.title LIKE ?"
            )

            parameters.append(
                f"%{search}%"
            )

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE "
                + " AND ".join(conditions)
            )

        with self.database.connection() as connection:
            total_row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM chat_conversations c
                {where_clause}
                """,
                parameters,
            ).fetchone()

            rows = connection.execute(
                f"""
                SELECT
                    c.*,
                    (
                        SELECT COUNT(*)
                        FROM chat_messages m
                        WHERE
                            m.conversation_id =
                            c.conversation_id
                    ) AS message_count,
                    (
                        SELECT content
                        FROM chat_messages m
                        WHERE
                            m.conversation_id =
                            c.conversation_id
                        ORDER BY
                            m.sequence DESC
                        LIMIT 1
                    ) AS last_message
                FROM chat_conversations c
                {where_clause}
                ORDER BY c.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                [
                    *parameters,
                    limit,
                    offset,
                ],
            ).fetchall()

        total = int(
            total_row["total"]
            if total_row
            else 0
        )

        return (
            [
                self._row_to_summary(row)
                for row in rows
            ],
            total,
        )

    def update_conversation(
        self,
        conversation_id: str,
        data: UpdateChatConversationInput,
    ) -> ChatConversationRecord | None:
        changes = data.model_dump(
            exclude_unset=True
        )

        if not changes:
            return self.get_conversation(
                conversation_id
            )

        assignments: list[str] = []
        parameters: list[Any] = []

        if "title" in changes:
            title = (
                str(changes["title"]).strip()
            )

            if not title:
                title = "New chat"

            assignments.append(
                "title = ?"
            )
            parameters.append(title)

        if "preferred_role_id" in changes:
            assignments.append(
                "preferred_role_id = ?"
            )
            parameters.append(
                changes[
                    "preferred_role_id"
                ]
            )

        if "settings" in changes:
            assignments.append(
                "settings_json = ?"
            )
            parameters.append(
                json.dumps(
                    changes["settings"],
                    ensure_ascii=False,
                )
            )

        if "archived" in changes:
            assignments.append(
                "archived_at = ?"
            )

            parameters.append(
                self._now()
                if changes["archived"]
                else None
            )

        assignments.append(
            "updated_at = ?"
        )

        parameters.append(
            self._now()
        )

        parameters.append(
            conversation_id
        )

        with self.database.connection() as connection:
            cursor = connection.execute(
                f"""
                UPDATE chat_conversations
                SET {", ".join(assignments)}
                WHERE conversation_id = ?
                """,
                parameters,
            )

            connection.commit()

        if cursor.rowcount <= 0:
            return None

        return self.get_conversation(
            conversation_id
        )

    def delete_conversation(
        self,
        conversation_id: str,
    ) -> bool:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM chat_conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            )

            connection.commit()

        return cursor.rowcount > 0

    def create_message(
        self,
        conversation_id: str,
        data: CreateChatMessageInput,
    ) -> ChatMessageRecord | None:
        message_id = str(uuid4())
        now = self._now()

        with self.database.connection() as connection:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

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

            sequence_row = connection.execute(
                """
                SELECT
                    COALESCE(
                        MAX(sequence),
                        0
                    ) + 1 AS next_sequence
                FROM chat_messages
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()

            sequence = int(
                sequence_row[
                    "next_sequence"
                ]
            )

            connection.execute(
                """
                INSERT INTO chat_messages (
                    message_id,
                    conversation_id,
                    sequence,
                    role,
                    content,
                    employee_role_id,
                    employee_title,
                    department_name,
                    machine_agent_id,
                    run_id,
                    model,
                    routing_confidence,
                    status,
                    sources_json,
                    usage_json,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?
                )
                """,
                (
                    message_id,
                    conversation_id,
                    sequence,
                    data.role,
                    data.content,
                    data.employee_role_id,
                    data.employee_title,
                    data.department_name,
                    data.machine_agent_id,
                    data.run_id,
                    data.model,
                    data.routing_confidence,
                    data.status,
                    json.dumps(
                        data.sources,
                        ensure_ascii=False,
                        default=str,
                    ),
                    json.dumps(
                        data.usage,
                        ensure_ascii=False,
                        default=str,
                    ),
                    json.dumps(
                        data.metadata,
                        ensure_ascii=False,
                        default=str,
                    ),
                    now,
                    now,
                ),
            )

            connection.execute(
                """
                UPDATE chat_conversations
                SET updated_at = ?
                WHERE conversation_id = ?
                """,
                (
                    now,
                    conversation_id,
                ),
            )

            connection.commit()

        return self.get_message(
            conversation_id,
            message_id,
        )

    def get_message(
        self,
        conversation_id: str,
        message_id: str,
    ) -> ChatMessageRecord | None:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM chat_messages
                WHERE
                    conversation_id = ?
                    AND message_id = ?
                """,
                (
                    conversation_id,
                    message_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_message(row)

    def update_message(
        self,
        conversation_id: str,
        message_id: str,
        data: UpdateChatMessageInput,
    ) -> ChatMessageRecord | None:
        changes = data.model_dump(
            exclude_unset=True
        )

        if not changes:
            return self.get_message(
                conversation_id,
                message_id,
            )

        column_map = {
            "content": "content",
            "employee_role_id":
                "employee_role_id",
            "employee_title":
                "employee_title",
            "department_name":
                "department_name",
            "machine_agent_id":
                "machine_agent_id",
            "run_id": "run_id",
            "model": "model",
            "routing_confidence":
                "routing_confidence",
            "status": "status",
        }

        assignments: list[str] = []
        parameters: list[Any] = []

        for field, column in column_map.items():
            if field not in changes:
                continue

            assignments.append(
                f"{column} = ?"
            )

            parameters.append(
                changes[field]
            )

        for field, column in (
            ("sources", "sources_json"),
            ("usage", "usage_json"),
            ("metadata", "metadata_json"),
        ):
            if field not in changes:
                continue

            assignments.append(
                f"{column} = ?"
            )

            parameters.append(
                json.dumps(
                    changes[field],
                    ensure_ascii=False,
                    default=str,
                )
            )

        now = self._now()

        assignments.append(
            "updated_at = ?"
        )
        parameters.append(now)

        parameters.extend(
            [
                conversation_id,
                message_id,
            ]
        )

        with self.database.connection() as connection:
            cursor = connection.execute(
                f"""
                UPDATE chat_messages
                SET {", ".join(assignments)}
                WHERE
                    conversation_id = ?
                    AND message_id = ?
                """,
                parameters,
            )

            if cursor.rowcount > 0:
                connection.execute(
                    """
                    UPDATE chat_conversations
                    SET updated_at = ?
                    WHERE conversation_id = ?
                    """,
                    (
                        now,
                        conversation_id,
                    ),
                )

            connection.commit()

        if cursor.rowcount <= 0:
            return None

        return self.get_message(
            conversation_id,
            message_id,
        )

    @staticmethod
    def _load_json(
        value: str | None,
        fallback: Any,
    ) -> Any:
        if not value:
            return fallback

        try:
            return json.loads(value)
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            return fallback

    def _row_to_message(
        self,
        row: Any,
    ) -> ChatMessageRecord:
        return ChatMessageRecord(
            message_id=row["message_id"],
            conversation_id=(
                row["conversation_id"]
            ),
            sequence=row["sequence"],
            role=row["role"],
            content=row["content"],
            employee_role_id=(
                row["employee_role_id"]
            ),
            employee_title=(
                row["employee_title"]
            ),
            department_name=(
                row["department_name"]
            ),
            machine_agent_id=(
                row["machine_agent_id"]
            ),
            run_id=row["run_id"],
            model=row["model"],
            routing_confidence=(
                row["routing_confidence"]
            ),
            status=row["status"],
            sources=self._load_json(
                row["sources_json"],
                [],
            ),
            usage=self._load_json(
                row["usage_json"],
                {},
            ),
            metadata=self._load_json(
                row["metadata_json"],
                {},
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_conversation(
        self,
        row: Any,
        message_rows: list[Any],
    ) -> ChatConversationRecord:
        return ChatConversationRecord(
            conversation_id=(
                row["conversation_id"]
            ),
            title=row["title"],
            preferred_role_id=(
                row["preferred_role_id"]
            ),
            settings=self._load_json(
                row["settings_json"],
                {},
            ),
            messages=[
                self._row_to_message(
                    message
                )
                for message in message_rows
            ],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            archived_at=row["archived_at"],
        )

    def _row_to_summary(
        self,
        row: Any,
    ) -> ChatConversationSummary:
        last_message = (
            row["last_message"] or ""
        )

        preview = (
            last_message[:160]
            + (
                "…"
                if len(last_message) > 160
                else ""
            )
        )

        return ChatConversationSummary(
            conversation_id=(
                row["conversation_id"]
            ),
            title=row["title"],
            preferred_role_id=(
                row["preferred_role_id"]
            ),
            message_count=int(
                row["message_count"] or 0
            ),
            last_message_preview=preview,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            archived_at=row["archived_at"],
        )


chat_history_repository = (
    ChatHistoryRepository(
        history_database
    )
)
