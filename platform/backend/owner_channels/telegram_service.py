import os
import re
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
    webhook_secret: str | None
    owner_user_id: int
    owner_chat_id: int

    @classmethod
    def from_env(
        cls,
        *,
        require_webhook_secret: bool = True,
    ) -> "TelegramIngressConfig":
        webhook_secret = os.getenv("DAP_TELEGRAM_WEBHOOK_SECRET", "").strip()
        owner_user_id = os.getenv("DAP_TELEGRAM_OWNER_USER_ID", "").strip()
        owner_chat_id = os.getenv("DAP_TELEGRAM_OWNER_CHAT_ID", "").strip()

        if require_webhook_secret and not webhook_secret:
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
            webhook_secret=webhook_secret or None,
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
        if self.config.webhook_secret is None:
            raise TelegramIngressConfigurationError(
                "Telegram webhook ingress is not configured."
            )
        if webhook_secret_header is None or not secrets.compare_digest(
            webhook_secret_header,
            self.config.webhook_secret,
        ):
            raise PermissionError("Telegram webhook secret validation failed.")

        return self.accept_polled(update=update)

    def accept_polled(
        self,
        *,
        update: TelegramUpdate,
    ) -> TelegramOwnerCommand:
        """Authenticate an update already obtained from Telegram's Bot API."""

        if update.callback_query is not None:
            return self._accept_callback(update)

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
        if message.chat.type != "private":
            raise PermissionError("Telegram owner commands require a private chat.")

        text = (message.text or "").strip()
        command, execution_id, objective, accepted, reason = self._parse(text)

        return TelegramOwnerCommand(
            update_id=update.update_id,
            message_id=message.message_id,
            command=command,
            execution_id=execution_id,
            objective=objective,
            idempotency_key=f"telegram-update-{update.update_id}",
            accepted=accepted,
            reason=reason,
        )

    def _accept_callback(self, update: TelegramUpdate) -> TelegramOwnerCommand:
        callback = update.callback_query
        if callback is None or callback.message is None:
            raise PermissionError("Telegram callback does not contain a message.")
        if callback.from_user.is_bot:
            raise PermissionError("Telegram callback sender is not an owner user.")
        if callback.from_user.id != self.config.owner_user_id:
            raise PermissionError(
                "Telegram callback sender is not the configured owner."
            )
        if callback.message.chat.id != self.config.owner_chat_id:
            raise PermissionError(
                "Telegram callback chat is not the configured owner chat."
            )
        if callback.message.chat.type != "private":
            raise PermissionError("Telegram approvals require a private chat.")

        data = callback.data or ""
        parts = data.split(":", maxsplit=2)
        if len(parts) != 3 or parts[0] != "dap" or parts[1] not in {"a", "c", "r"}:
            command = "unsupported"
            token = None
            accepted = False
            reason = "Telegram approval callback is not supported."
        else:
            command = {"a": "approve", "c": "confirm", "r": "reject"}[parts[1]]
            token = parts[2]
            accepted = re.fullmatch(r"[A-Za-z0-9_-]{16}", token) is not None
            reason = f"Owner {command} callback accepted."
            if not accepted:
                command = "unsupported"
                token = None
                reason = "Telegram approval callback token is invalid."

        return TelegramOwnerCommand(
            update_id=update.update_id,
            message_id=callback.message.message_id,
            command=command,
            approval_token=token,
            callback_query_id=callback.id,
            idempotency_key=f"telegram-update-{update.update_id}",
            accepted=accepted,
            reason=reason,
        )

    @staticmethod
    def _parse(
        text: str,
    ) -> tuple[str, str | None, str | None, bool, str]:
        if text == "/status":
            return "status", None, None, True, "Owner status command accepted."

        if text in {"/help", "/start"}:
            return "help", None, None, True, "Owner help command accepted."

        if text == "/health":
            return "health", None, None, True, "Owner health command accepted."

        if text == "/agents":
            return "agents", None, None, True, "Owner agents command accepted."

        if text == "/tasks":
            return "tasks", None, None, True, "Owner tasks command accepted."

        if text == "/company":
            return "company", None, None, True, "Owner company command accepted."

        if text.startswith("/plan"):
            parts = text.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                return (
                    "plan",
                    None,
                    parts[1].strip(),
                    True,
                    "Owner advisory plan command accepted.",
                )
            return (
                "unsupported",
                None,
                None,
                False,
                "Planning requires an objective.",
            )

        if text.startswith("/cancel"):
            parts = text.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                return (
                    "cancel",
                    parts[1].strip(),
                    None,
                    True,
                    "Owner cancellation command accepted for routing.",
                )

            return (
                "unsupported",
                None,
                None,
                False,
                "Cancellation requires an execution ID.",
            )

        return (
            "unsupported",
            None,
            None,
            False,
            "Telegram command is not supported by the owner gateway.",
        )
