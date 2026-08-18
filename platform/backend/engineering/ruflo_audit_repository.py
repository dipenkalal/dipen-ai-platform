from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import AgentTruthRepository
from engineering.ruflo_audit_evidence import RufloAuditEvidence


class RufloAuditPersistenceConflict(RuntimeError):
    """Raised when an evidence ID is reused with different immutable content."""


class PersistedRufloAuditRecord(BaseModel):
    """Read model for DAP-owned Ruflo evidence persisted beside task truth."""

    model_config = ConfigDict(frozen=True)

    evidence: RufloAuditEvidence
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stored_at: datetime
    evidence_persisted: Literal[True] = True
    task_ledger_mutated: Literal[False] = False


class RufloAuditRepository:
    """Persist immutable Ruflo evidence in the DAP truth database.

    The repository intentionally does not update ``task_ledger``. The canonical task
    remains owned by Agent Truth; the audit row references its ``source_task_id``.
    This keeps Phase 10F additive and prevents Ruflo evidence from becoming task
    authority.
    """

    def __init__(self, truth_repository: AgentTruthRepository) -> None:
        self.truth_repository = truth_repository
        self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ruflo_audit_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    evidence_sha256 TEXT NOT NULL,
                    source_task_id TEXT NOT NULL,
                    source_execution_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    candidate_disposition TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ruflo_audit_task
                ON ruflo_audit_evidence(source_task_id, stored_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ruflo_audit_request
                ON ruflo_audit_evidence(request_id)
                """
            )
            connection.commit()

    def persist(self, evidence: RufloAuditEvidence) -> PersistedRufloAuditRecord:
        evidence_sha256 = evidence.canonical_hash()
        stored_at = datetime.now(timezone.utc)

        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM ruflo_audit_evidence
                WHERE evidence_id = ?
                """,
                (evidence.evidence_id,),
            ).fetchone()

            if existing is not None:
                if str(existing["evidence_sha256"]) != evidence_sha256:
                    connection.rollback()
                    raise RufloAuditPersistenceConflict(
                        "Ruflo evidence ID is already bound to different content."
                    )

                connection.commit()
                return PersistedRufloAuditRecord(
                    evidence=RufloAuditEvidence.model_validate_json(
                        str(existing["evidence_json"])
                    ),
                    evidence_sha256=evidence_sha256,
                    stored_at=datetime.fromisoformat(str(existing["stored_at"])),
                )

            connection.execute(
                """
                INSERT INTO ruflo_audit_evidence (
                    evidence_id,
                    evidence_sha256,
                    source_task_id,
                    source_execution_id,
                    request_id,
                    candidate_disposition,
                    evidence_json,
                    stored_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.evidence_id,
                    evidence_sha256,
                    evidence.source_task_id,
                    evidence.source_execution_id,
                    evidence.request_id,
                    evidence.candidate_disposition,
                    evidence.model_dump_json(),
                    stored_at.isoformat(),
                ),
            )
            connection.commit()

        return PersistedRufloAuditRecord(
            evidence=evidence,
            evidence_sha256=evidence_sha256,
            stored_at=stored_at,
        )

    def get(self, evidence_id: str) -> PersistedRufloAuditRecord | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM ruflo_audit_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if row is None:
            return None

        return PersistedRufloAuditRecord(
            evidence=RufloAuditEvidence.model_validate_json(str(row["evidence_json"])),
            evidence_sha256=str(row["evidence_sha256"]),
            stored_at=datetime.fromisoformat(str(row["stored_at"])),
        )

    def list_for_task(self, task_id: str) -> list[PersistedRufloAuditRecord]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM ruflo_audit_evidence
                WHERE source_task_id = ?
                ORDER BY stored_at ASC, evidence_id ASC
                """,
                (task_id,),
            ).fetchall()

        return [
            PersistedRufloAuditRecord(
                evidence=RufloAuditEvidence.model_validate_json(
                    str(row["evidence_json"])
                ),
                evidence_sha256=str(row["evidence_sha256"]),
                stored_at=datetime.fromisoformat(str(row["stored_at"])),
            )
            for row in rows
        ]
