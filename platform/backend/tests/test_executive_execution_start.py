import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

_TEST_DATA_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="dap-execution-start-tests-")
)
os.environ.setdefault(
    "KNOWLEDGE_UPLOAD_DIRECTORY",
    str(_TEST_DATA_DIRECTORY / "knowledge-uploads"),
)
os.environ.setdefault(
    "DAP_AGENT_TRUTH_DB",
    str(_TEST_DATA_DIRECTORY / "global-agent-truth.db"),
)

from agents.registry import agent_registry
from agents.runtime_instrumentation import (
    InstrumentedAgentExecutor,
    RuntimeInstrumentation,
)
from agents.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentUsage,
)
from agents.truth_repository import AgentTruthRepository
from agents.truth_service import AgentTruthService
from app import app
from executive_office.delegation_service import ExecutiveDelegationService
from executive_office.execution_repository import (
    ExecutiveExecutionRepository,
)
from executive_office.execution_reservation_service import (
    ExecutiveReservationService,
)
from executive_office.execution_runner import ExecutiveExistingTaskRunner
from executive_office.execution_start_repository import (
    ExecutiveExecutionStartRepository,
)
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartRequest,
    OwnerExecutionStartAuthorization,
)
from executive_office.execution_start_service import (
    ExecutiveExecutionStartService,
)
from executive_office.repository import (
    ExecutiveDelegationRepository,
    IdempotencyConflictError,
)
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutiveExecutionRequest,
    ExecutivePlanRequest,
    OwnerExecutionAuthorization,
)
from executive_office.service import ExecutiveOfficeService


