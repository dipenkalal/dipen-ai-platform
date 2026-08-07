import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from executive_office.execution_recovery_schemas import (
    ExecutiveExecutionControlResponse,
)
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartResponse,
)
from executive_office.repository import IdempotencyConflictError


class ExecutionControlStateConflictError(RuntimeError):
    """Raised when cancellation or recovery loses its expected state."""


@dataclass(frozen=True)
class ExecutionRecoverySnapshot:
    execution_id: str
    delegation_id: str
    parent_task_id: str
    child_task_ids: tuple[str, ...]
    selected_agent_ids: tuple[str, ...]
    reservation_ids: tuple[str, ...]
    active_reservation_ids: tuple[str, ...]
    state: str
    validation_only: bool
    updated_at: datetime
    start_idempotency_key: str | None
    start_status: str | None
    start_updated_at: datetime | None
    start_response: ExecutiveExecutionStartResponse | None


class ExecutiveExecutionRecoveryRepository:
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
                CREATE TABLE IF NOT EXISTS executive_execution_controls (
                    idempotency_key TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_controls_execution_id
                ON executive_execution_controls(execution_id)
                """
            )
            connection.commit()

    def get_snapshot(
        self,
        execution_id: str,
    ) -> ExecutionRecoverySnapshot | None:
        with self.truth_repository.connection() as connection:
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
                    validation_only,
                    updated_at
                FROM executive_execution_records
                WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()

            if record is None:
                return None

            reservations = connection.execute(
                """
                SELECT reservation_id
                FROM executive_execution_reservations
                WHERE execution_id = ? AND released_at IS NULL
                ORDER BY reservation_id
                """,
                (execution_id,),
            ).fetchall()
            start = connection.execute(
                """
                SELECT
                    idempotency_key,
                    status,
                    response_json,
                    updated_at
                FROM executive_execution_starts
                WHERE execution_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (execution_id,),
            ).fetchone()

        start_response: ExecutiveExecutionStartResponse | None = None

        if start is not None and start["response_json"] is not None:
            try:
                start_response = (
                    ExecutiveExecutionStartResponse.model_validate_json(
                        str(start["response_json"])
                    )
                )
            except ValueError:
                start_response = None

        return ExecutionRecoverySnapshot(
            execution_id=str(record["execution_id"]),
            delegation_id=str(record["delegation_id"]),
            parent_task_id=str(record["parent_task_id"]),
            child_task_ids=self._json_tuple(
                str(record["child_task_ids_json"])
            ),
            selected_agent_ids=self._json_tuple(
                str(record["selected_agent_ids_json"])
            ),
            reservation_ids=self._json_tuple(
                str(record["reservation_ids_json"])
            ),
            active_reservation_ids=tuple(
                str(row["reservation_id"])
                for row in reservations
            ),
            state=str(record["state"]),
            validation_only=bool(record["validation_only"]),
            updated_at=self._parse_datetime(str(record["updated_at"])),
            start_idempotency_key=(
                str(start["idempotency_key"])
                if start is not None
                else None
            ),
            start_status=(
                str(start["status"])
                if start is not None
                else None
            ),
            start_updated_at=(
                self._parse_datetime(str(start["updated_at"]))
                if start is not None
                else None
            ),
            start_response=start_response,
        )

    def get_replay(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> ExecutiveExecutionControlResponse | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT request_hash, response_json
                FROM executive_execution_controls
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

        if row is None:
            return None

        return self._replay_from_row(
            row_request_hash=str(row["request_hash"]),
            row_response_json=str(row["response_json"]),
            request_hash=request_hash,
        )

    def persist(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveExecutionControlResponse,
    ) -> ExecutiveExecutionControlResponse:
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT request_hash, response_json
                FROM executive_execution_controls
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

            if existing is not None:
                replay = self._replay_from_row(
                    row_request_hash=str(existing["request_hash"]),
                    row_response_json=str(existing["response_json"]),
                    request_hash=request_hash,
                )
                connection.commit()
                return replay

            self._insert_control(
                connection=connection,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
            )
            connection.commit()

        return response

    def cancel_reserved(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveExecutionControlResponse,
        snapshot: ExecutionRecoverySnapshot,
    ) -> ExecutiveExecutionControlResponse:
        now = response.generated_at.isoformat()

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                existing = connection.execute(
                    """
                    SELECT request_hash, response_json
                    FROM executive_execution_controls
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()

                if existing is not None:
                    replay = self._replay_from_row(
                        row_request_hash=str(existing["request_hash"]),
                        row_response_json=str(existing["response_json"]),
                        request_hash=request_hash,
                    )
                    connection.commit()
                    return replay

                self._validate_snapshot_identity(
                    connection=connection,
                    snapshot=snapshot,
                    expected_states={"reserved"},
                )

                if snapshot.validation_only:
                    raise ExecutionControlStateConflictError(
                        "Validation-only execution records cannot be cancelled."
                    )

                start = connection.execute(
                    """
                    SELECT 1
                    FROM executive_execution_starts
                    WHERE execution_id = ?
                    LIMIT 1
                    """,
                    (snapshot.execution_id,),
                ).fetchone()

                if start is not None:
                    raise ExecutionControlStateConflictError(
                        "The execution crossed the start-claim boundary and "
                        "cannot be force-cancelled."
                    )

                self._validate_queued_children(
                    connection=connection,
                    snapshot=snapshot,
                )

                for task_id in snapshot.child_task_ids:
                    updated = connection.execute(
                        """
                        UPDATE task_ledger
                        SET
                            status = 'cancelled',
                            current_step = ?,
                            progress_percent = 0.0,
                            updated_at = ?,
                            completed_at = ?
                        WHERE
                            task_id = ?
                            AND status = 'queued'
                            AND source_run_id = ?
                            AND parent_task_id = ?
                        """,
                        (
                            "Cancelled by explicit owner control before "
                            "executor start.",
                            now,
                            now,
                            task_id,
                            snapshot.delegation_id,
                            snapshot.parent_task_id,
                        ),
                    )

                    if updated.rowcount != 1:
                        raise ExecutionControlStateConflictError(
                            f"Child task {task_id} changed before cancellation."
                        )

                released = connection.execute(
                    """
                    UPDATE executive_execution_reservations
                    SET released_at = ?
                    WHERE execution_id = ? AND released_at IS NULL
                    """,
                    (now, snapshot.execution_id),
                )

                if released.rowcount != len(snapshot.reservation_ids):
                    raise ExecutionControlStateConflictError(
                        "Active reservations changed before cancellation."
                    )

                execution = connection.execute(
                    """
                    UPDATE executive_execution_records
                    SET state = 'cancelled', updated_at = ?
                    WHERE execution_id = ? AND state = 'reserved'
                    """,
                    (now, snapshot.execution_id),
                )

                if execution.rowcount != 1:
                    raise ExecutionControlStateConflictError(
                        "Execution state changed before cancellation committed."
                    )

                self._update_parent(
                    connection=connection,
                    snapshot=snapshot,
                    target_status="manual_review",
                    now=now,
                )
                self._insert_control(
                    connection=connection,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                )
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        return response

    def finalize_recovery(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveExecutionControlResponse,
        snapshot: ExecutionRecoverySnapshot,
        start_response: ExecutiveExecutionStartResponse,
        target_state: str,
        release_reservations: bool,
        freeze_nonterminal: bool,
    ) -> ExecutiveExecutionControlResponse:
        if target_state not in {
            "completed",
            "failed",
            "manual_review",
        }:
            raise ValueError("Unsupported recovery terminal state.")

        now = response.generated_at.isoformat()

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                existing = connection.execute(
                    """
                    SELECT request_hash, response_json
                    FROM executive_execution_controls
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()

                if existing is not None:
                    replay = self._replay_from_row(
                        row_request_hash=str(existing["request_hash"]),
                        row_response_json=str(existing["response_json"]),
                        request_hash=request_hash,
                    )
                    connection.commit()
                    return replay

                self._validate_snapshot_identity(
                    connection=connection,
                    snapshot=snapshot,
                    expected_states={"running", "manual_review"},
                )

                if freeze_nonterminal:
                    for task_id in snapshot.child_task_ids:
                        connection.execute(
                            """
                            UPDATE task_ledger
                            SET
                                status = 'manual_review',
                                current_step = ?,
                                updated_at = ?
                            WHERE
                                task_id = ?
                                AND source_run_id = ?
                                AND parent_task_id = ?
                                AND status IN (
                                    'assigned',
                                    'queued',
                                    'running',
                                    'waiting'
                                )
                            """,
                            (
                                "Recovery found an ambiguous interrupted "
                                "execution; owner review is required.",
                                now,
                                task_id,
                                snapshot.delegation_id,
                                snapshot.parent_task_id,
                            ),
                        )

                if release_reservations:
                    connection.execute(
                        """
                        UPDATE executive_execution_reservations
                        SET released_at = ?
                        WHERE execution_id = ? AND released_at IS NULL
                        """,
                        (now, snapshot.execution_id),
                    )

                execution = connection.execute(
                    """
                    UPDATE executive_execution_records
                    SET state = ?, updated_at = ?
                    WHERE
                        execution_id = ?
                        AND state IN ('running', 'manual_review')
                    """,
                    (target_state, now, snapshot.execution_id),
                )

                if execution.rowcount != 1:
                    raise ExecutionControlStateConflictError(
                        "Execution state changed before recovery committed."
                    )

                if snapshot.start_idempotency_key is None:
                    raise ExecutionControlStateConflictError(
                        "Interrupted execution is missing its start claim."
                    )

                start = connection.execute(
                    """
                    UPDATE executive_execution_starts
                    SET
                        status = ?,
                        response_json = ?,
                        updated_at = ?
                    WHERE
                        execution_id = ?
                        AND idempotency_key = ?
                    """,
                    (
                        target_state,
                        start_response.model_dump_json(),
                        now,
                        snapshot.execution_id,
                        snapshot.start_idempotency_key,
                    ),
                )

                if start.rowcount != 1:
                    raise ExecutionControlStateConflictError(
                        "Execution start claim changed before recovery committed."
                    )

                parent_status = (
                    "completed"
                    if target_state == "completed"
                    else "manual_review"
                )
                self._update_parent(
                    connection=connection,
                    snapshot=snapshot,
                    target_status=parent_status,
                    now=now,
                )
                self._insert_control(
                    connection=connection,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                )
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        return response

    @staticmethod
    def _validate_snapshot_identity(
        *,
        connection: sqlite3.Connection,
        snapshot: ExecutionRecoverySnapshot,
        expected_states: set[str],
    ) -> None:
        record = connection.execute(
            """
            SELECT
                delegation_id,
                parent_task_id,
                child_task_ids_json,
                selected_agent_ids_json,
                reservation_ids_json,
                state
            FROM executive_execution_records
            WHERE execution_id = ?
            """,
            (snapshot.execution_id,),
        ).fetchone()

        if record is None:
            raise ExecutionControlStateConflictError(
                "Execution disappeared before the control transaction."
            )

        actual_children = tuple(
            str(item)
            for item in json.loads(str(record["child_task_ids_json"]))
        )
        actual_agents = tuple(
            str(item)
            for item in json.loads(str(record["selected_agent_ids_json"]))
        )
        actual_reservations = tuple(
            str(item)
            for item in json.loads(str(record["reservation_ids_json"]))
        )
        valid = (
            str(record["delegation_id"]) == snapshot.delegation_id
            and str(record["parent_task_id"]) == snapshot.parent_task_id
            and actual_children == snapshot.child_task_ids
            and actual_agents == snapshot.selected_agent_ids
            and actual_reservations == snapshot.reservation_ids
            and str(record["state"]) in expected_states
        )

        if not valid:
            raise ExecutionControlStateConflictError(
                "Execution identity or state changed before control commit."
            )

    @staticmethod
    def _validate_queued_children(
        *,
        connection: sqlite3.Connection,
        snapshot: ExecutionRecoverySnapshot,
    ) -> None:
        for task_id, agent_id in zip(
            snapshot.child_task_ids,
            snapshot.selected_agent_ids,
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
                raise ExecutionControlStateConflictError(
                    f"Reserved child task {task_id} is missing."
                )

            assigned = [
                str(item)
                for item in json.loads(
                    str(row["assigned_agent_ids_json"])
                )
            ]
            valid = (
                str(row["status"]) == "queued"
                and str(row["source_run_id"]) == snapshot.delegation_id
                and str(row["parent_task_id"]) == snapshot.parent_task_id
                and assigned == [agent_id]
            )

            if not valid:
                raise ExecutionControlStateConflictError(
                    f"Reserved child task {task_id} changed before cancellation."
                )

    @staticmethod
    def _update_parent(
        *,
        connection: sqlite3.Connection,
        snapshot: ExecutionRecoverySnapshot,
        target_status: str,
        now: str,
    ) -> None:
        rows = connection.execute(
            """
            SELECT status
            FROM task_ledger
            WHERE parent_task_id = ? AND source_run_id = ?
            """,
            (snapshot.parent_task_id, snapshot.delegation_id),
        ).fetchall()
        statuses = [str(row["status"]) for row in rows]

        if statuses:
            completed = sum(status == "completed" for status in statuses)
            terminal = sum(
                status in {
                    "completed",
                    "failed",
                    "cancelled",
                    "manual_review",
                }
                for status in statuses
            )
            weighted = completed + (0.5 * max(terminal - completed, 0))
            progress = round((weighted / len(statuses)) * 100.0, 2)
        else:
            progress = 0.0

        completed_at = now if target_status == "completed" else None
        current_step = (
            "All delegated child tasks completed with acceptance evidence"
            if target_status == "completed"
            else "Delegated execution requires owner review"
        )
        updated = connection.execute(
            """
            UPDATE task_ledger
            SET
                status = ?,
                current_step = ?,
                progress_percent = ?,
                updated_at = ?,
                completed_at = ?
            WHERE task_id = ? AND source_run_id = ?
            """,
            (
                target_status,
                current_step,
                progress,
                now,
                completed_at,
                snapshot.parent_task_id,
                snapshot.delegation_id,
            ),
        )

        if updated.rowcount != 1:
            raise ExecutionControlStateConflictError(
                "Parent task changed before control reconciliation."
            )

    @staticmethod
    def _insert_control(
        *,
        connection: sqlite3.Connection,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveExecutionControlResponse,
    ) -> None:
        connection.execute(
            """
            INSERT INTO executive_execution_controls (
                idempotency_key,
                execution_id,
                action,
                request_hash,
                response_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                idempotency_key,
                response.execution_id,
                response.action,
                request_hash,
                response.model_dump_json(),
                response.generated_at.isoformat(),
            ),
        )

    @staticmethod
    def _replay_from_row(
        *,
        row_request_hash: str,
        row_response_json: str,
        request_hash: str,
    ) -> ExecutiveExecutionControlResponse:
        if row_request_hash != request_hash:
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different "
                "Executive Office execution-control request."
            )

        stored = ExecutiveExecutionControlResponse.model_validate_json(
            row_response_json
        )
        return stored.model_copy(
            update={
                "disposition": "idempotent_replay",
                "idempotent_replay": True,
                "execution_replayed": False,
                "message": (
                    "Stored execution-control outcome returned without "
                    "replaying an agent, reservation, or broker action."
                ),
            }
        )

    @staticmethod
    def _json_tuple(value: str) -> tuple[str, ...]:
        return tuple(str(item) for item in json.loads(value))

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)


executive_execution_recovery_repository = (
    ExecutiveExecutionRecoveryRepository(
        agent_truth_repository
    )
)
