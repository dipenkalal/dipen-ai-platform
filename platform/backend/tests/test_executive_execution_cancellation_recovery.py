import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.registry import agent_registry
from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from agents.truth_service import AgentTruthService
from executive_office.execution_cancellation_reconciliation import (
    ExecutiveExecutionCancellationReconciler,
)
from executive_office.execution_cancellation_recovery import (
    ExecutiveCancellationAwareRecoveryService,
)
from executive_office.execution_cancellation_repository import (
    ExecutiveExecutionCancellationRepository,
)
from executive_office.execution_recovery_repository import (
    ExecutiveExecutionRecoveryRepository,
)
from executive_office.execution_recovery_schemas import (
    ExecutiveExecutionControlRequest,
    OwnerExecutionControlAuthorization,
)
from executive_office.execution_recovery_service import (
    ExecutiveExecutionRecoveryService,
)
from executive_office.execution_repository import ExecutiveExecutionRepository
from executive_office.execution_start_repository import (
    ExecutiveExecutionStartRepository,
)
from executive_office.execution_status_service import (
    ExecutiveExecutionStatusService,
)


class ExecutiveCancellationRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "cancellation-recovery.db"
        self.truth_repository = AgentTruthRepository(database_path)
        self.truth_service = AgentTruthService(agent_registry, self.truth_repository)
        ExecutiveExecutionRepository(self.truth_repository)
        ExecutiveExecutionStartRepository(self.truth_repository)
        self.cancellation_repository = ExecutiveExecutionCancellationRepository(
            self.truth_repository
        )
        self.recovery_repository = ExecutiveExecutionRecoveryRepository(
            self.truth_repository
        )
        self.reconciler = ExecutiveExecutionCancellationReconciler(
            self.truth_repository
        )
        self.now = datetime(2026, 8, 7, 5, 30, tzinfo=timezone.utc)
        recovery_service = ExecutiveExecutionRecoveryService(
            truth_service=self.truth_service,
            recovery_repository=self.recovery_repository,
            now_provider=lambda: self.now,
        )
        self.recovery = ExecutiveCancellationAwareRecoveryService(
            recovery_service=recovery_service,
            cancellation_repository=self.cancellation_repository,
            cancellation_reconciler=self.reconciler,
        )
        self.status_service = ExecutiveExecutionStatusService(
            truth_service=self.truth_service,
            truth_repository=self.truth_repository,
            cancellation_repository=self.cancellation_repository,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def seed_interrupted_cancellation(self) -> None:
        old = self.now - timedelta(minutes=10)
        parent = TaskLedgerRecord(
            task_id="parent-task-001",
            task_type="orchestration",
            objective="Coordinate bounded work",
            status="planned",
            requested_by="dipen-owner",
            source_run_id="delegation-001",
            created_at=old,
            updated_at=old,
        )
        completed_child = TaskLedgerRecord(
            task_id="child-task-001",
            task_type="agent",
            objective="Complete first bounded child",
            status="completed",
            requested_by="dipen-owner",
            assigned_agent_ids=["system-agent"],
            source_run_id="delegation-001",
            parent_task_id="parent-task-001",
            created_at=old,
            updated_at=old,
            started_at=old,
            completed_at=old + timedelta(seconds=30),
        )
        queued_child = TaskLedgerRecord(
            task_id="child-task-002",
            task_type="agent",
            objective="Do not start after cancellation",
            status="queued",
            requested_by="dipen-owner",
            assigned_agent_ids=["research-agent"],
            source_run_id="delegation-001",
            parent_task_id="parent-task-001",
            created_at=old,
            updated_at=old,
        )
        for task in (parent, completed_child, queued_child):
            self.truth_repository.upsert_task(task)

        with self.truth_repository.connection() as connection:
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "execution-001",
                    "delegation-001",
                    "parent-task-001",
                    json.dumps(["child-task-001", "child-task-002"]),
                    "execution-authorization-001",
                    "dipen-owner",
                    "Authorize bounded execution.",
                    "execution-request-hash",
                    json.dumps(["system-agent", "research-agent"]),
                    json.dumps(["reservation-001", "reservation-002"]),
                    "running",
                    "[]",
                    0,
                    old.isoformat(),
                    old.isoformat(),
                    old.isoformat(),
                ),
            )
            for reservation_id, agent_id, task_id in (
                ("reservation-001", "system-agent", "child-task-001"),
                ("reservation-002", "research-agent", "child-task-002"),
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
                    ) VALUES (?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        reservation_id,
                        "execution-001",
                        agent_id,
                        task_id,
                        old.isoformat(),
                    ),
                )
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
                ) VALUES (?, ?, ?, 'claimed', NULL, ?, ?)
                """,
                (
                    "start-request-0001",
                    "execution-001",
                    "start-request-hash",
                    old.isoformat(),
                    old.isoformat(),
                ),
            )
            connection.commit()

        self.cancellation_repository.request(
            idempotency_key="cancel-running-0001",
            request_hash="cancel-running-hash",
            execution_id="execution-001",
            delegation_id="delegation-001",
            parent_task_id="parent-task-001",
            child_task_ids=["child-task-001", "child-task-002"],
            authorization_id="cancel-authorization-001",
            requested_by="dipen-owner",
            authorization_statement="Stop remaining bounded work cooperatively.",
        )

    def recovery_request(self) -> ExecutiveExecutionControlRequest:
        return ExecutiveExecutionControlRequest(
            idempotency_key="recover-cancel-0001",
            owner_authorization=OwnerExecutionControlAuthorization(
                authorization_id="recover-authorization-001",
                execution_id="execution-001",
                delegation_id="delegation-001",
                parent_task_id="parent-task-001",
                child_task_ids=["child-task-001", "child-task-002"],
                scope="recover_interrupted_execution",
                statement="Recover the interrupted cooperative cancellation.",
            ),
        )

    def test_recovery_finishes_stale_cooperative_cancellation(self) -> None:
        self.seed_interrupted_cancellation()

        response = self.recovery.recover(
            execution_id="execution-001",
            request=self.recovery_request(),
        )
        status = self.status_service.get("execution-001")

        self.assertEqual(response.disposition, "recovered")
        self.assertEqual(response.state, "cancelled")
        self.assertTrue(response.reservation_released)
        self.assertFalse(response.execution_replayed)
        self.assertFalse(response.broker_activated)
        self.assertEqual(status.state, "cancelled")
        self.assertEqual(status.active_reservation_ids, [])
        self.assertIsNotNone(status.cancellation)
        assert status.cancellation is not None
        self.assertEqual(status.cancellation.state, "resolved")
        self.assertEqual(status.parent_task.status, "manual_review")
        child_statuses = {task.task_id: task.status for task in status.child_tasks}
        self.assertEqual(child_statuses["child-task-001"], "completed")
        self.assertEqual(child_statuses["child-task-002"], "cancelled")


if __name__ == "__main__":
    unittest.main()
