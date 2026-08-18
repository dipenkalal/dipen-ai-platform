from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import AgentTruthRepository
from engineering.engineering_audit_repository import EngineeringAuditRepository
from engineering.engineering_owner_review import EngineeringOwnerReviewDecision


class EngineeringOwnerReviewConflict(RuntimeError):
    """Raised when an evidence item already has a different immutable owner decision."""


class PersistedEngineeringOwnerReviewDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: EngineeringOwnerReviewDecision
    decision_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stored_at: datetime
    review_persisted: Literal[True] = True
    task_ledger_mutated: Literal[False] = False
    git_write_performed: Literal[False] = False
    pull_request_merged: Literal[False] = False
    deployment_performed: Literal[False] = False


class EngineeringOwnerReviewRepository:
    """Persist owner review decisions beside canonical task/evidence truth."""

    def __init__(
        self,
        truth_repository: AgentTruthRepository,
        audit_repository: EngineeringAuditRepository | None = None,
    ) -> None:
        self.truth_repository = truth_repository
        self.audit_repository = audit_repository or EngineeringAuditRepository(truth_repository)
        self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS engineering_owner_review_decisions (
                    decision_id TEXT PRIMARY KEY,
                    decision_sha256 TEXT NOT NULL,
                    review_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL UNIQUE,
                    evidence_sha256 TEXT NOT NULL,
                    source_task_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_engineering_owner_review_task
                ON engineering_owner_review_decisions(source_task_id, stored_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_engineering_owner_review_decision
                ON engineering_owner_review_decisions(decision, stored_at DESC)
                """
            )
            connection.commit()

    def persist(
        self,
        decision: EngineeringOwnerReviewDecision,
    ) -> PersistedEngineeringOwnerReviewDecision:
        task = self.truth_repository.get_task(decision.source_task_id)
        if task is None:
            raise ValueError("owner review must reference an existing canonical DAP task")

        evidence_record = self.audit_repository.get(decision.evidence_id)
        if evidence_record is None:
            raise ValueError("owner review must reference persisted engineering evidence")
        if evidence_record.evidence_sha256 != decision.evidence_sha256:
            raise ValueError("owner review evidence hash does not match persisted evidence")
        if evidence_record.evidence.source_task_id != decision.source_task_id:
            raise ValueError("owner review task does not match persisted engineering evidence")
        if evidence_record.evidence.outcome != "succeeded":
            raise ValueError("owner review decisions require successful engineering evidence")

        decision_sha256 = decision.canonical_hash()
        stored_at = datetime.now(timezone.utc)
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT decision_sha256, decision_json, stored_at
                FROM engineering_owner_review_decisions
                WHERE evidence_id = ?
                """,
                (decision.evidence_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["decision_sha256"]) != decision_sha256:
                    connection.rollback()
                    raise EngineeringOwnerReviewConflict(
                        "Engineering evidence already has a different owner review decision."
                    )
                connection.commit()
                return PersistedEngineeringOwnerReviewDecision(
                    decision=EngineeringOwnerReviewDecision.model_validate_json(
                        str(existing["decision_json"])
                    ),
                    decision_sha256=decision_sha256,
                    stored_at=datetime.fromisoformat(str(existing["stored_at"])),
                )

            connection.execute(
                """
                INSERT INTO engineering_owner_review_decisions (
                    decision_id,
                    decision_sha256,
                    review_id,
                    evidence_id,
                    evidence_sha256,
                    source_task_id,
                    owner_id,
                    decision,
                    decision_json,
                    stored_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision_sha256,
                    decision.review_id,
                    decision.evidence_id,
                    decision.evidence_sha256,
                    decision.source_task_id,
                    decision.owner_id,
                    decision.decision,
                    decision.model_dump_json(),
                    stored_at.isoformat(),
                ),
            )
            connection.commit()

        return PersistedEngineeringOwnerReviewDecision(
            decision=decision,
            decision_sha256=decision_sha256,
            stored_at=stored_at,
        )

    def get_for_evidence(
        self,
        evidence_id: str,
    ) -> PersistedEngineeringOwnerReviewDecision | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT decision_sha256, decision_json, stored_at
                FROM engineering_owner_review_decisions
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> list[PersistedEngineeringOwnerReviewDecision]:
        if limit < 1 or limit > 500:
            raise ValueError("owner review list limit must be between 1 and 500")
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT decision_sha256, decision_json, stored_at
                FROM engineering_owner_review_decisions
                ORDER BY stored_at DESC, decision_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> PersistedEngineeringOwnerReviewDecision:
        return PersistedEngineeringOwnerReviewDecision(
            decision=EngineeringOwnerReviewDecision.model_validate_json(
                str(row["decision_json"])
            ),
            decision_sha256=str(row["decision_sha256"]),
            stored_at=datetime.fromisoformat(str(row["stored_at"])),
        )
