from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from agents.truth_repository import AgentTruthRepository, agent_truth_repository


class TelegramSecurityConfigurationError(RuntimeError):
    """Raised when Telegram safety settings are invalid."""


@dataclass(frozen=True)
class TelegramSecurityConfig:
    approvals_enabled: bool = False
    approval_ttl_seconds: int = 300
    command_rate_limit: int = 20
    callback_rate_limit: int = 6
    rate_window_seconds: int = 60

    @classmethod
    def from_env(cls) -> "TelegramSecurityConfig":
        approvals_enabled = _enabled("DAP_TELEGRAM_APPROVALS_ENABLED", "false")
        approval_ttl = _bounded_int("DAP_TELEGRAM_APPROVAL_TTL", 300, 60, 600)
        command_limit = _bounded_int("DAP_TELEGRAM_COMMAND_RATE_LIMIT", 20, 1, 120)
        callback_limit = _bounded_int("DAP_TELEGRAM_CALLBACK_RATE_LIMIT", 6, 1, 30)
        rate_window = _bounded_int("DAP_TELEGRAM_RATE_WINDOW", 60, 10, 300)
        return cls(
            approvals_enabled=approvals_enabled,
            approval_ttl_seconds=approval_ttl,
            command_rate_limit=command_limit,
            callback_rate_limit=callback_limit,
            rate_window_seconds=rate_window,
        )


def _enabled(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise TelegramSecurityConfigurationError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise TelegramSecurityConfigurationError(
            f"{name} must be between {minimum} and {maximum}."
        )
    return value


class TelegramSecurityRepository:
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
                CREATE TABLE IF NOT EXISTS telegram_security_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    update_id INTEGER NOT NULL UNIQUE,
                    event_kind TEXT NOT NULL,
                    claimed_user_id INTEGER,
                    claimed_chat_id INTEGER,
                    reason TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telegram_rate_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bucket TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_telegram_rate_events_bucket_time
                ON telegram_rate_events(bucket, recorded_at);
                """
            )
            connection.commit()

    def record_rejection(
        self,
        *,
        update_id: int,
        event_kind: str,
        claimed_user_id: int | None,
        claimed_chat_id: int | None,
        reason: str,
    ) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO telegram_security_audit (
                    update_id, event_kind, claimed_user_id, claimed_chat_id,
                    reason, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    update_id,
                    event_kind,
                    claimed_user_id,
                    claimed_chat_id,
                    reason[:240],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.execute(
                """
                DELETE FROM telegram_security_audit
                WHERE audit_id <= (
                    SELECT COALESCE(MAX(audit_id) - 5000, 0)
                    FROM telegram_security_audit
                )
                """
            )
            connection.commit()

    def allow(self, *, bucket: str, limit: int, window_seconds: int) -> bool:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM telegram_rate_events WHERE recorded_at < ?",
                (cutoff.isoformat(),),
            )
            count = connection.execute(
                """
                SELECT COUNT(*) AS count FROM telegram_rate_events
                WHERE bucket = ? AND recorded_at >= ?
                """,
                (bucket, cutoff.isoformat()),
            ).fetchone()
            if count is not None and int(count["count"]) >= limit:
                connection.commit()
                return False
            connection.execute(
                "INSERT INTO telegram_rate_events (bucket, recorded_at) VALUES (?, ?)",
                (bucket, now.isoformat()),
            )
            connection.commit()
        return True


telegram_security_repository = TelegramSecurityRepository()
