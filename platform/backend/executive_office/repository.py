import json
from typing import Any

from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from agents.truth_schemas import TaskLedgerRecord
from executive_office.schemas import (
    ExecutiveDelegationResponse,
    OwnerApprovalRecord,
)


class IdempotencyConflictError(ValueError):
    """Raised when one idempotency key is reused for a different request."""


class ExecutiveDelegationRepository:
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
                CREATE TABLE IF NOT EXISTS executive_delegations (
                    idempotency_key TEXT PRIMARY KEY,
                    delegation_id TEXT NOT NULL UNIQUE,
                    decision_id TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS executive_approvals (
                    approval_id TEXT PRIMARY KEY,
                    delegation_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved INTEGER NOT NULL,
                    statement TEXT NOT NULL,
                    approved_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_executive_delegations_decision_id
                ON executive_delegations(decision_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_executive_approvals_delegation_id
                ON executive_approvals(delegation_id)
                """
            )
            connection.commit()

    def get_replay(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> ExecutiveDelegationResponse | None:
        with self.truth_repository.connection() as connection:
            existing = connection.execute(
                """
                SELECT request_hash, response_json
                FROM executive_delegations
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

        if existing is None:
            return None

        if str(existing["request_hash"]) != request_hash:
            raise IdempotencyConflictError(
                "The idempotency key is already bound to a different "
                "Executive Office delegation request."
            )

        stored = ExecutiveDelegationResponse.model_validate_json(
            str(existing["response_json"])
        )
        return stored.model_copy(
            update={
                "disposition": "idempotent_replay",
                "idempotent_replay": True,
                "message": (
                    "Existing delegation returned without creating duplicate "
                    "task or approval records."
                ),
            }
        )

    def persist(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveDelegationResponse,
        approval: OwnerApprovalRecord | None,
    ) -> ExecutiveDelegationResponse:
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT request_hash, response_json
                FROM executive_delegations
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

            if existing is not None:
                if str(existing["request_hash"]) != request_hash:
                    connection.rollback()
                    raise IdempotencyConflictError(
                        "The idempotency key is already bound to a different "
                        "Executive Office delegation request."
                    )

                stored = ExecutiveDelegationResponse.model_validate_json(
                    str(existing["response_json"])
                )
                connection.commit()
                return stored.model_copy(
                    update={
                        "disposition": "idempotent_replay",
                        "idempotent_replay": True,
                        "message": (
                            "Existing delegation returned without creating "
                            "duplicate task or approval records."
                        ),
                    }
                )

            tasks = [
                task
                for task in (
                    response.parent_task,
                    *response.child_tasks,
                )
                if task is not None
            ]

            for task in tasks:
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
                    """,
                    self._task_values(task),
                )

            if approval is not None:
                connection.execute(
                    """
                    INSERT INTO executive_approvals (
                        approval_id,
                        delegation_id,
                        decision_id,
                        approved_by,
                        approved,
                        statement,
                        approved_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        approval.approval_id,
                        response.delegation_id,
                        approval.decision_id,
                        approval.approved_by,
                        int(approval.approved),
                        approval.statement,
                        approval.approved_at.isoformat(),
                    ),
                )

            connection.execute(
                """
                INSERT INTO executive_delegations (
                    idempotency_key,
                    delegation_id,
                    decision_id,
                    request_hash,
                    response_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    idempotency_key,
                    response.delegation_id,
                    response.decision_id,
                    request_hash,
                    response.model_dump_json(),
                    response.generated_at.isoformat(),
                ),
            )
            connection.commit()

        return response

    @staticmethod
    def _task_values(
        task: TaskLedgerRecord,
    ) -> tuple[Any, ...]:
        return (
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
        )


executive_delegation_repository = ExecutiveDelegationRepository(
    agent_truth_repository
)
