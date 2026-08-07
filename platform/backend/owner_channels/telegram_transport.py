from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import ValidationError

from agents.truth_repository import AgentTruthRepository, agent_truth_repository
from owner_channels.telegram_command_service import (
    telegram_owner_command_router,
)
from owner_channels.telegram_schemas import TelegramOwnerCommand, TelegramUpdate
from owner_channels.telegram_service import (
    TelegramIngressConfig,
    TelegramOwnerIngressService,
)

logger = logging.getLogger(__name__)


class TelegramTransportConfigurationError(RuntimeError):
    """Raised when long polling is enabled without safe configuration."""


class TelegramBotApiError(RuntimeError):
    """A sanitized Telegram Bot API failure that never includes the bot token."""


@dataclass(frozen=True)
class TelegramTransportConfig:
    enabled: bool
    bot_token: str | None
    poll_timeout_seconds: int = 25
    retry_initial_seconds: float = 1.0
    retry_max_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> TelegramTransportConfig:
        enabled = os.getenv("DAP_TELEGRAM_POLLING_ENABLED", "false").strip().lower()
        is_enabled = enabled in {"1", "true", "yes", "on"}
        token = os.getenv("DAP_TELEGRAM_BOT_TOKEN", "").strip() or None
        if is_enabled and token is None:
            raise TelegramTransportConfigurationError(
                "DAP_TELEGRAM_BOT_TOKEN is required when Telegram polling is enabled."
            )

        try:
            poll_timeout = int(os.getenv("DAP_TELEGRAM_POLL_TIMEOUT", "25"))
        except ValueError as exc:
            raise TelegramTransportConfigurationError(
                "DAP_TELEGRAM_POLL_TIMEOUT must be an integer."
            ) from exc
        if not 1 <= poll_timeout <= 50:
            raise TelegramTransportConfigurationError(
                "DAP_TELEGRAM_POLL_TIMEOUT must be between 1 and 50 seconds."
            )

        return cls(
            enabled=is_enabled,
            bot_token=token,
            poll_timeout_seconds=poll_timeout,
        )


class TelegramBotClient(Protocol):
    async def prepare_long_polling(self) -> None: ...

    async def get_updates(
        self,
        *,
        offset: int | None,
        timeout: int,
    ) -> list[dict[str, object]]: ...

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int,
    ) -> None: ...


class TelegramCommandRouter(Protocol):
    def route(self, command: TelegramOwnerCommand) -> dict[str, object]: ...


