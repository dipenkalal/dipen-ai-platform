import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from agents.truth_repository import AgentTruthRepository
from executive_office.execution_cancellation_repository import (
    CancellationStateConflictError,
    ExecutiveExecutionCancellationRepository,
)
from executive_office.execution_cancellation_schemas import (
    ExecutiveRunningCancellationRequest,
    OwnerRunningCancellationAuthorization,
)
from executive_office.execution_cancellation_service import (
    ExecutiveExecutionCancellationService,
)
from executive_office.execution_repository import ExecutiveExecutionRepository
from executive_office.execution_start_repository import (
    ExecutionStartClaim,
    ExecutiveExecutionStartRepository,
)
from executive_office.execution_start_service import ExecutiveExecutionStartService
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import utc_now


class ExecutiveExecutionCancellationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = (
            Path(self.temporary_directory.name)
            / "execution-cancellation.db"
        )
        self.truth_repository = AgentTruthRepository(database_path)
        ExecutiveExecutionRepository(self.truth_repository)
        self.start_repository = ExecutiveExecutionStartRepository(
            self.truth_repository
        )
        self.repository = ExecutiveExecutionCancellationRepository(
            self.truth_repository
        )
        self.service = ExecutiveExecutionCancellationService(
            cancellation_repository=self.repository,
            start_repository=self.start_repository,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def seed_execution(
        self,
        *,
        execution_id: str = "execution-001",
        state: str = "running",
        validation_only: bool = False,
    ) -> None:
        now = utc_now().isoformat()

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
                    execution_id,
                    "delegation-001",
                    "parent-task-001",
                    json.dumps(["child-task-001"]),
                    "execution-authorization-001",
                    "dipen-owner",
                    "Authorize bounded execution.",
                    "execution-request-hash",
                    json.dumps(["system-agent"]),
                    json.dumps(["reservation-001"]),
                    state,
                    "[]",
                    int(validation_only),
                    now,
                    now,
                    now,
                ),
            )
            connection.commit()

    def request_cancellation(
        self,
        *,
        request_hash: str = "cancel-request-hash",
        idempotency_key: str = "cancel-request-0001",
        child_task_ids: list[str] | None = None,
    ):
        return self.repository.request(
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            execution_id="execution-001",
            delegation_id="delegation-001",
            parent_task_id="parent-task-001",
            child_task_ids=child_task_ids or ["child-task-001"],
            authorization_id="cancel-authorization-001",
            requested_by="dipen-owner",
            authorization_statement=(
                "Request cooperative cancellation of the exact running execution."
            ),
        )

    def service_request(
        self,
        *,
        idempotency_key: str = "service-cancel-0001",
        authorized_execution_id: str = "execution-001",
    ) -> ExecutiveRunningCancellationRequest:
        return ExecutiveRunningCancellationRequest(
            idempotency_key=idempotency_key,
            owner_authorization=OwnerRunningCancellationAuthorization(
                authorization_id="service-cancel-authorization-001",
                execution_id=authorized_execution_id,
                delegation_id="delegation-001",
                parent_task_id="parent-task-001",
                child_task_ids=["child-task-001"],
                statement="Stop this exact running execution cooperatively.",
            ),
        )

    def execution_state(self) -> str:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT state
                FROM executive_execution_records
                WHERE execution_id = 'execution-001'
                """
            ).fetchone()

        assert row is not None
        return str(row["state"])

    def test_request_persists_intent_without_mutating_execution(self) -> None:
        self.seed_execution()

        record = self.request_cancellation()

        self.assertEqual(record.state, "requested")
        self.assertEqual(record.execution_id, "execution-001")
        self.assertEqual(record.requested_by, "dipen-owner")
        self.assertFalse(record.idempotent_replay)
        self.assertIsNone(record.observed_at)
        self.assertIsNone(record.resolved_at)
        self.assertEqual(self.execution_state(), "running")

    def test_service_binds_authorization_to_exact_execution(self) -> None:
        self.seed_execution()

        record = self.service.request(
            execution_id="execution-001",
            request=self.service_request(),
        )

        self.assertEqual(record.execution_id, "execution-001")
        self.assertEqual(record.state, "requested")

        with self.assertRaises(CancellationStateConflictError):
            self.service.request(
                execution_id="execution-001",
                request=self.service_request(
                    idempotency_key="service-cancel-0002",
                    authorized_execution_id="different-execution",
                ),
            )

    def test_same_request_replays_and_changed_hash_conflicts(self) -> None:
        self.seed_execution()
        first = self.request_cancellation()
        replay = self.request_cancellation()

        self.assertEqual(first.cancellation_id, replay.cancellation_id)
        self.assertTrue(replay.idempotent_replay)

        with self.assertRaises(IdempotencyConflictError):
            self.request_cancellation(request_hash="different-request-hash")

    def test_non_running_execution_is_rejected(self) -> None:
        self.seed_execution(state="completed")

        with self.assertRaises(CancellationStateConflictError):
            self.request_cancellation()

        self.assertIsNone(
            self.repository.get_for_execution("execution-001")
        )

    def test_execution_identity_mismatch_is_rejected(self) -> None:
        self.seed_execution()

        with self.assertRaises(CancellationStateConflictError):
            self.request_cancellation(child_task_ids=["different-child"])

    def test_runtime_can_acknowledge_and_resolve_intent(self) -> None:
        self.seed_execution()
        self.request_cancellation()

        observed = self.repository.mark_observed("execution-001")
        resolved = self.repository.mark_resolved("execution-001")

        self.assertEqual(observed.state, "observed")
        self.assertIsNotNone(observed.observed_at)
        self.assertEqual(resolved.state, "resolved")
        self.assertIsNotNone(resolved.observed_at)
        self.assertIsNotNone(resolved.resolved_at)
        self.assertEqual(self.execution_state(), "running")


class FakeCancellationRepository:
    def __init__(self) -> None:
        self.calls = 0
        self.observed: list[str] = []

    def get_for_execution(self, execution_id: str):
        del execution_id
        self.calls += 1

        if self.calls == 1:
            return None

        return SimpleNamespace(state="requested")

    def mark_observed(self, execution_id: str):
        self.observed.append(execution_id)
        return SimpleNamespace(state="observed")


class FakeCancellationReconciler:
    def __init__(self) -> None:
        self.responses = []

    def finalize_observed(self, *, claim, idempotency_key, response):
        del claim, idempotency_key
        self.responses.append(response)
        return response


class FakeTruthService:
    def get_task(self, task_id: str):
        return SimpleNamespace(
            task_id=task_id,
            objective=f"Execute {task_id}",
        )


class FakeRunner:
    def __init__(self) -> None:
        self.tasks: list[str] = []

    async def run(self, *, request, task, delegation_id):
        del request, delegation_id
        self.tasks.append(task.task_id)
        now = datetime.now(timezone.utc)
        return SimpleNamespace(
            status="completed",
            run_id=f"run-{task.task_id}",
            answer="completed",
            started_at=now,
            completed_at=now,
        )


class FakeCompletionService:
    def reconcile_terminal(self, *, claim, response):
        del claim
        return response


class FakeStartRepository:
    pass


class ExecutiveExecutionCancellationCheckpointTests(
    unittest.IsolatedAsyncioTestCase
):
    async def test_checkpoint_stops_before_next_child(self) -> None:
        cancellation_repository = FakeCancellationRepository()
        cancellation_reconciler = FakeCancellationReconciler()
        runner = FakeRunner()
        service = ExecutiveExecutionStartService(
            truth_service=FakeTruthService(),
            start_repository=FakeStartRepository(),
            completion_service=FakeCompletionService(),
            runner=runner,
            cancellation_repository=cancellation_repository,
            cancellation_reconciler=cancellation_reconciler,
        )
        claim = ExecutionStartClaim(
            execution_id="execution-001",
            delegation_id="delegation-001",
            parent_task_id="parent-task-001",
            child_task_ids=("child-task-001", "child-task-002"),
            selected_agent_ids=("system-agent", "research-agent"),
            reservation_ids=("reservation-001", "reservation-002"),
        )

        response = await service._run_claimed_execution(
            claim=claim,
            idempotency_key="start-request-0001",
        )

        self.assertEqual(runner.tasks, ["child-task-001"])
        self.assertEqual(cancellation_repository.observed, ["execution-001"])
        self.assertEqual(len(cancellation_reconciler.responses), 1)
        self.assertEqual(response.state, "cancelled")
        self.assertEqual(response.disposition, "cancelled")
        self.assertEqual(response.parent_task_status, "manual_review")
        self.assertEqual(len(response.task_results), 1)
        self.assertTrue(response.reservation_released)
        self.assertFalse(response.broker_activated)


if __name__ == "__main__":
    unittest.main()
