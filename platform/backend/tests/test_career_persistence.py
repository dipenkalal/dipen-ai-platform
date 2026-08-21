from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.truth_repository import AgentTruthRepository
from career.repository import (
    CareerPersistenceConflict,
    CareerRepository,
)
from career.schemas import (
    CareerApplication,
    CareerApplicationEvent,
    CareerFitAssessment,
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerSource,
)
from gateway.research_retrieval_repository import (
    ResearchRetrievalRepository,
)


NOW = datetime(
    2026,
    8,
    20,
    18,
    0,
    tzinfo=timezone.utc,
)

SUCCESS_EVIDENCE_ID = (
    "research-retrieval-111111111111111111111111"
)

FAILED_EVIDENCE_ID = (
    "research-retrieval-222222222222222222222222"
)


class CareerPersistenceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )

        self.database_path = (
            Path(self.temporary_directory.name)
            / "agent-truth.db"
        )

        self.truth = AgentTruthRepository(
            self.database_path
        )

        ResearchRetrievalRepository(self.truth)

        with self.truth.connection() as connection:
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
                    SUCCESS_EVIDENCE_ID,
                    "1" * 64,
                    "career-test-success",
                    None,
                    "succeeded",
                    "completed",
                    "public-web-retrieval",
                    "https://jobs.example.test/acme/123",
                    "https://jobs.example.test/acme/123",
                    "research-citation-test",
                    "internet-content-test",
                    "{}",
                    NOW.isoformat(),
                ),
            )

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
                    FAILED_EVIDENCE_ID,
                    "2" * 64,
                    "career-test-failure",
                    None,
                    "failed",
                    "response",
                    "public-web-retrieval",
                    "https://jobs.example.test/acme/fail",
                    None,
                    None,
                    None,
                    "{}",
                    NOW.isoformat(),
                ),
            )

            connection.commit()

        self.repository = CareerRepository(
            self.truth
        )

        self.source = CareerSource(
            source_id="career-source-acme-greenhouse",
            display_name="Acme Careers",
            employer_name="Acme",
            source_kind="official_structured_ats",
            connector_kind="greenhouse",
            trust_tier=0,
            canonical_base_url=(
                "https://boards.greenhouse.io/acme"
            ),
            state="active",
            last_verified_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )

        self.job = CareerJobPosting(
            job_id="career-job-acme-123",
            employer_name="Acme",
            requisition_id="123",
            canonical_job_url=(
                "https://jobs.example.test/acme/123"
            ),
            canonical_apply_url=(
                "https://jobs.example.test/acme/123/apply"
            ),
            current_snapshot_id=None,
            verification_state="RETRIEVED",
            lifecycle_state="ACTIVE",
            first_seen_at=NOW,
            last_seen_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )

        self.repository.upsert_source(
            self.source
        )
        self.repository.upsert_job(
            self.job
        )

        self.snapshot = CareerJobSnapshot.build(
            job_id=self.job.job_id,
            source_id=self.source.source_id,
            title="Junior Cloud Engineer",
            employer_name="Acme",
            location_text="Ontario, Canada",
            work_mode="HYBRID",
            employment_type="Full-time",
            description_text=(
                "Support cloud infrastructure and "
                "deployment automation."
            ),
            posted_at=NOW - timedelta(hours=12),
            freshness_state="WITHIN_72H",
            salary_text="$70,000-$85,000",
            requirements={
                "experience_years_max": 3,
                "cloud": ["AWS"],
            },
            normalized_text_sha256="a" * 64,
            observed_at=NOW,
        )

        self.repository.persist_snapshot(
            self.snapshot
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_initializes_exact_career_tables(
        self,
    ) -> None:
        with self.truth.connection() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name LIKE 'career_%'
                ORDER BY name
                """
            ).fetchall()

        names = {
            str(row["name"])
            for row in rows
        }

        self.assertEqual(
            names,
            {
                "career_application_events",
                "career_applications",
                "career_fit_assessments",
                "career_job_evidence_links",
                "career_job_postings",
                "career_job_snapshots",
                "career_sources",
            },
        )

    def test_requires_phase16_evidence_table(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            truth = AgentTruthRepository(
                Path(tmp) / "truth.db"
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "requires the Phase-16",
            ):
                CareerRepository(truth)

    def test_source_and_job_round_trip(
        self,
    ) -> None:
        self.assertEqual(
            self.repository.get_source(
                self.source.source_id
            ),
            self.source,
        )

        self.assertEqual(
            self.repository.get_job(
                self.job.job_id
            ),
            self.job,
        )

        updated = self.job.model_copy(
            update={
                "current_snapshot_id": (
                    self.snapshot.snapshot_id
                ),
                "verification_state": "VERIFIED",
                "updated_at": NOW
                + timedelta(seconds=1),
            }
        )

        stored = self.repository.upsert_job(
            updated
        )

        self.assertEqual(
            stored.current_snapshot_id,
            self.snapshot.snapshot_id,
        )
        self.assertEqual(
            stored.verification_state,
            "VERIFIED",
        )

    def test_snapshot_is_append_only_and_idempotent(
        self,
    ) -> None:
        stored = self.repository.persist_snapshot(
            self.snapshot
        )

        self.assertEqual(stored, self.snapshot)

        tampered = self.snapshot.model_copy(
            update={
                "title": "Tampered title",
            }
        )

        with self.assertRaises(
            CareerPersistenceConflict
        ):
            self.repository.persist_snapshot(
                tampered
            )

    def test_snapshot_foreign_keys_are_enforced(
        self,
    ) -> None:
        bad = CareerJobSnapshot.build(
            job_id=self.job.job_id,
            source_id="career-source-missing",
            title="Cloud Support Engineer",
            employer_name="Acme",
            description_text="Support cloud systems.",
            freshness_state="UNKNOWN",
            normalized_text_sha256="b" * 64,
            observed_at=NOW,
        )

        with self.assertRaises(
            CareerPersistenceConflict
        ):
            self.repository.persist_snapshot(bad)

    def test_evidence_link_requires_successful_phase16_evidence(
        self,
    ) -> None:
        good = CareerJobEvidenceLink.build(
            job_id=self.job.job_id,
            snapshot_id=self.snapshot.snapshot_id,
            research_evidence_id=(
                SUCCESS_EVIDENCE_ID
            ),
            evidence_role="JOB_DETAIL",
            linked_at=NOW,
        )

        stored = (
            self.repository.persist_evidence_link(
                good
            )
        )

        self.assertEqual(stored, good)

        failed = CareerJobEvidenceLink.build(
            job_id=self.job.job_id,
            snapshot_id=self.snapshot.snapshot_id,
            research_evidence_id=(
                FAILED_EVIDENCE_ID
            ),
            evidence_role="JOB_DETAIL",
            linked_at=NOW,
        )

        with self.assertRaisesRegex(
            ValueError,
            "successful retrieval evidence",
        ):
            self.repository.persist_evidence_link(
                failed
            )

    def test_evidence_link_rejects_unknown_evidence(
        self,
    ) -> None:
        missing = CareerJobEvidenceLink.build(
            job_id=self.job.job_id,
            snapshot_id=self.snapshot.snapshot_id,
            research_evidence_id=(
                "research-retrieval-"
                "333333333333333333333333"
            ),
            evidence_role="JOB_DETAIL",
            linked_at=NOW,
        )

        with self.assertRaisesRegex(
            ValueError,
            "existing retrieval evidence",
        ):
            self.repository.persist_evidence_link(
                missing
            )

    def test_fit_assessment_is_versioned_and_immutable(
        self,
    ) -> None:
        assessment = CareerFitAssessment.build(
            job_id=self.job.job_id,
            snapshot_id=self.snapshot.snapshot_id,
            profile_version="profile-abc123",
            scorer_version="career-v1",
            fit_score=91.0,
            verdict="APPLY",
            score_breakdown={
                "skills": 95,
                "seniority": 90,
            },
            explanation={
                "summary": "Strong fit.",
            },
            assessed_at=NOW,
        )

        stored = (
            self.repository.persist_fit_assessment(
                assessment
            )
        )

        self.assertEqual(stored, assessment)

        duplicate = CareerFitAssessment.build(
            job_id=self.job.job_id,
            snapshot_id=self.snapshot.snapshot_id,
            profile_version="profile-abc123",
            scorer_version="career-v1",
            fit_score=40.0,
            verdict="CONSIDER",
            score_breakdown={
                "skills": 40,
            },
            explanation={
                "summary": "Different result.",
            },
            assessed_at=NOW
            + timedelta(seconds=1),
        )

        with self.assertRaises(
            CareerPersistenceConflict
        ):
            self.repository.persist_fit_assessment(
                duplicate
            )

    def test_hard_exclusion_requires_skip(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "hard exclusions require SKIP",
        ):
            CareerFitAssessment.build(
                job_id=self.job.job_id,
                snapshot_id=(
                    self.snapshot.snapshot_id
                ),
                profile_version="profile-abc123",
                scorer_version="career-v1",
                fit_score=80.0,
                verdict="APPLY",
                hard_exclusion_codes=[
                    "FRENCH_REQUIRED",
                ],
                assessed_at=NOW,
            )

    def test_application_and_append_only_event(
        self,
    ) -> None:
        application = CareerApplication(
            application_id=(
                "career-application-acme-123"
            ),
            job_id=self.job.job_id,
            state="SHORTLISTED",
            created_at=NOW,
            updated_at=NOW,
        )

        stored = (
            self.repository.upsert_application(
                application
            )
        )

        self.assertEqual(stored, application)

        event = CareerApplicationEvent.build(
            application_id=(
                application.application_id
            ),
            from_state=None,
            to_state="SHORTLISTED",
            actor_kind="OWNER",
            actor_id="dipen",
            reason="Owner shortlisted role.",
            occurred_at=NOW,
        )

        stored_event = (
            self.repository
            .persist_application_event(event)
        )

        self.assertEqual(
            stored_event,
            event,
        )

        self.assertEqual(
            self.repository.list_application_events(
                application.application_id
            ),
            [event],
        )

    def test_applied_confirmed_requires_explicit_confirmation(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "requires explicit external confirmation",
        ):
            CareerApplication(
                application_id=(
                    "career-application-invalid"
                ),
                job_id=self.job.job_id,
                state="APPLIED_CONFIRMED",
                created_at=NOW,
                updated_at=NOW,
            )


    def test_integer_and_float_fit_scores_share_canonical_identity(
        self,
    ) -> None:
        integer_score = CareerFitAssessment.build(
            job_id=self.job.job_id,
            snapshot_id=self.snapshot.snapshot_id,
            profile_version="profile-number-probe",
            scorer_version="career-v1",
            fit_score=80,
            verdict="APPLY",
            assessed_at=NOW,
        )

        float_score = CareerFitAssessment.build(
            job_id=self.job.job_id,
            snapshot_id=self.snapshot.snapshot_id,
            profile_version="profile-number-probe",
            scorer_version="career-v1",
            fit_score=80.0,
            verdict="APPLY",
            assessed_at=NOW,
        )

        self.assertEqual(
            integer_score.fit_score,
            80.0,
        )

        self.assertEqual(
            integer_score,
            float_score,
        )

        self.assertEqual(
            integer_score.assessment_id,
            float_score.assessment_id,
        )

        restored = CareerFitAssessment.model_validate_json(
            integer_score.model_dump_json()
        )

        self.assertEqual(
            restored,
            integer_score,
        )


if __name__ == "__main__":
    unittest.main()
