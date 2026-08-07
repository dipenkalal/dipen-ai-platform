import hashlib
import json
import sqlite3

from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from executive_office.execution_cancellation_schemas import (
    CancellationRequestState,
    ExecutiveRunningCancellationRecord,
)
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import utc_now


class CancellationStateConflictError(RuntimeError):
    """Raised when running cancellation intent cannot be stored safely."""


class ExecutiveExecutionCancellationRepository:
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
                CREATE TABLE IF NOT EXISTS executive_execution_cancellations (
                    idempotency_key TEXT PRIMARY KEY,
                    cancellation_id TEXT NOT NULL UNIQUE,
                    execution_id TEXT NOT NULL UNIQUE,
                    delegation_id TEXT NOT NULL,
                    parent_task_id TEXT NOT NULL,
                    child_task_ids_json TEXT NOT NULL,
                    authorization_id TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    authorization_statement TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    observed_at TEXT,
                    resolved_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_cancellations_state
                ON executive_execution_cancellations(state)
                """
            )
            connection.commit()

    def get_replay(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> ExecutiveRunningCancellationRecord | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM executive_execution_cancellations
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

        if row is None:
            return None

        if str(row["request_hash"]) != request_hash:
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different "
                "running-cancellation request."
            )

        return self._record_from_row(row).model_copy(
            update={
                "idempotent_replay": True,
                "message": (
                    "Stored cancellation intent returned without repeating "
                    "runtime or task-ledger actions."
                ),
            }
        )

    def get_for_execution(
        self,
        execution_id: str,
    ) -> ExecutiveRunningCancellationRecord | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM executive_execution_cancellations
                WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()

        return self._record_from_row(row) if row is not None else None

    def request(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        execution_id: str,
        delegation_id: str,
        parent_task_id: str,
        child_task_ids: list[str],
        authorization_id: str,
        requested_by: str,
        authorization_statement: str,
    ) -> ExecutiveRunningCancellationRecord:
        cancellation_id = self._cancellation_id(
            execution_id=execution_id,
            idempotency_key=idempotency_key,
        )
        now = utc_now()

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                existing_key = connection.execute(
                    """
                    SELECT *
                    FROM executive_execution_cancellations
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()

                if existing_key is not None:
                    if str(existing_key["request_hash"]) != request_hash:
                        raise IdempotencyConflictError(
                            "The idempotency key is already bound to a different "
                            "running-cancellation request."
                        )
                    connection.commit()
                    return self._record_from_row(existing_key).model_copy(
                        update={
                            "idempotent_replay": True,
                            "message": (
                                "Stored cancellation intent returned without "
                                "repeating runtime or task-ledger actions."
                            ),
                        }
                    )

                existing_execution = connection.execute(
                    """
                    SELECT idempotency_key
                    FROM executive_execution_cancellations
                    WHERE execution_id = ?
                    """,
                    (execution_id,),
                ).fetchone()

                if existing_execution is not None:
                    raise CancellationStateConflictError(
                        "The execution already has a durable cancellation request."
                    )

                execution = connection.execute(
                    """
                    SELECT
                        delegation_id,
                        parent_task_id,
                        child_task_ids_json,
                        state,
                        validation_only
                    FROM executive_execution_records
                    WHERE execution_id = ?
                    """,
                    (execution_id,),
                ).fetchone()

                if execution is None:
                    raise CancellationStateConflictError(
                        "The requested execution does not exist."
                    )
                if bool(execution["validation_only"]):
                    raise CancellationStateConflictError(
                        "Validation-only execution records cannot be cancelled."
                    )
                if str(execution["state"]) != "running":
                    raise CancellationStateConflictError(
                        "Running cancellation intent requires execution state running."
                    )

                stored_children = [
                    str(item)
                    for item in json.loads(
                        str(execution["child_task_ids_json"])
                    )
                ]
                identity_matches = (
                    str(execution["delegation_id"]) == delegation_id
                    and str(execution["parent_task_id"]) == parent_task_id
                    and stored_children == child_task_ids
                )

                if not identity_matches:
                    raise CancellationStateConflictError(
                        "Cancellation identity does not match the running execution."
                    )

                connection.execute(
                    """
                    INSERT INTO executive_execution_cancellations (
                        idempotency_key,
                        cancellation_id,
                        execution_id,
                        delegation_id,
                        parent_task_id,
                        child_task_ids_json,
                        authorization_id,
                        requested_by,
                        authorization_statement,
                        request_hash,
                        state,
                        requested_at,
                        observed_at,
                        resolved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'requested', ?, NULL, NULL)
                    """,
                    (
                        idempotency_key,
                        cancellation_id,
                        execution_id,
                        delegation_id,
                        parent_task_id,
                        json.dumps(child_task_ids),
                        authorization_id,
                        requested_by,
                        authorization_statement,
                        request_hash,
                        now.isoformat(),
                    ),
                )
            except (
                CancellationStateConflictError,
                IdempotencyConflictError,
                sqlite3.IntegrityError,
            ) as error:
                connection.rollback()

                if isinstance(error, sqlite3.IntegrityError):
                    raise CancellationStateConflictError(
                        "Cancellation intent collided with another request."
                    ) from error

                raise
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        return ExecutiveRunningCancellationRecord(
            cancellation_id=cancellation_id,
            execution_id=execution_id,
            delegation_id=delegation_id,
            parent_task_id=parent_task_id,
            child_task_ids=child_task_ids,
            authorization_id=authorization_id,
            requested_by="dipen-owner",
            state="requested",
            requested_at=now,
            message=(
                "Running cancellation intent stored durably. Runtime execution "
                "state was not changed and no agent or broker action occurred."
            ),
        )

    def mark_observed(
        self,
        execution_id: str,
    ) -> ExecutiveRunningCancellationRecord:
        return self._transition(
            execution_id=execution_id,
            target_state="observed",
        )

    def mark_resolved(
        self,
        execution_id: str,
    ) -> ExecutiveRunningCancellationRecord:
        return self._transition(
            execution_id=execution_id,
            target_state="resolved",
        )

    def _transition(
        self,
        *,
        execution_id: str,
        target_state: CancellationRequestState,
    ) -> ExecutiveRunningCancellationRecord:
        now = utc_now()

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT *
                FROM executive_execution_cancellations
                WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()

            if row is None:
                connection.rollback()
                raise CancellationStateConflictError(
                    "The execution has no durable cancellation request."
                )

            current_state = str(row["state"])

            if target_state == "observed":
                allowed = {"requested", "observed"}
                timestamp_column = "observed_at"
            elif target_state == "resolved":
                allowed = {"requested", "observed", "resolved"}
                timestamp_column = "resolved_at"
            else:
                connection.rollback()
                raise ValueError("Unsupported cancellation transition.")

            if current_state not in allowed:
                connection.rollback()
                raise CancellationStateConflictError(
                    "Cancellation request is not in a transitionable state."
                )

            if current_state != target_state:
                connection.execute(
                    f"""
                    UPDATE executive_execution_cancellations
                    SET state = ?, {timestamp_column} = ?
                    WHERE execution_id = ? AND state = ?
                    """,
                    (
                        target_state,
                        now.isoformat(),
                        execution_id,
                        current_state,
                    ),
                )
                connection.commit()
            else:
                connection.commit()

        record = self.get_for_execution(execution_id)

        if record is None:
            raise CancellationStateConflictError(
                "Cancellation request disappeared after transition."
            )

        return record.model_copy(
            update={
                "message": (
                    "Cancellation intent acknowledged by the bounded runtime."
                    if target_state == "observed"
                    else "Cancellation intent resolved after durable reconciliation."
                )
            }
        )

    @staticmethod
    def _cancellation_id(
        *,
        execution_id: str,
        idempotency_key: str,
    ) -> str:
        digest = hashlib.sha256(
            f"{execution_id}|{idempotency_key}".encode()
        ).hexdigest()[:24]
        return f"execution-cancellation-{digest}"

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> ExecutiveRunningCancellationRecord:
        return ExecutiveRunningCancellationRecord(
            cancellation_id=str(row["cancellation_id"]),
            execution_id=str(row["execution_id"]),
            delegation_id=str(row["delegation_id"]),
            parent_task_id=str(row["parent_task_id"]),
            child_task_ids=[
                str(item)
                for item in json.loads(str(row["child_task_ids_json"]))
            ],
            authorization_id=str(row["authorization_id"]),
            requested_by="dipen-owner",
            state=str(row["state"]),
            requested_at=utc_now().fromisoformat(str(row["requested_at"])),
            observed_at=(
                utc_now().fromisoformat(str(row["observed_at"]))
                if row["observed_at"] is not None
                else None
            ),
            resolved_at=(
                utc_now().fromisoformat(str(row["resolved_at"]))
                if row["resolved_at"] is not None
                else None
            ),
            message="Durable running cancellation request.",
        )


executive_execution_cancellation_repository = (
    ExecutiveExecutionCancellationRepository(agent_truth_repository)
)
