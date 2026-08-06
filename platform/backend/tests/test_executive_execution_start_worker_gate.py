import os
import tempfile
import unittest
from pathlib import Path

_TEST_DATA_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="dap-execution-worker-gate-tests-")
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
from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import AgentHeartbeat
from agents.truth_service import AgentTruthService
from executive_office.delegation_service import ExecutiveDelegationService
from executive_office.execution_repository import (
    ExecutiveExecutionRepository,
)
from executive_office.execution_reservation_service import (
    ExecutiveReservationService,
)
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
from executive_office.repository import ExecutiveDelegationRepository
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutiveExecutionRequest,
    ExecutivePlanRequest,
    OwnerExecutionAuthorization,
)
from executive_office.service import ExecutiveOfficeService


class NeverCalledRunner:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **kwargs):
        del kwargs
        self.calls += 1
        raise AssertionError("The busy-worker gate did not block execution.")


class ExecutiveExecutionStartWorkerGateTests(
    unittest.IsolatedAsyncioTestCase
):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = (
            Path(self.temporary_directory.name)
            / "execution-worker-gate.db"
        )
        self.truth_repository = AgentTruthRepository(database_path)
        self.truth_service = AgentTruthService(
            agent_registry,
            self.truth_repository,
        )
        delegation_repository = ExecutiveDelegationRepository(
            self.truth_repository
        )
        execution_repository = ExecutiveExecutionRepository(
            self.truth_repository
        )
        start_repository = ExecutiveExecutionStartRepository(
            self.truth_repository
        )
        advisory_service = ExecutiveOfficeService()
        delegation_service = ExecutiveDelegationService(
            advisory_service=advisory_service,
            truth_service=self.truth_service,
            delegation_repository=delegation_repository,
        )
        reservation_service = ExecutiveReservationService(
            delegation_service=delegation_service,
            advisory_service=advisory_service,
            truth_service=self.truth_service,
            execution_repository=execution_repository,
        )
        delegation = delegation_service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(
                    objectives=["Research storage upgrade options"]
                ),
                idempotency_key="worker-gate-source-0001",
            )
        )
        self.assertEqual(delegation.disposition, "delegated")
        parent = delegation.parent_task
        assert parent is not None
        child_task_ids = [
            task.task_id for task in delegation.child_tasks
        ]
        reservation = reservation_service.admit(
            ExecutiveExecutionRequest(
                delegation_id=delegation.delegation_id,
                parent_task_id=parent.task_id,
                child_task_ids=child_task_ids,
                idempotency_key="worker-gate-reservation-0001",
                validation_only=False,
                owner_authorization=OwnerExecutionAuthorization(
                    authorization_id="worker-gate-reserve-owner-0001",
                    delegation_id=delegation.delegation_id,
                    parent_task_id=parent.task_id,
                    child_task_ids=child_task_ids,
                    validation_only=False,
                    statement=(
                        "Reserve the exact task without starting its agent."
                    ),
                ),
            )
        )
        self.assertEqual(reservation.disposition, "reserved")
        self.delegation = delegation
        self.reservation = reservation
        self.runner = NeverCalledRunner()
        self.service = ExecutiveExecutionStartService(
            reservation_service=reservation_service,
            truth_service=self.truth_service,
            start_repository=start_repository,
            runner=self.runner,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def active_reservation_count(self) -> int:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM executive_execution_reservations
                WHERE execution_id = ? AND released_at IS NULL
                """,
                (self.reservation.execution_id,),
            ).fetchone()

        assert row is not None
        return int(row["total"])

    def execution_state(self) -> str:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT state
                FROM executive_execution_records
                WHERE execution_id = ?
                """,
                (self.reservation.execution_id,),
            ).fetchone()

        assert row is not None
        return str(row["state"])

    async def test_busy_worker_enters_manual_review_without_runner(self) -> None:
        agent_id = self.reservation.selected_agent_ids[0]
        self.truth_service.record_heartbeat(
            AgentHeartbeat(
                agent_id=agent_id,
                worker_id="worker-gate-test-runtime",
                status="busy",
                current_task_id="unrelated-running-task",
            )
        )
        request = ExecutiveExecutionStartRequest(
            idempotency_key="worker-gate-start-0001",
            owner_authorization=OwnerExecutionStartAuthorization(
                authorization_id="worker-gate-start-owner-0001",
                execution_id=self.reservation.execution_id,
                delegation_id=self.delegation.delegation_id,
                child_task_ids=list(self.reservation.child_task_ids),
                statement="Start only if the reserved agent remains available.",
            ),
        )

        first = await self.service.start(
            execution_id=self.reservation.execution_id,
            request=request,
        )
        replay = await self.service.start(
            execution_id=self.reservation.execution_id,
            request=request,
        )

        self.assertEqual(first.disposition, "manual_review")
        self.assertEqual(first.state, "manual_review")
        self.assertFalse(first.execution_started)
        self.assertFalse(first.reservation_released)
        self.assertEqual(replay.disposition, "idempotent_replay")
        self.assertEqual(self.runner.calls, 0)
        self.assertEqual(self.execution_state(), "manual_review")
        self.assertEqual(self.active_reservation_count(), 1)


if __name__ == "__main__":
    unittest.main()
