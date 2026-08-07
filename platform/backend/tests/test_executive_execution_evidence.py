import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from agents.registry import agent_registry
from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from agents.truth_service import AgentTruthService
from executive_office.execution_completion_service import (
    ExecutiveExecutionCompletionService,
)
from executive_office.execution_repository import ExecutiveExecutionRepository
from executive_office.execution_start_repository import (
    ExecutionStartClaim,
    ExecutiveExecutionStartRepository,
)
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartResponse,
    ExecutiveTaskExecutionResult,
)
from executive_office.execution_status_service import ExecutiveExecutionStatusService


class ExecutiveExecutionEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "execution-evidence.db"
        self.truth_repository = AgentTruthRepository(database_path)
        self.truth_service = AgentTruthService(
            agent_registry,
            self.truth_repository,
        )
        ExecutiveExecutionRepository(self.truth_repository)
        ExecutiveExecutionStartRepository(self.truth_repository)
        self.completion_service = ExecutiveExecutionCompletionService(
            truth_service=self.truth_service,
            truth_repository=self.truth_repository,
        )
        self.status_service = ExecutiveExecutionStatusService(
            truth_service=self.truth_service,
            truth_repository=self.truth_repository,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def seed_tasks(self, *, child_status: str = "completed") -> None:
        now = self.now()
        self.truth_repository.upsert_task(
            TaskLedgerRecord(
                task_id="parent-task-001",
                task_type="orchestration",
                objective="Complete the delegated project",
                status="planned",
                requested_by="dipen-owner",
                source_run_id="delegation-001",
                created_at=now,
                updated_at=now,
            )
        )
        self.truth_repository.upsert_task(
            TaskLedgerRecord(
                task_id="child-task-001",
                task_type="agent",
                objective="Prepare a technical progress report",
                status=child_status,
                requested_by="dipen-owner",
                assigned_agent_ids=["system-agent"],
                source_run_id="delegation-001",
                parent_task_id="parent-task-001",
                created_at=now,
                updated_at=now,
                completed_at=(now if child_status == "completed" else None),
            )
        )

    def test_terminal_completion_adds_evidence_and_completes_parent(self) -> None:
        self.seed_tasks()
        now = self.now()
        claim = ExecutionStartClaim(
            execution_id="execution-001",
            delegation_id="delegation-001",
            parent_task_id="parent-task-001",
            child_task_ids=("child-task-001",),
            selected_agent_ids=("system-agent",),
            reservation_ids=("reservation-001",),
        )
        response = ExecutiveExecutionStartResponse(
            execution_id="execution-001",
            delegation_id="delegation-001",
            child_task_ids=["child-task-001"],
            disposition="completed",
            state="completed",
            task_results=[
                ExecutiveTaskExecutionResult(
                    task_id="child-task-001",
                    agent_id="system-agent",
                    run_id="agent-run-001",
                    status="completed",
                    answer="Validated technical report output.",
                    started_at=now,
                    completed_at=now,
                )
            ],
            execution_started=True,
            reservation_released=True,
            message="completed",
        )

        reconciled = self.completion_service.reconcile_terminal(
            claim=claim,
            response=response,
        )

        self.assertEqual(reconciled.parent_task_status, "completed")
        self.assertEqual(len(reconciled.acceptance_evidence), 1)
        self.assertTrue(reconciled.acceptance_evidence[0].accepted)
        self.assertEqual(len(reconciled.acceptance_evidence[0].output_sha256), 64)
        parent = self.truth_service.get_task("parent-task-001")
        self.assertEqual(parent.status, "completed")
        self.assertEqual(parent.progress_percent, 100.0)

    def test_failed_child_moves_parent_to_manual_review(self) -> None:
        self.seed_tasks(child_status="failed")
        claim = ExecutionStartClaim(
            execution_id="execution-002",
            delegation_id="delegation-001",
            parent_task_id="parent-task-001",
            child_task_ids=("child-task-001",),
            selected_agent_ids=("system-agent",),
            reservation_ids=("reservation-002",),
        )
        response = ExecutiveExecutionStartResponse(
            execution_id="execution-002",
            delegation_id="delegation-001",
            child_task_ids=["child-task-001"],
            disposition="failed",
            state="failed",
            execution_started=True,
            reservation_released=True,
            message="failed",
        )

        reconciled = self.completion_service.reconcile_terminal(
            claim=claim,
            response=response,
        )

        self.assertEqual(reconciled.parent_task_status, "manual_review")
        self.assertEqual(
            self.truth_service.get_task("parent-task-001").status,
            "manual_review",
        )

    def test_status_reads_tasks_reservations_and_stored_evidence(self) -> None:
        self.seed_tasks()
        now = self.now()
        stored_response = ExecutiveExecutionStartResponse(
            execution_id="execution-003",
            delegation_id="delegation-001",
            child_task_ids=["child-task-001"],
            disposition="completed",
            state="completed",
            execution_started=True,
            reservation_released=True,
            message="completed",
        )

        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO executive_execution_records (
                    execution_id, delegation_id, parent_task_id,
                    child_task_ids_json, authorization_id, authorized_by,
                    authorization_statement, request_hash,
                    selected_agent_ids_json, reservation_ids_json, state,
                    validation_evidence_json, validation_only, requested_at,
                    admitted_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "execution-003",
                    "delegation-001",
                    "parent-task-001",
                    '["child-task-001"]',
                    "authorization-003",
                    "dipen-owner",
                    "bounded execution",
                    "request-hash-003",
                    '["system-agent"]',
                    '["reservation-003"]',
                    "completed",
                    "[]",
                    0,
                    now.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO executive_execution_starts (
                    idempotency_key, execution_id, request_hash, status,
                    response_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "start-key-003",
                    "execution-003",
                    "start-hash-003",
                    "completed",
                    stored_response.model_dump_json(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.commit()

        status = self.status_service.get("execution-003")

        self.assertEqual(status.state, "completed")
        self.assertEqual(status.parent_task.task_id, "parent-task-001")
        self.assertEqual([task.task_id for task in status.child_tasks], ["child-task-001"])
        self.assertEqual(status.active_reservation_ids, [])
        self.assertFalse(status.broker_activated)

    def test_unknown_execution_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            self.status_service.get("execution-missing")


if __name__ == "__main__":
    unittest.main()
