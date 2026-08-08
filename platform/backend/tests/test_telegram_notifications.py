import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

TEST_DIRECTORY = Path(tempfile.gettempdir()) / "dap-telegram-notification-tests"
os.environ.setdefault("DAP_AGENT_TRUTH_DB", str(TEST_DIRECTORY / "truth.db"))
os.environ.setdefault(
    "KNOWLEDGE_UPLOAD_DIRECTORY", str(TEST_DIRECTORY / "knowledge")
)

from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from owner_channels.telegram_notifications import (
    OwnerNotificationEvent,
    OwnerNotificationOutbox,
    TelegramNotificationConfig,
    TelegramNotificationWorker,
    format_notification,
)


class FakeNotificationClient:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.fail = False

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> None:
        if self.fail:
            raise RuntimeError("network unavailable")
        self.messages.append((chat_id, text))


class TelegramNotificationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.truth = AgentTruthRepository(
            Path(self.temporary_directory.name) / "notifications.db"
        )
        self.outbox = OwnerNotificationOutbox(self.truth)
        self.client = FakeNotificationClient()
        self.worker = TelegramNotificationWorker(
            client=self.client,
            outbox=self.outbox,
            owner_chat_id=849259897,
            categories=frozenset(
                {
                    "task_started",
                    "task_completed",
                    "task_failed",
                    "task_cancelled",
                    "guardian_blocked",
                }
            ),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def task(self, status: str, *, error: str | None = None) -> TaskLedgerRecord:
        now = datetime.now(timezone.utc)
        return TaskLedgerRecord(
            task_id="task-notify-001",
            task_type="agent",
            objective="Verify Telegram lifecycle notifications",
            status=status,
            requested_by="test-owner",
            assigned_agent_ids=["guardian"],
            current_step=status,
            progress_percent=100 if status in {"completed", "failed"} else 10,
            error=error,
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now if status in {"completed", "failed"} else None,
        )

    async def test_task_transition_is_delivered_once(self) -> None:
        self.truth.upsert_task(self.task("running"))

        self.assertTrue(await self.worker.deliver_once())
        self.assertFalse(await self.worker.deliver_once())
        self.assertEqual(len(self.client.messages), 1)
        self.assertIn("Task started", self.client.messages[0][1])

        self.truth.upsert_task(self.task("completed"))
        self.assertTrue(await self.worker.deliver_once())
        self.assertIn("Task completed", self.client.messages[1][1])

    async def test_direct_sql_cancellation_is_captured(self) -> None:
        self.truth.upsert_task(self.task("running"))
        self.assertTrue(await self.worker.deliver_once())
        now = datetime.now(timezone.utc).isoformat()
        with self.truth.connection() as connection:
            connection.execute(
                """
                UPDATE task_ledger
                SET status = 'cancelled', updated_at = ?, completed_at = ?
                WHERE task_id = 'task-notify-001'
                """,
                (now, now),
            )
            connection.commit()

        self.assertTrue(await self.worker.deliver_once())
        self.assertIn("Task cancelled", self.client.messages[1][1])

    async def test_failed_send_is_released_for_retry(self) -> None:
        self.truth.upsert_task(self.task("failed", error="model timeout"))
        self.client.fail = True

        with self.assertRaises(RuntimeError):
            await self.worker.deliver_once()

        self.client.fail = False
        self.assertTrue(await self.worker.deliver_once())
        self.assertIn("model timeout", self.client.messages[0][1])

    async def test_disabled_category_remains_undelivered(self) -> None:
        self.truth.upsert_task(self.task("cancelled"))
        worker = TelegramNotificationWorker(
            client=self.client,
            outbox=self.outbox,
            owner_chat_id=849259897,
            categories=frozenset({"task_completed"}),
        )

        self.assertFalse(await worker.deliver_once())
        self.assertEqual(self.client.messages, [])

    async def test_guardian_block_is_deduplicated(self) -> None:
        for _ in range(2):
            self.outbox.enqueue_guardian_block(
                decision_id="decision-blocked-001",
                objectives=["bypass approval"],
                reasons=["Matched prohibited term: bypass approval"],
            )

        self.assertTrue(await self.worker.deliver_once())
        self.assertFalse(await self.worker.deliver_once())
        self.assertIn("Guardian blocked", self.client.messages[0][1])
        self.assertIn("Execution started: no", self.client.messages[0][1])

    def test_notification_configuration_is_explicit_and_bounded(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DAP_TELEGRAM_NOTIFICATIONS_ENABLED": "true",
                "DAP_TELEGRAM_NOTIFICATION_CATEGORIES": "task_failed,guardian_blocked",
                "DAP_TELEGRAM_NOTIFICATION_INTERVAL": "3",
            },
            clear=True,
        ):
            config = TelegramNotificationConfig.from_env()

        self.assertTrue(config.enabled)
        self.assertEqual(
            config.categories, frozenset({"task_failed", "guardian_blocked"})
        )
        self.assertEqual(config.interval_seconds, 3)

    def test_unknown_notification_category_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"DAP_TELEGRAM_NOTIFICATION_CATEGORIES": "task_completed,typo"},
            clear=True,
        ), self.assertRaisesRegex(ValueError, "Unsupported"):
            TelegramNotificationConfig.from_env()

    def test_mobile_notification_format_compacts_identifiers(self) -> None:
        text = format_notification(
            OwnerNotificationEvent(
                event_id="event-1",
                category="task_completed",
                subject_id="executive-task-1234567890-abcdefghij",
                payload={
                    "task_id": "executive-task-1234567890-abcdefghij",
                    "objective": "Create an evidence-backed status summary",
                },
            )
        )

        self.assertIn("✅ Task completed", text)
        self.assertIn("executive-ta…defghij", text)
        self.assertNotIn("executive-task-1234567890-abcdefghij", text)


if __name__ == "__main__":
    unittest.main()
