import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

TEST_DATA_DIRECTORY = Path(tempfile.gettempdir()) / "dap-telegram-transport-tests"
os.environ.setdefault(
    "KNOWLEDGE_UPLOAD_DIRECTORY",
    str(TEST_DATA_DIRECTORY / "knowledge-uploads"),
)
os.environ.setdefault(
    "DAP_AGENT_TRUTH_DB",
    str(TEST_DATA_DIRECTORY / "agent-truth.db"),
)

from agents.truth_repository import AgentTruthRepository
from owner_channels.telegram_service import (
    TelegramIngressConfig,
    TelegramOwnerIngressService,
)
from owner_channels.telegram_security import (
    TelegramSecurityConfig,
    TelegramSecurityRepository,
)
from owner_channels.telegram_transport import (
    TelegramBotApiError,
    TelegramHttpBotClient,
    TelegramLongPollingWorker,
    TelegramPollingOffsetRepository,
    TelegramTransportConfig,
    TelegramTransportConfigurationError,
    approval_reply_markup,
    format_telegram_response,
)


def telegram_update(
    *,
    update_id: int,
    text: str = "/help",
    user_id: int = 101,
) -> dict[str, object]:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 77,
            "date": 1786084800,
            "chat": {"id": 202, "type": "private"},
            "from": {
                "id": user_id,
                "is_bot": False,
                "username": "dipen",
            },
            "text": text,
        },
    }


def telegram_callback_update(*, update_id: int, user_id: int = 101):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "callback-transport-001",
            "from": {"id": user_id, "is_bot": False},
            "message": {
                "message_id": 88,
                "date": 1786084800,
                "chat": {"id": 202, "type": "private"},
            },
            "data": "dap:a:Abcd_1234-xyz789",
        },
    }


class FakeTelegramClient:
    def __init__(self, updates: list[dict[str, object]]) -> None:
        self.updates = updates
        self.requested_offsets: list[int | None] = []
        self.sent_messages: list[tuple[int, str, int]] = []
        self.fail_send = False
        self.answered_callbacks: list[tuple[str, str]] = []

    async def prepare_long_polling(self) -> None:
        return None

    async def get_updates(
        self,
        *,
        offset: int | None,
        timeout: int,
    ) -> list[dict[str, object]]:
        self.requested_offsets.append(offset)
        return self.updates

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, object] | None = None,
    ) -> None:
        if self.fail_send:
            raise TelegramBotApiError("send failed")
        self.sent_messages.append((chat_id, text, reply_to_message_id))

    async def answer_callback_query(
        self, *, callback_query_id: str, text: str
    ) -> None:
        self.answered_callbacks.append((callback_query_id, text))


class FakeRouter:
    def __init__(self) -> None:
        self.calls = 0

    def route(self, command) -> dict[str, object]:
        self.calls += 1
        if command.command == "approve":
            return {
                "ok": True,
                "command": "approve",
                "approval_state": "approved",
                "execution_started": False,
                "message": "Tasks recorded without execution.",
            }
        return {
            "ok": True,
            "command": command.command,
            "commands": ["/status", "/cancel <execution_id>", "/help"],
        }


class TelegramOwnerTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        truth = AgentTruthRepository(
            Path(self.temporary_directory.name) / "telegram-transport.db"
        )
        self.offsets = TelegramPollingOffsetRepository(truth)
        self.security = TelegramSecurityRepository(truth)
        self.client = FakeTelegramClient([telegram_update(update_id=3001)])
        self.router = FakeRouter()
        self.worker = TelegramLongPollingWorker(
            client=self.client,
            ingress=TelegramOwnerIngressService(
                TelegramIngressConfig(
                    webhook_secret=None,
                    owner_user_id=101,
                    owner_chat_id=202,
                )
            ),
            router=self.router,
            offsets=self.offsets,
            owner_chat_id=202,
            poll_timeout_seconds=10,
            security=self.security,
            security_config=TelegramSecurityConfig(
                command_rate_limit=20,
                callback_rate_limit=6,
                rate_window_seconds=60,
            ),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_poll_routes_replies_and_persists_next_offset(self) -> None:
        processed = await self.worker.poll_once()

        self.assertEqual(processed, 1)
        self.assertEqual(self.router.calls, 1)
        self.assertEqual(self.client.requested_offsets, [None])
        self.assertEqual(self.offsets.get_next_update_id(), 3002)
        self.assertEqual(self.client.sent_messages[0][0], 202)
        self.assertIn("/cancel <execution_id>", self.client.sent_messages[0][1])

        self.client.updates = []
        await self.worker.poll_once()
        self.assertEqual(self.client.requested_offsets[-1], 3002)

    async def test_offset_does_not_advance_until_reply_succeeds(self) -> None:
        self.client.fail_send = True
        with self.assertRaises(TelegramBotApiError):
            await self.worker.poll_once()

        self.assertIsNone(self.offsets.get_next_update_id())

    async def test_unauthorized_update_gets_no_reply_and_is_consumed(self) -> None:
        self.client.updates = [telegram_update(update_id=3002, user_id=999)]

        processed = await self.worker.poll_once()

        self.assertEqual(processed, 1)
        self.assertEqual(self.router.calls, 0)
        self.assertEqual(self.client.sent_messages, [])
        self.assertEqual(self.offsets.get_next_update_id(), 3003)
        with self.security.truth_repository.connection() as connection:
            row = connection.execute(
                "SELECT * FROM telegram_security_audit WHERE update_id = 3002"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["event_kind"], "unauthorized_message")
        self.assertEqual(row["claimed_user_id"], 999)

    async def test_rate_limit_consumes_update_without_routing_or_reply(self) -> None:
        self.worker.security_config = TelegramSecurityConfig(
            command_rate_limit=1,
            callback_rate_limit=1,
            rate_window_seconds=60,
        )
        await self.worker.poll_once()
        self.client.updates = [telegram_update(update_id=3002)]

        processed = await self.worker.poll_once()

        self.assertEqual(processed, 1)
        self.assertEqual(self.router.calls, 1)
        self.assertEqual(len(self.client.sent_messages), 1)
        self.assertEqual(self.offsets.get_next_update_id(), 3003)
        with self.security.truth_repository.connection() as connection:
            row = connection.execute(
                "SELECT * FROM telegram_security_audit WHERE update_id = 3002"
            ).fetchone()
        self.assertEqual(row["event_kind"], "rate_limited_command")

    async def test_owner_callback_is_answered_once_after_safe_routing(self) -> None:
        self.client.updates = [telegram_callback_update(update_id=3003)]

        processed = await self.worker.poll_once()

        self.assertEqual(processed, 1)
        self.assertEqual(self.offsets.get_next_update_id(), 3004)
        self.assertIn("Execution started: no", self.client.sent_messages[0][1])
        self.assertEqual(
            self.client.answered_callbacks,
            [("callback-transport-001", "DAP recorded your decision.")],
        )


class TelegramHttpBotClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_removes_webhook_without_dropping_updates(self) -> None:
        requests: list[httpx.Request] = []

        async def record_request(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"ok": True, "result": True})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(record_request)
        ) as http_client:
            client = TelegramHttpBotClient(token="test-token", client=http_client)
            await client.prepare_long_polling()

        self.assertEqual(requests[0].url.path, "/bottest-token/deleteWebhook")
        self.assertIn(b'"drop_pending_updates":false', requests[0].content)

    async def test_api_error_does_not_expose_token(self) -> None:
        token = "secret-token-123"

        async def fail_request(_: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"ok": False})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(fail_request)
        ) as http_client:
            client = TelegramHttpBotClient(token=token, client=http_client)
            with self.assertRaises(TelegramBotApiError) as captured:
                await client.get_updates(offset=None, timeout=1)

        self.assertNotIn(token, str(captured.exception))
        self.assertTrue(captured.exception.__suppress_context__)


