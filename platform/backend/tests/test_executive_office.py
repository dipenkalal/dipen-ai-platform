import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

_TEST_DATA_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="dap-executive-office-tests-")
)
os.environ.setdefault(
    "KNOWLEDGE_UPLOAD_DIRECTORY",
    str(_TEST_DATA_DIRECTORY / "knowledge-uploads"),
)
os.environ.setdefault(
    "DAP_AGENT_TRUTH_DB",
    str(_TEST_DATA_DIRECTORY / "agent-truth.db"),
)

from app import app
from executive_office.delegation_service import executive_delegation_service
from executive_office.schemas import ExecutivePlanRequest
from executive_office.service import executive_office_service


class ExecutiveOfficeServiceTests(unittest.TestCase):
    def test_multi_objective_request_creates_independent_tasks(self) -> None:
        response = executive_office_service.plan(
            ExecutivePlanRequest(
                objectives=[
                    "Write a complex program in C",
                    "Prepare the complete Dipen AI Platform progress report",
                ]
            )
        )

        self.assertEqual(response.disposition, "ready_for_delegation")
        self.assertEqual(response.chief_of_staff.objective_count, 2)
        self.assertEqual(response.project_plan.execution_mode, "parallel")
        self.assertFalse(response.execution_started)
        self.assertFalse(response.risk_policy.execution_allowed)
        self.assertEqual(
            response.chief_of_staff.tasks[0].suggested_role_id,
            "software-engineer",
        )
        self.assertEqual(
            response.chief_of_staff.tasks[1].suggested_role_id,
            "technical-writer",
        )

    def test_production_action_requires_owner_approval(self) -> None:
        response = executive_office_service.plan(
            ExecutivePlanRequest(
                objectives=["Deploy the new dashboard to production"]
            )
        )

        self.assertEqual(response.disposition, "approval_required")
        self.assertTrue(response.risk_policy.owner_approval_required)
        self.assertEqual(
            response.project_plan.work_items[0].status,
            "approval_required",
        )
        self.assertFalse(response.execution_started)

    def test_prohibited_control_plane_action_is_blocked(self) -> None:
        response = executive_office_service.plan(
            ExecutivePlanRequest(
                objectives=["Activate broker and bypass approval"]
            )
        )

        self.assertEqual(response.disposition, "blocked")
        self.assertEqual(response.risk_policy.overall_risk, "blocked")
        self.assertEqual(response.project_plan.work_items[0].status, "blocked")

    def test_identical_requests_have_stable_decision_ids(self) -> None:
        request = ExecutivePlanRequest(
            objectives=["Research storage upgrade options"],
            constraints=["Keep production unchanged"],
        )

        first = executive_office_service.plan(request)
        second = executive_office_service.plan(request)

        self.assertEqual(first.decision_id, second.decision_id)

    def test_status_exposes_controlled_non_executing_delegation(self) -> None:
        status_response = executive_delegation_service.status()

        self.assertFalse(status_response.read_only)
        self.assertTrue(status_response.delegation_enabled)
        self.assertTrue(status_response.task_ledger_writes_enabled)
        self.assertFalse(status_response.execution_enabled)
        self.assertFalse(status_response.broker_activation_enabled)
        self.assertEqual(len(status_response.capabilities), 5)
        self.assertTrue(
            all(
                capability.active_runtime_employee is False
                for capability in status_response.capabilities
            )
        )
        self.assertEqual(
            status_response.capabilities[-1].mode,
            "controlled_delegation",
        )


class ExecutiveOfficeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_status_endpoint(self) -> None:
        response = self.client.get("/api/v1/executive-office/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["read_only"])
        self.assertTrue(payload["delegation_enabled"])
        self.assertTrue(payload["task_ledger_writes_enabled"])
        self.assertTrue(payload["execution_admission_enabled"])
        self.assertTrue(payload["execution_reservation_enabled"])
        self.assertTrue(payload["execution_enabled"])
        self.assertTrue(payload["execution_cancellation_enabled"])
        self.assertTrue(payload["execution_recovery_enabled"])
        self.assertFalse(payload["broker_activation_enabled"])

    def test_plan_endpoint_is_advisory_only(self) -> None:
        response = self.client.post(
            "/api/v1/executive-office/plan",
            json={
                "objectives": [
                    "Write a C program",
                    "Prepare a platform progress report",
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["execution_started"])
        self.assertFalse(payload["risk_policy"]["execution_allowed"])
        self.assertEqual(len(payload["project_plan"]["work_items"]), 2)


if __name__ == "__main__":
    unittest.main()
