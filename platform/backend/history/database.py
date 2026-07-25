import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


DEFAULT_DATABASE_PATH = (
    Path.home()
    / "dap"
    / "data"
    / "agent-history"
    / "agent-runs.db"
)


def get_database_path() -> Path:
    configured_path = os.getenv(
        "DAP_AGENT_HISTORY_DB"
    )

    if configured_path:
        return Path(configured_path).expanduser()

    return DEFAULT_DATABASE_PATH


class HistoryDatabase:
    def __init__(
        self,
        database_path: Path | None = None,
    ) -> None:
        self.database_path = (
            database_path
            or get_database_path()
        )

    def initialize(self) -> None:
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.connection() as connection:
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

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_agent_runs_started_at
                ON agent_runs(started_at DESC)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_agent_runs_agent_id
                ON agent_runs(agent_id)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_agent_runs_status
                ON agent_runs(status)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_agent_runs_model
                ON agent_runs(model)
                """
            )

            connection.commit()

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
            connection.execute(
                "PRAGMA foreign_keys = ON"
            )
            connection.execute(
                "PRAGMA journal_mode = WAL"
            )

            yield connection

        finally:
            connection.close()


history_database = HistoryDatabase()
