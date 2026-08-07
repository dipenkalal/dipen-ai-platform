import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agents.registry import agent_registry
from agents.runtime_instrumentation import (
    InstrumentedAgentExecutor,
    RuntimeInstrumentation,
)
from agents.schemas import AgentRunRequest, AgentRunResponse
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
from executive_office.execution_runner import ExecutiveExistingTaskRunner
from executive_office.execution_start_repository import (
    ExecutionStartClaim,
    ExecutiveExecutionStartRepository,
)
from executive_office.execution_start_service import ExecutiveExecutionStartService
from executive_office.execution_status_service import (
    ExecutiveExecutionStatusService,
)
from tools.base import (
    BaseTool,
    CancellationAwareTool,
    ToolDefinition,
    ToolExecutionResult,
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


class DurableCancellationRequestTool(BaseTool):
    definition = ToolDefinition(
        id="test.request-durable-cancellation",
        name="Request durable cancellation",
        description="Create the real owner cancellation record during bounded work.",
        category="test",
    )

    def __init__(
        self,
        cancellation_repository: ExecutiveExecutionCancellationRepository,
    ) -> None:
        self.cancellation_repository = cancellation_repository
        self.calls = 0

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        self.calls += 1
        self.cancellation_repository.request(
            idempotency_key="cancel-in-child-0001",
            request_hash="cancel-in-child-hash",
            execution_id="execution-in-child-001",
            delegation_id="delegation-in-child-001",
            parent_task_id="parent-in-child-001",
            child_task_ids=["child-in-child-001"],
            authorization_id="cancel-in-child-authorization-001",
            requested_by="dipen-owner",
            authorization_statement=(
                "Stop this exact bounded execution cooperatively from inside the child."
            ),
        )
        return ToolExecutionResult(
            tool_id=self.definition.id,
            success=True,
            output=arguments,
        )


class ToolCallingAgentExecutor:
    def __init__(self, tool: BaseTool) -> None:
        self.tool = CancellationAwareTool(tool)
        self.calls = 0

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        self.calls += 1
        await self.tool.execute({"objective": request.objective})
        raise AssertionError(
            "The cancellation-aware tool should stop the child after returning."
        )


class ExecutiveInChildCancellationEndToEndTests(
    unittest.IsolatedAsyncioTestCase
):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "in-child-cancellation.db"
        self.truth_repository = AgentTruthRepository(database_path)
        self.truth_service = AgentTruthService(agent_registry, self.truth_repository)
        ExecutiveExecutionRepository(self.truth_repository)
        ExecutiveExecutionStartRepository(self.truth_repository)
        self.cancellation_repository = ExecutiveExecutionCancellationRepository(
            self.truth_repository
        )
        self.reconciler = ExecutiveExecutionCancellationReconciler(
            self.truth_repository
        )
        self.status_service = ExecutiveExecutionStatusService(
            truth_service=self.truth_service,
            truth_repository=self.truth_repository,
            cancellation_repository=self.cancellation_repository,
        )
        self.now = datetime(2026, 8, 7, 6, 40, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def seed_running_execution(self) -> ExecutionStartClaim:
        parent = TaskLedgerRecord(
            task_id="parent-in-child-001",
            task_type="orchestration",
            objective="Coordinate one bounded child",
            status="planned",
            requested_by="dipen-owner",
            source_run_id="delegation-in-child-001",
            created_at=self.now,
            updated_at=self.now,
        )
        child = TaskLedgerRecord(
            task_id="child-in-child-001",
            task_type="agent",
            objective="Run one cancellable tool boundary",
            status="queued",
            requested_by="dipen-owner",
            assigned_agent_ids=["system-agent"],
            source_run_id="delegation-in-child-001",
            parent_task_id="parent-in-child-001",
            created_at=self.now,
            updated_at=self.now,
        )
        self.truth_repository.upsert_task(parent)
        self.truth_repository.upsert_task(child)

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
                    "execution-in-child-001",
                    "delegation-in-child-001",
                    "parent-in-child-001",
                    json.dumps(["child-in-child-001"]),
                    "execution-in-child-authorization-001",
                    "dipen-owner",
                    "Authorize one bounded child execution.",
                    "execution-in-child-request-hash",
                    json.dumps(["system-agent"]),
                    json.dumps(["reservation-in-child-001"]),
                    "running",
                    "[]",
                    0,
                    self.now.isoformat(),
                    self.now.isoformat(),
                    self.now.isoformat(),
                ),
            )
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
                    "reservation-in-child-001",
                    "execution-in-child-001",
                    "system-agent",
                    "child-in-child-001",
                    self.now.isoformat(),
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
                    "start-in-child-0001",
                    "execution-in-child-001",
                    "start-in-child-hash",
                    self.now.isoformat(),
                    self.now.isoformat(),
                ),
            )
            connection.commit()

        return ExecutionStartClaim(
            execution_id="execution-in-child-001",
            delegation_id="delegation-in-child-001",
            parent_task_id="parent-in-child-001",
            child_task_ids=("child-in-child-001",),
            selected_agent_ids=("system-agent",),
            reservation_ids=("reservation-in-child-001",),
        )

    async def test_durable_request_inside_tool_reconciles_atomically(self) -> None:
        claim = self.seed_running_execution()
        request_tool = DurableCancellationRequestTool(
            self.cancellation_repository
        )
        raw_executor = ToolCallingAgentExecutor(request_tool)
        instrumented = InstrumentedAgentExecutor(
            raw_executor,
            RuntimeInstrumentation(self.truth_service),
            heartbeat_interval_seconds=60.0,
        )
        runner = ExecutiveExistingTaskRunner(
            instrumented,
            truth_service=self.truth_service,
        )
        service = ExecutiveExecutionStartService(
            truth_service=self.truth_service,
            start_repository=ExecutiveExecutionStartRepository(
                self.truth_repository
            ),
            runner=runner,
            cancellation_repository=self.cancellation_repository,
            cancellation_reconciler=self.reconciler,
        )

        response = await service._run_claimed_execution(
            claim=claim,
            idempotency_key="start-in-child-0001",
        )
        status = self.status_service.get("execution-in-child-001")

        self.assertEqual(request_tool.calls, 1)
        self.assertEqual(raw_executor.calls, 1)
        self.assertEqual(response.state, "cancelled")
        self.assertEqual(response.disposition, "cancelled")
        self.assertTrue(response.reservation_released)
        self.assertFalse(response.broker_activated)
        self.assertIn("after-tool-call", response.message)
        self.assertEqual(status.state, "cancelled")
        self.assertEqual(status.active_reservation_ids, [])
        self.assertEqual(status.parent_task.status, "manual_review")
        self.assertEqual(status.child_tasks[0].status, "cancelled")
        self.assertIsNotNone(status.cancellation)
        assert status.cancellation is not None
        self.assertEqual(status.cancellation.state, "resolved")

        with self.truth_repository.connection() as connection:
            start = connection.execute(
                """
                SELECT status
                FROM executive_execution_starts
                WHERE execution_id = ? AND idempotency_key = ?
                """,
                ("execution-in-child-001", "start-in-child-0001"),
            ).fetchone()

        assert start is not None
        self.assertEqual(str(start["status"]), "cancelled")


if __name__ == "__main__":
    unittest.main()
