from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import AgentTruthRepository
from gateway.structured_json_projection import (
    StructuredJSONProjectionEvidence,
)

PROJECTION_EVIDENCE_TABLE = "structured_json_projection_evidence"

MAX_RECENT_PROJECTION_RECORDS = 100


class StructuredJSONProjectionPersistenceConflict(RuntimeError):
    """
    Raised when a projection evidence ID is reused
    with different immutable evidence content.
    """


class StructuredJSONProjectionParentBindingError(ValueError):
    """
    Raised when projection evidence does not bind to
    its persisted Phase16 Research retrieval evidence.
    """


class PersistedStructuredJSONProjectionRecord(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )

    evidence: StructuredJSONProjectionEvidence

    evidence_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
    )

    stored_at: datetime

    evidence_persisted: Literal[True] = True

    task_ledger_mutated: Literal[False] = False

    knowledge_mutated: Literal[False] = False

    career_truth_mutated: Literal[False] = False


class StructuredJSONProjectionRepository:
    """
    Dedicated persistence for complete-body structured
    JSON projection evidence.

    The repository owns no network, browser, credential,
    Career-truth, scoring, shortlist, or application
    authority.

    A projection may be persisted only when its immutable
    source binding matches an existing successful Phase16
    Research retrieval evidence row.
    """

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
                CREATE TABLE IF NOT EXISTS
                structured_json_projection_evidence (
                    projection_evidence_id TEXT PRIMARY KEY,
                    evidence_sha256 TEXT NOT NULL,

                    research_evidence_id TEXT NOT NULL,

                    projector_id TEXT NOT NULL,
                    projection_profile_id TEXT NOT NULL,
                    projection_profile_version TEXT NOT NULL,

                    source_url TEXT NOT NULL,
                    source_body_sha256 TEXT NOT NULL,
                    source_byte_count INTEGER NOT NULL,
                    source_content_type TEXT NOT NULL,

                    complete_document_parse INTEGER NOT NULL,
                    source_root_kind TEXT NOT NULL,
                    source_record_count INTEGER NOT NULL,
                    projected_record_count INTEGER NOT NULL,

                    projection_sha256 TEXT NOT NULL,
                    projection_char_count INTEGER NOT NULL,
                    projection_truncated INTEGER NOT NULL,

                    evidence_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_structured_json_projection_research
                ON structured_json_projection_evidence(
                    research_evidence_id,
                    stored_at ASC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_structured_json_projection_profile
                ON structured_json_projection_evidence(
                    projection_profile_id,
                    stored_at ASC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_structured_json_projection_source_body
                ON structured_json_projection_evidence(
                    source_body_sha256,
                    stored_at ASC
                )
                """
            )

            connection.commit()

    def persist(
        self,
        evidence: StructuredJSONProjectionEvidence,
    ) -> PersistedStructuredJSONProjectionRecord:
        validated = StructuredJSONProjectionEvidence.model_validate(
            evidence.model_dump()
        )

        evidence_json = self._canonical_evidence_json(validated)

        evidence_sha256 = self._sha256_text(evidence_json)

        stored_at = datetime.now(timezone.utc)

        with self.truth_repository.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                self._validate_parent_binding(
                    connection=connection,
                    evidence=validated,
                )

                existing = connection.execute(
                    """
                    SELECT
                        evidence_sha256,
                        evidence_json,
                        stored_at
                    FROM structured_json_projection_evidence
                    WHERE projection_evidence_id = ?
                    """,
                    (validated.projection_evidence_id,),
                ).fetchone()

                if existing is not None:
                    existing_sha = str(existing["evidence_sha256"])

                    existing_json = str(existing["evidence_json"])

                    if (
                        existing_sha != evidence_sha256
                        or existing_json != evidence_json
                    ):
                        connection.rollback()

                        raise (
                            StructuredJSONProjectionPersistenceConflict(
                                "Structured JSON projection "
                                "evidence ID is already bound "
                                "to different immutable content."
                            )
                        )

                    connection.commit()

                    return PersistedStructuredJSONProjectionRecord(
                        evidence=(
                            StructuredJSONProjectionEvidence.model_validate_json(
                                existing_json
                            )
                        ),
                        evidence_sha256=(existing_sha),
                        stored_at=(datetime.fromisoformat(str(existing["stored_at"]))),
                    )

                connection.execute(
                    """
                    INSERT INTO
                    structured_json_projection_evidence (
                        projection_evidence_id,
                        evidence_sha256,
                        research_evidence_id,
                        projector_id,
                        projection_profile_id,
                        projection_profile_version,
                        source_url,
                        source_body_sha256,
                        source_byte_count,
                        source_content_type,
                        complete_document_parse,
                        source_root_kind,
                        source_record_count,
                        projected_record_count,
                        projection_sha256,
                        projection_char_count,
                        projection_truncated,
                        evidence_json,
                        stored_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        validated.projection_evidence_id,
                        evidence_sha256,
                        validated.research_evidence_id,
                        validated.projector_id,
                        validated.projection_profile_id,
                        validated.projection_profile_version,
                        validated.source_url,
                        validated.source_body_sha256,
                        validated.source_byte_count,
                        validated.source_content_type,
                        int(validated.complete_document_parse),
                        validated.source_root_kind,
                        validated.source_record_count,
                        validated.projected_record_count,
                        validated.projection_sha256,
                        validated.projection_char_count,
                        int(validated.projection_truncated),
                        evidence_json,
                        stored_at.isoformat(),
                    ),
                )

                connection.commit()

            except Exception:
                if connection.in_transaction:
                    connection.rollback()

                raise

        return PersistedStructuredJSONProjectionRecord(
            evidence=validated,
            evidence_sha256=evidence_sha256,
            stored_at=stored_at,
        )

    def get(
        self,
        projection_evidence_id: str,
    ) -> PersistedStructuredJSONProjectionRecord | None:
        with self.truth_repository.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    evidence_sha256,
                    evidence_json,
                    stored_at
                FROM structured_json_projection_evidence
                WHERE projection_evidence_id = ?
                """,
                (projection_evidence_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def list_for_research_evidence(
        self,
        research_evidence_id: str,
    ) -> list[PersistedStructuredJSONProjectionRecord]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    evidence_sha256,
                    evidence_json,
                    stored_at
                FROM structured_json_projection_evidence
                WHERE research_evidence_id = ?
                ORDER BY
                    stored_at ASC,
                    projection_evidence_id ASC
                """,
                (research_evidence_id,),
            ).fetchall()

        return [self._row_to_record(row) for row in rows]

    def list_for_profile(
        self,
        projection_profile_id: str,
    ) -> list[PersistedStructuredJSONProjectionRecord]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    evidence_sha256,
                    evidence_json,
                    stored_at
                FROM structured_json_projection_evidence
                WHERE projection_profile_id = ?
                ORDER BY
                    stored_at ASC,
                    projection_evidence_id ASC
                """,
                (projection_profile_id,),
            ).fetchall()

        return [self._row_to_record(row) for row in rows]

    def list_recent(
        self,
        *,
        limit: int = 50,
    ) -> list[PersistedStructuredJSONProjectionRecord]:
        if not (1 <= limit <= MAX_RECENT_PROJECTION_RECORDS):
            raise ValueError(
                "Projection evidence limit must be "
                "between 1 and "
                f"{MAX_RECENT_PROJECTION_RECORDS}."
            )

        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    evidence_sha256,
                    evidence_json,
                    stored_at
                FROM structured_json_projection_evidence
                ORDER BY
                    stored_at DESC,
                    projection_evidence_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _canonical_evidence_json(
        evidence: StructuredJSONProjectionEvidence,
    ) -> str:
        return json.dumps(
            evidence.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @staticmethod
    def _sha256_text(
        value: str,
    ) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def _validate_parent_binding(
        cls,
        *,
        connection: sqlite3.Connection,
        evidence: StructuredJSONProjectionEvidence,
    ) -> None:
        try:
            row = connection.execute(
                """
                SELECT evidence_json
                FROM research_retrieval_evidence
                WHERE evidence_id = ?
                """,
                (evidence.research_evidence_id,),
            ).fetchone()

        except sqlite3.OperationalError as exc:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Phase16 research retrieval evidence table is unavailable."
                )
            ) from exc

        if row is None:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Structured projection requires "
                    "existing Phase16 Research "
                    "retrieval evidence."
                )
            )

        try:
            parent = json.loads(str(row["evidence_json"]))

        except (
            json.JSONDecodeError,
            TypeError,
        ) as exc:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Parent Research retrieval evidence JSON is invalid."
                )
            ) from exc

        if not isinstance(
            parent,
            dict,
        ):
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Parent Research retrieval evidence must be an object."
                )
            )

        cls._require_parent_field(
            parent,
            "evidence_id",
        )

        if str(parent["evidence_id"]) != evidence.research_evidence_id:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Parent Research evidence ID does not match projection binding."
                )
            )

        if parent.get("outcome") != "succeeded":
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Structured projection parent "
                    "Research retrieval must have "
                    "succeeded."
                )
            )

        if parent.get("stage") != "completed":
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Structured projection parent Research retrieval must be completed."
                )
            )

        cls._require_parent_field(
            parent,
            "source_body_sha256",
        )

        if str(parent["source_body_sha256"]) != evidence.source_body_sha256:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Projection source body SHA-256 "
                    "does not match parent Research "
                    "retrieval evidence."
                )
            )

        cls._require_parent_field(
            parent,
            "byte_count",
        )

        try:
            parent_byte_count = int(parent["byte_count"])

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Parent Research byte count is invalid."
                )
            ) from exc

        if parent_byte_count != evidence.source_byte_count:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Projection source byte count "
                    "does not match parent Research "
                    "retrieval evidence."
                )
            )

        cls._require_parent_field(
            parent,
            "content_type",
        )

        if str(parent["content_type"]) != evidence.source_content_type:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Projection source content type "
                    "does not match parent Research "
                    "retrieval evidence."
                )
            )

        final_url = parent.get("final_url")

        requested_url = parent.get("requested_url")

        parent_source_url = (
            final_url
            if isinstance(
                final_url,
                str,
            )
            and final_url
            else requested_url
        )

        if (
            not isinstance(
                parent_source_url,
                str,
            )
            or parent_source_url != evidence.source_url
        ):
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Projection source URL does not "
                    "match parent Research retrieval "
                    "evidence."
                )
            )

        cls._require_parent_field(
            parent,
            "observed_at",
        )

        parent_observed_at = cls._parse_parent_datetime(parent["observed_at"])

        if parent_observed_at != evidence.observed_at:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Projection observed_at does not "
                    "match parent Research retrieval "
                    "evidence."
                )
            )

    @staticmethod
    def _require_parent_field(
        parent: dict[str, Any],
        field: str,
    ) -> None:
        if parent.get(field) is None:
            raise (
                StructuredJSONProjectionParentBindingError(
                    f"Parent Research retrieval evidence is missing {field}."
                )
            )

    @staticmethod
    def _parse_parent_datetime(
        value: Any,
    ) -> datetime:
        if not isinstance(
            value,
            str,
        ):
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Parent Research observed_at must be a timestamp string."
                )
            )

        try:
            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError as exc:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Parent Research observed_at is invalid."
                )
            ) from exc

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise (
                StructuredJSONProjectionParentBindingError(
                    "Parent Research observed_at must be timezone-aware."
                )
            )

        return parsed

    @staticmethod
    def _row_to_record(
        row: sqlite3.Row,
    ) -> PersistedStructuredJSONProjectionRecord:
        evidence_json = str(row["evidence_json"])

        evidence_sha256 = str(row["evidence_sha256"])

        actual_sha256 = hashlib.sha256(evidence_json.encode("utf-8")).hexdigest()

        if actual_sha256 != evidence_sha256:
            raise (
                StructuredJSONProjectionPersistenceConflict(
                    "Persisted structured projection "
                    "evidence hash does not match "
                    "stored immutable JSON."
                )
            )

        return PersistedStructuredJSONProjectionRecord(
            evidence=(
                StructuredJSONProjectionEvidence.model_validate_json(evidence_json)
            ),
            evidence_sha256=(evidence_sha256),
            stored_at=datetime.fromisoformat(str(row["stored_at"])),
        )
