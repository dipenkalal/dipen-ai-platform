from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

from career.schemas import (
    CareerApplication,
    CareerApplicationEvent,
    CareerFitAssessment,
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerSource,
)


class CareerPersistenceConflict(RuntimeError):
    """Raised when immutable Career truth conflicts."""


class TruthRepositoryProtocol(Protocol):
    def connection(
        self,
    ) -> Iterator[sqlite3.Connection]:
        ...


class CareerRepository:
    """DAP-native Career persistence over the existing truth DB."""

    def __init__(
        self,
        truth_repository: TruthRepositoryProtocol,
        *,
        initialize: bool = True,
    ) -> None:
        self.truth_repository = truth_repository

        if initialize:
            self.initialize()

    @contextmanager
    def _connection(self):
        with self.truth_repository.connection() as connection:
            connection.execute(
                "PRAGMA foreign_keys = ON"
            )
            yield connection

    def initialize(self) -> None:
        with self._connection() as connection:
            evidence_table = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'research_retrieval_evidence'
                """
            ).fetchone()

            if evidence_table is None:
                raise RuntimeError(
                    "Career persistence requires the "
                    "Phase-16 research_retrieval_evidence "
                    "table."
                )

            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS career_sources (
                    source_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    employer_name TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    connector_kind TEXT NOT NULL,
                    trust_tier INTEGER NOT NULL
                        CHECK (trust_tier BETWEEN 0 AND 3),
                    canonical_base_url TEXT NOT NULL,
                    state TEXT NOT NULL,
                    last_verified_at TEXT,
                    last_error_code TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS
                career_job_postings (
                    job_id TEXT PRIMARY KEY,
                    employer_name TEXT NOT NULL,
                    requisition_id TEXT,
                    canonical_job_url TEXT NOT NULL,
                    canonical_apply_url TEXT,
                    current_snapshot_id TEXT,
                    verification_state TEXT NOT NULL,
                    lifecycle_state TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (current_snapshot_id)
                        REFERENCES career_job_snapshots(
                            snapshot_id
                        )
                        DEFERRABLE INITIALLY DEFERRED
                );

                CREATE TABLE IF NOT EXISTS
                career_job_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    employer_name TEXT NOT NULL,
                    location_text TEXT,
                    work_mode TEXT,
                    employment_type TEXT,
                    description_text TEXT NOT NULL,
                    description_sha256 TEXT NOT NULL,
                    posted_at TEXT,
                    closing_at TEXT,
                    freshness_state TEXT NOT NULL,
                    salary_text TEXT,
                    requirements_json TEXT NOT NULL,
                    normalized_text_sha256 TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY (job_id)
                        REFERENCES career_job_postings(job_id),
                    FOREIGN KEY (source_id)
                        REFERENCES career_sources(source_id)
                );

                CREATE TABLE IF NOT EXISTS
                career_job_evidence_links (
                    link_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    research_evidence_id TEXT NOT NULL,
                    evidence_role TEXT NOT NULL,
                    linked_at TEXT NOT NULL,
                    FOREIGN KEY (job_id)
                        REFERENCES career_job_postings(job_id),
                    FOREIGN KEY (snapshot_id)
                        REFERENCES career_job_snapshots(
                            snapshot_id
                        ),
                    FOREIGN KEY (research_evidence_id)
                        REFERENCES research_retrieval_evidence(
                            evidence_id
                        )
                );

                CREATE TABLE IF NOT EXISTS
                career_fit_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    profile_version TEXT NOT NULL,
                    scorer_version TEXT NOT NULL,
                    fit_score REAL NOT NULL
                        CHECK (
                            fit_score >= 0
                            AND fit_score <= 100
                        ),
                    verdict TEXT NOT NULL,
                    hard_exclusion_codes_json TEXT NOT NULL,
                    score_breakdown_json TEXT NOT NULL,
                    explanation_json TEXT NOT NULL,
                    assessed_at TEXT NOT NULL,
                    FOREIGN KEY (job_id)
                        REFERENCES career_job_postings(job_id),
                    FOREIGN KEY (snapshot_id)
                        REFERENCES career_job_snapshots(
                            snapshot_id
                        ),
                    UNIQUE (
                        snapshot_id,
                        profile_version,
                        scorer_version
                    )
                );

                CREATE TABLE IF NOT EXISTS
                career_applications (
                    application_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    owner_approved_at TEXT,
                    applied_confirmed_at TEXT,
                    applied_confirmation_kind TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (job_id)
                        REFERENCES career_job_postings(job_id)
                );

                CREATE TABLE IF NOT EXISTS
                career_application_events (
                    event_id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    actor_kind TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_id TEXT,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY (application_id)
                        REFERENCES career_applications(
                            application_id
                        )
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_sources_state_tier
                ON career_sources(state, trust_tier);

                CREATE INDEX IF NOT EXISTS
                idx_career_sources_employer
                ON career_sources(employer_name);

                CREATE INDEX IF NOT EXISTS
                idx_career_jobs_state_seen
                ON career_job_postings(
                    verification_state,
                    lifecycle_state,
                    last_seen_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_jobs_employer_req
                ON career_job_postings(
                    employer_name,
                    requisition_id
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_jobs_url
                ON career_job_postings(
                    canonical_job_url
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_snapshots_job
                ON career_job_snapshots(
                    job_id,
                    observed_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_snapshots_freshness
                ON career_job_snapshots(
                    freshness_state,
                    posted_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_snapshots_hash
                ON career_job_snapshots(
                    normalized_text_sha256
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_evidence_snapshot
                ON career_job_evidence_links(
                    snapshot_id
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_evidence_research
                ON career_job_evidence_links(
                    research_evidence_id
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_fit_verdict
                ON career_fit_assessments(
                    verdict,
                    assessed_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_applications_state
                ON career_applications(
                    state,
                    updated_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_career_applications_job
                ON career_applications(job_id);

                CREATE INDEX IF NOT EXISTS
                idx_career_application_events
                ON career_application_events(
                    application_id,
                    occurred_at ASC
                );
                """
            )
            connection.commit()

    def upsert_source(
        self,
        source: CareerSource,
    ) -> CareerSource:
        existing = self.get_source(source.source_id)

        if (
            existing is not None
            and existing.created_at != source.created_at
        ):
            raise CareerPersistenceConflict(
                "Career source created_at is immutable."
            )

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO career_sources (
                    source_id,
                    display_name,
                    employer_name,
                    source_kind,
                    connector_kind,
                    trust_tier,
                    canonical_base_url,
                    state,
                    last_verified_at,
                    last_error_code,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    employer_name = excluded.employer_name,
                    source_kind = excluded.source_kind,
                    connector_kind = excluded.connector_kind,
                    trust_tier = excluded.trust_tier,
                    canonical_base_url =
                        excluded.canonical_base_url,
                    state = excluded.state,
                    last_verified_at =
                        excluded.last_verified_at,
                    last_error_code =
                        excluded.last_error_code,
                    updated_at = excluded.updated_at
                """,
                (
                    source.source_id,
                    source.display_name,
                    source.employer_name,
                    source.source_kind,
                    source.connector_kind,
                    source.trust_tier,
                    source.canonical_base_url,
                    source.state,
                    (
                        source.last_verified_at.isoformat()
                        if source.last_verified_at
                        else None
                    ),
                    source.last_error_code,
                    source.created_at.isoformat(),
                    source.updated_at.isoformat(),
                ),
            )
            connection.commit()

        stored = self.get_source(source.source_id)

        if stored is None:
            raise RuntimeError(
                "Career source could not be read "
                "after save."
            )

        return stored

    def get_source(
        self,
        source_id: str,
    ) -> CareerSource | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM career_sources
                WHERE source_id = ?
                """,
                (source_id,),
            ).fetchone()

        if row is None:
            return None

        return CareerSource.model_validate(dict(row))

    def upsert_job(
        self,
        job: CareerJobPosting,
    ) -> CareerJobPosting:
        existing = self.get_job(job.job_id)

        if existing is not None:
            if (
                existing.created_at != job.created_at
                or existing.first_seen_at
                != job.first_seen_at
            ):
                raise CareerPersistenceConflict(
                    "Career job creation identity "
                    "fields are immutable."
                )

        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO career_job_postings (
                        job_id,
                        employer_name,
                        requisition_id,
                        canonical_job_url,
                        canonical_apply_url,
                        current_snapshot_id,
                        verification_state,
                        lifecycle_state,
                        first_seen_at,
                        last_seen_at,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    ON CONFLICT(job_id) DO UPDATE SET
                        employer_name =
                            excluded.employer_name,
                        requisition_id =
                            excluded.requisition_id,
                        canonical_job_url =
                            excluded.canonical_job_url,
                        canonical_apply_url =
                            excluded.canonical_apply_url,
                        current_snapshot_id =
                            excluded.current_snapshot_id,
                        verification_state =
                            excluded.verification_state,
                        lifecycle_state =
                            excluded.lifecycle_state,
                        last_seen_at =
                            excluded.last_seen_at,
                        updated_at =
                            excluded.updated_at
                    """,
                    (
                        job.job_id,
                        job.employer_name,
                        job.requisition_id,
                        job.canonical_job_url,
                        job.canonical_apply_url,
                        job.current_snapshot_id,
                        job.verification_state,
                        job.lifecycle_state,
                        job.first_seen_at.isoformat(),
                        job.last_seen_at.isoformat(),
                        job.created_at.isoformat(),
                        job.updated_at.isoformat(),
                    ),
                )
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise CareerPersistenceConflict(
                "Career job violates persistence "
                f"integrity: {error}"
            ) from error

        stored = self.get_job(job.job_id)

        if stored is None:
            raise RuntimeError(
                "Career job could not be read after save."
            )

        return stored

    def get_job(
        self,
        job_id: str,
    ) -> CareerJobPosting | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM career_job_postings
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return CareerJobPosting.model_validate(
            dict(row)
        )

    def persist_snapshot(
        self,
        snapshot: CareerJobSnapshot,
    ) -> CareerJobSnapshot:
        existing = self.get_snapshot(
            snapshot.snapshot_id
        )

        if existing is not None:
            if existing != snapshot:
                raise CareerPersistenceConflict(
                    "Career snapshot ID is already "
                    "bound to different content."
                )

            return existing

        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO career_job_snapshots (
                        snapshot_id,
                        job_id,
                        source_id,
                        title,
                        employer_name,
                        location_text,
                        work_mode,
                        employment_type,
                        description_text,
                        description_sha256,
                        posted_at,
                        closing_at,
                        freshness_state,
                        salary_text,
                        requirements_json,
                        normalized_text_sha256,
                        observed_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        snapshot.snapshot_id,
                        snapshot.job_id,
                        snapshot.source_id,
                        snapshot.title,
                        snapshot.employer_name,
                        snapshot.location_text,
                        snapshot.work_mode,
                        snapshot.employment_type,
                        snapshot.description_text,
                        snapshot.description_sha256,
                        (
                            snapshot.posted_at.isoformat()
                            if snapshot.posted_at
                            else None
                        ),
                        (
                            snapshot.closing_at.isoformat()
                            if snapshot.closing_at
                            else None
                        ),
                        snapshot.freshness_state,
                        snapshot.salary_text,
                        json.dumps(
                            snapshot.requirements,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                            default=str,
                        ),
                        snapshot.normalized_text_sha256,
                        snapshot.observed_at.isoformat(),
                    ),
                )
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise CareerPersistenceConflict(
                "Career snapshot violates persistence "
                f"integrity: {error}"
            ) from error

        stored = self.get_snapshot(
            snapshot.snapshot_id
        )

        if stored is None:
            raise RuntimeError(
                "Career snapshot could not be read "
                "after save."
            )

        return stored

    def get_snapshot(
        self,
        snapshot_id: str,
    ) -> CareerJobSnapshot | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM career_job_snapshots
                WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchone()

        if row is None:
            return None

        payload = dict(row)
        payload["requirements"] = json.loads(
            payload.pop("requirements_json")
        )

        return CareerJobSnapshot.model_validate(
            payload
        )

    def persist_evidence_link(
        self,
        link: CareerJobEvidenceLink,
    ) -> CareerJobEvidenceLink:
        existing = self.get_evidence_link(
            link.link_id
        )

        if existing is not None:
            if existing != link:
                raise CareerPersistenceConflict(
                    "Career evidence-link ID is "
                    "already bound to different content."
                )

            return existing

        with self._connection() as connection:
            snapshot_row = connection.execute(
                """
                SELECT job_id
                FROM career_job_snapshots
                WHERE snapshot_id = ?
                """,
                (link.snapshot_id,),
            ).fetchone()

            if snapshot_row is None:
                raise ValueError(
                    "Career evidence link references "
                    "an unknown snapshot."
                )

            if str(snapshot_row["job_id"]) != link.job_id:
                raise ValueError(
                    "Career evidence link job does not "
                    "match snapshot job."
                )

            evidence_row = connection.execute(
                """
                SELECT outcome
                FROM research_retrieval_evidence
                WHERE evidence_id = ?
                """,
                (link.research_evidence_id,),
            ).fetchone()

            if evidence_row is None:
                raise ValueError(
                    "Career evidence link requires "
                    "existing retrieval evidence."
                )

            if str(evidence_row["outcome"]) != "succeeded":
                raise ValueError(
                    "Career evidence link requires "
                    "successful retrieval evidence."
                )

            try:
                connection.execute(
                    """
                    INSERT INTO
                    career_job_evidence_links (
                        link_id,
                        job_id,
                        snapshot_id,
                        research_evidence_id,
                        evidence_role,
                        linked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        link.link_id,
                        link.job_id,
                        link.snapshot_id,
                        link.research_evidence_id,
                        link.evidence_role,
                        link.linked_at.isoformat(),
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                raise CareerPersistenceConflict(
                    "Career evidence link violates "
                    f"persistence integrity: {error}"
                ) from error

        stored = self.get_evidence_link(link.link_id)

        if stored is None:
            raise RuntimeError(
                "Career evidence link could not be "
                "read after save."
            )

        return stored

    def get_evidence_link(
        self,
        link_id: str,
    ) -> CareerJobEvidenceLink | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM career_job_evidence_links
                WHERE link_id = ?
                """,
                (link_id,),
            ).fetchone()

        if row is None:
            return None

        return CareerJobEvidenceLink.model_validate(
            dict(row)
        )

    def persist_fit_assessment(
        self,
        assessment: CareerFitAssessment,
    ) -> CareerFitAssessment:
        existing = self.get_fit_assessment(
            assessment.assessment_id
        )

        if existing is not None:
            if existing != assessment:
                raise CareerPersistenceConflict(
                    "Career assessment ID is already "
                    "bound to different content."
                )

            return existing

        with self._connection() as connection:
            snapshot_row = connection.execute(
                """
                SELECT job_id
                FROM career_job_snapshots
                WHERE snapshot_id = ?
                """,
                (assessment.snapshot_id,),
            ).fetchone()

            if snapshot_row is None:
                raise ValueError(
                    "Career assessment references "
                    "an unknown snapshot."
                )

            if (
                str(snapshot_row["job_id"])
                != assessment.job_id
            ):
                raise ValueError(
                    "Career assessment job does not "
                    "match snapshot job."
                )

            try:
                connection.execute(
                    """
                    INSERT INTO career_fit_assessments (
                        assessment_id,
                        job_id,
                        snapshot_id,
                        profile_version,
                        scorer_version,
                        fit_score,
                        verdict,
                        hard_exclusion_codes_json,
                        score_breakdown_json,
                        explanation_json,
                        assessed_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        assessment.assessment_id,
                        assessment.job_id,
                        assessment.snapshot_id,
                        assessment.profile_version,
                        assessment.scorer_version,
                        assessment.fit_score,
                        assessment.verdict,
                        json.dumps(
                            assessment.hard_exclusion_codes,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        json.dumps(
                            assessment.score_breakdown,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                            default=str,
                        ),
                        json.dumps(
                            assessment.explanation,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                            default=str,
                        ),
                        assessment.assessed_at.isoformat(),
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                current = (
                    self.get_fit_assessment_for_version(
                        snapshot_id=(
                            assessment.snapshot_id
                        ),
                        profile_version=(
                            assessment.profile_version
                        ),
                        scorer_version=(
                            assessment.scorer_version
                        ),
                    )
                )

                if current == assessment:
                    return assessment

                raise CareerPersistenceConflict(
                    "A different assessment already "
                    "exists for this snapshot/profile/"
                    f"scorer version: {error}"
                ) from error

        stored = self.get_fit_assessment(
            assessment.assessment_id
        )

        if stored is None:
            raise RuntimeError(
                "Career assessment could not be "
                "read after save."
            )

        return stored

    def get_fit_assessment(
        self,
        assessment_id: str,
    ) -> CareerFitAssessment | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM career_fit_assessments
                WHERE assessment_id = ?
                """,
                (assessment_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_assessment(row)

    def get_fit_assessment_for_version(
        self,
        *,
        snapshot_id: str,
        profile_version: str,
        scorer_version: str,
    ) -> CareerFitAssessment | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM career_fit_assessments
                WHERE snapshot_id = ?
                  AND profile_version = ?
                  AND scorer_version = ?
                """,
                (
                    snapshot_id,
                    profile_version,
                    scorer_version,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_assessment(row)

    @staticmethod
    def _row_to_assessment(
        row: sqlite3.Row,
    ) -> CareerFitAssessment:
        payload = dict(row)
        payload["hard_exclusion_codes"] = (
            json.loads(
                payload.pop(
                    "hard_exclusion_codes_json"
                )
            )
        )
        payload["score_breakdown"] = json.loads(
            payload.pop("score_breakdown_json")
        )
        payload["explanation"] = json.loads(
            payload.pop("explanation_json")
        )

        return CareerFitAssessment.model_validate(
            payload
        )

    def upsert_application(
        self,
        application: CareerApplication,
    ) -> CareerApplication:
        existing = self.get_application(
            application.application_id
        )

        if existing is not None:
            if (
                existing.job_id != application.job_id
                or existing.created_at
                != application.created_at
            ):
                raise CareerPersistenceConflict(
                    "Career application identity fields "
                    "are immutable."
                )

        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO career_applications (
                        application_id,
                        job_id,
                        state,
                        owner_approved_at,
                        applied_confirmed_at,
                        applied_confirmation_kind,
                        notes,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(application_id)
                    DO UPDATE SET
                        state = excluded.state,
                        owner_approved_at =
                            excluded.owner_approved_at,
                        applied_confirmed_at =
                            excluded.applied_confirmed_at,
                        applied_confirmation_kind =
                            excluded.applied_confirmation_kind,
                        notes = excluded.notes,
                        updated_at = excluded.updated_at
                    """,
                    (
                        application.application_id,
                        application.job_id,
                        application.state,
                        (
                            application.owner_approved_at
                            .isoformat()
                            if application.owner_approved_at
                            else None
                        ),
                        (
                            application.applied_confirmed_at
                            .isoformat()
                            if application.applied_confirmed_at
                            else None
                        ),
                        (
                            application
                            .applied_confirmation_kind
                        ),
                        application.notes,
                        application.created_at.isoformat(),
                        application.updated_at.isoformat(),
                    ),
                )
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise CareerPersistenceConflict(
                "Career application violates "
                f"persistence integrity: {error}"
            ) from error

        stored = self.get_application(
            application.application_id
        )

        if stored is None:
            raise RuntimeError(
                "Career application could not be "
                "read after save."
            )

        return stored

    def get_application(
        self,
        application_id: str,
    ) -> CareerApplication | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM career_applications
                WHERE application_id = ?
                """,
                (application_id,),
            ).fetchone()

        if row is None:
            return None

        return CareerApplication.model_validate(
            dict(row)
        )

    def persist_application_event(
        self,
        event: CareerApplicationEvent,
    ) -> CareerApplicationEvent:
        existing = self.get_application_event(
            event.event_id
        )

        if existing is not None:
            if existing != event:
                raise CareerPersistenceConflict(
                    "Career application-event ID is "
                    "already bound to different content."
                )

            return existing

        if (
            self.get_application(
                event.application_id
            )
            is None
        ):
            raise ValueError(
                "Career application event references "
                "an unknown application."
            )

        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO
                    career_application_events (
                        event_id,
                        application_id,
                        from_state,
                        to_state,
                        actor_kind,
                        actor_id,
                        reason,
                        evidence_id,
                        occurred_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.application_id,
                        event.from_state,
                        event.to_state,
                        event.actor_kind,
                        event.actor_id,
                        event.reason,
                        event.evidence_id,
                        event.occurred_at.isoformat(),
                    ),
                )
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise CareerPersistenceConflict(
                "Career application event violates "
                f"persistence integrity: {error}"
            ) from error

        stored = self.get_application_event(
            event.event_id
        )

        if stored is None:
            raise RuntimeError(
                "Career application event could not "
                "be read after save."
            )

        return stored

    def get_application_event(
        self,
        event_id: str,
    ) -> CareerApplicationEvent | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM career_application_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

        if row is None:
            return None

        return CareerApplicationEvent.model_validate(
            dict(row)
        )


    def get_research_evidence_projection(
        self,
        evidence_id: str,
    ) -> dict[str, str | None] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    outcome,
                    evidence_json
                FROM research_retrieval_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if row is None:
            return None

        try:
            payload = json.loads(
                str(row["evidence_json"])
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "Research retrieval evidence contains "
                "invalid persisted JSON."
            ) from error

        normalized_hash = payload.get(
            "normalized_text_sha256"
        )
        final_url = payload.get("final_url")

        return {
            "outcome": str(row["outcome"]),
            "normalized_text_sha256": (
                str(normalized_hash)
                if normalized_hash is not None
                else None
            ),
            "final_url": (
                str(final_url)
                if final_url is not None
                else None
            ),
        }

    def create_application_with_event(
        self,
        application: CareerApplication,
        event: CareerApplicationEvent,
    ) -> CareerApplication:
        if event.application_id != application.application_id:
            raise ValueError(
                "Initial application event identity "
                "does not match application."
            )

        if event.from_state is not None:
            raise ValueError(
                "Initial application event must have "
                "from_state=None."
            )

        if event.to_state != application.state:
            raise ValueError(
                "Initial application event state does "
                "not match application."
            )

        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")

                existing = connection.execute(
                    """
                    SELECT 1
                    FROM career_applications
                    WHERE application_id = ?
                    """,
                    (application.application_id,),
                ).fetchone()

                if existing is not None:
                    connection.rollback()
                    raise CareerPersistenceConflict(
                        "Career application already exists."
                    )

                connection.execute(
                    """
                    INSERT INTO career_applications (
                        application_id,
                        job_id,
                        state,
                        owner_approved_at,
                        applied_confirmed_at,
                        applied_confirmation_kind,
                        notes,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        application.application_id,
                        application.job_id,
                        application.state,
                        (
                            application.owner_approved_at
                            .isoformat()
                            if application.owner_approved_at
                            else None
                        ),
                        (
                            application.applied_confirmed_at
                            .isoformat()
                            if application.applied_confirmed_at
                            else None
                        ),
                        application.applied_confirmation_kind,
                        application.notes,
                        application.created_at.isoformat(),
                        application.updated_at.isoformat(),
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO career_application_events (
                        event_id,
                        application_id,
                        from_state,
                        to_state,
                        actor_kind,
                        actor_id,
                        reason,
                        evidence_id,
                        occurred_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.application_id,
                        event.from_state,
                        event.to_state,
                        event.actor_kind,
                        event.actor_id,
                        event.reason,
                        event.evidence_id,
                        event.occurred_at.isoformat(),
                    ),
                )

                connection.commit()
        except sqlite3.IntegrityError as error:
            raise CareerPersistenceConflict(
                "Atomic Career application creation "
                f"failed integrity checks: {error}"
            ) from error

        stored = self.get_application(
            application.application_id
        )

        if stored is None:
            raise RuntimeError(
                "Career application disappeared after "
                "atomic creation."
            )

        return stored

    def transition_application_atomic(
        self,
        *,
        expected: CareerApplication,
        updated: CareerApplication,
        event: CareerApplicationEvent,
    ) -> CareerApplication:
        if (
            expected.application_id
            != updated.application_id
        ):
            raise ValueError(
                "Application identity cannot change "
                "during transition."
            )

        if expected.job_id != updated.job_id:
            raise ValueError(
                "Application job identity cannot change."
            )

        if expected.created_at != updated.created_at:
            raise ValueError(
                "Application created_at is immutable."
            )

        if updated.updated_at < expected.updated_at:
            raise ValueError(
                "Application updated_at cannot move backward."
            )

        if event.application_id != expected.application_id:
            raise ValueError(
                "Transition event application identity "
                "does not match."
            )

        if event.from_state != expected.state:
            raise ValueError(
                "Transition event from_state does not "
                "match expected application state."
            )

        if event.to_state != updated.state:
            raise ValueError(
                "Transition event to_state does not "
                "match updated application state."
            )

        if event.occurred_at != updated.updated_at:
            raise ValueError(
                "Transition event timestamp must match "
                "application updated_at."
            )

        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    """
                    SELECT *
                    FROM career_applications
                    WHERE application_id = ?
                    """,
                    (expected.application_id,),
                ).fetchone()

                if row is None:
                    connection.rollback()
                    raise KeyError(
                        "Unknown Career application: "
                        f"{expected.application_id}"
                    )

                current = (
                    CareerApplication.model_validate(
                        dict(row)
                    )
                )

                if current != expected:
                    connection.rollback()
                    raise CareerPersistenceConflict(
                        "Career application transition "
                        "rejected because persisted state "
                        "changed."
                    )

                event_row = connection.execute(
                    """
                    SELECT 1
                    FROM career_application_events
                    WHERE event_id = ?
                    """,
                    (event.event_id,),
                ).fetchone()

                if event_row is not None:
                    connection.rollback()
                    raise CareerPersistenceConflict(
                        "Career application transition "
                        "event already exists."
                    )

                connection.execute(
                    """
                    UPDATE career_applications
                    SET
                        state = ?,
                        owner_approved_at = ?,
                        applied_confirmed_at = ?,
                        applied_confirmation_kind = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE application_id = ?
                    """,
                    (
                        updated.state,
                        (
                            updated.owner_approved_at
                            .isoformat()
                            if updated.owner_approved_at
                            else None
                        ),
                        (
                            updated.applied_confirmed_at
                            .isoformat()
                            if updated.applied_confirmed_at
                            else None
                        ),
                        updated.applied_confirmation_kind,
                        updated.notes,
                        updated.updated_at.isoformat(),
                        updated.application_id,
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO career_application_events (
                        event_id,
                        application_id,
                        from_state,
                        to_state,
                        actor_kind,
                        actor_id,
                        reason,
                        evidence_id,
                        occurred_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.application_id,
                        event.from_state,
                        event.to_state,
                        event.actor_kind,
                        event.actor_id,
                        event.reason,
                        event.evidence_id,
                        event.occurred_at.isoformat(),
                    ),
                )

                connection.commit()
        except sqlite3.IntegrityError as error:
            raise CareerPersistenceConflict(
                "Atomic Career application transition "
                f"failed integrity checks: {error}"
            ) from error

        stored = self.get_application(
            updated.application_id
        )

        if stored is None:
            raise RuntimeError(
                "Career application disappeared after "
                "atomic transition."
            )

        return stored

    def list_application_events(
        self,
        application_id: str,
    ) -> list[CareerApplicationEvent]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM career_application_events
                WHERE application_id = ?
                ORDER BY occurred_at ASC, event_id ASC
                """,
                (application_id,),
            ).fetchall()

        return [
            CareerApplicationEvent.model_validate(
                dict(row)
            )
            for row in rows
        ]
