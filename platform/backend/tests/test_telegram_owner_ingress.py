import unittest

from owner_channels.telegram_schemas import TelegramUpdate
from owner_channels.telegram_service import (
    TelegramIngressConfig,
    TelegramOwnerIngressService,
)


class TelegramOwnerIngressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TelegramOwnerIngressService(
            TelegramIngressConfig(
                webhook_secret="telegram-secret-001",
                owner_user_id=101,
                owner_chat_id=202,
            )
        )

    @staticmethod
    def update(
        text: str,
        *,
        update_id: int = 9001,
        user_id: int = 101,
        chat_id: int = 202,
        is_bot: bool = False,
    ) -> TelegramUpdate:
        return TelegramUpdate.model_validate(
            {
                "update_id": update_id,
                "message": {
                    "message_id": 77,
                    "date": 1786084800,
                    "chat": {
                        "id": chat_id,
                        "type": "private",
                    },
                    "from": {
                        "id": user_id,
                        "is_bot": is_bot,
                        "username": "dipen",
                    },
                    "text": text,
                },
            }
        )

    def test_status_command_is_bound_to_owner_and_update_id(self) -> None:
        result = self.service.accept(
            update=self.update("/status"),
            webhook_secret_header="telegram-secret-001",
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.command, "status")
        self.assertEqual(result.authorized_by, "dipen-owner")
        self.assertEqual(result.idempotency_key, "telegram-update-9001")

    def test_cancel_command_extracts_exact_execution_id(self) -> None:
        result = self.service.accept(
            update=self.update("/cancel execution-abc-123"),
            webhook_secret_header="telegram-secret-001",
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.command, "cancel")
        self.assertEqual(result.execution_id, "execution-abc-123")

    def test_cancel_without_execution_id_is_not_accepted(self) -> None:
        result = self.service.accept(
            update=self.update("/cancel"),
            webhook_secret_header="telegram-secret-001",
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.command, "unsupported")
        self.assertIsNone(result.execution_id)

    def test_read_only_owner_commands_are_accepted(self) -> None:
        for text, expected in (
            ("/agents", "agents"),
            ("/tasks", "tasks"),
            ("/company", "company"),
        ):
            with self.subTest(text=text):
                result = self.service.accept(
                    update=self.update(text),
                    webhook_secret_header="telegram-secret-001",
                )
                self.assertTrue(result.accepted)
                self.assertEqual(result.command, expected)

    def test_wrong_webhook_secret_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.accept(
                update=self.update("/status"),
                webhook_secret_header="wrong-secret",
            )

    def test_wrong_owner_user_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.accept(
                update=self.update("/status", user_id=999),
                webhook_secret_header="telegram-secret-001",
            )

    def test_wrong_owner_chat_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.accept(
                update=self.update("/status", chat_id=999),
                webhook_secret_header="telegram-secret-001",
            )

    def test_bot_sender_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.accept(
                update=self.update("/status", is_bot=True),
                webhook_secret_header="telegram-secret-001",
            )

    def test_unknown_command_is_normalized_without_side_effect_permission(self) -> None:
        result = self.service.accept(
            update=self.update("/deploy production"),
            webhook_secret_header="telegram-secret-001",
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.command, "unsupported")


if __name__ == "__main__":
    unittest.main()
