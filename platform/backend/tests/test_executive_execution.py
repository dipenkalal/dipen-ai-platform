import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

_TEST_DATA_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="dap-executive-execution-tests-")
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
from app import app
from executive_office.delegation_service import ExecutiveDelegationService
from executive_office.execution_repository import (
    ExecutiveExecutionRepository,
)
from executive_office.execution_service import ExecutiveExecutionService
from executive_office.repository import (
    ExecutiveDelegationRepository,
    IdempotencyConflictError,
)
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutiveExecutionRequest,
    ExecutivePlanRequest,
    OwnerApprovalRecord,
    OwnerExecutionAuthorization,
)
from executive_office.service import ExecutiveOfficeService


class ExecutiveExecutionAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = (
            Path(self.temporary_directory.name)
            / "owner-triggered-execution.db"
        )
        self.truth_repository = AgentTruthRepository(database_path)
        self.truth_service = AgentTruthService(
            agent_registry,
            self.truth_repository,
        )
        self.delegation_repository = ExecutiveDelegationRepository(
            self.truth_repository
        )
        self.execution_repository = ExecutiveExecutionRepository(
            self.truth_repository
        )
        self.advisory_service = ExecutiveOfficeService()
        self.delegation_service = ExecutiveDelegationService(
            advisory_service=self.advisory_service,
            truth_service=self.truth_service,
            delegation_repository=self.delegation_repository,
        )
        self.service = ExecutiveExecutionService(
            delegation_service=self.delegation_service,
            advisory_service=self.advisory_service,
            truth_service=self.truth_service,
            execution_repository=self.execution_repository,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_delegation(
        self,
        *,
        objective: str = "Research storage upgrade options",
        idempotency_key: str = "execution-source-delegation-0001",
    ):
        response = self.delegation_service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(objectives=[objective]),
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
        idempotency_key: str = "execution-admission-0001",
        validation_only: bool = True,
        authorized_by: str = "dipen-owner",
        approved: bool = True,
        child_task_ids: list[str] | None = None,
    ) -> ExecutiveExecutionRequest:
        parent = delegation.parent_task
        assert parent is not None
        selected_ids = child_task_ids or [
            task.task_id for task in delegation.child_tasks
        ]
        authorization = OwnerExecutionAuthorization(
            authorization_id=f"owner-{idempotency_key}",
            delegation_id=delegation.delegation_id,
            parent_task_id=parent.task_id,
            child_task_ids=list(selected_ids),
            authorized_by=authorized_by,
            approved=approved,
            validation_only=validation_only,
            statement=(
                "Authorize the exact selected delegated tasks for bounded "
                "Executive Office admission."
            ),
        )
        return ExecutiveExecutionRequest(
            delegation_id=delegation.delegation_id,
            parent_task_id=parent.task_id,
            child_task_ids=list(selected_ids),
            idempotency_key=idempotency_key,
            validation_only=validation_only,
            owner_authorization=authorization,
        )

    def task_statuses(self) -> dict[str, str]:
        tasks, _ = self.truth_repository.list_tasks()
        return {task.task_id: task.status for task in tasks}

    def test_validation_only_admission_preserves_task_state(self) -> None:
        delegation = self.create_delegation()
        request = self.build_request(delegation)
        before = self.task_statuses()

        with patch(
            "agents.runtime.instrumented_agent_executor.run"
        ) as executor_run:
            response = self.service.admit(request)

        self.assertEqual(response.disposition, "validated")
        self.assertEqual(response.state, "validated")
        self.assertTrue(response.admission_validated)
        self.assertTrue(response.validation_only)
        self.assertFalse(response.task_ledger_mutated)
        self.assertFalse(response.reservation_acquired)
        self.assertFalse(response.execution_started)
        self.assertFalse(response.broker_activated)
        self.assertEqual(self.task_statuses(), before)
        executor_run.assert_not_called()

    def test_unknown_delegation_is_rejected_without_executor(self) -> None:
        request = ExecutiveExecutionRequest(
            delegation_id="unknown-delegation-0001",
            parent_task_id="unknown-parent-0001",
            child_task_ids=["unknown-child-0001"],
            idempotency_key="unknown-execution-0001",
            owner_authorization=OwnerExecutionAuthorization(
                authorization_id="unknown-authorization-0001",
                delegation_id="unknown-delegation-0001",
                parent_task_id="unknown-parent-0001",
                child_task_ids=["unknown-child-0001"],
                statement="Authorize validation of the unknown task set.",
            ),
        )

        with patch(
            "agents.runtime.instrumented_agent_executor.run"
        ) as executor_run:
            response = self.service.admit(request)

        self.assertEqual(response.disposition, "rejected")
        self.assertFalse(response.execution_started)
        executor_run.assert_not_called()

    def test_mismatched_child_task_is_rejected(self) -> None:
        delegation = self.create_delegation()
        request = self.build_request(
            delegation,
            child_task_ids=["different-child-task-0001"],
        )

        response = self.service.admit(request)

        self.assertEqual(response.disposition, "rejected")
        self.assertFalse(response.admission_validated)

    def test_stale_child_status_is_rejected(self) -> None:
        delegation = self.create_delegation()
        child = delegation.child_tasks[0]
        self.truth_repository.upsert_task(
            child.model_copy(update={"status": "completed"})
        )

        response = self.service.admit(
            self.build_request(
                delegation,
                idempotency_key="stale-task-execution-0001",
            )
        )

        self.assertEqual(response.disposition, "task_state_conflict")
        self.assertIn(
            "completed",
            response.validation_evidence[-1].detail,
        )

    def test_missing_or_wrong_owner_authorization_is_rejected(self) -> None:
        delegation = self.create_delegation()
        parent = delegation.parent_task
        assert parent is not None
        child_ids = [task.task_id for task in delegation.child_tasks]
        missing = ExecutiveExecutionRequest(
            delegation_id=delegation.delegation_id,
            parent_task_id=parent.task_id,
            child_task_ids=child_ids,
            idempotency_key="missing-owner-authorization-0001",
        )
        wrong_owner = self.build_request(
            delegation,
            idempotency_key="wrong-owner-authorization-0001",
            authorized_by="another-owner",
        )

        missing_response = self.service.admit(missing)
        wrong_owner_response = self.service.admit(wrong_owner)

        self.assertEqual(
            missing_response.disposition,
            "authorization_required",
        )
        self.assertEqual(
            wrong_owner_response.disposition,
            "authorization_required",
        )

    def test_busy_worker_is_rejected(self) -> None:
        delegation = self.create_delegation()
        agent_id = delegation.child_tasks[0].assigned_agent_ids[0]
        self.truth_service.record_heartbeat(
            AgentHeartbeat(
                agent_id=agent_id,
                worker_id="execution-test-worker",
                status="busy",
                current_task_id="different-running-task",
            )
        )

        response = self.service.admit(
            self.build_request(
                delegation,
                idempotency_key="busy-worker-execution-0001",
            )
        )

        self.assertEqual(response.disposition, "worker_unavailable")
        self.assertFalse(response.execution_started)

    def test_high_risk_delegation_is_rejected_by_execution_policy(self) -> None:
        plan = ExecutivePlanRequest(
            objectives=["Deploy the dashboard to production"]
        )
        decision = self.advisory_service.plan(plan)
        delegation = self.delegation_service.delegate(
            ExecutiveDelegationRequest(
                plan=plan,
                idempotency_key="high-risk-source-delegation-0001",
                owner_approval=OwnerApprovalRecord(
                    approval_id="high-risk-delegation-approval-0001",
                    decision_id=decision.decision_id,
                    statement=(
                        "Approve task-ledger delegation only; do not execute."
                    ),
                ),
            )
        )
        self.assertEqual(delegation.disposition, "delegated")

        response = self.service.admit(
            self.build_request(
                delegation,
                idempotency_key="high-risk-execution-0001",
            )
        )

        self.assertEqual(response.disposition, "rejected")
        self.assertIn(
            "low-risk",
            response.message,
        )

    def test_replay_is_resolved_before_worker_recheck(self) -> None:
        delegation = self.create_delegation()
        request = self.build_request(
            delegation,
            idempotency_key="execution-replay-0001",
        )
        first = self.service.admit(request)
        agent_id = delegation.child_tasks[0].assigned_agent_ids[0]
        self.truth_service.record_heartbeat(
            AgentHeartbeat(
                agent_id=agent_id,
                worker_id="execution-replay-worker",
                status="busy",
                current_task_id="later-task",
            )
        )

        replay = self.service.admit(request)

        self.assertEqual(first.disposition, "validated")
        self.assertEqual(replay.disposition, "idempotent_replay")
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.execution_id, first.execution_id)

    def test_reused_idempotency_key_with_different_request_conflicts(self) -> None:
        delegation = self.create_delegation()
        first = self.build_request(
            delegation,
            idempotency_key="execution-conflict-0001",
        )
        second = first.model_copy(
            update={
                "owner_authorization": (
                    first.owner_authorization.model_copy(
                        update={"statement": "A different execution purpose."}
                    )
                    if first.owner_authorization is not None
                    else None
                )
            }
        )
        self.service.admit(first)

        with self.assertRaises(IdempotencyConflictError):
            self.service.admit(second)

    def test_execution_enabled_request_remains_disabled(self) -> None:
        delegation = self.create_delegation()
        before = self.task_statuses()
        response = self.service.admit(
            self.build_request(
                delegation,
                idempotency_key="execution-enabled-disabled-0001",
                validation_only=False,
            )
        )

        self.assertEqual(response.disposition, "execution_disabled")
        self.assertFalse(response.execution_started)
        self.assertFalse(response.reservation_acquired)
        self.assertEqual(self.task_statuses(), before)


class ExecutiveExecutionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        truth_repository = AgentTruthRepository(
            Path(self.temporary_directory.name) / "execution-api.db"
        )
        truth_service = AgentTruthService(
            agent_registry,
            truth_repository,
        )
        delegation_repository = ExecutiveDelegationRepository(
            truth_repository
        )
        execution_repository = ExecutiveExecutionRepository(
            truth_repository
        )
        advisory_service = ExecutiveOfficeService()
        delegation_service = ExecutiveDelegationService(
            advisory_service=advisory_service,
            truth_service=truth_service,
            delegation_repository=delegation_repository,
        )
        self.service = ExecutiveExecutionService(
            delegation_service=delegation_service,
            advisory_service=advisory_service,
            truth_service=truth_service,
            execution_repository=execution_repository,
        )
        self.delegation = delegation_service.delegate(
            ExecutiveDelegationRequest(
                plan=ExecutivePlanRequest(
                    objectives=["Research storage upgrade options"]
                ),
                idempotency_key="api-execution-source-0001",
            )
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def payload(
        self,
        *,
        statement: str,
    ) -> dict:
        parent = self.delegation.parent_task
        assert parent is not None
        child_ids = [
            task.task_id for task in self.delegation.child_tasks
        ]
        return {
            "delegation_id": self.delegation.delegation_id,
            "parent_task_id": parent.task_id,
            "child_task_ids": child_ids,
            "idempotency_key": "api-execution-conflict-0001",
            "validation_only": True,
            "owner_authorization": {
                "authorization_id": "api-owner-execution-0001",
                "delegation_id": self.delegation.delegation_id,
                "parent_task_id": parent.task_id,
                "child_task_ids": child_ids,
                "authorized_by": "dipen-owner",
                "approved": True,
                "scope": "execute_delegated_tasks",
                "validation_only": True,
                "statement": statement,
            },
        }

    def test_execute_endpoint_maps_idempotency_conflict_to_409(self) -> None:
        with patch(
            "executive_office.routes.executive_execution_service",
            self.service,
        ):
            first = self.client.post(
                "/api/v1/executive-office/execute",
                json=self.payload(statement="Authorize validation only."),
            )
            second = self.client.post(
                "/api/v1/executive-office/execute",
                json=self.payload(statement="Different authorization purpose."),
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["disposition"], "validated")
        self.assertEqual(second.status_code, 409)


if __name__ == "__main__":
    unittest.main()
