from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from agents.truth_repository import AgentTruthRepository, agent_truth_repository
from executive_office.delegation_service import (
    ExecutiveDelegationService,
    executive_delegation_service,
)
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutivePlanRequest,
    OwnerApprovalRecord,
)
from executive_office.service import ExecutiveOfficeService, executive_office_service


@dataclass(frozen=True)
class TelegramApprovalProposal:
    token: str
    decision_id: str
    request: ExecutivePlanRequest
    expires_at: datetime
    state: str
    result: dict[str, object] | None = None


class TelegramApprovalRepository:
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
                CREATE TABLE IF NOT EXISTS telegram_approval_proposals (
                    token TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    plan_request_json TEXT NOT NULL,
                    source_update_id INTEGER NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    acted_at TEXT,
                    callback_update_id INTEGER,
                    result_json TEXT
                );

                CREATE TABLE IF NOT EXISTS telegram_approval_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    callback_update_id INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    FOREIGN KEY(token) REFERENCES telegram_approval_proposals(token)
                );
                """
            )
            connection.commit()

    def create(
        self,
        *,
        decision_id: str,
        request: ExecutivePlanRequest,
        source_update_id: int,
        ttl_seconds: int,
    ) -> TelegramApprovalProposal:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        request_json = request.model_dump_json()
        with self.truth_repository.connection() as connection:
            existing = connection.execute(
                """
                SELECT * FROM telegram_approval_proposals
                WHERE source_update_id = ?
                """,
                (source_update_id,),
            ).fetchone()
            if existing is not None:
                return self._from_row(existing)
            token = secrets.token_urlsafe(12)
            connection.execute(
                """
                INSERT INTO telegram_approval_proposals (
                    token, decision_id, plan_request_json, source_update_id,
                    state, created_at, expires_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    token,
                    decision_id,
                    request_json,
                    source_update_id,
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            connection.commit()
        return TelegramApprovalProposal(
            token=token,
            decision_id=decision_id,
            request=request,
            expires_at=expires_at,
            state="pending",
        )

    def begin_action(
        self,
        *,
        token: str,
        action: str,
        callback_update_id: int,
    ) -> TelegramApprovalProposal:
        now = datetime.now(timezone.utc)
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM telegram_approval_proposals WHERE token = ?",
                (token,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise KeyError("Approval request was not found.")
            proposal = self._from_row(row)
            if proposal.expires_at <= now and proposal.state in {
                "pending",
                "awaiting_confirmation",
            }:
                connection.execute(
                    """
                    UPDATE telegram_approval_proposals
                    SET state = 'expired', acted_at = ?, callback_update_id = ?
                    WHERE token = ? AND state IN ('pending', 'awaiting_confirmation')
                    """,
                    (now.isoformat(), callback_update_id, token),
                )
                connection.execute(
                    """
                    INSERT INTO telegram_approval_audit (
                        token, decision_id, action, actor, callback_update_id,
                        recorded_at, outcome
                    ) VALUES (?, ?, ?, 'dipen-owner', ?, ?, 'expired')
                    """,
                    (
                        token,
                        proposal.decision_id,
                        action,
                        callback_update_id,
                        now.isoformat(),
                    ),
                )
                connection.commit()
                return TelegramApprovalProposal(
                    **{**proposal.__dict__, "state": "expired"}
                )
            if proposal.state == "processing" and action == "confirm":
                connection.commit()
                return proposal
            if proposal.state == "awaiting_confirmation" and action == "confirm":
                connection.execute(
                    """
                    UPDATE telegram_approval_proposals
                    SET state = 'processing', acted_at = ?, callback_update_id = ?
                    WHERE token = ? AND state = 'awaiting_confirmation'
                    """,
                    (now.isoformat(), callback_update_id, token),
                )
                connection.execute(
                    """
                    INSERT INTO telegram_approval_audit (
                        token, decision_id, action, actor, callback_update_id,
                        recorded_at, outcome
                    ) VALUES (?, ?, 'confirm', 'dipen-owner', ?, ?, 'processing')
                    """,
                    (token, proposal.decision_id, callback_update_id, now.isoformat()),
                )
                connection.commit()
                return TelegramApprovalProposal(
                    **{**proposal.__dict__, "state": "processing"}
                )
            if proposal.state == "awaiting_confirmation" and action == "reject":
                connection.execute(
                    """
                    UPDATE telegram_approval_proposals
                    SET state = 'rejected', acted_at = ?, callback_update_id = ?
                    WHERE token = ? AND state = 'awaiting_confirmation'
                    """,
                    (now.isoformat(), callback_update_id, token),
                )
                connection.execute(
                    """
                    INSERT INTO telegram_approval_audit (
                        token, decision_id, action, actor, callback_update_id,
                        recorded_at, outcome
                    ) VALUES (?, ?, 'reject', 'dipen-owner', ?, ?, 'rejected')
                    """,
                    (
                        token,
                        proposal.decision_id,
                        callback_update_id,
                        now.isoformat(),
                    ),
                )
                connection.commit()
                return TelegramApprovalProposal(
                    **{**proposal.__dict__, "state": "rejected"}
                )

            if proposal.state != "pending":
                connection.commit()
                return proposal
            state = "awaiting_confirmation" if action == "approve" else "rejected"
            connection.execute(
                """
                UPDATE telegram_approval_proposals
                SET state = ?, acted_at = ?, callback_update_id = ?
                WHERE token = ? AND state = 'pending'
                """,
                (state, now.isoformat(), callback_update_id, token),
            )
            connection.execute(
                """
                INSERT INTO telegram_approval_audit (
                    token, decision_id, action, actor, callback_update_id,
                    recorded_at, outcome
                ) VALUES (?, ?, ?, 'dipen-owner', ?, ?, ?)
                """,
                (
                    token,
                    proposal.decision_id,
                    action,
                    callback_update_id,
                    now.isoformat(),
                    state,
                ),
            )
            connection.commit()
        return TelegramApprovalProposal(**{**proposal.__dict__, "state": state})

    def finish(
        self,
        *,
        token: str,
        state: str,
        result: dict[str, object],
    ) -> TelegramApprovalProposal:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                UPDATE telegram_approval_proposals
                SET state = ?, result_json = ?
                WHERE token = ? AND state = 'processing'
                """,
                (state, json.dumps(result, sort_keys=True), token),
            )
            connection.execute(
                """
                UPDATE telegram_approval_audit
                SET outcome = ?
                WHERE audit_id = (
                    SELECT MAX(audit_id) FROM telegram_approval_audit
                    WHERE token = ? AND action = 'confirm'
                )
                """,
                (state, token),
            )
            row = connection.execute(
                "SELECT * FROM telegram_approval_proposals WHERE token = ?",
                (token,),
            ).fetchone()
            connection.commit()
        if row is None:
            raise KeyError("Approval request disappeared.")
        return self._from_row(row)

    @staticmethod
    def _from_row(row) -> TelegramApprovalProposal:
        result = json.loads(row["result_json"]) if row["result_json"] else None
        return TelegramApprovalProposal(
            token=str(row["token"]),
            decision_id=str(row["decision_id"]),
            request=ExecutivePlanRequest.model_validate_json(
                str(row["plan_request_json"])
            ),
            expires_at=datetime.fromisoformat(str(row["expires_at"])),
            state=str(row["state"]),
            result=result if isinstance(result, dict) else None,
        )


class TelegramApprovalService:
    def __init__(
        self,
        *,
        repository: TelegramApprovalRepository,
        planning_service: ExecutiveOfficeService = executive_office_service,
        delegation_service: ExecutiveDelegationService = executive_delegation_service,
        ttl_seconds: int = 300,
        enabled: bool = False,
    ) -> None:
        self.repository = repository
        self.planning_service = planning_service
        self.delegation_service = delegation_service
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

    def propose(
        self,
        *,
        request: ExecutivePlanRequest,
        decision_id: str,
        source_update_id: int,
    ) -> TelegramApprovalProposal:
        if not self.enabled:
            raise PermissionError("Telegram delegation approvals are disabled.")
        return self.repository.create(
            decision_id=decision_id,
            request=request,
            source_update_id=source_update_id,
            ttl_seconds=self.ttl_seconds,
        )

    def decide(
        self,
        *,
        token: str,
        action: str,
        callback_update_id: int,
    ) -> dict[str, object]:
        if not self.enabled:
            return self._terminal(
                "disabled", "Telegram approvals are disabled. No task was changed."
            )
        if action not in {"approve", "confirm", "reject"}:
            raise ValueError("Unsupported approval action.")
        proposal = self.repository.begin_action(
            token=token,
            action=action,
            callback_update_id=callback_update_id,
        )
        if proposal.result is not None:
            return {**proposal.result, "idempotent_replay": True}
        if proposal.state == "expired":
            return self._terminal("expired", "Approval expired. No task was changed.")
        if proposal.state == "rejected":
            return self._terminal("rejected", "Plan rejected. No task was changed.")
        if proposal.state == "awaiting_confirmation":
            return {
                **self._terminal(
                    "awaiting_confirmation",
                    "Review the plan and confirm delegation. No task was changed.",
                ),
                "confirmation_token": proposal.token,
            }
        if proposal.state != "processing":
            return self._terminal(
                proposal.state,
                "Approval was already used. No additional task was changed.",
            )

        revalidated = self.planning_service.plan(proposal.request)
        if revalidated.decision_id != proposal.decision_id:
            revalidation_result = self._terminal(
                "revalidation_failed",
                "Plan changed during revalidation. No task was changed.",
            )
            self.repository.finish(
                token=token,
                state="failed",
                result=revalidation_result,
            )
            return revalidation_result

        delegation = self.delegation_service.delegate(
            ExecutiveDelegationRequest(
                plan=proposal.request,
                idempotency_key=f"telegram-approval-{token}",
                owner_approval=OwnerApprovalRecord(
                    approval_id=f"telegram-owner-{token}",
                    decision_id=proposal.decision_id,
                    statement=(
                        "Dipen approved this exact bounded plan through the "
                        "authenticated Telegram owner channel. Delegation only; "
                        "this approval did not start runtime execution."
                    ),
                ),
            )
        )
        result: dict[str, object] = {
            "ok": delegation.disposition in {"delegated", "idempotent_replay"},
            "command": "approve",
            "approval_state": "approved",
            "delegation_id": delegation.delegation_id,
            "disposition": delegation.disposition,
            "task_ledger_written": delegation.task_ledger_written,
            "execution_started": delegation.execution_started,
            "message": delegation.message,
            "idempotent_replay": delegation.idempotent_replay,
        }
        self.repository.finish(token=token, state="approved", result=result)
        return result

    @staticmethod
    def _terminal(state: str, message: str) -> dict[str, object]:
        return {
            "ok": state == "rejected",
            "command": "approval",
            "approval_state": state,
            "task_ledger_written": False,
            "execution_started": False,
            "message": message,
            "idempotent_replay": False,
        }


telegram_approval_repository = TelegramApprovalRepository()
telegram_approval_service = TelegramApprovalService(
    repository=telegram_approval_repository,
)
