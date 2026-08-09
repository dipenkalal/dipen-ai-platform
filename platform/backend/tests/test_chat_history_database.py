from datetime import datetime, timezone

from history.database import HistoryDatabase


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def test_chat_tables_initialize_idempotently(
    tmp_path,
) -> None:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()
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

    assert "chat_conversations" in tables
    assert "chat_messages" in tables

    assert (
        "idx_chat_conversations_updated_at"
        in indexes
    )

    assert (
        "idx_chat_messages_conversation_sequence"
        in indexes
    )


def test_deleting_conversation_cascades_messages(
    tmp_path,
) -> None:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()

    now = utc_now()

    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_conversations (
                conversation_id,
                title,
                preferred_role_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "conversation-1",
                "System health",
                "auto",
                now,
                now,
            ),
        )

        connection.execute(
            """
            INSERT INTO chat_messages (
                message_id,
                conversation_id,
                sequence,
                role,
                content,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "message-1",
                "conversation-1",
                1,
                "user",
                "Check the DAP system health.",
                now,
                now,
            ),
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
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                "message-2",
                "conversation-1",
                2,
                "assistant",
                "System health is good.",
                "systems-engineer",
                "Systems Engineer",
                "Infrastructure and Operations",
                "system-agent",
                "run-1",
                "qwen3:1.7b",
                0.99,
                now,
                now,
            ),
        )

        connection.commit()

        count_before = connection.execute(
            """
            SELECT COUNT(*)
            FROM chat_messages
            WHERE conversation_id = ?
            """,
            ("conversation-1",),
        ).fetchone()[0]

        assert count_before == 2

        connection.execute(
            """
            DELETE FROM chat_conversations
            WHERE conversation_id = ?
            """,
            ("conversation-1",),
        )

        connection.commit()

        count_after = connection.execute(
            """
            SELECT COUNT(*)
            FROM chat_messages
            WHERE conversation_id = ?
            """,
            ("conversation-1",),
        ).fetchone()[0]

    assert count_after == 0


def test_existing_history_tables_remain_available(
    tmp_path,
) -> None:
    database = HistoryDatabase(
        tmp_path / "history.db"
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

    assert "agent_runs" in tables
    assert "orchestration_runs" in tables
    assert "orchestration_task_runs" in tables
