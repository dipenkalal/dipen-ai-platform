from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import AgentTruthRepository
from gateway.research_retrieval_evidence import ResearchRetrievalEvidence


class ResearchRetrievalPersistenceConflict(RuntimeError):
    """Raised when an evidence ID is reused with different immutable content."""


class PersistedResearchRetrievalRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence: ResearchRetrievalEvidence
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stored_at: datetime
    evidence_persisted: Literal[True] = True
    task_ledger_mutated: Literal[False] = False
    knowledge_mutated: Literal[False] = False


class ResearchRetrievalRepository:
    """Persist immutable internet research evidence beside canonical DAP truth."""

    def __init__(self, truth_repository: AgentTruthRepository) -> None:
        self.truth_repository = truth_repository
        self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_retrieval_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    evidence_sha256 TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    canonical_task_id TEXT,
                    outcome TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    requested_url TEXT NOT NULL,
                    final_url TEXT,
                    citation_id TEXT,
                    content_evidence_id TEXT,
                    evidence_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_retrieval_request
                ON research_retrieval_evidence(request_id, stored_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_retrieval_task
                ON research_retrieval_evidence(canonical_task_id, stored_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_retrieval_outcome
                ON research_retrieval_evidence(outcome, stored_at DESC)
                """
            )
            connection.commit()

    def persist(
        self,
        evidence: ResearchRetrievalEvidence,
    ) -> PersistedResearchRetrievalRecord:
        if evidence.canonical_hash() != evidence.evidence_sha256:
            raise ValueError("research retrieval evidence hash does not match canonical content")
        if (
            evidence.canonical_task_id is not None
            and self.truth_repository.get_task(evidence.canonical_task_id) is None
        ):
            raise ValueError(
                "task-bound research evidence must reference an existing canonical DAP task"
            )

        stored_at = datetime.now(timezone.utc)
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM research_retrieval_evidence
                WHERE evidence_id = ?
                """,
                (evidence.evidence_id,),
            ).fetchone()

            if existing is not None:
                if str(existing["evidence_sha256"]) != evidence.evidence_sha256:
                    connection.rollback()
                    raise ResearchRetrievalPersistenceConflict(
                        "Research retrieval evidence ID is already bound to different content."
                    )
                connection.commit()
                return PersistedResearchRetrievalRecord(
                    evidence=ResearchRetrievalEvidence.model_validate_json(
                        str(existing["evidence_json"])
                    ),
                    evidence_sha256=evidence.evidence_sha256,
                    stored_at=datetime.fromisoformat(str(existing["stored_at"])),
                )

            citation_id = evidence.citation.citation_id if evidence.citation else None
            connection.execute(
                """
                INSERT INTO research_retrieval_evidence (
                    evidence_id,
                    evidence_sha256,
                    request_id,
                    canonical_task_id,
                    outcome,
                    stage,
                    provider_id,
                    requested_url,
                    final_url,
                    citation_id,
                    content_evidence_id,
                    evidence_json,
                    stored_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.evidence_id,
                    evidence.evidence_sha256,
                    evidence.request_id,
                    evidence.canonical_task_id,
                    evidence.outcome,
                    evidence.stage,
                    evidence.provider_id,
                    evidence.requested_url,
                    evidence.final_url,
                    citation_id,
                    evidence.content_evidence_id,
                    evidence.model_dump_json(),
                    stored_at.isoformat(),
                ),
            )
            connection.commit()

        return PersistedResearchRetrievalRecord(
            evidence=evidence,
            evidence_sha256=evidence.evidence_sha256,
            stored_at=stored_at,
        )

    def get(self, evidence_id: str) -> PersistedResearchRetrievalRecord | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM research_retrieval_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_for_request(self, request_id: str) -> list[PersistedResearchRetrievalRecord]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM research_retrieval_evidence
                WHERE request_id = ?
                ORDER BY stored_at ASC, evidence_id ASC
                """,
                (request_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_for_task(self, task_id: str) -> list[PersistedResearchRetrievalRecord]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM research_retrieval_evidence
                WHERE canonical_task_id = ?
                ORDER BY stored_at ASC, evidence_id ASC
                """,
                (task_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> list[PersistedResearchRetrievalRecord]:
        if limit < 1 or limit > 500:
            raise ValueError("research retrieval list limit must be between 1 and 500")
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT evidence_sha256, evidence_json, stored_at
                FROM research_retrieval_evidence
                ORDER BY stored_at DESC, evidence_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> PersistedResearchRetrievalRecord:
        return PersistedResearchRetrievalRecord(
            evidence=ResearchRetrievalEvidence.model_validate_json(str(row["evidence_json"])),
            evidence_sha256=str(row["evidence_sha256"]),
            stored_at=datetime.fromisoformat(str(row["stored_at"])),
        )
