import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from agents.truth_schemas import (
    AgentHeartbeat,
    TaskLedgerRecord,
)


DEFAULT_TRUTH_DATABASE_PATH = (
    Path.home()
    / "dap"
    / "data"
    / "agent-history"
    / "agent-truth.db"
)


def get_truth_database_path() -> Path:
    configured_path = os.getenv("DAP_AGENT_TRUTH_DB")

    if configured_path:
        return Path(configured_path).expanduser()

    return DEFAULT_TRUTH_DATABASE_PATH


class AgentTruthRepository:
    def __init__(
        self,
        database_path: Path | None = None,
    ) -> None:
        self.database_path = (
            database_path
            or get_truth_database_path()
        )
        self.initialize()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                agent_runtime_heartbeats (
                    agent_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_task_id TEXT,
                    model TEXT,
                    process_id INTEGER,
                    container_id TEXT,
                    details_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY (agent_id, worker_id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                task_ledger (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    assigned_agent_ids_json TEXT NOT NULL,
                    source_run_id TEXT,
                    parent_task_id TEXT,
                    current_step TEXT,
                    progress_percent REAL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_agent_runtime_observed_at
                ON agent_runtime_heartbeats(
                    observed_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_agent_runtime_status
                ON agent_runtime_heartbeats(status)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_task_ledger_updated_at
                ON task_ledger(updated_at DESC)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_task_ledger_status
                ON task_ledger(status)
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
                "PRAGMA journal_mode = WAL"
            )
            yield connection
        finally:
            connection.close()

    def record_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeat:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO agent_runtime_heartbeats (
                    agent_id,
                    worker_id,
                    status,
                    current_task_id,
                    model,
                    process_id,
                    container_id,
                    details_json,
                    observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id, worker_id)
                DO UPDATE SET
                    status = excluded.status,
                    current_task_id = excluded.current_task_id,
                    model = excluded.model,
                    process_id = excluded.process_id,
                    container_id = excluded.container_id,
                    details_json = excluded.details_json,
                    observed_at = excluded.observed_at
                """,
                (
                    heartbeat.agent_id,
                    heartbeat.worker_id,
                    heartbeat.status,
                    heartbeat.current_task_id,
                    heartbeat.model,
                    heartbeat.process_id,
                    heartbeat.container_id,
                    json.dumps(
                        heartbeat.details,
                        ensure_ascii=False,
                        default=str,
                    ),
                    heartbeat.observed_at.isoformat(),
                ),
            )
            connection.commit()

        stored = self.get_latest_heartbeat(
            heartbeat.agent_id
        )

        if stored is None:
            raise RuntimeError(
                "Heartbeat could not be read after save."
            )

        return stored

    def get_latest_heartbeat(
        self,
        agent_id: str,
    ) -> AgentHeartbeat | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM agent_runtime_heartbeats
                WHERE agent_id = ?
                ORDER BY observed_at DESC
                LIMIT 1
                """,
                (agent_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_heartbeat(row)

    def list_latest_heartbeats(
        self,
    ) -> dict[str, AgentHeartbeat]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM agent_runtime_heartbeats
                ORDER BY observed_at DESC
                """
            ).fetchall()

        latest: dict[str, AgentHeartbeat] = {}

        for row in rows:
            agent_id = str(row["agent_id"])

            if agent_id not in latest:
                latest[agent_id] = (
                    self._row_to_heartbeat(row)
                )

        return latest

    def upsert_task(
        self,
        task: TaskLedgerRecord,
    ) -> TaskLedgerRecord:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO task_ledger (
                    task_id,
                    task_type,
                    objective,
                    status,
                    priority,
                    requested_by,
                    assigned_agent_ids_json,
                    source_run_id,
                    parent_task_id,
                    current_step,
                    progress_percent,
                    error,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(task_id) DO UPDATE SET
                    task_type = excluded.task_type,
                    objective = excluded.objective,
                    status = excluded.status,
                    priority = excluded.priority,
                    requested_by = excluded.requested_by,
                    assigned_agent_ids_json =
                        excluded.assigned_agent_ids_json,
                    source_run_id = excluded.source_run_id,
                    parent_task_id = excluded.parent_task_id,
                    current_step = excluded.current_step,
                    progress_percent = excluded.progress_percent,
                    error = excluded.error,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at
                """,
                (
                    task.task_id,
                    task.task_type,
                    task.objective,
                    task.status,
                    task.priority,
                    task.requested_by,
                    json.dumps(
                        task.assigned_agent_ids,
                        ensure_ascii=False,
                    ),
                    task.source_run_id,
                    task.parent_task_id,
                    task.current_step,
                    task.progress_percent,
                    task.error,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    (
                        task.started_at.isoformat()
                        if task.started_at
                        else None
                    ),
                    (
                        task.completed_at.isoformat()
                        if task.completed_at
                        else None
                    ),
                ),
            )
            connection.commit()

        stored = self.get_task(task.task_id)

        if stored is None:
            raise RuntimeError(
                "Task could not be read after save."
            )

        return stored

    def get_task(
        self,
        task_id: str,
    ) -> TaskLedgerRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM task_ledger
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_task(row)

    def list_tasks(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[TaskLedgerRecord], int]:
        parameters: list[Any] = []
        where_clause = ""

        if status:
            where_clause = "WHERE status = ?"
            parameters.append(status)

        with self.connection() as connection:
            total_row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM task_ledger
                {where_clause}
                """,
                parameters,
            ).fetchone()

            rows = connection.execute(
                f"""
                SELECT *
                FROM task_ledger
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()

        total = int(
            total_row["total"]
            if total_row
            else 0
        )

        return (
            [self._row_to_task(row) for row in rows],
            total,
        )

    @staticmethod
    def _row_to_heartbeat(
        row: sqlite3.Row,
    ) -> AgentHeartbeat:
        return AgentHeartbeat(
            agent_id=row["agent_id"],
            worker_id=row["worker_id"],
            status=row["status"],
            current_task_id=row["current_task_id"],
            model=row["model"],
            process_id=row["process_id"],
            container_id=row["container_id"],
            details=json.loads(row["details_json"]),
            observed_at=row["observed_at"],
        )

    @staticmethod
    def _row_to_task(
        row: sqlite3.Row,
    ) -> TaskLedgerRecord:
        return TaskLedgerRecord(
            task_id=row["task_id"],
            task_type=row["task_type"],
            objective=row["objective"],
            status=row["status"],
            priority=row["priority"],
            requested_by=row["requested_by"],
            assigned_agent_ids=json.loads(
                row["assigned_agent_ids_json"]
            ),
            source_run_id=row["source_run_id"],
            parent_task_id=row["parent_task_id"],
            current_step=row["current_step"],
            progress_percent=row["progress_percent"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )


agent_truth_repository = AgentTruthRepository()
