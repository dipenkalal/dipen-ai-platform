from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agents.truth_repository import AgentTruthRepository

ResearchOperationsOutcome = Literal[
    "succeeded",
    "failed",
    "cancelled",
    "healthy",
    "degraded",
]
ResearchOperationsEventType = Literal[
    "retrieval-source",
    "search-discovery",
    "provider-health",
    "reliability-benchmark",
]


class ResearchOperationsEvent(BaseModel):
    """Append-only operational metadata. Never contains retrieved source content."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(pattern=r"^research-ops-[0-9a-f]{24}$")
    event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_type: ResearchOperationsEventType
    provider_id: str
    outcome: ResearchOperationsOutcome
    request_id: str | None = None
    evidence_id: str | None = None
    source_family: str | None = None
    stage: str | None = None
    error_code: str | None = None
    duration_ms: float = Field(ge=0)
    attempt_count: int = Field(default=1, ge=1, le=2)
    transient_retry_count: int = Field(default=0, ge=0, le=1)
    recovered_after_retry: bool = False
    recorded_at: datetime
    contains_retrieved_source_content: Literal[False] = False
    contains_provider_snippets_or_titles: Literal[False] = False
    task_ledger_mutation_performed: Literal[False] = False
    automatic_knowledge_mutation_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False

    @field_validator("recorded_at")
    @classmethod
    def require_aware_recorded_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("research operations event timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> ResearchOperationsEvent:
        if self.transient_retry_count >= self.attempt_count:
            raise ValueError("retry count must be lower than attempt count")
        if self.recovered_after_retry and (
            self.outcome != "succeeded" or self.transient_retry_count < 1
        ):
            raise ValueError("recovered-after-retry requires a successful retried event")
        if self.canonical_hash() != self.event_sha256:
            raise ValueError("research operations event SHA-256 mismatch")
        if self.event_id != f"research-ops-{self.event_sha256[:24]}":
            raise ValueError("research operations event ID mismatch")
        return self

    def canonical_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"event_id", "event_sha256"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def build(
        cls,
        *,
        event_type: ResearchOperationsEventType,
        provider_id: str,
        outcome: ResearchOperationsOutcome,
        duration_ms: float,
        recorded_at: datetime,
        request_id: str | None = None,
        evidence_id: str | None = None,
        source_family: str | None = None,
        stage: str | None = None,
        error_code: str | None = None,
        attempt_count: int = 1,
        transient_retry_count: int = 0,
        recovered_after_retry: bool = False,
    ) -> ResearchOperationsEvent:
        payload = {
            "event_type": event_type,
            "provider_id": provider_id,
            "outcome": outcome,
            "request_id": request_id,
            "evidence_id": evidence_id,
            "source_family": source_family,
            "stage": stage,
            "error_code": error_code,
            "duration_ms": round(float(duration_ms), 3),
            "attempt_count": attempt_count,
            "transient_retry_count": transient_retry_count,
            "recovered_after_retry": recovered_after_retry,
            "recorded_at": recorded_at.isoformat(),
            "contains_retrieved_source_content": False,
            "contains_provider_snippets_or_titles": False,
            "task_ledger_mutation_performed": False,
            "automatic_knowledge_mutation_performed": False,
            "guardian_contacted": False,
            "privileged_host_action_performed": False,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        event_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls.model_validate(
            {
                "event_id": f"research-ops-{event_sha256[:24]}",
                "event_sha256": event_sha256,
                **payload,
            }
        )


class ResearchOperationsRepository:
    """Append-only telemetry beside DAP truth; never mutates retrieval evidence."""

    def __init__(
        self,
        truth_repository: AgentTruthRepository,
        *,
        initialize: bool = True,
    ) -> None:
        self.truth_repository = truth_repository
        if initialize:
            self.initialize()

    def initialize(self) -> None:
        with self.truth_repository.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_operations_events (
                    event_id TEXT PRIMARY KEY,
                    event_sha256 TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    request_id TEXT,
                    evidence_id TEXT,
                    source_family TEXT,
                    stage TEXT,
                    error_code TEXT,
                    duration_ms REAL NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    transient_retry_count INTEGER NOT NULL,
                    recovered_after_retry INTEGER NOT NULL,
                    event_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_ops_recorded
                ON research_operations_events(recorded_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_ops_type_outcome
                ON research_operations_events(event_type, outcome, recorded_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_ops_request
                ON research_operations_events(request_id, recorded_at DESC)
                """
            )
            connection.commit()

    def persist(self, event: ResearchOperationsEvent) -> ResearchOperationsEvent:
        if event.canonical_hash() != event.event_sha256:
            raise ValueError("research operations event hash mismatch")
        with self.truth_repository.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT event_sha256, event_json
                FROM research_operations_events
                WHERE event_id = ?
                """,
                (event.event_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["event_sha256"]) != event.event_sha256:
                    connection.rollback()
                    raise RuntimeError(
                        "research operations event ID is bound to different content"
                    )
                connection.commit()
                return ResearchOperationsEvent.model_validate_json(
                    str(existing["event_json"])
                )

            connection.execute(
                """
                INSERT INTO research_operations_events (
                    event_id,
                    event_sha256,
                    event_type,
                    provider_id,
                    outcome,
                    request_id,
                    evidence_id,
                    source_family,
                    stage,
                    error_code,
                    duration_ms,
                    attempt_count,
                    transient_retry_count,
                    recovered_after_retry,
                    event_json,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_sha256,
                    event.event_type,
                    event.provider_id,
                    event.outcome,
                    event.request_id,
                    event.evidence_id,
                    event.source_family,
                    event.stage,
                    event.error_code,
                    event.duration_ms,
                    event.attempt_count,
                    event.transient_retry_count,
                    int(event.recovered_after_retry),
                    event.model_dump_json(),
                    event.recorded_at.isoformat(),
                ),
            )
            connection.commit()
        return event

    def list_recent(self, *, limit: int = 500) -> list[ResearchOperationsEvent]:
        if limit < 1 or limit > 2000:
            raise ValueError("research operations event limit must be between 1 and 2000")
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT event_json
                FROM research_operations_events
                ORDER BY recorded_at DESC, event_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ResearchOperationsEvent.model_validate_json(str(row["event_json"]))
            for row in rows
        ]

    @staticmethod
    def missing_table(error: sqlite3.OperationalError) -> bool:
        return "no such table: research_operations_events" in str(error).lower()