class TelegramTransportConfigurationTests(unittest.TestCase):
    def test_enabled_polling_requires_token(self) -> None:
        with patch.dict(
            os.environ,
            {"DAP_TELEGRAM_POLLING_ENABLED": "true"},
            clear=True,
        ), self.assertRaises(TelegramTransportConfigurationError):
            TelegramTransportConfig.from_env()

    def test_status_response_is_compact_and_deterministic(self) -> None:
        text = format_telegram_response(
            {
                "ok": True,
                "command": "status",
                "version": "0.17.0",
                "execution_enabled": False,
                "execution_cancellation_enabled": True,
                "capability_count": 7,
            }
        )

        self.assertEqual(
            text,
            "DAP 0.17.0\nExecution: disabled\nCancellation: enabled\nCapabilities: 7",
        )

    def test_read_only_responses_are_compact(self) -> None:
        agents = format_telegram_response(
            {
                "ok": True,
                "command": "agents",
                "summary": {"available": 1, "busy": 1, "offline": 0},
                "agents": [
                    {"id": "guardian", "name": "Guardian", "status": "available"}
                ],
            }
        )
        tasks = format_telegram_response(
            {
                "ok": True,
                "command": "tasks",
                "total": 1,
                "tasks": [{"task_id": "task-001", "status": "running"}],
            }
        )
        company = format_telegram_response(
            {
                "ok": True,
                "command": "company",
                "organization_name": "Dipen AI Platform",
                "summary": {
                    "department_count": 4,
                    "role_count": 12,
                    "active_roles": 8,
                    "mapped_agent_roles": 5,
                },
            }
        )

        self.assertIn("Guardian: available", agents)
        self.assertIn("task-001: running", tasks)
        self.assertIn("Departments: 4", company)

    def test_plan_response_explicitly_says_execution_did_not_start(self) -> None:
        text = format_telegram_response(
            {
                "ok": True,
                "command": "plan",
                "decision_id": "executive-decision-001",
                "disposition": "ready_for_delegation",
                "overall_risk": "low",
                "execution_started": False,
                "tasks": [
                    {"task_id": "decision-task-1", "role_id": "research-analyst"}
                ],
            }
        )

        self.assertIn("Execution started: no", text)
        self.assertIn("Risk: low", text)

    def test_plan_markup_contains_only_scoped_approve_and_reject(self) -> None:
        markup = approval_reply_markup(
            {
                "ok": True,
                "command": "plan",
                "approval": {"token": "approval-token-001"},
            }
        )

        self.assertEqual(
            markup,
            {
                "inline_keyboard": [
                    [
                        {
                            "text": "Approve delegation",
                            "callback_data": "dap:a:approval-token-001",
                        },
                        {
                            "text": "Reject",
                            "callback_data": "dap:r:approval-token-001",
                        },
                    ]
                ]
            },
        )

    def test_first_approval_requires_separate_confirmation(self) -> None:
        markup = approval_reply_markup(
            {
                "ok": False,
                "command": "approval",
                "approval_state": "awaiting_confirmation",
                "confirmation_token": "approval-token-001",
            }
        )

        self.assertEqual(
            markup,
            {
                "inline_keyboard": [
                    [
                        {
                            "text": "Confirm delegation",
                            "callback_data": "dap:c:approval-token-001",
                        },
                        {
                            "text": "Reject",
                            "callback_data": "dap:r:approval-token-001",
                        },
                    ]
                ]
            },
        )

    def test_mobile_formatting_compacts_ids_and_labels(self) -> None:
        text = format_telegram_response(
            {
                "ok": True,
                "command": "plan",
                "decision_id": "executive-decision-956d5e745c74baa4a1dd",
                "disposition": "ready_for_delegation",
                "overall_risk": "low",
                "tasks": [
                    {
                        "task_id": "executive-decision-956d5e745c74baa4a1dd-task-1",
                        "role_id": "research-analyst",
                    }
                ],
            }
        )

        self.assertIn("Plan: ready for delegation", text)
        self.assertIn("Decision: executive-de…aa4a1dd", text)
        self.assertIn("research analyst", text)
        self.assertNotIn("executive-decision-956d5e745c74baa4a1dd-task-1", text)

    def test_health_response_reports_transport_and_backend(self) -> None:
        text = format_telegram_response(
            {
                "ok": True,
                "command": "health",
                "backend": "online",
                "telegram_polling": "online",
                "version": "0.10.0",
            }
        )

        self.assertIn("DAP health: healthy", text)
        self.assertIn("Telegram polling: online", text)


if __name__ == "__main__":
    unittest.main()
