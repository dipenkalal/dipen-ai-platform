import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DATABASE_PATH = Path.home() / "dap" / "data" / "agent-history" / "agent-runs.db"


def get_database_path() -> Path:
    configured_path = os.getenv("DAP_AGENT_HISTORY_DB")

    if configured_path:
        return Path(configured_path).expanduser()

    return DEFAULT_DATABASE_PATH


class HistoryDatabase:
    def __init__(
        self,
        database_path: Path | None = None,
    ) -> None:
        self.database_path = database_path or get_database_path()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.connection() as connection:
            self._create_agent_runs_table(
                connection,
            )

            self._create_orchestration_runs_table(
                connection,
            )

            self._create_orchestration_task_runs_table(
                connection,
            )

            self._create_chat_conversations_table(
                connection,
            )

            self._create_chat_messages_table(
                connection,
            )

            self._create_indexes(
                connection,
            )

            connection.commit()

    @staticmethod
    def _create_agent_runs_table(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                objective TEXT NOT NULL,
                model TEXT,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                answer TEXT NOT NULL DEFAULT '',
                error TEXT,
                request_json TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                usage_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_orchestration_runs_table(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            orchestration_runs (
                run_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                objective TEXT NOT NULL,
                status TEXT NOT NULL,
                execution_mode TEXT NOT NULL,
                lead_agent_id TEXT NOT NULL,
                selected_agent_ids_json
                    TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                synthesis_json TEXT,
                validation_json TEXT,
                final_answer TEXT NOT NULL
                    DEFAULT '',
                usage_json TEXT NOT NULL,
                error TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _create_orchestration_task_runs_table(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            orchestration_task_runs (
                id INTEGER PRIMARY KEY
                    AUTOINCREMENT,
                orchestration_run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                depends_on_json TEXT NOT NULL,
                answer TEXT NOT NULL DEFAULT '',
                steps_json TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                usage_json TEXT NOT NULL,
                error TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (
                    orchestration_run_id
                )
                REFERENCES orchestration_runs (
                    run_id
                )
                ON DELETE CASCADE,
                UNIQUE (
                    orchestration_run_id,
                    task_id
                )
            )
            """
        )

    @staticmethod
    def _create_chat_conversations_table(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            chat_conversations (
                conversation_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                preferred_role_id TEXT,
                settings_json TEXT NOT NULL
                    DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT
            )
            """
        )

    @staticmethod
    def _create_chat_messages_table(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            chat_messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,

                employee_role_id TEXT,
                employee_title TEXT,
                department_name TEXT,
                machine_agent_id TEXT,

                run_id TEXT,
                model TEXT,
                routing_confidence REAL,

                status TEXT NOT NULL
                    DEFAULT 'completed',

                sources_json TEXT NOT NULL
                    DEFAULT '[]',
                usage_json TEXT NOT NULL
                    DEFAULT '{}',
                metadata_json TEXT NOT NULL
                    DEFAULT '{}',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (
                    conversation_id
                )
                REFERENCES chat_conversations (
                    conversation_id
                )
                ON DELETE CASCADE,

                UNIQUE (
                    conversation_id,
                    sequence
                )
            )
            """
        )

    @staticmethod
    def _create_indexes(
        connection: sqlite3.Connection,
    ) -> None:
        statements = (
            """
            CREATE INDEX IF NOT EXISTS
            idx_chat_conversations_updated_at
            ON chat_conversations(
                updated_at DESC
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_chat_conversations_archived_at
            ON chat_conversations(
                archived_at
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_chat_messages_conversation_sequence
            ON chat_messages(
                conversation_id,
                sequence
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_chat_messages_run_id
            ON chat_messages(
                run_id
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_agent_runs_started_at
            ON agent_runs(started_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_agent_runs_agent_id
            ON agent_runs(agent_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_agent_runs_status
            ON agent_runs(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_agent_runs_model
            ON agent_runs(model)
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_orchestration_runs_started_at
            ON orchestration_runs(
                started_at DESC
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_orchestration_runs_status
            ON orchestration_runs(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_orchestration_runs_mode
            ON orchestration_runs(
                execution_mode
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_orchestration_runs_lead
            ON orchestration_runs(
                lead_agent_id
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_orchestration_tasks_run_id
            ON orchestration_task_runs(
                orchestration_run_id
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_orchestration_tasks_agent
            ON orchestration_task_runs(
                agent_id
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_orchestration_tasks_status
            ON orchestration_task_runs(
                status
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS
            idx_orchestration_tasks_sequence
            ON orchestration_task_runs(
                orchestration_run_id,
                sequence
            )
            """,
        )

        for statement in statements:
            connection.execute(statement)

    @contextmanager
    def connection(
        self,
    ) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30.0,
        )

        connection.row_factory = sqlite3.Row

        try:
            connection.execute("PRAGMA foreign_keys = ON")

            connection.execute("PRAGMA journal_mode = WAL")

            yield connection

        finally:
            connection.close()


history_database = HistoryDatabase()
