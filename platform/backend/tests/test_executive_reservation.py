import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TEST_DATA_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="dap-execution-reservation-tests-")
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
from agents.truth_service import AgentTruthService
from executive_office.delegation_service import ExecutiveDelegationService
from executive_office.execution_repository import (
    ExecutiveExecutionRepository,
)
from executive_office.execution_reservation_service import (
    ExecutiveReservationService,
)
from executive_office.repository import ExecutiveDelegationRepository
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutiveExecutionRequest,
    ExecutivePlanRequest,
    OwnerExecutionAuthorization,
)
from executive_office.service import ExecutiveOfficeService


class ExecutiveExecutionReservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = (
            Path(self.temporary_directory.name)
            / "execution-reservation.db"
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
        advisory_service = ExecutiveOfficeService()
        delegation_service = ExecutiveDelegationService(
            advisory_service=advisory_service,
            truth_service=self.truth_service,
            delegation_repository=delegation_repository,
        )
        self.delegation_service = delegation_service
        self.service = ExecutiveReservationService(
            delegation_service=delegation_service,
            advisory_service=advisory_service,
            truth_service=self.truth_service,
            execution_repository=self.execution_repository,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_delegation(
        self,
        *,
        idempotency_key: str,
    ):
        response = self.delegation_service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(
                    objectives=["Research storage upgrade options"]
                ),
                idempotency_key=idempotency_key,
            )
        )
        self.assertEqual(response.disposition, "delegated")
        self.assertIsNotNone(response.parent_task)
        self.assertEqual(len(response.child_tasks), 1)
        return response

    @staticmethod
    def build_request(
        delegation,
        *,
        idempotency_key: str,
        validation_only: bool,
    ) -> ExecutiveExecutionRequest:
        parent = delegation.parent_task
        assert parent is not None
        child_task_ids = [
            task.task_id for task in delegation.child_tasks
        ]
        authorization = OwnerExecutionAuthorization(
            authorization_id=f"owner-{idempotency_key}",
            delegation_id=delegation.delegation_id,
            parent_task_id=parent.task_id,
            child_task_ids=child_task_ids,
            validation_only=validation_only,
            statement=(
                "Authorize the exact selected tasks for bounded reservation "
                "without starting an executor or broker."
            ),
        )
        return ExecutiveExecutionRequest(
            delegation_id=delegation.delegation_id,
            parent_task_id=parent.task_id,
            child_task_ids=child_task_ids,
            idempotency_key=idempotency_key,
            validation_only=validation_only,
            owner_authorization=authorization,
        )

    def active_reservations(self) -> list[dict[str, str]]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT reservation_id, execution_id, agent_id, task_id
                FROM executive_execution_reservations
                WHERE released_at IS NULL
                ORDER BY reservation_id
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def test_reservation_queues_child_without_starting_executor(self) -> None:
        delegation = self.create_delegation(
            idempotency_key="reservation-source-0001"
        )
        parent = delegation.parent_task
        assert parent is not None
        child = delegation.child_tasks[0]

        with patch(
            "agents.runtime.instrumented_agent_executor.run"
        ) as executor_run:
            response = self.service.admit(
                self.build_request(
                    delegation,
                    idempotency_key="reservation-execution-0001",
                    validation_only=False,
                )
            )

        self.assertEqual(response.disposition, "reserved")
        self.assertEqual(response.state, "reserved")
        self.assertTrue(response.admission_validated)
        self.assertTrue(response.task_ledger_mutated)
        self.assertTrue(response.reservation_acquired)
        self.assertFalse(response.execution_started)
        self.assertFalse(response.broker_activated)
        self.assertEqual(len(response.reservation_ids), 1)
        self.assertEqual(
            self.truth_service.get_task(parent.task_id).status,
            "planned",
        )
        self.assertEqual(
            self.truth_service.get_task(child.task_id).status,
            "queued",
        )
        self.assertEqual(len(self.active_reservations()), 1)
        executor_run.assert_not_called()

    def test_reserved_replay_does_not_duplicate_reservation(self) -> None:
        delegation = self.create_delegation(
            idempotency_key="reservation-replay-source-0001"
        )
        request = self.build_request(
            delegation,
            idempotency_key="reservation-replay-0001",
            validation_only=False,
        )

        first = self.service.admit(request)
        replay = self.service.admit(request)

        self.assertEqual(first.disposition, "reserved")
        self.assertEqual(replay.disposition, "idempotent_replay")
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.execution_id, first.execution_id)
        self.assertEqual(len(self.active_reservations()), 1)

    def test_validation_only_detects_active_reservation(self) -> None:
        first_delegation = self.create_delegation(
            idempotency_key="reservation-validation-first-0001"
        )
        second_delegation = self.create_delegation(
            idempotency_key="reservation-validation-second-0001"
        )
        first = self.service.admit(
            self.build_request(
                first_delegation,
                idempotency_key="reservation-validation-acquire-0001",
                validation_only=False,
            )
        )
        second_child = second_delegation.child_tasks[0]

        second = self.service.admit(
            self.build_request(
                second_delegation,
                idempotency_key="reservation-validation-check-0001",
                validation_only=True,
            )
        )

        self.assertEqual(first.disposition, "reserved")
        self.assertEqual(second.disposition, "reservation_conflict")
        self.assertFalse(second.reservation_acquired)
        self.assertFalse(second.task_ledger_mutated)
        self.assertEqual(
            self.truth_service.get_task(second_child.task_id).status,
            "assigned",
        )

    def test_database_collision_rolls_back_second_task(self) -> None:
        first_delegation = self.create_delegation(
            idempotency_key="reservation-collision-first-0001"
        )
        second_delegation = self.create_delegation(
            idempotency_key="reservation-collision-second-0001"
        )
        first = self.service.admit(
            self.build_request(
                first_delegation,
                idempotency_key="reservation-collision-acquire-0001",
                validation_only=False,
            )
        )
        second_child = second_delegation.child_tasks[0]

        with patch.object(
            self.execution_repository,
            "list_active_reserved_agents",
            return_value=[],
        ):
            second = self.service.admit(
                self.build_request(
                    second_delegation,
                    idempotency_key="reservation-collision-attempt-0001",
                    validation_only=False,
                )
            )

        self.assertEqual(first.disposition, "reserved")
        self.assertEqual(second.disposition, "reservation_conflict")
        self.assertFalse(second.reservation_acquired)
        self.assertFalse(second.task_ledger_mutated)
        self.assertEqual(
            self.truth_service.get_task(second_child.task_id).status,
            "assigned",
        )
        self.assertEqual(len(self.active_reservations()), 1)

        with self.truth_repository.connection() as connection:
            records = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM executive_execution_records
                """
            ).fetchone()

        assert records is not None
        self.assertEqual(records["total"], 1)

    def test_status_reports_reservation_without_execution(self) -> None:
        status = self.service.status()

        self.assertTrue(status.execution_admission_enabled)
        self.assertTrue(status.execution_reservation_enabled)
        self.assertFalse(status.execution_enabled)
        self.assertFalse(status.broker_activation_enabled)


if __name__ == "__main__":
    unittest.main()
