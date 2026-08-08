from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from agents.truth_repository import AgentTruthRepository, agent_truth_repository

logger = logging.getLogger(__name__)

SUPPORTED_NOTIFICATION_CATEGORIES = frozenset(
    {
        "task_started",
        "task_completed",
        "task_failed",
        "task_cancelled",
        "guardian_blocked",
    }
)


@dataclass(frozen=True)
class TelegramNotificationConfig:
    enabled: bool
    categories: frozenset[str]
    interval_seconds: float = 2.0

    @classmethod
    def from_env(cls) -> TelegramNotificationConfig:
        enabled = os.getenv(
            "DAP_TELEGRAM_NOTIFICATIONS_ENABLED", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        raw_categories = os.getenv(
            "DAP_TELEGRAM_NOTIFICATION_CATEGORIES",
            "task_started,task_completed,task_failed,task_cancelled,guardian_blocked",
        )
        categories = frozenset(
            item.strip() for item in raw_categories.split(",") if item.strip()
        )
        unsupported = categories - SUPPORTED_NOTIFICATION_CATEGORIES
        if unsupported:
            raise ValueError(
                "Unsupported Telegram notification categories: "
                + ", ".join(sorted(unsupported))
            )
        try:
            interval = float(
                os.getenv("DAP_TELEGRAM_NOTIFICATION_INTERVAL", "2")
            )
        except ValueError as exc:
            raise ValueError(
                "DAP_TELEGRAM_NOTIFICATION_INTERVAL must be numeric."
            ) from exc
        if not 0.5 <= interval <= 60:
            raise ValueError(
                "DAP_TELEGRAM_NOTIFICATION_INTERVAL must be between 0.5 and 60."
            )
        return cls(
            enabled=enabled,
            categories=categories,
            interval_seconds=interval,
        )


@dataclass(frozen=True)
class OwnerNotificationEvent:
    event_id: str
    category: str
    subject_id: str
    payload: dict[str, object]


class OwnerNotificationOutbox:
    def __init__(
        self,
        truth_repository: AgentTruthRepository = agent_truth_repository,
    ) -> None:
        self.truth_repository = truth_repository
        self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS owner_notification_outbox (
                    event_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telegram_notification_deliveries (
                    event_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    delivered_at TEXT,
                    error TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_owner_notification_created
                ON owner_notification_outbox(created_at, event_id);

                CREATE TRIGGER IF NOT EXISTS task_lifecycle_notification_insert
                AFTER INSERT ON task_ledger
                WHEN NEW.status IN ('running', 'completed', 'failed', 'cancelled')
                BEGIN
                    INSERT OR IGNORE INTO owner_notification_outbox (
                        event_id, category, subject_id, payload_json, created_at
                    ) VALUES (
                        NEW.task_id || ':' || NEW.status || ':' || NEW.updated_at,
                        'task_' || CASE NEW.status
                            WHEN 'running' THEN 'started'
                            ELSE NEW.status
                        END,
                        NEW.task_id,
                        json_object(
                            'task_id', NEW.task_id,
                            'status', NEW.status,
                            'objective', NEW.objective,
                            'error', NEW.error
                        ),
                        NEW.updated_at
                    );
                END;

                CREATE TRIGGER IF NOT EXISTS task_lifecycle_notification_update
                AFTER UPDATE OF status ON task_ledger
                WHEN NEW.status != OLD.status
                    AND NEW.status IN ('running', 'completed', 'failed', 'cancelled')
                BEGIN
                    INSERT OR IGNORE INTO owner_notification_outbox (
                        event_id, category, subject_id, payload_json, created_at
                    ) VALUES (
                        NEW.task_id || ':' || NEW.status || ':' || NEW.updated_at,
                        'task_' || CASE NEW.status
                            WHEN 'running' THEN 'started'
                            ELSE NEW.status
                        END,
                        NEW.task_id,
                        json_object(
                            'task_id', NEW.task_id,
                            'status', NEW.status,
                            'objective', NEW.objective,
                            'error', NEW.error
                        ),
                        NEW.updated_at
                    );
                END;
                """
            )
            connection.commit()

    def enqueue_guardian_block(
        self,
        *,
        decision_id: str,
        objectives: list[str],
        reasons: list[str],
    ) -> None:
        event_id = f"guardian-blocked:{decision_id}"
        payload = {
            "decision_id": decision_id,
            "objectives": objectives,
            "reasons": reasons,
        }
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO owner_notification_outbox (
                    event_id, category, subject_id, payload_json, created_at
                ) VALUES (?, 'guardian_blocked', ?, ?, ?)
                """,
                (
                    event_id,
                    decision_id,
                    json.dumps(payload, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()

    def claim_next(
        self, *, categories: frozenset[str]
    ) -> OwnerNotificationEvent | None:
        if not categories:
            return None
        placeholders = ",".join("?" for _ in categories)
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"""
                SELECT event_id, category, subject_id, payload_json
                FROM owner_notification_outbox AS event
                WHERE event.category IN ({placeholders})
                  AND NOT EXISTS (
                    SELECT 1 FROM telegram_notification_deliveries AS delivery
                    WHERE delivery.event_id = event.event_id
                  )
                ORDER BY event.created_at, event.event_id
                LIMIT 1
                """,
                tuple(sorted(categories)),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                """
                INSERT INTO telegram_notification_deliveries (
                    event_id, state, claimed_at
                ) VALUES (?, 'claimed', ?)
                """,
                (str(row["event_id"]), datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
        payload = json.loads(str(row["payload_json"]))
        return OwnerNotificationEvent(
            event_id=str(row["event_id"]),
            category=str(row["category"]),
            subject_id=str(row["subject_id"]),
            payload=payload if isinstance(payload, dict) else {},
        )

    def mark_delivered(self, event_id: str) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                UPDATE telegram_notification_deliveries
                SET state = 'delivered', delivered_at = ?, error = NULL
                WHERE event_id = ? AND state = 'claimed'
                """,
                (datetime.now(timezone.utc).isoformat(), event_id),
            )
            connection.commit()

    def release(self, event_id: str, error: str) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                "DELETE FROM telegram_notification_deliveries WHERE event_id = ?",
                (event_id,),
            )
            connection.commit()
        logger.warning("Telegram notification delivery failed: %s", error)


class NotificationBotClient(Protocol):
    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> None: ...


class TelegramNotificationWorker:
    def __init__(
        self,
        *,
        client: NotificationBotClient,
        outbox: OwnerNotificationOutbox,
        owner_chat_id: int,
        categories: frozenset[str],
    ) -> None:
        self.client = client
        self.outbox = outbox
        self.owner_chat_id = owner_chat_id
        self.categories = categories

    async def deliver_once(self) -> bool:
        event = await asyncio.to_thread(
            self.outbox.claim_next, categories=self.categories
        )
        if event is None:
            return False
        try:
            await self.client.send_message(
                chat_id=self.owner_chat_id,
                text=format_notification(event),
            )
        except Exception as exc:
            await asyncio.to_thread(
                self.outbox.release, event.event_id, type(exc).__name__
            )
            raise
        await asyncio.to_thread(self.outbox.mark_delivered, event.event_id)
        return True

    async def run(
        self, *, stop_event: asyncio.Event, interval_seconds: float
    ) -> None:
        while not stop_event.is_set():
            try:
                delivered = await self.deliver_once()
                if delivered:
                    continue
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram notification iteration failed.")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


def format_notification(event: OwnerNotificationEvent) -> str:
    task_id = _compact(event.payload.get("task_id", event.subject_id))
    objective = _truncate(event.payload.get("objective"), limit=180)
    if event.category == "guardian_blocked":
        reasons = event.payload.get("reasons")
        reason = reasons[0] if isinstance(reasons, list) and reasons else "Policy block"
        return "\n".join(
            [
                "🛡️ Guardian blocked an operation",
                f"Decision: {_compact(event.payload.get('decision_id'))}",
                f"Reason: {_truncate(reason, limit=180)}",
                "Execution started: no",
            ]
        )
    titles = {
        "task_started": "▶️ Task started",
        "task_completed": "✅ Task completed",
        "task_failed": "❌ Task failed",
        "task_cancelled": "⏹️ Task cancelled",
    }
    lines = [titles.get(event.category, "DAP notification"), f"Task: {task_id}"]
    if objective:
        lines.append(f"Objective: {objective}")
    error = _truncate(event.payload.get("error"), limit=180)
    if error and event.category == "task_failed":
        lines.append(f"Error: {error}")
    return "\n".join(lines)


def _compact(value: object, *, limit: int = 20) -> str:
    text = str(value or "unknown")
    return text if len(text) <= limit else f"{text[:12]}…{text[-7:]}"


def _truncate(value: object, *, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


owner_notification_outbox = OwnerNotificationOutbox()
