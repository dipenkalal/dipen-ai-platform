import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TEST_DATA_DIRECTORY = Path(tempfile.gettempdir()) / "dap-telegram-routing-tests"
os.environ.setdefault(
    "KNOWLEDGE_UPLOAD_DIRECTORY",
    str(TEST_DATA_DIRECTORY / "knowledge-uploads"),
)
os.environ.setdefault(
    "DAP_AGENT_TRUTH_DB",
    str(TEST_DATA_DIRECTORY / "agent-truth.db"),
)

from agents.truth_repository import AgentTruthRepository
from owner_channels.telegram_command_service import TelegramOwnerCommandRouter
from owner_channels.telegram_repository import TelegramCommandReceiptRepository
from owner_channels.telegram_schemas import TelegramOwnerCommand


class FakeOfficeStatusService:
    def status(self):
        return SimpleNamespace(
            version="0.10.0",
            execution_enabled=True,
            execution_cancellation_enabled=True,
            execution_recovery_enabled=True,
            broker_activation_enabled=False,
            capabilities=[object(), object()],
        )


class FakeExecutionStatusService:
    def get(self, execution_id: str):
        if execution_id == "invalid-test-id":
            raise KeyError(f"Unknown execution: {execution_id}")
        return SimpleNamespace(
            execution_id=execution_id,
            delegation_id="delegation-001",
            parent_task=SimpleNamespace(task_id="parent-task-001"),
            child_tasks=[
                SimpleNamespace(task_id="child-task-001"),
                SimpleNamespace(task_id="child-task-002"),
            ],
        )


class FakeCancellationService:
    def __init__(self) -> None:
        self.calls = []

    def request(self, *, execution_id: str, request):
        self.calls.append((execution_id, request))
        return SimpleNamespace(
            cancellation_id="cancellation-001",
            state="requested",
            idempotent_replay=False,
            message="Cancellation stored.",
        )


class FakeModel:
    def __init__(self, **values) -> None:
        self.values = values

    def model_dump(self, *, mode: str):
        return self.values


class FakeTruthService:
    def list_agent_states(self):
        return SimpleNamespace(
            summary=FakeModel(
                registered=2,
                enabled=2,
                available=1,
                busy=1,
                degraded=0,
                offline=0,
                unreported=0,
                disabled=0,
            ),
            agents=[
                SimpleNamespace(
                    agent=SimpleNamespace(id="guardian", name="Guardian"),
                    runtime_status="available",
                    current_task_id=None,
                ),
                SimpleNamespace(
                    agent=SimpleNamespace(id="builder", name="Builder"),
                    runtime_status="busy",
                    current_task_id="task-001",
                ),
            ],
        )

    def list_tasks(self, *, limit: int):
        return SimpleNamespace(
            total=1,
            tasks=[
                SimpleNamespace(
                    task_id="task-001",
                    status="running",
                    priority="normal",
                    progress_percent=50.0,
                )
            ],
        )


class FakeOrganizationRegistry:
    def snapshot(self):
        return SimpleNamespace(
            organization_name="Dipen AI Platform",
            registry_version="1.0.0",
            summary=FakeModel(
                department_count=4,
                role_count=12,
                active_roles=8,
                mapped_agent_roles=5,
            ),
        )


class FakePlanningService:
    def __init__(self) -> None:
        self.requests = []

    def plan(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            decision_id="executive-decision-001",
            disposition="ready_for_delegation",
            risk_policy=SimpleNamespace(
                overall_risk="low",
                owner_approval_required=False,
            ),
            chief_of_staff=SimpleNamespace(
                tasks=[
                    SimpleNamespace(
                        task_id="decision-task-1",
                        suggested_role_id="research-analyst",
                    )
                ]
            ),
            execution_started=False,
            message="Plan created without execution.",
        )


class FakeApprovalService:
    def __init__(self) -> None:
        self.proposals = []
        self.decisions = []

    def propose(self, *, request, decision_id: str, source_update_id: int):
        self.proposals.append((request, decision_id, source_update_id))
        return SimpleNamespace(
            token="approval-token-001",
            expires_at=SimpleNamespace(isoformat=lambda: "2026-08-08T10:10:00+00:00"),
        )

    def decide(self, *, token: str, action: str, callback_update_id: int):
        self.decisions.append((token, action, callback_update_id))
        return {
            "ok": True,
            "command": action,
            "approval_state": "approved",
            "task_ledger_written": True,
            "execution_started": False,
            "message": "Tasks recorded without execution.",
        }


class TelegramOwnerRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        truth = AgentTruthRepository(
            Path(self.temporary_directory.name) / "telegram-routing.db"
        )
        self.receipts = TelegramCommandReceiptRepository(truth)
        self.cancellation = FakeCancellationService()
        self.planning = FakePlanningService()
        self.approvals = FakeApprovalService()
        self.router = TelegramOwnerCommandRouter(
            receipt_repository=self.receipts,
            office_status_service=FakeOfficeStatusService(),
            execution_status_service=FakeExecutionStatusService(),
            cancellation_service=self.cancellation,
            truth_service=FakeTruthService(),
            organization_registry=FakeOrganizationRegistry(),
            planning_service=self.planning,
            approval_service=self.approvals,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def command(
        name: str,
        *,
        update_id: int,
        execution_id: str | None = None,
        objective: str | None = None,
    ) -> TelegramOwnerCommand:
        return TelegramOwnerCommand(
            update_id=update_id,
            message_id=77,
            command=name,
            execution_id=execution_id,
            objective=objective,
            idempotency_key=f"telegram-update-{update_id}",
            accepted=True,
            reason="accepted",
        )

    def test_status_is_durable_and_replayed(self) -> None:
        command = self.command("status", update_id=1001)
        first = self.router.route(command)
        replay = self.router.route(command)

        self.assertTrue(first["ok"])
        self.assertFalse(first["broker_activation_enabled"])
        self.assertTrue(replay["idempotent_replay"])

    def test_cancel_replay_does_not_repeat_downstream_action(self) -> None:
        command = self.command(
            "cancel",
            update_id=1002,
            execution_id="execution-001",
        )
        first = self.router.route(command)
        replay = self.router.route(command)

        self.assertTrue(first["ok"])
        self.assertEqual(first["state"], "requested")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(len(self.cancellation.calls), 1)

        execution_id, request = self.cancellation.calls[0]
        self.assertEqual(execution_id, "execution-001")
        authorization = request.owner_authorization
        self.assertEqual(authorization.authorized_by, "dipen-owner")
        self.assertEqual(authorization.delegation_id, "delegation-001")
        self.assertEqual(authorization.parent_task_id, "parent-task-001")
        self.assertEqual(
            authorization.child_task_ids,
            ["child-task-001", "child-task-002"],
        )
        self.assertEqual(request.idempotency_key, "telegram-update-1002")

    def test_unknown_cancel_is_safe_clear_and_durable(self) -> None:
        command = self.command(
            "cancel", update_id=1007, execution_id="invalid-test-id"
        )

        first = self.router.route(command)
        replay = self.router.route(command)

        self.assertFalse(first["ok"])
        self.assertEqual(
            first["message"],
            "Execution not found: invalid-test-id. No task was changed.",
        )
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(self.cancellation.calls, [])

    def test_health_reports_backend_and_live_polling_worker(self) -> None:
        result = self.router.route(self.command("health", update_id=1008))

        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "online")
        self.assertEqual(result["telegram_polling"], "online")

    def test_read_only_company_views_route_without_execution(self) -> None:
        agents = self.router.route(self.command("agents", update_id=1003))
        tasks = self.router.route(self.command("tasks", update_id=1004))
        company = self.router.route(self.command("company", update_id=1005))

        self.assertEqual(agents["summary"]["available"], 1)
        self.assertEqual(agents["agents"][1]["current_task_id"], "task-001")
        self.assertEqual(tasks["tasks"][0]["status"], "running")
        self.assertEqual(company["summary"]["department_count"], 4)
        self.assertEqual(self.cancellation.calls, [])

    def test_plan_is_advisory_and_never_allows_external_actions(self) -> None:
        result = self.router.route(
            self.command(
                "plan",
                update_id=1006,
                objective="Research storage upgrade options",
            )
        )

        self.assertEqual(result["disposition"], "ready_for_delegation")
        self.assertFalse(result["execution_started"])
        self.assertEqual(len(self.planning.requests), 1)
        request = self.planning.requests[0]
        self.assertEqual(request.requested_by, "dipen-owner")
        self.assertFalse(request.allow_external_actions)
        self.assertEqual(result["approval"]["scope"], "delegate_planned_tasks_only")
        self.assertEqual(len(self.approvals.proposals), 1)
        self.assertEqual(self.cancellation.calls, [])

    def test_approval_callback_routes_once_without_execution(self) -> None:
        command = self.command("approve", update_id=1010)
        command.approval_token = "approval-token-001"

        first = self.router.route(command)
        replay = self.router.route(command)

        self.assertTrue(first["task_ledger_written"])
        self.assertFalse(first["execution_started"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(
            self.approvals.decisions,
            [("approval-token-001", "approve", 1010)],
        )


if __name__ == "__main__":
    unittest.main()
