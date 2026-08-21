from __future__ import annotations

import json
import tempfile
import unittest
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from agents.truth_repository import (
    AgentTruthRepository,
)
from career.repository import CareerRepository
from career.schemas import (
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerSource,
)
from career.service import (
    CareerAdmissionRejected,
    CareerAuthorizationRejected,
    CareerDomainService,
    CareerTransitionRejected,
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

CONTENT_HASH = "a" * 64

SUCCESS_EVIDENCE_ID = (
    "research-retrieval-"
    "111111111111111111111111"
)


class CareerDomainServiceTestCase(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()

        self.db = (
            Path(self.tmp.name)
            / "agent-truth.db"
        )

        self.truth = AgentTruthRepository(
            self.db
        )

        ResearchRetrievalRepository(
            self.truth
        )

        self.repository = CareerRepository(
            self.truth
        )

        with self.truth.connection() as connection:
            connection.execute(
                """
                INSERT INTO
                research_retrieval_evidence (
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
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    SUCCESS_EVIDENCE_ID,
                    "1" * 64,
                    "career-service-success",
                    None,
                    "succeeded",
                    "completed",
                    "public-web-retrieval",
                    (
                        "https://jobs.example.test/"
                        "acme/123"
                    ),
                    (
                        "https://jobs.example.test/"
                        "acme/123"
                    ),
                    "research-citation-test",
                    "internet-content-test",
                    json.dumps(
                        {
                            "normalized_text_sha256":
                                CONTENT_HASH,
                            "final_url": (
                                "https://jobs.example.test/"
                                "acme/123"
                            ),
                        }
                    ),
                    NOW.isoformat(),
                ),
            )
            connection.commit()

        self.source = CareerSource(
            source_id=(
                "career-source-acme-greenhouse"
            ),
            display_name="Acme Careers",
            employer_name="Acme",
            source_kind=(
                "official_structured_ats"
            ),
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
                "https://jobs.example.test/"
                "acme/123"
            ),
            canonical_apply_url=(
                "https://jobs.example.test/"
                "acme/123/apply"
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

        self.service = CareerDomainService(
            self.repository
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _snapshot(
        self,
        *,
        freshness: str = "WITHIN_72H",
        normalized_hash: str = CONTENT_HASH,
    ) -> CareerJobSnapshot:
        posted_at = (
            NOW - timedelta(hours=12)
            if freshness
            in {
                "WITHIN_72H",
                "OLDER_THAN_72H",
            }
            else None
        )

        return CareerJobSnapshot.build(
            job_id=self.job.job_id,
            source_id=self.source.source_id,
            title="Junior Cloud Engineer",
            employer_name="Acme",
            location_text="Ontario, Canada",
            work_mode="HYBRID",
            employment_type="Full-time",
            description_text=(
                "Support cloud infrastructure "
                "and deployment automation."
            ),
            posted_at=posted_at,
            freshness_state=freshness,
            normalized_text_sha256=(
                normalized_hash
            ),
            observed_at=NOW,
        )

    def _admit(
        self,
        *,
        freshness: str = "WITHIN_72H",
    ) -> CareerJobPosting:
        snapshot = self._snapshot(
            freshness=freshness
        )

        link = CareerJobEvidenceLink.build(
            job_id=self.job.job_id,
            snapshot_id=snapshot.snapshot_id,
            research_evidence_id=(
                SUCCESS_EVIDENCE_ID
            ),
            evidence_role="JOB_DETAIL",
            linked_at=NOW,
        )

        return (
            self.service
            .admit_verified_snapshot(
                snapshot=snapshot,
                evidence_link=link,
            )
        )

    def _shortlist(
        self,
        *,
        at: datetime | None = None,
    ):
        self._admit()

        return (
            self.service
            .create_shortlisted_application(
                application_id=(
                    "career-application-acme-123"
                ),
                job_id=self.job.job_id,
                owner_id="dipen",
                reason="Owner shortlisted role.",
                occurred_at=(
                    at
                    or NOW
                    + timedelta(seconds=1)
                ),
            )
        )

    def test_verified_admission_binds_snapshot_and_evidence(
        self,
    ) -> None:
        admitted = self._admit()

        self.assertEqual(
            admitted.verification_state,
            "VERIFIED",
        )

        self.assertIsNotNone(
            admitted.current_snapshot_id
        )

        snapshot = (
            self.repository.get_snapshot(
                admitted.current_snapshot_id
            )
        )

        self.assertIsNotNone(snapshot)

    def test_verified_admission_rejects_content_hash_mismatch(
        self,
    ) -> None:
        snapshot = self._snapshot(
            normalized_hash="b" * 64
        )

        link = CareerJobEvidenceLink.build(
            job_id=self.job.job_id,
            snapshot_id=snapshot.snapshot_id,
            research_evidence_id=(
                SUCCESS_EVIDENCE_ID
            ),
            evidence_role="JOB_DETAIL",
            linked_at=NOW,
        )

        with self.assertRaisesRegex(
            CareerAdmissionRejected,
            "does not match retrieval evidence",
        ):
            self.service.admit_verified_snapshot(
                snapshot=snapshot,
                evidence_link=link,
            )

        self.assertIsNone(
            self.repository.get_snapshot(
                snapshot.snapshot_id
            )
        )

    def test_shortlist_requires_verified_fresh_job(
        self,
    ) -> None:
        self._admit(
            freshness="UNKNOWN"
        )

        with self.assertRaisesRegex(
            CareerAdmissionRejected,
            "requires a VERIFIED job",
        ):
            self.service.create_shortlisted_application(
                application_id=(
                    "career-application-acme-unknown"
                ),
                job_id=self.job.job_id,
                owner_id="dipen",
                reason="Owner shortlist attempt.",
                occurred_at=(
                    NOW + timedelta(seconds=1)
                ),
            )

    def test_deterministic_preparation_is_bounded(
        self,
    ) -> None:
        application = self._shortlist()

        preparing = (
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="PREPARING",
                actor_kind="DETERMINISTIC_SYSTEM",
                actor_id="dap-career",
                reason="Prepare application materials.",
                occurred_at=(
                    NOW + timedelta(seconds=2)
                ),
            )
        )

        self.assertEqual(
            preparing.state,
            "PREPARING",
        )

        ready = (
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="READY_FOR_REVIEW",
                actor_kind="DETERMINISTIC_SYSTEM",
                actor_id="dap-career",
                reason="Materials prepared.",
                occurred_at=(
                    NOW + timedelta(seconds=3)
                ),
            )
        )

        self.assertEqual(
            ready.state,
            "READY_FOR_REVIEW",
        )

        events = (
            self.repository.list_application_events(
                application.application_id
            )
        )

        self.assertEqual(
            [
                event.to_state
                for event in events
            ],
            [
                "SHORTLISTED",
                "PREPARING",
                "READY_FOR_REVIEW",
            ],
        )

    def test_deterministic_system_cannot_owner_approve(
        self,
    ) -> None:
        application = self._shortlist()

        self.service.transition_application(
            application_id=application.application_id,
            to_state="PREPARING",
            actor_kind="DETERMINISTIC_SYSTEM",
            actor_id="dap-career",
            reason="Prepare.",
            occurred_at=(
                NOW + timedelta(seconds=2)
            ),
        )

        self.service.transition_application(
            application_id=application.application_id,
            to_state="READY_FOR_REVIEW",
            actor_kind="DETERMINISTIC_SYSTEM",
            actor_id="dap-career",
            reason="Ready.",
            occurred_at=(
                NOW + timedelta(seconds=3)
            ),
        )

        with self.assertRaisesRegex(
            CareerAuthorizationRejected,
            "not authorized",
        ):
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="OWNER_APPROVED",
                actor_kind="DETERMINISTIC_SYSTEM",
                actor_id="dap-career",
                reason="Attempt approval.",
                occurred_at=(
                    NOW + timedelta(seconds=4)
                ),
            )

    def test_owner_approval_and_manual_applied_confirmation(
        self,
    ) -> None:
        application = self._shortlist()

        self.service.transition_application(
            application_id=application.application_id,
            to_state="PREPARING",
            actor_kind="DETERMINISTIC_SYSTEM",
            actor_id="dap-career",
            reason="Prepare.",
            occurred_at=(
                NOW + timedelta(seconds=2)
            ),
        )

        self.service.transition_application(
            application_id=application.application_id,
            to_state="READY_FOR_REVIEW",
            actor_kind="DETERMINISTIC_SYSTEM",
            actor_id="dap-career",
            reason="Ready.",
            occurred_at=(
                NOW + timedelta(seconds=3)
            ),
        )

        approved = (
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="OWNER_APPROVED",
                actor_kind="OWNER",
                actor_id="dipen",
                reason="Owner reviewed and approved.",
                occurred_at=(
                    NOW + timedelta(seconds=4)
                ),
            )
        )

        self.assertEqual(
            approved.state,
            "OWNER_APPROVED",
        )

        self.assertIsNotNone(
            approved.owner_approved_at
        )

        with self.assertRaises(
            CareerAuthorizationRejected
        ):
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="APPLIED_CONFIRMED",
                actor_kind="DETERMINISTIC_SYSTEM",
                actor_id="dap-career",
                reason="Forbidden submit.",
                occurred_at=(
                    NOW + timedelta(seconds=5)
                ),
            )

        applied = (
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="APPLIED_CONFIRMED",
                actor_kind="OWNER",
                actor_id="dipen",
                reason=(
                    "Owner confirms manual "
                    "external submission."
                ),
                occurred_at=(
                    NOW + timedelta(seconds=6)
                ),
            )
        )

        self.assertEqual(
            applied.state,
            "APPLIED_CONFIRMED",
        )

        self.assertEqual(
            applied.applied_confirmation_kind,
            "OWNER_MANUAL",
        )

        self.assertIsNotNone(
            applied.applied_confirmed_at
        )

    def test_illegal_transition_does_not_mutate_application(
        self,
    ) -> None:
        application = self._shortlist()

        with self.assertRaisesRegex(
            CareerTransitionRejected,
            "Illegal Career application transition",
        ):
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="OFFER",
                actor_kind="OWNER",
                actor_id="dipen",
                reason="Invalid skip.",
                occurred_at=(
                    NOW + timedelta(seconds=2)
                ),
            )

        stored = self.repository.get_application(
            application.application_id
        )

        self.assertEqual(
            stored.state,
            "SHORTLISTED",
        )

        events = (
            self.repository.list_application_events(
                application.application_id
            )
        )

        self.assertEqual(
            len(events),
            1,
        )

    def test_closed_state_is_terminal(
        self,
    ) -> None:
        application = self._shortlist()

        closed = (
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="CLOSED",
                actor_kind="OWNER",
                actor_id="dipen",
                reason="Owner closed application.",
                occurred_at=(
                    NOW + timedelta(seconds=2)
                ),
            )
        )

        self.assertEqual(
            closed.state,
            "CLOSED",
        )

        with self.assertRaises(
            CareerTransitionRejected
        ):
            self.service.transition_application(
                application_id=(
                    application.application_id
                ),
                to_state="SHORTLISTED",
                actor_kind="OWNER",
                actor_id="dipen",
                reason="Illegal reopen.",
                occurred_at=(
                    NOW + timedelta(seconds=3)
                ),
            )


if __name__ == "__main__":
    unittest.main()