class FakeRawAgentExecutor:
    def __init__(
        self,
        *,
        status: str = "completed",
        answer: str = "Bounded agent work completed.",
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.answer = answer
        self.error = error
        self.requests: list[AgentRunRequest] = []

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        self.requests.append(request)

        if self.error is not None:
            raise self.error

        now = datetime.now(timezone.utc)
        return AgentRunResponse(
            run_id=f"start-run-{len(self.requests)}",
            agent_id=request.agent_id or "unknown-agent",
            objective=request.objective,
            status=self.status,
            answer=self.answer,
            steps=[],
            usage=AgentUsage(latency_ms=1.0),
            started_at=now,
            completed_at=now,
        )


class ExecutiveExecutionStartTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = (
            Path(self.temporary_directory.name)
            / "bounded-execution-start.db"
        )
        self.truth_repository = AgentTruthRepository(database_path)
        self.truth_service = AgentTruthService(
            agent_registry,
            self.truth_repository,
        )
        delegation_repository = ExecutiveDelegationRepository(
            self.truth_repository
        )
        self.execution_repository = ExecutiveExecutionRepository(
            self.truth_repository
        )
        self.start_repository = ExecutiveExecutionStartRepository(
            self.truth_repository
        )
        advisory_service = ExecutiveOfficeService()
        self.delegation_service = ExecutiveDelegationService(
            advisory_service=advisory_service,
            truth_service=self.truth_service,
            delegation_repository=delegation_repository,
        )
        self.reservation_service = ExecutiveReservationService(
            delegation_service=self.delegation_service,
            advisory_service=advisory_service,
            truth_service=self.truth_service,
            execution_repository=self.execution_repository,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def reserve_execution(
        self,
        *,
        suffix: str,
    ):
        delegation = self.delegation_service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(
                    objectives=["Research storage upgrade options"]
                ),
                idempotency_key=f"start-source-{suffix}",
            )
        )
        self.assertEqual(delegation.disposition, "delegated")
        parent = delegation.parent_task
        assert parent is not None
        child_task_ids = [
            task.task_id for task in delegation.child_tasks
        ]
        reservation = self.reservation_service.admit(
            ExecutiveExecutionRequest(
                delegation_id=delegation.delegation_id,
                parent_task_id=parent.task_id,
                child_task_ids=child_task_ids,
                idempotency_key=f"start-reservation-{suffix}",
                validation_only=False,
                owner_authorization=OwnerExecutionAuthorization(
                    authorization_id=f"reserve-owner-{suffix}",
                    delegation_id=delegation.delegation_id,
                    parent_task_id=parent.task_id,
                    child_task_ids=child_task_ids,
                    validation_only=False,
                    statement=(
                        "Authorize exact task reservation without silently "
                        "starting the executor."
                    ),
                ),
            )
        )
        self.assertEqual(reservation.disposition, "reserved")
        return delegation, reservation

    @staticmethod
    def start_request(
        *,
        delegation,
        reservation,
        suffix: str,
        statement: str = "Start the exact reserved bounded agent execution.",
        execution_id: str | None = None,
    ) -> ExecutiveExecutionStartRequest:
        selected_execution_id = execution_id or reservation.execution_id
        return ExecutiveExecutionStartRequest(
            idempotency_key=f"start-request-{suffix}",
            owner_authorization=OwnerExecutionStartAuthorization(
                authorization_id=f"start-owner-{suffix}",
                execution_id=selected_execution_id,
                delegation_id=delegation.delegation_id,
                child_task_ids=list(reservation.child_task_ids),
                statement=statement,
            ),
        )

    def service(
        self,
        raw_executor: FakeRawAgentExecutor,
    ) -> ExecutiveExecutionStartService:
        instrumented = InstrumentedAgentExecutor(
            raw_executor,
            RuntimeInstrumentation(self.truth_service),
            heartbeat_interval_seconds=60.0,
        )
        runner = ExecutiveExistingTaskRunner(
            instrumented,
            truth_service=self.truth_service,
        )
        return ExecutiveExecutionStartService(
            reservation_service=self.reservation_service,
            truth_service=self.truth_service,
            start_repository=self.start_repository,
            runner=runner,
        )

    def execution_state(self, execution_id: str) -> str:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT state
                FROM executive_execution_records
                WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()

        assert row is not None
        return str(row["state"])

    def active_reservation_count(self, execution_id: str) -> int:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM executive_execution_reservations
                WHERE execution_id = ? AND released_at IS NULL
                """,
                (execution_id,),
            ).fetchone()

        assert row is not None
        return int(row["total"])

    async def test_completed_start_runs_once_and_releases_reservation(self) -> None:
        delegation, reservation = self.reserve_execution(suffix="success-0001")
        raw_executor = FakeRawAgentExecutor()
        service = self.service(raw_executor)
        request = self.start_request(
            delegation=delegation,
            reservation=reservation,
            suffix="success-0001",
        )

        response = await service.start(
            execution_id=reservation.execution_id,
            request=request,
        )

        self.assertEqual(response.disposition, "completed")
        self.assertEqual(response.state, "completed")
        self.assertTrue(response.execution_started)
        self.assertTrue(response.reservation_released)
        self.assertFalse(response.broker_activated)
        self.assertEqual(len(response.task_results), 1)
        self.assertEqual(len(raw_executor.requests), 1)
        child = self.truth_service.get_task(
            reservation.child_task_ids[0]
        )
        self.assertEqual(child.status, "completed")
        self.assertEqual(child.source_run_id, delegation.delegation_id)
        self.assertEqual(
            self.execution_state(reservation.execution_id),
            "completed",
        )
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            0,
        )
        agent_id = reservation.selected_agent_ids[0]
        state = self.truth_service.get_agent_state(agent_id)
        self.assertEqual(state.runtime_status, "available")
        self.assertIsNone(state.current_task_id)

    async def test_failed_agent_result_releases_reservation(self) -> None:
        delegation, reservation = self.reserve_execution(suffix="failed-0001")
        raw_executor = FakeRawAgentExecutor(
            status="failed",
            answer="The bounded agent returned a deterministic failure.",
        )
        service = self.service(raw_executor)

        response = await service.start(
            execution_id=reservation.execution_id,
            request=self.start_request(
                delegation=delegation,
                reservation=reservation,
                suffix="failed-0001",
            ),
        )

        self.assertEqual(response.disposition, "failed")
        self.assertEqual(response.state, "failed")
        self.assertTrue(response.reservation_released)
        child = self.truth_service.get_task(
            reservation.child_task_ids[0]
        )
        self.assertEqual(child.status, "failed")
        self.assertEqual(
            self.execution_state(reservation.execution_id),
            "failed",
        )
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            0,
        )

    async def test_same_start_request_replays_without_second_run(self) -> None:
        delegation, reservation = self.reserve_execution(suffix="replay-0001")
        raw_executor = FakeRawAgentExecutor()
        service = self.service(raw_executor)
        request = self.start_request(
            delegation=delegation,
            reservation=reservation,
            suffix="replay-0001",
        )

        first = await service.start(
            execution_id=reservation.execution_id,
            request=request,
        )
        replay = await service.start(
            execution_id=reservation.execution_id,
            request=request,
        )

        self.assertEqual(first.disposition, "completed")
        self.assertEqual(replay.disposition, "idempotent_replay")
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(len(raw_executor.requests), 1)

    async def test_changed_reuse_of_start_key_conflicts(self) -> None:
        delegation, reservation = self.reserve_execution(suffix="conflict-0001")
        raw_executor = FakeRawAgentExecutor()
        service = self.service(raw_executor)
        first = self.start_request(
            delegation=delegation,
            reservation=reservation,
            suffix="conflict-0001",
        )
        changed = self.start_request(
            delegation=delegation,
            reservation=reservation,
            suffix="conflict-0001",
            statement="A different bounded execution-start purpose.",
        )
        await service.start(
            execution_id=reservation.execution_id,
            request=first,
        )

        with self.assertRaises(IdempotencyConflictError):
            await service.start(
                execution_id=reservation.execution_id,
                request=changed,
            )

        self.assertEqual(len(raw_executor.requests), 1)

    async def test_authorization_mismatch_does_not_claim_or_run(self) -> None:
        delegation, reservation = self.reserve_execution(suffix="auth-0001")
        raw_executor = FakeRawAgentExecutor()
        service = self.service(raw_executor)
        request = self.start_request(
            delegation=delegation,
            reservation=reservation,
            suffix="auth-0001",
            execution_id="different-execution-id",
        )

        response = await service.start(
            execution_id=reservation.execution_id,
            request=request,
        )

        self.assertEqual(response.disposition, "authorization_required")
        self.assertFalse(response.execution_started)
        self.assertEqual(raw_executor.requests, [])
        self.assertEqual(
            self.execution_state(reservation.execution_id),
            "reserved",
        )
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            1,
        )

    async def test_stale_queued_task_is_rejected_before_runner(self) -> None:
        delegation, reservation = self.reserve_execution(suffix="stale-0001")
        child = self.truth_service.get_task(
            reservation.child_task_ids[0]
        )
        self.truth_service.upsert_task(
            child.model_copy(update={"status": "assigned"})
        )
        raw_executor = FakeRawAgentExecutor()
        service = self.service(raw_executor)

        response = await service.start(
            execution_id=reservation.execution_id,
            request=self.start_request(
                delegation=delegation,
                reservation=reservation,
                suffix="stale-0001",
            ),
        )

        self.assertEqual(response.disposition, "state_conflict")
        self.assertFalse(response.execution_started)
        self.assertEqual(raw_executor.requests, [])
        self.assertEqual(
            self.execution_state(reservation.execution_id),
            "reserved",
        )

    async def test_ambiguous_exception_enters_manual_review_and_replays(self) -> None:
        delegation, reservation = self.reserve_execution(suffix="review-0001")
        raw_executor = FakeRawAgentExecutor(
            error=RuntimeError("simulated ambiguous provider disconnect")
        )
        service = self.service(raw_executor)
        request = self.start_request(
            delegation=delegation,
            reservation=reservation,
            suffix="review-0001",
        )

        first = await service.start(
            execution_id=reservation.execution_id,
            request=request,
        )
        replay = await service.start(
            execution_id=reservation.execution_id,
            request=request,
        )

        self.assertEqual(first.disposition, "manual_review")
        self.assertEqual(first.state, "manual_review")
        self.assertFalse(first.reservation_released)
        self.assertEqual(replay.disposition, "idempotent_replay")
        self.assertEqual(len(raw_executor.requests), 1)
        self.assertEqual(
            self.execution_state(reservation.execution_id),
            "manual_review",
        )
        self.assertEqual(
            self.active_reservation_count(reservation.execution_id),
            1,
        )

    async def test_nonterminal_agent_response_enters_manual_review(self) -> None:
        delegation, reservation = self.reserve_execution(
            suffix="nonterminal-0001"
        )
        raw_executor = FakeRawAgentExecutor(status="running")
        service = self.service(raw_executor)

        response = await service.start(
            execution_id=reservation.execution_id,
            request=self.start_request(
                delegation=delegation,
                reservation=reservation,
                suffix="nonterminal-0001",
            ),
        )

        self.assertEqual(response.disposition, "manual_review")
        self.assertFalse(response.reservation_released)
        self.assertEqual(len(raw_executor.requests), 1)
        self.assertEqual(
            self.execution_state(reservation.execution_id),
            "manual_review",
        )

    def test_status_reports_execution_without_broker_activation(self) -> None:
        service = self.service(FakeRawAgentExecutor())

        status = service.status()

        self.assertTrue(status.execution_admission_enabled)
        self.assertTrue(status.execution_reservation_enabled)
        self.assertTrue(status.execution_enabled)
        self.assertFalse(status.broker_activation_enabled)


class ExecutiveExecutionStartApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.async_case = ExecutiveExecutionStartTests(
            methodName="test_status_reports_execution_without_broker_activation"
        )
        self.async_case.setUp()
        self.addCleanup(self.async_case.tearDown)
        self.delegation, self.reservation = (
            self.async_case.reserve_execution(suffix="api-0001")
        )
        self.raw_executor = FakeRawAgentExecutor()
        self.service = self.async_case.service(self.raw_executor)
        self.client = TestClient(app)

    def payload(self, statement: str) -> dict:
        return {
            "idempotency_key": "start-request-api-0001",
            "owner_authorization": {
                "authorization_id": "start-owner-api-0001",
                "execution_id": self.reservation.execution_id,
                "delegation_id": self.delegation.delegation_id,
                "child_task_ids": self.reservation.child_task_ids,
                "authorized_by": "dipen-owner",
                "approved": True,
                "scope": "start_reserved_execution",
                "statement": statement,
            },
        }

    def test_start_endpoint_maps_changed_idempotency_to_409(self) -> None:
        route = (
            "/api/v1/executive-office/executions/"
            f"{self.reservation.execution_id}/start"
        )

        with patch(
            "executive_office.routes.executive_execution_start_service",
            self.service,
        ):
            first = self.client.post(
                route,
                json=self.payload("Start the exact reserved execution."),
            )
            second = self.client.post(
                route,
                json=self.payload("A changed execution-start purpose."),
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["disposition"], "completed")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(len(self.raw_executor.requests), 1)


if __name__ == "__main__":
    unittest.main()
