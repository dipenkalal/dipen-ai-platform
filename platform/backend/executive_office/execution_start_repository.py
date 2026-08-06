import json
import sqlite3
from dataclasses import dataclass

from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartResponse,
)
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import utc_now


class ExecutionStartStateConflictError(RuntimeError):
    """Raised when a reserved execution cannot be claimed safely."""


@dataclass(frozen=True)
class ExecutionIdentity:
    execution_id: str
    delegation_id: str
    child_task_ids: tuple[str, ...]
    state: str


@dataclass(frozen=True)
class ExecutionStartClaim:
    execution_id: str
    delegation_id: str
    parent_task_id: str
    child_task_ids: tuple[str, ...]
    selected_agent_ids: tuple[str, ...]
    reservation_ids: tuple[str, ...]


class ExecutiveExecutionStartRepository:
    def __init__(
        self,
        truth_repository: AgentTruthRepository,
    ) -> None:
        self.truth_repository = truth_repository
        self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS executive_execution_starts (
                    idempotency_key TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL UNIQUE,
                    request_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_starts_execution_id
                ON executive_execution_starts(execution_id)
                """
            )
            connection.commit()

    def get_identity(
        self,
        execution_id: str,
    ) -> ExecutionIdentity | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    execution_id,
                    delegation_id,
                    child_task_ids_json,
                    state
                FROM executive_execution_records
                WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()

        if row is None:
            return None

        return ExecutionIdentity(
            execution_id=str(row["execution_id"]),
            delegation_id=str(row["delegation_id"]),
            child_task_ids=tuple(
                str(item)
                for item in json.loads(
                    str(row["child_task_ids_json"])
                )
            ),
            state=str(row["state"]),
        )

    def get_replay(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> ExecutiveExecutionStartResponse | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    execution_id,
                    request_hash,
                    response_json
                FROM executive_execution_starts
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

            if row is None:
                return None

            return self._replay_from_row(
                connection=connection,
                execution_id=str(row["execution_id"]),
                row_request_hash=str(row["request_hash"]),
                response_json=(
                    str(row["response_json"])
                    if row["response_json"] is not None
                    else None
                ),
                request_hash=request_hash,
            )

    def claim(
        self,
        *,
        execution_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> ExecutionStartClaim | ExecutiveExecutionStartResponse:
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                existing_key = connection.execute(
                    """
                    SELECT
                        execution_id,
                        request_hash,
                        response_json
                    FROM executive_execution_starts
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()

                if existing_key is not None:
                    replay = self._replay_from_row(
                        connection=connection,
                        execution_id=str(existing_key["execution_id"]),
                        row_request_hash=str(
                            existing_key["request_hash"]
                        ),
                        response_json=(
                            str(existing_key["response_json"])
                            if existing_key["response_json"] is not None
                            else None
                        ),
                        request_hash=request_hash,
                    )
                    connection.commit()
                    return replay

                record = connection.execute(
                    """
                    SELECT
                        execution_id,
                        delegation_id,
                        parent_task_id,
                        child_task_ids_json,
                        selected_agent_ids_json,
                        reservation_ids_json,
                        state,
                        validation_only
                    FROM executive_execution_records
                    WHERE execution_id = ?
                    """,
                    (execution_id,),
                ).fetchone()

                if record is None:
                    raise ExecutionStartStateConflictError(
                        "The requested execution does not exist."
                    )
                if str(record["state"]) != "reserved":
                    raise ExecutionStartStateConflictError(
                        "The execution is not in reserved state."
                    )
                if bool(record["validation_only"]):
                    raise ExecutionStartStateConflictError(
                        "A validation-only execution cannot be started."
                    )

                existing_execution = connection.execute(
                    """
                    SELECT idempotency_key
                    FROM executive_execution_starts
                    WHERE execution_id = ?
                    """,
                    (execution_id,),
                ).fetchone()

                if existing_execution is not None:
                    raise ExecutionStartStateConflictError(
                        "The execution has already been claimed by another "
                        "start request."
                    )

                child_task_ids = tuple(
                    str(item)
                    for item in json.loads(
                        str(record["child_task_ids_json"])
                    )
                )
                selected_agent_ids = tuple(
                    str(item)
                    for item in json.loads(
                        str(record["selected_agent_ids_json"])
                    )
                )
                reservation_ids = tuple(
                    str(item)
                    for item in json.loads(
                        str(record["reservation_ids_json"])
                    )
                )

                if not child_task_ids or not (
                    len(child_task_ids)
                    == len(selected_agent_ids)
                    == len(reservation_ids)
                ):
                    raise ExecutionStartStateConflictError(
                        "The reserved execution mapping is incomplete."
                    )

                parent_task_id = str(record["parent_task_id"])
                delegation_id = str(record["delegation_id"])
                self._validate_reservations(
                    connection=connection,
                    execution_id=execution_id,
                    child_task_ids=child_task_ids,
                    selected_agent_ids=selected_agent_ids,
                    reservation_ids=reservation_ids,
                )
                self._validate_queued_tasks(
                    connection=connection,
                    delegation_id=delegation_id,
                    parent_task_id=parent_task_id,
                    child_task_ids=child_task_ids,
                    selected_agent_ids=selected_agent_ids,
                )

                claimed_at = utc_now().isoformat()
                connection.execute(
                    """
                    INSERT INTO executive_execution_starts (
                        idempotency_key,
                        execution_id,
                        request_hash,
                        status,
                        response_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, 'claimed', NULL, ?, ?)
                    """,
                    (
                        idempotency_key,
                        execution_id,
                        request_hash,
                        claimed_at,
                        claimed_at,
                    ),
                )
                updated = connection.execute(
                    """
                    UPDATE executive_execution_records
                    SET state = 'running', updated_at = ?
                    WHERE execution_id = ? AND state = 'reserved'
                    """,
                    (claimed_at, execution_id),
                )

                if updated.rowcount != 1:
                    raise ExecutionStartStateConflictError(
                        "The execution state changed before the start claim "
                        "committed."
                    )
            except (
                ExecutionStartStateConflictError,
                IdempotencyConflictError,
                sqlite3.IntegrityError,
            ) as error:
                connection.rollback()

                if isinstance(error, sqlite3.IntegrityError):
                    raise ExecutionStartStateConflictError(
                        "The execution start claim collided with another "
                        "request."
                    ) from error

                raise
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        return ExecutionStartClaim(
            execution_id=execution_id,
            delegation_id=delegation_id,
            parent_task_id=parent_task_id,
            child_task_ids=child_task_ids,
            selected_agent_ids=selected_agent_ids,
            reservation_ids=reservation_ids,
        )

    def complete(
        self,
        *,
        idempotency_key: str,
        response: ExecutiveExecutionStartResponse,
    ) -> ExecutiveExecutionStartResponse:
        if response.state not in {"completed", "failed"}:
            raise ValueError(
                "A released execution must be completed or failed."
            )

        now = response.generated_at.isoformat()

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                execution_updated = connection.execute(
                    """
                    UPDATE executive_execution_records
                    SET state = ?, updated_at = ?
                    WHERE execution_id = ? AND state = 'running'
                    """,
                    (response.state, now, response.execution_id),
                )

                if execution_updated.rowcount != 1:
                    raise ExecutionStartStateConflictError(
                        "The running execution changed before completion."
                    )

                connection.execute(
                    """
                    UPDATE executive_execution_reservations
                    SET released_at = ?
                    WHERE execution_id = ? AND released_at IS NULL
                    """,
                    (now, response.execution_id),
                )
                start_updated = connection.execute(
                    """
                    UPDATE executive_execution_starts
                    SET
                        status = ?,
                        response_json = ?,
                        updated_at = ?
                    WHERE
                        idempotency_key = ?
                        AND execution_id = ?
                        AND status = 'claimed'
                    """,
                    (
                        response.state,
                        response.model_dump_json(),
                        now,
                        idempotency_key,
                        response.execution_id,
                    ),
                )

                if start_updated.rowcount != 1:
                    raise ExecutionStartStateConflictError(
                        "The execution start claim changed before completion."
                    )
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        return response

    def mark_manual_review(
        self,
        *,
        idempotency_key: str,
        response: ExecutiveExecutionStartResponse,
    ) -> ExecutiveExecutionStartResponse:
        if response.state != "manual_review":
            raise ValueError(
                "Manual-review persistence requires manual_review state."
            )

        now = response.generated_at.isoformat()

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                connection.execute(
                    """
                    UPDATE executive_execution_records
                    SET state = 'manual_review', updated_at = ?
                    WHERE execution_id = ? AND state = 'running'
                    """,
                    (now, response.execution_id),
                )
                updated = connection.execute(
                    """
                    UPDATE executive_execution_starts
                    SET
                        status = 'manual_review',
                        response_json = ?,
                        updated_at = ?
                    WHERE
                        idempotency_key = ?
                        AND execution_id = ?
                        AND status = 'claimed'
                    """,
                    (
                        response.model_dump_json(),
                        now,
                        idempotency_key,
                        response.execution_id,
                    ),
                )

                if updated.rowcount != 1:
                    raise ExecutionStartStateConflictError(
                        "The execution start claim changed before manual review."
                    )
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        return response

    @staticmethod
    def _validate_reservations(
        *,
        connection: sqlite3.Connection,
        execution_id: str,
        child_task_ids: tuple[str, ...],
        selected_agent_ids: tuple[str, ...],
        reservation_ids: tuple[str, ...],
    ) -> None:
        rows = connection.execute(
            """
            SELECT reservation_id, agent_id, task_id
            FROM executive_execution_reservations
            WHERE execution_id = ? AND released_at IS NULL
            ORDER BY reservation_id
            """,
            (execution_id,),
        ).fetchall()
        expected = {
            (reservation_id, agent_id, task_id)
            for reservation_id, agent_id, task_id in zip(
                reservation_ids,
                selected_agent_ids,
                child_task_ids,
                strict=True,
            )
        }
        actual = {
            (
                str(row["reservation_id"]),
                str(row["agent_id"]),
                str(row["task_id"]),
            )
            for row in rows
        }

        if actual != expected:
            raise ExecutionStartStateConflictError(
                "The active execution reservations do not match the reserved "
                "task and agent mapping."
            )

    @staticmethod
    def _validate_queued_tasks(
        *,
        connection: sqlite3.Connection,
        delegation_id: str,
        parent_task_id: str,
        child_task_ids: tuple[str, ...],
        selected_agent_ids: tuple[str, ...],
    ) -> None:
        for task_id, agent_id in zip(
            child_task_ids,
            selected_agent_ids,
            strict=True,
        ):
            row = connection.execute(
                """
                SELECT
                    status,
                    source_run_id,
                    parent_task_id,
                    assigned_agent_ids_json
                FROM task_ledger
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()

            if row is None:
                raise ExecutionStartStateConflictError(
                    f"Reserved child task {task_id} is missing."
                )

            assigned_agent_ids = json.loads(
                str(row["assigned_agent_ids_json"])
            )
            valid = (
                str(row["status"]) == "queued"
                and str(row["source_run_id"]) == delegation_id
                and str(row["parent_task_id"]) == parent_task_id
                and assigned_agent_ids == [agent_id]
            )

            if not valid:
                raise ExecutionStartStateConflictError(
                    f"Reserved child task {task_id} is no longer queued for "
                    "the expected agent."
                )

    @staticmethod
    def _replay_from_row(
        *,
        connection: sqlite3.Connection,
        execution_id: str,
        row_request_hash: str,
        response_json: str | None,
        request_hash: str,
    ) -> ExecutiveExecutionStartResponse:
        if row_request_hash != request_hash:
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different "
                "Executive Office start request."
            )

        if response_json is not None:
            stored = ExecutiveExecutionStartResponse.model_validate_json(
                response_json
            )
            return stored.model_copy(
                update={
                    "disposition": "idempotent_replay",
                    "idempotent_replay": True,
                    "message": (
                        "Stored execution-start outcome returned without "
                        "invoking any agent again."
                    ),
                }
            )

        record = connection.execute(
            """
            SELECT delegation_id, child_task_ids_json, state
            FROM executive_execution_records
            WHERE execution_id = ?
            """,
            (execution_id,),
        ).fetchone()

        if record is None:
            raise ExecutionStartStateConflictError(
                "The claimed execution record is missing."
            )

        return ExecutiveExecutionStartResponse(
            execution_id=execution_id,
            delegation_id=str(record["delegation_id"]),
            child_task_ids=[
                str(item)
                for item in json.loads(
                    str(record["child_task_ids_json"])
                )
            ],
            disposition="idempotent_replay",
            state="running",
            execution_started=True,
            reservation_released=False,
            idempotent_replay=True,
            message=(
                "The execution start was already claimed and will not be "
                "invoked again. Reconcile the running execution state instead."
            ),
        )


executive_execution_start_repository = ExecutiveExecutionStartRepository(
    agent_truth_repository
)
