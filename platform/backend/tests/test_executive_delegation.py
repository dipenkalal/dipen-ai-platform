import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

_TEST_DATA_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="dap-controlled-delegation-tests-")
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
from agents.truth_schemas import AgentHeartbeat, TaskLedgerRecord
from agents.truth_service import AgentTruthService
from app import app
from executive_office.delegation_service import ExecutiveDelegationService
from executive_office.repository import (
    ExecutiveDelegationRepository,
    IdempotencyConflictError,
)
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutivePlanRequest,
    OwnerApprovalRecord,
)
from executive_office.service import ExecutiveOfficeService


class ExecutiveDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = (
            Path(self.temporary_directory.name)
            / "controlled-delegation.db"
        )
        self.truth_repository = AgentTruthRepository(database_path)
        self.truth_service = AgentTruthService(
            agent_registry,
            self.truth_repository,
        )
        self.delegation_repository = ExecutiveDelegationRepository(
            self.truth_repository
        )
        self.advisory_service = ExecutiveOfficeService()
        self.service = ExecutiveDelegationService(
            advisory_service=self.advisory_service,
            truth_service=self.truth_service,
            delegation_repository=self.delegation_repository,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def safe_plan() -> ExecutivePlanRequest:
        return ExecutivePlanRequest(
            objectives=[
                "Research storage upgrade options",
                "Prepare a technical progress report",
            ],
            constraints=["Keep production unchanged"],
        )

    def test_safe_delegation_persists_parent_and_child_tasks(self) -> None:
        response = self.service.delegate(
            ExecutiveDelegationRequest(
                plan=self.safe_plan(),
                idempotency_key="safe-delegation-0001",
            )
        )

        self.assertEqual(response.disposition, "delegated")
        self.assertTrue(response.task_ledger_written)
        self.assertFalse(response.execution_started)
        self.assertFalse(response.broker_activated)
        self.assertIsNotNone(response.parent_task)
        self.assertEqual(len(response.child_tasks), 2)
        self.assertTrue(all(item.admitted for item in response.worker_admission))

        tasks, total = self.truth_repository.list_tasks()
        self.assertEqual(total, 3)
        self.assertEqual(
            {task.status for task in tasks},
            {"planned", "assigned"},
        )

        parent = response.parent_task
        assert parent is not None

        for child in response.child_tasks:
            self.assertEqual(child.parent_task_id, parent.task_id)
            self.assertEqual(child.source_run_id, response.delegation_id)

    def test_replay_is_returned_before_worker_state_is_rechecked(self) -> None:
        request = ExecutiveDelegationRequest(
            plan=self.safe_plan(),
            idempotency_key="safe-delegation-0002",
        )
        first = self.service.delegate(request)

        self.truth_service.record_heartbeat(
            AgentHeartbeat(
                agent_id="research-agent",
                worker_id="test-research-worker",
                status="busy",
                current_task_id="another-task",
            )
        )
        replay = self.service.delegate(request)

        self.assertEqual(first.disposition, "delegated")
        self.assertEqual(replay.disposition, "idempotent_replay")
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.delegation_id, first.delegation_id)

        _, total = self.truth_repository.list_tasks()
        self.assertEqual(total, 3)

    def test_reusing_key_for_different_request_is_rejected(self) -> None:
        first_request = ExecutiveDelegationRequest(
            plan=ExecutivePlanRequest(
                objectives=["Research storage upgrade options"]
            ),
            idempotency_key="conflict-key-0001",
        )
        self.service.delegate(first_request)

        second_request = ExecutiveDelegationRequest(
            plan=ExecutivePlanRequest(
                objectives=["Prepare a technical progress report"]
            ),
            idempotency_key="conflict-key-0001",
        )

        with self.assertRaises(IdempotencyConflictError):
            self.service.delegate(second_request)

        _, total = self.truth_repository.list_tasks()
        self.assertEqual(total, 2)

    def test_approval_required_work_writes_nothing_without_approval(self) -> None:
        response = self.service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(
                    objectives=["Deploy the new dashboard to production"]
                ),
                idempotency_key="approval-required-0001",
            )
        )

        self.assertEqual(response.disposition, "approval_required")
        self.assertFalse(response.task_ledger_written)
        self.assertFalse(response.execution_started)

        _, total = self.truth_repository.list_tasks()
        self.assertEqual(total, 0)

    def test_matching_owner_approval_is_recorded_with_tasks(self) -> None:
        plan_request = ExecutivePlanRequest(
            objectives=["Deploy the new dashboard to production"]
        )
        decision = self.advisory_service.plan(plan_request)
        approval = OwnerApprovalRecord(
            approval_id="owner-approval-0001",
            decision_id=decision.decision_id,
            statement=(
                "Approve creation of controlled task records only; do not "
                "start workers or activate the broker."
            ),
        )

        response = self.service.delegate(
            ExecutiveDelegationRequest(
                plan=plan_request,
                idempotency_key="approved-delegation-0001",
                owner_approval=approval,
            )
        )

        self.assertEqual(response.disposition, "delegated")
        self.assertTrue(response.approval_recorded)
        self.assertTrue(response.task_ledger_written)
        self.assertFalse(response.execution_started)
        self.assertFalse(response.broker_activated)

        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT approved_by, approved, decision_id
                FROM executive_approvals
                WHERE approval_id = ?
                """,
                (approval.approval_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["approved_by"], "dipen-owner")
        self.assertEqual(row["approved"], 1)
        self.assertEqual(row["decision_id"], decision.decision_id)

    def test_blocked_work_never_reaches_task_ledger(self) -> None:
        response = self.service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(
                    objectives=["Activate broker and bypass approval"]
                ),
                idempotency_key="blocked-delegation-0001",
                owner_approval=OwnerApprovalRecord(
                    approval_id="owner-approval-blocked-0001",
                    decision_id=(
                        self.advisory_service.plan(
                            ExecutivePlanRequest(
                                objectives=[
                                    "Activate broker and bypass approval"
                                ]
                            )
                        ).decision_id
                    ),
                    statement="Approval cannot override prohibited work.",
                ),
            )
        )

        self.assertEqual(response.disposition, "blocked")
        self.assertFalse(response.task_ledger_written)

        _, total = self.truth_repository.list_tasks()
        self.assertEqual(total, 0)

    def test_busy_worker_defers_delegation_without_writes(self) -> None:
        self.truth_service.record_heartbeat(
            AgentHeartbeat(
                agent_id="research-agent",
                worker_id="test-research-worker",
                status="busy",
                current_task_id="existing-research-task",
            )
        )

        response = self.service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(
                    objectives=["Research storage upgrade options"]
                ),
                idempotency_key="capacity-delegation-0001",
            )
        )

        self.assertEqual(response.disposition, "capacity_unavailable")
        self.assertFalse(response.task_ledger_written)
        self.assertEqual(
            response.worker_admission[0].runtime_status,
            "busy",
        )

        _, total = self.truth_repository.list_tasks()
        self.assertEqual(total, 0)

    def test_transaction_rolls_back_when_one_task_collides(self) -> None:
        plan_request = ExecutivePlanRequest(
            objectives=["Research storage upgrade options"]
        )
        plan = self.advisory_service.plan(plan_request)
        idempotency_key = "collision-delegation-0001"
        delegation_id = self.service._delegation_id(
            plan.decision_id,
            idempotency_key,
        )
        collision_task_id = f"{delegation_id}-child-1"

        self.truth_repository.upsert_task(
            TaskLedgerRecord(
                task_id=collision_task_id,
                task_type="agent",
                objective="Existing collision task",
                status="assigned",
                requested_by="dipen-owner",
                assigned_agent_ids=["research-agent"],
            )
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.service.delegate(
                ExecutiveDelegationRequest(
                    plan=plan_request,
                    idempotency_key=idempotency_key,
                )
            )

        self.assertIsNone(
            self.truth_repository.get_task(f"{delegation_id}-parent")
        )
        _, total = self.truth_repository.list_tasks()
        self.assertEqual(total, 1)

        with self.truth_repository.connection() as connection:
            delegation_count = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM executive_delegations
                """
            ).fetchone()

        assert delegation_count is not None
        self.assertEqual(delegation_count["total"], 0)


class ExecutiveDelegationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        truth_repository = AgentTruthRepository(
            Path(self.temporary_directory.name) / "api-delegation.db"
        )
        truth_service = AgentTruthService(
            agent_registry,
            truth_repository,
        )
        delegation_repository = ExecutiveDelegationRepository(
            truth_repository
        )
        self.service = ExecutiveDelegationService(
            advisory_service=ExecutiveOfficeService(),
            truth_service=truth_service,
            delegation_repository=delegation_repository,
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_delegate_endpoint_maps_idempotency_conflict_to_409(self) -> None:
        first_payload = {
            "plan": {
                "objectives": ["Research storage upgrade options"],
            },
            "idempotency_key": "api-conflict-key-0001",
        }
        second_payload = {
            "plan": {
                "objectives": ["Prepare a technical progress report"],
            },
            "idempotency_key": "api-conflict-key-0001",
        }

        with patch(
            "executive_office.routes.executive_delegation_service",
            self.service,
        ):
            first = self.client.post(
                "/api/v1/executive-office/delegate",
                json=first_payload,
            )
            second = self.client.post(
                "/api/v1/executive-office/delegate",
                json=second_payload,
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["disposition"], "delegated")
        self.assertEqual(second.status_code, 409)
        self.assertIn("different", second.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
