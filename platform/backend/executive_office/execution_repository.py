import json
import sqlite3

from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import (
    ExecutiveDelegationResponse,
    ExecutiveExecutionResponse,
    OwnerExecutionAuthorization,
)


class ReservationConflictError(RuntimeError):
    """Raised when a machine agent already has an active reservation."""


class ExecutionStateConflictError(RuntimeError):
    """Raised when task state changes before atomic reservation."""


class ExecutiveExecutionRepository:
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
                CREATE TABLE IF NOT EXISTS executive_execution_admissions (
                    idempotency_key TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL UNIQUE,
                    delegation_id TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS executive_execution_records (
                    execution_id TEXT PRIMARY KEY,
                    delegation_id TEXT NOT NULL,
                    parent_task_id TEXT NOT NULL,
                    child_task_ids_json TEXT NOT NULL,
                    authorization_id TEXT NOT NULL,
                    authorized_by TEXT NOT NULL,
                    authorization_statement TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    selected_agent_ids_json TEXT NOT NULL,
                    reservation_ids_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    validation_evidence_json TEXT NOT NULL,
                    validation_only INTEGER NOT NULL,
                    requested_at TEXT NOT NULL,
                    admitted_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS executive_execution_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    released_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_admissions_delegation_id
                ON executive_execution_admissions(delegation_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_records_delegation_id
                ON executive_execution_records(delegation_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_reservations_execution_id
                ON executive_execution_reservations(execution_id)
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_execution_reservations_active_agent
                ON executive_execution_reservations(agent_id)
                WHERE released_at IS NULL
                """
            )
            connection.commit()

    def get_delegation(
        self,
        delegation_id: str,
    ) -> ExecutiveDelegationResponse | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT response_json
                FROM executive_delegations
                WHERE delegation_id = ?
                """,
                (delegation_id,),
            ).fetchone()

        if row is None:
            return None

        return ExecutiveDelegationResponse.model_validate_json(
            str(row["response_json"])
        )

    def list_active_reserved_agents(
        self,
        agent_ids: list[str],
    ) -> list[str]:
        unique_agent_ids = sorted(set(agent_ids))

        if not unique_agent_ids:
            return []

        placeholders = ", ".join("?" for _ in unique_agent_ids)

        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT agent_id
                FROM executive_execution_reservations
                WHERE
                    released_at IS NULL
                    AND agent_id IN ({placeholders})
                ORDER BY agent_id
                """,
                unique_agent_ids,
            ).fetchall()

        return [str(row["agent_id"]) for row in rows]

    def get_replay(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> ExecutiveExecutionResponse | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT request_hash, response_json
                FROM executive_execution_admissions
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
        response: ExecutiveExecutionResponse,
    ) -> ExecutiveExecutionResponse:
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT request_hash, response_json
                FROM executive_execution_admissions
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

            self._insert_admission(
                connection=connection,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
            )
            connection.commit()

        return response

    def reserve_and_queue(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveExecutionResponse,
        authorization: OwnerExecutionAuthorization,
        task_agent_pairs: list[tuple[str, str]],
    ) -> ExecutiveExecutionResponse:
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                existing = connection.execute(
                    """
                    SELECT request_hash, response_json
                    FROM executive_execution_admissions
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

                self._validate_parent_for_reservation(
                    connection=connection,
                    response=response,
                )
                self._validate_children_for_reservation(
                    connection=connection,
                    response=response,
                    task_agent_pairs=task_agent_pairs,
                )

                try:
                    self._insert_execution_record(
                        connection=connection,
                        request_hash=request_hash,
                        response=response,
                        authorization=authorization,
                    )
                    self._insert_reservations(
                        connection=connection,
                        response=response,
                        task_agent_pairs=task_agent_pairs,
                    )
                except sqlite3.IntegrityError as error:
                    raise ReservationConflictError(
                        "At least one machine agent already has an active "
                        "execution reservation."
                    ) from error

                for task_id, _ in task_agent_pairs:
                    updated = connection.execute(
                        """
                        UPDATE task_ledger
                        SET
                            status = 'queued',
                            current_step = ?,
                            progress_percent = 0.0,
                            updated_at = ?
                        WHERE
                            task_id = ?
                            AND status = 'assigned'
                            AND source_run_id = ?
                            AND parent_task_id = ?
                        """,
                        (
                            (
                                "Reserved for owner-triggered execution; the "
                                "executor has not started."
                            ),
                            response.generated_at.isoformat(),
                            task_id,
                            response.delegation_id,
                            response.parent_task_id,
                        ),
                    )

                    if updated.rowcount != 1:
                        raise ExecutionStateConflictError(
                            f"Child task {task_id} changed before reservation."
                        )

                parent_updated = connection.execute(
                    """
                    UPDATE task_ledger
                    SET
                        current_step = ?,
                        updated_at = ?
                    WHERE
                        task_id = ?
                        AND status = 'planned'
                        AND source_run_id = ?
                    """,
                    (
                        (
                            "Selected child tasks are queued under execution "
                            f"{response.execution_id}; no executor has started."
                        ),
                        response.generated_at.isoformat(),
                        response.parent_task_id,
                        response.delegation_id,
                    ),
                )

                if parent_updated.rowcount != 1:
                    raise ExecutionStateConflictError(
                        "The parent task changed before reservation."
                    )

                self._insert_admission(
                    connection=connection,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                )
            except (
                ExecutionStateConflictError,
                IdempotencyConflictError,
                ReservationConflictError,
            ):
                connection.rollback()
                raise
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        return response

    @staticmethod
    def _validate_parent_for_reservation(
        *,
        connection: sqlite3.Connection,
        response: ExecutiveExecutionResponse,
    ) -> None:
        row = connection.execute(
            """
            SELECT status, source_run_id
            FROM task_ledger
            WHERE task_id = ?
            """,
            (response.parent_task_id,),
        ).fetchone()

        if (
            row is None
            or str(row["status"]) != "planned"
            or str(row["source_run_id"]) != response.delegation_id
        ):
            raise ExecutionStateConflictError(
                "The parent task is no longer planned for this delegation."
            )

    @staticmethod
    def _validate_children_for_reservation(
        *,
        connection: sqlite3.Connection,
        response: ExecutiveExecutionResponse,
        task_agent_pairs: list[tuple[str, str]],
    ) -> None:
        if len(task_agent_pairs) != len(response.child_task_ids):
            raise ExecutionStateConflictError(
                "The task-to-agent reservation mapping is incomplete."
            )

        for task_id, agent_id in task_agent_pairs:
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
                raise ExecutionStateConflictError(
                    f"Child task {task_id} is missing."
                )

            assigned_agent_ids = json.loads(
                str(row["assigned_agent_ids_json"])
            )
            valid = (
                str(row["status"]) == "assigned"
                and str(row["source_run_id"]) == response.delegation_id
                and str(row["parent_task_id"]) == response.parent_task_id
                and assigned_agent_ids == [agent_id]
            )

            if not valid:
                raise ExecutionStateConflictError(
                    f"Child task {task_id} changed before reservation."
                )

    @staticmethod
    def _insert_execution_record(
        *,
        connection: sqlite3.Connection,
        request_hash: str,
        response: ExecutiveExecutionResponse,
        authorization: OwnerExecutionAuthorization,
    ) -> None:
        connection.execute(
            """
            INSERT INTO executive_execution_records (
                execution_id,
                delegation_id,
                parent_task_id,
                child_task_ids_json,
                authorization_id,
                authorized_by,
                authorization_statement,
                request_hash,
                selected_agent_ids_json,
                reservation_ids_json,
                state,
                validation_evidence_json,
                validation_only,
                requested_at,
                admitted_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                response.execution_id,
                response.delegation_id,
                response.parent_task_id,
                json.dumps(response.child_task_ids, ensure_ascii=False),
                authorization.authorization_id,
                authorization.authorized_by,
                authorization.statement,
                request_hash,
                json.dumps(
                    response.selected_agent_ids,
                    ensure_ascii=False,
                ),
                json.dumps(
                    response.reservation_ids,
                    ensure_ascii=False,
                ),
                response.state,
                json.dumps(
                    [
                        item.model_dump(mode="json")
                        for item in response.validation_evidence
                    ],
                    ensure_ascii=False,
                    default=str,
                ),
                int(response.validation_only),
                response.generated_at.isoformat(),
                response.generated_at.isoformat(),
                response.generated_at.isoformat(),
            ),
        )

    @staticmethod
    def _insert_reservations(
        *,
        connection: sqlite3.Connection,
        response: ExecutiveExecutionResponse,
        task_agent_pairs: list[tuple[str, str]],
    ) -> None:
        if len(response.reservation_ids) != len(task_agent_pairs):
            raise ExecutionStateConflictError(
                "Reservation IDs do not match the selected task set."
            )

        for reservation_id, (task_id, agent_id) in zip(
            response.reservation_ids,
            task_agent_pairs,
            strict=True,
        ):
            connection.execute(
                """
                INSERT INTO executive_execution_reservations (
                    reservation_id,
                    execution_id,
                    agent_id,
                    task_id,
                    acquired_at,
                    released_at
                )
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (
                    reservation_id,
                    response.execution_id,
                    agent_id,
                    task_id,
                    response.generated_at.isoformat(),
                ),
            )

    @staticmethod
    def _insert_admission(
        *,
        connection: sqlite3.Connection,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveExecutionResponse,
    ) -> None:
        connection.execute(
            """
            INSERT INTO executive_execution_admissions (
                idempotency_key,
                execution_id,
                delegation_id,
                request_hash,
                response_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                idempotency_key,
                response.execution_id,
                response.delegation_id,
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
    ) -> ExecutiveExecutionResponse:
        if row_request_hash != request_hash:
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different "
                "Executive Office execution request."
            )

        stored = ExecutiveExecutionResponse.model_validate_json(
            row_response_json
        )
        return stored.model_copy(
            update={
                "disposition": "idempotent_replay",
                "idempotent_replay": True,
                "message": (
                    "Existing execution admission returned without repeating "
                    "policy, worker, reservation, task transition, or executor "
                    "activity."
                ),
            }
        )


executive_execution_repository = ExecutiveExecutionRepository(
    agent_truth_repository
)
