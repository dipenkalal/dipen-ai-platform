import json
import sqlite3

from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from executive_office.execution_cancellation_repository import (
    CancellationStateConflictError,
)
from executive_office.execution_start_repository import ExecutionStartClaim
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartResponse,
)


class ExecutiveExecutionCancellationReconciler:
    def __init__(
        self,
        truth_repository: AgentTruthRepository = agent_truth_repository,
    ) -> None:
        self.truth_repository = truth_repository

    def finalize_observed(
        self,
        *,
        claim: ExecutionStartClaim,
        idempotency_key: str,
        response: ExecutiveExecutionStartResponse,
    ) -> ExecutiveExecutionStartResponse:
        if response.state != "cancelled":
            raise ValueError("Cancellation reconciliation requires cancelled state.")

        now = response.generated_at.isoformat()

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            try:
                cancellation = connection.execute(
                    """
                    SELECT state, delegation_id, parent_task_id, child_task_ids_json
                    FROM executive_execution_cancellations
                    WHERE execution_id = ?
                    """,
                    (claim.execution_id,),
                ).fetchone()

                if cancellation is None:
                    raise CancellationStateConflictError(
                        "Observed cancellation record is missing."
                    )

                stored_children = tuple(
                    str(item)
                    for item in json.loads(
                        str(cancellation["child_task_ids_json"])
                    )
                )
                identity_matches = (
                    str(cancellation["state"]) == "observed"
                    and str(cancellation["delegation_id"]) == claim.delegation_id
                    and str(cancellation["parent_task_id"]) == claim.parent_task_id
                    and stored_children == claim.child_task_ids
                )

                if not identity_matches:
                    raise CancellationStateConflictError(
                        "Observed cancellation identity changed before reconciliation."
                    )

                execution = connection.execute(
                    """
                    UPDATE executive_execution_records
                    SET state = 'cancelled', updated_at = ?
                    WHERE execution_id = ? AND state = 'running'
                    """,
                    (now, claim.execution_id),
                )

                if execution.rowcount != 1:
                    raise CancellationStateConflictError(
                        "Running execution changed before cancellation reconciliation."
                    )

                for task_id in claim.child_task_ids:
                    connection.execute(
                        """
                        UPDATE task_ledger
                        SET
                            status = 'cancelled',
                            current_step = ?,
                            updated_at = ?,
                            completed_at = ?
                        WHERE
                            task_id = ?
                            AND source_run_id = ?
                            AND parent_task_id = ?
                            AND status IN ('assigned', 'queued', 'waiting')
                        """,
                        (
                            "Cancelled cooperatively before the next bounded child start.",
                            now,
                            now,
                            task_id,
                            claim.delegation_id,
                            claim.parent_task_id,
                        ),
                    )

                connection.execute(
                    """
                    UPDATE executive_execution_reservations
                    SET released_at = ?
                    WHERE execution_id = ? AND released_at IS NULL
                    """,
                    (now, claim.execution_id),
                )

                parent = connection.execute(
                    """
                    UPDATE task_ledger
                    SET
                        status = 'manual_review',
                        current_step = ?,
                        updated_at = ?
                    WHERE task_id = ? AND source_run_id = ?
                    """,
                    (
                        "Delegated execution was cooperatively cancelled by owner request.",
                        now,
                        claim.parent_task_id,
                        claim.delegation_id,
                    ),
                )

                if parent.rowcount != 1:
                    raise CancellationStateConflictError(
                        "Parent task changed before cancellation reconciliation."
                    )

                cancellation_updated = connection.execute(
                    """
                    UPDATE executive_execution_cancellations
                    SET state = 'resolved', resolved_at = ?
                    WHERE execution_id = ? AND state = 'observed'
                    """,
                    (now, claim.execution_id),
                )

                if cancellation_updated.rowcount != 1:
                    raise CancellationStateConflictError(
                        "Cancellation request changed before reconciliation."
                    )

                start = connection.execute(
                    """
                    UPDATE executive_execution_starts
                    SET
                        status = 'cancelled',
                        response_json = ?,
                        updated_at = ?
                    WHERE
                        execution_id = ?
                        AND idempotency_key = ?
                        AND status = 'claimed'
                    """,
                    (
                        response.model_dump_json(),
                        now,
                        claim.execution_id,
                        idempotency_key,
                    ),
                )

                if start.rowcount != 1:
                    raise CancellationStateConflictError(
                        "Execution start claim changed before cancellation reconciliation."
                    )
            except (
                CancellationStateConflictError,
                sqlite3.IntegrityError,
            ):
                connection.rollback()
                raise
            else:
                connection.commit()

        return response


executive_execution_cancellation_reconciler = (
    ExecutiveExecutionCancellationReconciler()
)