class TelegramHttpBotClient:
    def __init__(self, *, token: str, client: httpx.AsyncClient) -> None:
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._client = client

    async def prepare_long_polling(self) -> None:
        await self._call(
            "deleteWebhook",
            {"drop_pending_updates": False},
            timeout=10.0,
        )

    async def get_updates(
        self,
        *,
        offset: int | None,
        timeout: int,
    ) -> list[dict[str, object]]:
        payload: dict[str, object] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = await self._call(
            "getUpdates",
            payload,
            timeout=timeout + 5.0,
        )
        if not isinstance(result, list):
            raise TelegramBotApiError("Telegram getUpdates returned an invalid result.")
        return [item for item in result if isinstance(item, dict)]

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int,
    ) -> None:
        await self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "reply_parameters": {"message_id": reply_to_message_id},
            },
            timeout=10.0,
        )

    async def _call(
        self,
        method: str,
        payload: dict[str, object],
        *,
        timeout: float | None = None,
    ) -> object:
        try:
            response = await self._client.post(
                f"{self._base_url}/{method}",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            raise TelegramBotApiError(
                f"Telegram Bot API {method} request failed."
            ) from None
        if not isinstance(body, dict) or body.get("ok") is not True:
            raise TelegramBotApiError(
                f"Telegram Bot API {method} rejected the request."
            )
        return body.get("result")


class TelegramPollingOffsetRepository:
    def __init__(
        self,
        truth_repository: AgentTruthRepository = agent_truth_repository,
    ) -> None:
        self.truth_repository = truth_repository
        self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_polling_state (
                    consumer TEXT PRIMARY KEY,
                    next_update_id INTEGER NOT NULL
                )
                """
            )
            connection.commit()

    def get_next_update_id(self) -> int | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT next_update_id FROM telegram_polling_state
                WHERE consumer = 'owner-command-gateway'
                """
            ).fetchone()
        return int(row["next_update_id"]) if row is not None else None

    def advance(self, update_id: int) -> None:
        next_update_id = update_id + 1
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO telegram_polling_state (consumer, next_update_id)
                VALUES ('owner-command-gateway', ?)
                ON CONFLICT(consumer) DO UPDATE SET
                    next_update_id = MAX(next_update_id, excluded.next_update_id)
                """,
                (next_update_id,),
            )
            connection.commit()


class TelegramLongPollingWorker:
    def __init__(
        self,
        *,
        client: TelegramBotClient,
        ingress: TelegramOwnerIngressService,
        router: TelegramCommandRouter = telegram_owner_command_router,
        offsets: TelegramPollingOffsetRepository,
        owner_chat_id: int,
        poll_timeout_seconds: int = 25,
    ) -> None:
        self.client = client
        self.ingress = ingress
        self.router = router
        self.offsets = offsets
        self.owner_chat_id = owner_chat_id
        self.poll_timeout_seconds = poll_timeout_seconds

    async def poll_once(self) -> int:
        updates = await self.client.get_updates(
            offset=self.offsets.get_next_update_id(),
            timeout=self.poll_timeout_seconds,
        )
        processed = 0
        for raw_update in updates:
            update_id = raw_update.get("update_id")
            if not isinstance(update_id, int):
                logger.warning("Skipping Telegram update without an integer update_id.")
                continue
            try:
                update = TelegramUpdate.model_validate(raw_update)
                command = self.ingress.accept_polled(update=update)
            except PermissionError as exc:
                logger.warning(
                    "Rejected Telegram update %s: %s",
                    update_id,
                    exc,
                )
                self.offsets.advance(update_id)
                processed += 1
                continue
            except ValidationError:
                logger.warning("Rejected malformed Telegram update %s.", update_id)
                self.offsets.advance(update_id)
                processed += 1
                continue

            result = await asyncio.to_thread(self.router.route, command)
            await self.client.send_message(
                chat_id=self.owner_chat_id,
                text=format_telegram_response(result),
                reply_to_message_id=command.message_id,
            )
            self.offsets.advance(update_id)
            processed += 1
        return processed

    async def run(
        self,
        *,
        stop_event: asyncio.Event,
        retry_initial_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
    ) -> None:
        retry_delay = retry_initial_seconds
        polling_prepared = False
        while not stop_event.is_set():
            try:
                if not polling_prepared:
                    await self.client.prepare_long_polling()
                    polling_prepared = True
                await self.poll_once()
                retry_delay = retry_initial_seconds
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram long polling iteration failed.")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=retry_delay)
                except TimeoutError:
                    pass
                retry_delay = min(retry_delay * 2, retry_max_seconds)


def format_telegram_response(result: dict[str, object]) -> str:
    command = result.get("command")
    if command == "help" and result.get("ok") is True:
        commands = result.get("commands", [])
        command_lines = commands if isinstance(commands, list) else []
        return "Available owner commands:\n" + "\n".join(
            str(item) for item in command_lines
        )
    if command == "status" and result.get("ok") is True:
        return "\n".join(
            [
                f"DAP {result.get('version', 'unknown')}",
                f"Execution: {'enabled' if result.get('execution_enabled') else 'disabled'}",
                "Cancellation: "
                + ("enabled" if result.get("execution_cancellation_enabled") else "disabled"),
                f"Capabilities: {result.get('capability_count', 0)}",
            ]
        )
    if command == "agents" and result.get("ok") is True:
        summary = _as_dict(result.get("summary"))
        agents = _as_dict_list(result.get("agents"))
        lines = [
            (
                "Agents: "
                f"{summary.get('available', 0)} available, "
                f"{summary.get('busy', 0)} busy, "
                f"{summary.get('offline', 0)} offline"
            )
        ]
        lines.extend(
            f"{agent.get('name', agent.get('id', 'unknown'))}: "
            f"{agent.get('status', 'unknown')}"
            for agent in agents
        )
        return "\n".join(lines)
    if command == "tasks" and result.get("ok") is True:
        tasks = _as_dict_list(result.get("tasks"))
        if not tasks:
            return "Tasks: none recorded."
        lines = [f"Tasks: {result.get('total', len(tasks))} total (latest 5)"]
        lines.extend(
            f"{task.get('task_id', 'unknown')}: {task.get('status', 'unknown')}"
            for task in tasks
        )
        return "\n".join(lines)
    if command == "company" and result.get("ok") is True:
        summary = _as_dict(result.get("summary"))
        return "\n".join(
            [
                str(result.get("organization_name", "Dipen AI Platform")),
                f"Departments: {summary.get('department_count', 0)}",
                f"Roles: {summary.get('role_count', 0)}",
                f"Active roles: {summary.get('active_roles', 0)}",
                f"Mapped agents: {summary.get('mapped_agent_roles', 0)}",
            ]
        )
    if command == "plan" and result.get("ok") is True:
        tasks = _as_dict_list(result.get("tasks"))
        lines = [
            f"Plan: {result.get('disposition', 'unknown')}",
            f"Risk: {result.get('overall_risk', 'unknown')}",
            f"Decision: {result.get('decision_id', 'unknown')}",
            "Execution started: no",
        ]
        lines.extend(
            f"{task.get('task_id', 'unknown')} -> {task.get('role_id', 'unknown')}"
            for task in tasks
        )
        return "\n".join(lines)
    if command == "cancel" and result.get("ok") is True:
        return str(result.get("message") or "Cancellation request accepted.")
    return str(result.get("message") or "Telegram command could not be completed.")


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def build_telegram_polling_worker(
    *,
    config: TelegramTransportConfig,
    client: httpx.AsyncClient,
) -> TelegramLongPollingWorker:
    if not config.enabled or config.bot_token is None:
        raise TelegramTransportConfigurationError("Telegram polling is not enabled.")
    ingress_config = TelegramIngressConfig.from_env(require_webhook_secret=False)
    return TelegramLongPollingWorker(
        client=TelegramHttpBotClient(token=config.bot_token, client=client),
        ingress=TelegramOwnerIngressService(ingress_config),
        offsets=TelegramPollingOffsetRepository(),
        owner_chat_id=ingress_config.owner_chat_id,
        poll_timeout_seconds=config.poll_timeout_seconds,
    )
