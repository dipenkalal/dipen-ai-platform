import os
import secrets
from dataclasses import dataclass

from owner_channels.telegram_schemas import (
    TelegramOwnerCommand,
    TelegramUpdate,
)


class TelegramIngressConfigurationError(RuntimeError):
    """Raised when the Telegram owner ingress is not safely configured."""


@dataclass(frozen=True)
class TelegramIngressConfig:
    webhook_secret: str
    owner_user_id: int
    owner_chat_id: int

    @classmethod
    def from_env(cls) -> "TelegramIngressConfig":
        webhook_secret = os.getenv("DAP_TELEGRAM_WEBHOOK_SECRET", "").strip()
        owner_user_id = os.getenv("DAP_TELEGRAM_OWNER_USER_ID", "").strip()
        owner_chat_id = os.getenv("DAP_TELEGRAM_OWNER_CHAT_ID", "").strip()

        if not webhook_secret:
            raise TelegramIngressConfigurationError(
                "DAP_TELEGRAM_WEBHOOK_SECRET is required."
            )

        try:
            parsed_user_id = int(owner_user_id)
            parsed_chat_id = int(owner_chat_id)
        except ValueError as exc:
            raise TelegramIngressConfigurationError(
                "Telegram owner user/chat IDs must be integers."
            ) from exc

        return cls(
            webhook_secret=webhook_secret,
            owner_user_id=parsed_user_id,
            owner_chat_id=parsed_chat_id,
        )


class TelegramOwnerIngressService:
    def __init__(self, config: TelegramIngressConfig) -> None:
        self.config = config

    def accept(
        self,
        *,
        update: TelegramUpdate,
        webhook_secret_header: str | None,
    ) -> TelegramOwnerCommand:
        if webhook_secret_header is None or not secrets.compare_digest(
            webhook_secret_header,
            self.config.webhook_secret,
        ):
            raise PermissionError("Telegram webhook secret validation failed.")

        message = update.message
        if message is None:
            raise PermissionError("Telegram update does not contain a message.")

        sender = message.from_user
        if sender is None or sender.is_bot:
            raise PermissionError("Telegram sender identity is not an owner user.")
        if sender.id != self.config.owner_user_id:
            raise PermissionError("Telegram sender is not the configured owner.")
        if message.chat.id != self.config.owner_chat_id:
            raise PermissionError("Telegram chat is not the configured owner chat.")

        text = (message.text or "").strip()
        command, execution_id, accepted, reason = self._parse(text)

        return TelegramOwnerCommand(
            update_id=update.update_id,
            message_id=message.message_id,
            command=command,
            execution_id=execution_id,
            idempotency_key=f"telegram-update-{update.update_id}",
            accepted=accepted,
            reason=reason,
        )

    @staticmethod
    def _parse(text: str) -> tuple[str, str | None, bool, str]:
        if text == "/status":
            return "status", None, True, "Owner status command accepted."

        if text == "/help":
            return "help", None, True, "Owner help command accepted."

        if text.startswith("/cancel"):
            parts = text.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                return (
                    "cancel",
                    parts[1].strip(),
                    True,
                    "Owner cancellation command accepted for routing.",
                )

            return (
                "unsupported",
                None,
                False,
                "Cancellation requires an execution ID.",
            )

        return (
            "unsupported",
            None,
            False,
            "Telegram command is not supported by the owner gateway.",
        )
