from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import AgentTruthRepository
from engineering.engineering_audit_evidence import EngineeringAuditEvidence


class EngineeringAuditPersistenceConflict(RuntimeError):
    """Raised when an evidence ID is reused with different immutable content."""


class PersistedEngineeringAuditRecord(BaseModel):
    """Read model for DAP-owned engineering evidence persisted beside task truth."""

    model_config = ConfigDict(frozen=True)

    evidence: EngineeringAuditEvidence
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stored_at: datetime
    evidence_persisted: Literal[True] = True
    task_ledger_mutated: Literal[False] = False


class EngineeringAuditRepository:
    """Persist immutable Engineering Agent evidence without changing task authority."""

    def __init__(self, truth_repository: AgentTruthRepository) -> None:
        self.truth_repository = truth_repository
        self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS engineering_audit_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    evidence_sha256 TEXT NOT NULL,
                    source_task_id TEXT NOT NULL,
                    source_execution_id TEXT NOT NULL,
                    work_order_id TEXT NOT NULL,
                    ticket_id TEXT NOT NULL,
                    guardian_admission_id TEXT NOT NULL,
                    delivery_id TEXT,
                    publication_id TEXT,
                    outcome TEXT NOT NULL,
                    commit_sha TEXT,
                    draft_pull_request_number INTEGER,
                    evidence_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_engineering_audit_task
                ON engineering_audit_evidence(source_task_id, stored_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_engineering_audit_work_order
                ON engineering_audit_evidence(work_order_id, stored_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_engineering_audit_outcome
                ON engineering_audit_evidence(outcome, stored_at DESC)
                """
            )
            connection.commit()

    def persist(
        self,
        evidence: EngineeringAuditEvidence,
    ) -> PersistedEngineeringAuditRecord:
        if self.truth_repository.get_task(evidence.source_task_id) is None:
            raise ValueError(
                "engineering evidence must reference an existing canonical DAP task"
            )

        evidence_sha256 = evidence.canonical_hash()
        stored_at = datetime.now(timezone.utc)

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM engineering_audit_evidence
                WHERE evidence_id = ?
                """,
                (evidence.evidence_id,),
            ).fetchone()

            if existing is not None:
                if str(existing["evidence_sha256"]) != evidence_sha256:
                    connection.rollback()
                    raise EngineeringAuditPersistenceConflict(
                        "Engineering evidence ID is already bound to different content."
                    )

                connection.commit()
                return PersistedEngineeringAuditRecord(
                    evidence=EngineeringAuditEvidence.model_validate_json(
                        str(existing["evidence_json"])
                    ),
                    evidence_sha256=evidence_sha256,
                    stored_at=datetime.fromisoformat(str(existing["stored_at"])),
                )

            connection.execute(
                """
                INSERT INTO engineering_audit_evidence (
                    evidence_id,
                    evidence_sha256,
                    source_task_id,
                    source_execution_id,
                    work_order_id,
                    ticket_id,
                    guardian_admission_id,
                    delivery_id,
                    publication_id,
                    outcome,
                    commit_sha,
                    draft_pull_request_number,
                    evidence_json,
                    stored_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.evidence_id,
                    evidence_sha256,
                    evidence.source_task_id,
                    evidence.source_execution_id,
                    evidence.work_order_id,
                    evidence.ticket_id,
                    evidence.guardian_admission_id,
                    evidence.delivery_id,
                    evidence.publication_id,
                    evidence.outcome,
                    evidence.commit_sha,
                    evidence.draft_pull_request_number,
                    evidence.model_dump_json(),
                    stored_at.isoformat(),
                ),
            )
            connection.commit()

        return PersistedEngineeringAuditRecord(
            evidence=evidence,
            evidence_sha256=evidence_sha256,
            stored_at=stored_at,
        )

    def get(self, evidence_id: str) -> PersistedEngineeringAuditRecord | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM engineering_audit_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_record(row)

    def list_for_task(self, task_id: str) -> list[PersistedEngineeringAuditRecord]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM engineering_audit_evidence
                WHERE source_task_id = ?
                ORDER BY stored_at ASC, evidence_id ASC
                """,
                (task_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_for_work_order(
        self,
        work_order_id: str,
    ) -> list[PersistedEngineeringAuditRecord]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM engineering_audit_evidence
                WHERE work_order_id = ?
                ORDER BY stored_at ASC, evidence_id ASC
                """,
                (work_order_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> list[PersistedEngineeringAuditRecord]:
        if limit < 1 or limit > 500:
            raise ValueError("engineering audit list limit must be between 1 and 500")
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM engineering_audit_evidence
                ORDER BY stored_at DESC, evidence_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: object) -> PersistedEngineeringAuditRecord:
        return PersistedEngineeringAuditRecord(
            evidence=EngineeringAuditEvidence.model_validate_json(
                str(row["evidence_json"])
            ),
            evidence_sha256=str(row["evidence_sha256"]),
            stored_at=datetime.fromisoformat(str(row["stored_at"])),
        )
