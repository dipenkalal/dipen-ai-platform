import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from agents.truth_repository import AgentTruthRepository, agent_truth_repository
from executive_office.schemas import utc_now
from owner_channels.telegram_schemas import TelegramOwnerCommand


class TelegramReceiptConflictError(RuntimeError):
    """Raised when one Telegram update ID is reused for different content."""


@dataclass(frozen=True)
class TelegramCommandReceipt:
    update_id: int
    request_hash: str
    command: str
    execution_id: str | None
    state: str
    response_json: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class TelegramCommandReceiptRepository:
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
                CREATE TABLE IF NOT EXISTS telegram_owner_command_receipts (
                    update_id INTEGER PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    command TEXT NOT NULL,
                    execution_id TEXT,
                    state TEXT NOT NULL,
                    response_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_telegram_receipts_state
                ON telegram_owner_command_receipts(state)
                """
            )
            connection.commit()

    def claim(self, command: TelegramOwnerCommand) -> TelegramCommandReceipt:
        request_hash = self._request_hash(command)
        now = utc_now()
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM telegram_owner_command_receipts
                WHERE update_id = ?
                """,
                (command.update_id,),
            ).fetchone()
            if row is not None:
                receipt = self._from_row(row)
                if receipt.request_hash != request_hash:
                    connection.rollback()
                    raise TelegramReceiptConflictError(
                        "Telegram update ID is already bound to different command content."
                    )
                connection.commit()
                return receipt
            connection.execute(
                """
                INSERT INTO telegram_owner_command_receipts (
                    update_id, request_hash, command, execution_id,
                    state, response_json, error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'claimed', NULL, NULL, ?, ?)
                """,
                (
                    command.update_id,
                    request_hash,
                    command.command,
                    command.execution_id,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.commit()
        return TelegramCommandReceipt(
            update_id=command.update_id,
            request_hash=request_hash,
            command=command.command,
            execution_id=command.execution_id,
            state="claimed",
            response_json=None,
            error=None,
            created_at=now,
            updated_at=now,
        )

    def complete(self, *, update_id: int, response: dict[str, object]) -> TelegramCommandReceipt:
        return self._finish(
            update_id=update_id,
            state="completed",
            response_json=json.dumps(response, sort_keys=True, default=str),
            error=None,
        )

    def fail(self, *, update_id: int, error: str) -> TelegramCommandReceipt:
        return self._finish(
            update_id=update_id,
            state="failed",
            response_json=None,
            error=error,
        )

    def _finish(
        self,
        *,
        update_id: int,
        state: str,
        response_json: str | None,
        error: str | None,
    ) -> TelegramCommandReceipt:
        now = utc_now()
        with self.truth_repository.connection() as connection:
            updated = connection.execute(
                """
                UPDATE telegram_owner_command_receipts
                SET state = ?, response_json = ?, error = ?, updated_at = ?
                WHERE update_id = ? AND state = 'claimed'
                """,
                (state, response_json, error, now.isoformat(), update_id),
            )
            if updated.rowcount != 1:
                row = connection.execute(
                    "SELECT * FROM telegram_owner_command_receipts WHERE update_id = ?",
                    (update_id,),
                ).fetchone()
                if row is None:
                    raise TelegramReceiptConflictError("Telegram command receipt is missing.")
                connection.commit()
                return self._from_row(row)
            connection.commit()
            row = connection.execute(
                "SELECT * FROM telegram_owner_command_receipts WHERE update_id = ?",
                (update_id,),
            ).fetchone()
        if row is None:
            raise TelegramReceiptConflictError("Telegram command receipt disappeared.")
        return self._from_row(row)

    @staticmethod
    def _request_hash(command: TelegramOwnerCommand) -> str:
        canonical = json.dumps(
            command.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> TelegramCommandReceipt:
        return TelegramCommandReceipt(
            update_id=int(row["update_id"]),
            request_hash=str(row["request_hash"]),
            command=str(row["command"]),
            execution_id=(str(row["execution_id"]) if row["execution_id"] is not None else None),
            state=str(row["state"]),
            response_json=(str(row["response_json"]) if row["response_json"] is not None else None),
            error=(str(row["error"]) if row["error"] is not None else None),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )


telegram_command_receipt_repository = TelegramCommandReceiptRepository()
