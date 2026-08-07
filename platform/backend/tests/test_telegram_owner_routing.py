import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault(
    "KNOWLEDGE_UPLOAD_DIRECTORY",
    str(Path(tempfile.gettempdir()) / "dap-test-knowledge-uploads"),
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


class TelegramOwnerRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        truth = AgentTruthRepository(
            Path(self.temporary_directory.name) / "telegram-routing.db"
        )
        self.receipts = TelegramCommandReceiptRepository(truth)
        self.cancellation = FakeCancellationService()
        self.router = TelegramOwnerCommandRouter(
            receipt_repository=self.receipts,
            office_status_service=FakeOfficeStatusService(),
            execution_status_service=FakeExecutionStatusService(),
            cancellation_service=self.cancellation,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def command(
        name: str,
        *,
        update_id: int,
        execution_id: str | None = None,
    ) -> TelegramOwnerCommand:
        return TelegramOwnerCommand(
            update_id=update_id,
            message_id=77,
            command=name,
            execution_id=execution_id,
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


if __name__ == "__main__":
    unittest.main()
