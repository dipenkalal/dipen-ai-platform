from __future__ import annotations

import inspect
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
from career.repository import (
    CareerPersistenceConflict,
    CareerRepository,
)
from career.schemas import (
    CareerApplication,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerSource,
)
from career.service import (
    CareerDomainService,
    CareerMaterialRejected,
)
from gateway.research_retrieval_repository import (
    ResearchRetrievalRepository,
)


NOW = datetime(
    2026,
    9,
    2,
    16,
    0,
    tzinfo=timezone.utc,
)

CONTENT_HASH = "c" * 64


class CareerMaterialServiceTestCase(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()

        self.db = (
            Path(self.tmp.name)
            / "material-service.db"
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

        self.source = CareerSource(
            source_id=(
                "career-source-material-service"
            ),
            display_name="Material Careers",
            employer_name="Material Employer",
            source_kind=(
                "official_structured_ats"
            ),
            connector_kind="greenhouse",
            trust_tier=3,
            canonical_base_url=(
                "https://example.test/careers"
            ),
            state="active",
            last_verified_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )

        self.job = CareerJobPosting(
            job_id="career-job-material-service",
            employer_name="Material Employer",
            requisition_id="MAT-1",
            canonical_job_url=(
                "https://example.test/jobs/1"
            ),
            canonical_apply_url=(
                "https://example.test/jobs/1/apply"
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
            title="Cloud Engineer",
            employer_name="Material Employer",
            location_text="Toronto, ON",
            work_mode="HYBRID",
            employment_type="Full-time",
            description_text=(
                "Support cloud infrastructure."
            ),
            posted_at=(
                NOW - timedelta(hours=4)
            ),
            freshness_state="WITHIN_72H",
            normalized_text_sha256=(
                CONTENT_HASH
            ),
            observed_at=NOW,
        )

        self.repository.persist_snapshot(
            self.snapshot
        )

        job_payload = self.job.model_dump(
            mode="python"
        )

        job_payload["current_snapshot_id"] = (
            self.snapshot.snapshot_id
        )
        job_payload["verification_state"] = (
            "VERIFIED"
        )
        job_payload["updated_at"] = (
            NOW + timedelta(seconds=1)
        )

        self.job = CareerJobPosting.model_validate(
            job_payload
        )

        self.repository.upsert_job(
            self.job
        )

        self.application = CareerApplication(
            application_id=(
                "career-application-material-service"
            ),
            job_id=self.job.job_id,
            state="PREPARING",
            created_at=NOW,
            updated_at=NOW,
        )

        self.repository.upsert_application(
            self.application
        )

        self.service = CareerDomainService(
            self.repository
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _material(self):
        return self.service.create_material(
            application_id=(
                self.application.application_id
            ),
            material_kind="RESUME",
            label="primary",
            created_at=(
                NOW + timedelta(seconds=2)
            ),
        )

    def _initial_version(self):
        material = self._material()

        version = (
            self.service
            .create_initial_material_version(
                material_id=material.material_id,
                source_snapshot_id=(
                    self.snapshot.snapshot_id
                ),
                content_format="MARKDOWN",
                content_text="# Resume v1",
                created_by_kind="DAP_GENERATOR",
                created_by_id="material-test",
                creation_mechanism="unit-test",
                profile_version="master-v1",
                model_provider="local",
                model_name="test-model",
                occurred_at=(
                    NOW + timedelta(seconds=3)
                ),
            )
        )

        return material, version

    def test_material_creation_requires_preparing(
        self,
    ) -> None:
        payload = self.application.model_dump(
            mode="python"
        )
        payload["state"] = "SHORTLISTED"
        payload["updated_at"] = (
            NOW + timedelta(seconds=2)
        )

        self.repository.upsert_application(
            CareerApplication.model_validate(
                payload
            )
        )

        with self.assertRaisesRegex(
            CareerMaterialRejected,
            "PREPARING",
        ):
            self.service.create_material(
                application_id=(
                    self.application.application_id
                ),
                material_kind="RESUME",
                label="primary",
                created_at=(
                    NOW + timedelta(seconds=3)
                ),
            )

    def test_initial_version_and_created_event_are_paired(
        self,
    ) -> None:
        _, version = self._initial_version()

        events = (
            self.repository
            .list_material_events(
                version.material_version_id
            )
        )

        self.assertEqual(
            [event.event_kind for event in events],
            ["CREATED"],
        )

        self.assertEqual(
            events[0].actor_kind,
            "DAP_SYSTEM",
        )

    def test_derived_version_has_exact_lineage(
        self,
    ) -> None:
        _, first = self._initial_version()

        second = (
            self.service
            .create_derived_material_version(
                parent_material_version_id=(
                    first.material_version_id
                ),
                source_snapshot_id=(
                    self.snapshot.snapshot_id
                ),
                content_format="MARKDOWN",
                content_text="# Resume v2",
                created_by_kind="OWNER",
                created_by_id="dipen",
                creation_mechanism="owner-edit",
                occurred_at=(
                    NOW + timedelta(seconds=4)
                ),
            )
        )

        self.assertEqual(
            second.version_number,
            2,
        )

        self.assertEqual(
            second.parent_material_version_id,
            first.material_version_id,
        )

        events = (
            self.repository
            .list_material_events(
                second.material_version_id
            )
        )

        self.assertEqual(
            [event.event_kind for event in events],
            ["CREATED"],
        )

    def test_old_version_cannot_be_marked_ready(
        self,
    ) -> None:
        _, first = self._initial_version()

        self.service.create_derived_material_version(
            parent_material_version_id=(
                first.material_version_id
            ),
            source_snapshot_id=(
                self.snapshot.snapshot_id
            ),
            content_format="MARKDOWN",
            content_text="# Resume v2",
            created_by_kind="DAP_GENERATOR",
            created_by_id="material-test",
            creation_mechanism="revision",
            occurred_at=(
                NOW + timedelta(seconds=4)
            ),
        )

        with self.assertRaisesRegex(
            CareerMaterialRejected,
            "latest immutable version",
        ):
            self.service.mark_material_version_ready(
                material_version_id=(
                    first.material_version_id
                ),
                actor_kind="DAP_SYSTEM",
                actor_id="dap",
                reason="Ready.",
                occurred_at=(
                    NOW + timedelta(seconds=5)
                ),
            )

    def test_ready_then_owner_approval(
        self,
    ) -> None:
        _, version = self._initial_version()

        ready = (
            self.service
            .mark_material_version_ready(
                material_version_id=(
                    version.material_version_id
                ),
                actor_kind="DAP_SYSTEM",
                actor_id="dap",
                reason="Preparation complete.",
                occurred_at=(
                    NOW + timedelta(seconds=4)
                ),
            )
        )

        self.assertEqual(
            ready.event_kind,
            "MARKED_READY_FOR_REVIEW",
        )

        updated = (
            self.service.transition_application(
                application_id=(
                    self.application.application_id
                ),
                to_state="READY_FOR_REVIEW",
                actor_kind="DETERMINISTIC_SYSTEM",
                actor_id="dap",
                reason=(
                    "Prepared materials ready."
                ),
                occurred_at=(
                    NOW + timedelta(seconds=5)
                ),
            )
        )

        self.assertEqual(
            updated.state,
            "READY_FOR_REVIEW",
        )

        approved = (
            self.service
            .approve_material_version(
                material_version_id=(
                    version.material_version_id
                ),
                owner_id="dipen",
                reason="Approved.",
                occurred_at=(
                    NOW + timedelta(seconds=6)
                ),
            )
        )

        self.assertEqual(
            approved.event_kind,
            "APPROVED",
        )

        self.assertEqual(
            approved.actor_kind,
            "OWNER",
        )

        kinds = [
            event.event_kind
            for event in (
                self.repository
                .list_material_events(
                    version.material_version_id
                )
            )
        ]

        self.assertEqual(
            kinds,
            [
                "CREATED",
                "MARKED_READY_FOR_REVIEW",
                "APPROVED",
            ],
        )

    def test_owner_decision_requires_ready_event(
        self,
    ) -> None:
        _, version = self._initial_version()

        self.service.transition_application(
            application_id=(
                self.application.application_id
            ),
            to_state="READY_FOR_REVIEW",
            actor_kind="DETERMINISTIC_SYSTEM",
            actor_id="dap",
            reason="Test transition.",
            occurred_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        with self.assertRaisesRegex(
            CareerMaterialRejected,
            "marked ready",
        ):
            self.service.approve_material_version(
                material_version_id=(
                    version.material_version_id
                ),
                owner_id="dipen",
                reason="Premature approval.",
                occurred_at=(
                    NOW + timedelta(seconds=6)
                ),
            )

    def test_owner_rejection_is_version_specific(
        self,
    ) -> None:
        _, version = self._initial_version()

        self.service.mark_material_version_ready(
            material_version_id=(
                version.material_version_id
            ),
            actor_kind="OWNER",
            actor_id="dipen",
            reason="Ready for review.",
            occurred_at=(
                NOW + timedelta(seconds=4)
            ),
        )

        self.service.transition_application(
            application_id=(
                self.application.application_id
            ),
            to_state="READY_FOR_REVIEW",
            actor_kind="DETERMINISTIC_SYSTEM",
            actor_id="dap",
            reason="Ready.",
            occurred_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        rejected = (
            self.service
            .reject_material_version(
                material_version_id=(
                    version.material_version_id
                ),
                owner_id="dipen",
                reason="Needs revision.",
                occurred_at=(
                    NOW + timedelta(seconds=6)
                ),
            )
        )

        self.assertEqual(
            rejected.event_kind,
            "REJECTED",
        )

        with self.assertRaisesRegex(
            CareerMaterialRejected,
            "already has",
        ):
            self.service.approve_material_version(
                material_version_id=(
                    version.material_version_id
                ),
                owner_id="dipen",
                reason="Conflicting decision.",
                occurred_at=(
                    NOW + timedelta(seconds=7)
                ),
            )

    def test_service_exposes_no_submission_method(
        self,
    ) -> None:
        forbidden = {
            "apply",
            "auto_apply",
            "send_application",
            "submit",
            "submit_application",
        }

        methods = {
            name
            for name, value
            in inspect.getmembers(
                CareerDomainService
            )
            if inspect.isfunction(value)
        }

        self.assertEqual(
            methods & forbidden,
            set(),
        )


    def _ready_primary_resume(self):
        material, version = self._initial_version()

        self.service.mark_material_version_ready(
            material_version_id=(
                version.material_version_id
            ),
            actor_kind="DAP_SYSTEM",
            actor_id="dap",
            reason="Ready.",
            occurred_at=(
                NOW + timedelta(seconds=4)
            ),
        )

        return material, version

    def test_missing_primary_resume_blocks_readiness(
        self,
    ) -> None:
        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertFalse(result.ready)

        self.assertIn(
            "PRIMARY_RESUME_MISSING",
            {
                blocker.code
                for blocker in result.blockers
            },
        )

    def test_resume_without_version_blocks_readiness(
        self,
    ) -> None:
        material = self._material()

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        blockers = {
            (
                blocker.code,
                blocker.material_id,
            )
            for blocker in result.blockers
        }

        self.assertIn(
            (
                "BLOCKING_MATERIAL_HAS_NO_VERSION",
                material.material_id,
            ),
            blockers,
        )

    def test_absent_cover_letter_does_not_block(
        self,
    ) -> None:
        self._ready_primary_resume()

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertTrue(result.ready)
        self.assertEqual(result.blockers, ())

    def test_present_cover_letter_becomes_blocking(
        self,
    ) -> None:
        self._ready_primary_resume()

        cover = self.service.create_material(
            application_id=(
                self.application.application_id
            ),
            material_kind="COVER_LETTER",
            label="primary",
            created_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertFalse(result.ready)

        self.assertIn(
            (
                "BLOCKING_MATERIAL_HAS_NO_VERSION",
                cover.material_id,
            ),
            {
                (
                    blocker.code,
                    blocker.material_id,
                )
                for blocker in result.blockers
            },
        )

    def test_notes_do_not_block_readiness(
        self,
    ) -> None:
        self._ready_primary_resume()

        self.service.create_material(
            application_id=(
                self.application.application_id
            ),
            material_kind="APPLICATION_NOTES",
            label="working",
            created_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertTrue(result.ready)

    def test_alternate_resume_label_does_not_block(
        self,
    ) -> None:
        self._ready_primary_resume()

        self.service.create_material(
            application_id=(
                self.application.application_id
            ),
            material_kind="RESUME",
            label="alternate",
            created_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertTrue(result.ready)

    def test_missing_ready_event_blocks(
        self,
    ) -> None:
        _, version = self._initial_version()

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertIn(
            (
                "READY_EVENT_MISSING",
                version.material_version_id,
            ),
            {
                (
                    blocker.code,
                    blocker.material_version_id,
                )
                for blocker in result.blockers
            },
        )

    def test_current_snapshot_drift_blocks(
        self,
    ) -> None:
        _, version = self._ready_primary_resume()

        newer = CareerJobSnapshot.build(
            job_id=self.job.job_id,
            source_id=self.source.source_id,
            title="Cloud Engineer Updated",
            employer_name="Material Employer",
            location_text="Toronto, ON",
            work_mode="HYBRID",
            employment_type="Full-time",
            description_text=(
                "Updated cloud infrastructure role."
            ),
            posted_at=(
                NOW - timedelta(hours=3)
            ),
            freshness_state="WITHIN_72H",
            normalized_text_sha256=(
                "d" * 64
            ),
            observed_at=(
                NOW + timedelta(seconds=10)
            ),
        )

        self.repository.persist_snapshot(
            newer
        )

        payload = self.job.model_dump(
            mode="python"
        )

        payload["current_snapshot_id"] = (
            newer.snapshot_id
        )
        payload["updated_at"] = (
            NOW + timedelta(seconds=11)
        )

        self.job = CareerJobPosting.model_validate(
            payload
        )

        self.repository.upsert_job(
            self.job
        )

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertIn(
            (
                "LATEST_VERSION_SNAPSHOT_STALE",
                version.material_version_id,
            ),
            {
                (
                    blocker.code,
                    blocker.material_version_id,
                )
                for blocker in result.blockers
            },
        )

    def test_rejected_latest_version_blocks(
        self,
    ) -> None:
        _, version = self._ready_primary_resume()

        self.service.transition_application(
            application_id=(
                self.application.application_id
            ),
            to_state="READY_FOR_REVIEW",
            actor_kind="DETERMINISTIC_SYSTEM",
            actor_id="dap",
            reason="Ready.",
            occurred_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        self.service.reject_material_version(
            material_version_id=(
                version.material_version_id
            ),
            owner_id="dipen",
            reason="Needs revision.",
            occurred_at=(
                NOW + timedelta(seconds=6)
            ),
        )

        self.service.transition_application(
            application_id=(
                self.application.application_id
            ),
            to_state="PREPARING",
            actor_kind="OWNER",
            actor_id="dipen",
            reason="Return for revision.",
            occurred_at=(
                NOW + timedelta(seconds=7)
            ),
        )

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertIn(
            "LATEST_VERSION_REJECTED",
            {
                blocker.code
                for blocker in result.blockers
            },
        )

    def test_complete_resume_and_cover_package_ready(
        self,
    ) -> None:
        self._ready_primary_resume()

        cover = self.service.create_material(
            application_id=(
                self.application.application_id
            ),
            material_kind="COVER_LETTER",
            label="primary",
            created_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        cover_version = (
            self.service
            .create_initial_material_version(
                material_id=cover.material_id,
                source_snapshot_id=(
                    self.snapshot.snapshot_id
                ),
                content_format="MARKDOWN",
                content_text="# Cover Letter",
                created_by_kind="DAP_GENERATOR",
                created_by_id="material-test",
                creation_mechanism="unit-test",
                occurred_at=(
                    NOW + timedelta(seconds=6)
                ),
            )
        )

        self.service.mark_material_version_ready(
            material_version_id=(
                cover_version.material_version_id
            ),
            actor_kind="DAP_SYSTEM",
            actor_id="dap",
            reason="Cover ready.",
            occurred_at=(
                NOW + timedelta(seconds=7)
            ),
        )

        result = (
            self.service
            .evaluate_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertTrue(result.ready)

    def test_guarded_advancement_succeeds_when_ready(
        self,
    ) -> None:
        self._ready_primary_resume()

        updated = (
            self.service
            .advance_preparing_application_to_review(
                application_id=(
                    self.application.application_id
                ),
                reason="Material package ready.",
                occurred_at=(
                    NOW + timedelta(seconds=5)
                ),
            )
        )

        self.assertEqual(
            updated.state,
            "READY_FOR_REVIEW",
        )

        events = (
            self.repository
            .list_application_events(
                self.application.application_id
            )
        )

        self.assertEqual(
            events[-1].actor_kind,
            "DETERMINISTIC_SYSTEM",
        )

        self.assertEqual(
            events[-1].actor_id,
            "career-material-readiness",
        )

    def test_guarded_advancement_cannot_bypass_blocker(
        self,
    ) -> None:
        before = (
            self.repository.get_application(
                self.application.application_id
            )
        )

        before_events = (
            self.repository
            .list_application_events(
                self.application.application_id
            )
        )

        with self.assertRaisesRegex(
            CareerMaterialRejected,
            "PRIMARY_RESUME_MISSING",
        ):
            (
                self.service
                .advance_preparing_application_to_review(
                    application_id=(
                        self.application.application_id
                    ),
                    reason="Attempt bypass.",
                    occurred_at=(
                        NOW + timedelta(seconds=5)
                    ),
                )
            )

        after = (
            self.repository.get_application(
                self.application.application_id
            )
        )

        after_events = (
            self.repository
            .list_application_events(
                self.application.application_id
            )
        )

        self.assertEqual(before, after)
        self.assertEqual(
            before_events,
            after_events,
        )


    def _seed_second_verified_job(self):
        job = CareerJobPosting(
            job_id="career-job-material-service-second",
            employer_name="Second Material Employer",
            requisition_id="MAT-2",
            canonical_job_url=(
                "https://example.test/jobs/2"
            ),
            canonical_apply_url=(
                "https://example.test/jobs/2/apply"
            ),
            current_snapshot_id=None,
            verification_state="RETRIEVED",
            lifecycle_state="ACTIVE",
            first_seen_at=NOW,
            last_seen_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )

        self.repository.upsert_job(job)

        snapshot = CareerJobSnapshot.build(
            job_id=job.job_id,
            source_id=self.source.source_id,
            title="Platform Support Engineer",
            employer_name="Second Material Employer",
            location_text="Ontario, Canada",
            work_mode="HYBRID",
            employment_type="Full-time",
            description_text=(
                "Support cloud platform operations."
            ),
            posted_at=(
                NOW - timedelta(hours=2)
            ),
            freshness_state="WITHIN_72H",
            normalized_text_sha256=("e" * 64),
            observed_at=NOW,
        )

        self.repository.persist_snapshot(snapshot)

        payload = job.model_dump(
            mode="python"
        )

        payload["current_snapshot_id"] = (
            snapshot.snapshot_id
        )
        payload["verification_state"] = "VERIFIED"
        payload["updated_at"] = (
            NOW + timedelta(seconds=1)
        )

        job = CareerJobPosting.model_validate(
            payload
        )

        self.repository.upsert_job(job)

        return job, snapshot

    def test_repository_lists_applications_for_job(
        self,
    ) -> None:
        applications = (
            self.repository
            .list_applications_for_job(
                self.application.job_id
            )
        )

        self.assertEqual(
            len(applications),
            1,
        )

        self.assertEqual(
            applications[0].application_id,
            self.application.application_id,
        )

    def test_cockpit_creation_uses_server_owned_identity(
        self,
    ) -> None:
        job, _ = self._seed_second_verified_job()

        created = (
            self.service
            .create_cockpit_application(
                job_id=job.job_id,
                reason="Owner shortlisted job.",
                occurred_at=(
                    NOW + timedelta(seconds=20)
                ),
            )
        )

        self.assertTrue(
            created.application_id.startswith(
                "career-application-"
            )
        )

        self.assertNotEqual(
            created.application_id,
            self.application.application_id,
        )

        events = (
            self.repository
            .list_application_events(
                created.application_id
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0].actor_kind,
            "OWNER",
        )
        self.assertEqual(
            events[0].actor_id,
            "dipen-owner",
        )

    def test_cockpit_creation_rejects_existing_job_workspace(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            CareerPersistenceConflict,
            "already exists",
        ):
            self.service.create_cockpit_application(
                job_id=self.job.job_id,
                reason="Duplicate attempt.",
                occurred_at=(
                    NOW + timedelta(seconds=20)
                ),
            )

        applications = (
            self.repository
            .list_applications_for_job(
                self.job.job_id
            )
        )

        self.assertEqual(
            len(applications),
            1,
        )

    def _ready_for_owner_review(self):
        _, version = self._ready_primary_resume()

        self.service.advance_preparing_application_to_review(
            application_id=(
                self.application.application_id
            ),
            reason="Package ready.",
            occurred_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        return version

    def test_application_approval_requires_material_approval(
        self,
    ) -> None:
        version = self._ready_for_owner_review()

        result = (
            self.service
            .evaluate_application_approval(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertFalse(result.approved)

        self.assertIn(
            (
                "APPROVED_EVENT_MISSING",
                version.material_version_id,
            ),
            {
                (
                    blocker.code,
                    blocker.material_version_id,
                )
                for blocker in result.blockers
            },
        )

    def test_guarded_owner_approval_succeeds_exact_package(
        self,
    ) -> None:
        version = self._ready_for_owner_review()

        self.service.approve_material_version(
            material_version_id=(
                version.material_version_id
            ),
            owner_id="dipen-owner",
            reason="Resume approved.",
            occurred_at=(
                NOW + timedelta(seconds=6)
            ),
        )

        result = (
            self.service
            .evaluate_application_approval(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertTrue(result.approved)

        updated = (
            self.service
            .approve_ready_application(
                application_id=(
                    self.application.application_id
                ),
                reason="Current package approved.",
                occurred_at=(
                    NOW + timedelta(seconds=7)
                ),
            )
        )

        self.assertEqual(
            updated.state,
            "OWNER_APPROVED",
        )

        events = (
            self.repository
            .list_application_events(
                self.application.application_id
            )
        )

        self.assertEqual(
            events[-1].actor_kind,
            "OWNER",
        )
        self.assertEqual(
            events[-1].actor_id,
            "dipen-owner",
        )

    def test_present_cover_letter_requires_exact_approval(
        self,
    ) -> None:
        _, resume_version = (
            self._ready_primary_resume()
        )

        cover = self.service.create_material(
            application_id=(
                self.application.application_id
            ),
            material_kind="COVER_LETTER",
            label="primary",
            created_at=(
                NOW + timedelta(seconds=5)
            ),
        )

        cover_version = (
            self.service
            .create_initial_material_version(
                material_id=cover.material_id,
                source_snapshot_id=(
                    self.snapshot.snapshot_id
                ),
                content_format="MARKDOWN",
                content_text="# Cover",
                created_by_kind="OWNER",
                created_by_id="dipen-owner",
                creation_mechanism="owner-edit",
                occurred_at=(
                    NOW + timedelta(seconds=6)
                ),
            )
        )

        self.service.mark_material_version_ready(
            material_version_id=(
                cover_version.material_version_id
            ),
            actor_kind="OWNER",
            actor_id="dipen-owner",
            reason="Cover ready.",
            occurred_at=(
                NOW + timedelta(seconds=7)
            ),
        )

        self.service.advance_preparing_application_to_review(
            application_id=(
                self.application.application_id
            ),
            reason="Package ready.",
            occurred_at=(
                NOW + timedelta(seconds=8)
            ),
        )

        self.service.approve_material_version(
            material_version_id=(
                resume_version.material_version_id
            ),
            owner_id="dipen-owner",
            reason="Resume approved.",
            occurred_at=(
                NOW + timedelta(seconds=9)
            ),
        )

        result = (
            self.service
            .evaluate_application_approval(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertFalse(result.approved)

        self.assertIn(
            (
                "APPROVED_EVENT_MISSING",
                cover_version.material_version_id,
            ),
            {
                (
                    blocker.code,
                    blocker.material_version_id,
                )
                for blocker in result.blockers
            },
        )

    def test_snapshot_drift_blocks_owner_approval(
        self,
    ) -> None:
        version = self._ready_for_owner_review()

        self.service.approve_material_version(
            material_version_id=(
                version.material_version_id
            ),
            owner_id="dipen-owner",
            reason="Resume approved.",
            occurred_at=(
                NOW + timedelta(seconds=6)
            ),
        )

        newer = CareerJobSnapshot.build(
            job_id=self.job.job_id,
            source_id=self.source.source_id,
            title="Cloud Engineer Revised",
            employer_name="Material Employer",
            location_text="Toronto, ON",
            work_mode="HYBRID",
            employment_type="Full-time",
            description_text=(
                "Revised cloud role."
            ),
            posted_at=(
                NOW - timedelta(hours=1)
            ),
            freshness_state="WITHIN_72H",
            normalized_text_sha256=("f" * 64),
            observed_at=(
                NOW + timedelta(seconds=10)
            ),
        )

        self.repository.persist_snapshot(newer)

        payload = self.job.model_dump(
            mode="python"
        )

        payload["current_snapshot_id"] = (
            newer.snapshot_id
        )
        payload["updated_at"] = (
            NOW + timedelta(seconds=11)
        )

        self.repository.upsert_job(
            CareerJobPosting.model_validate(
                payload
            )
        )

        result = (
            self.service
            .evaluate_application_approval(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertIn(
            "LATEST_VERSION_SNAPSHOT_STALE",
            {
                blocker.code
                for blocker in result.blockers
            },
        )

        with self.assertRaisesRegex(
            CareerMaterialRejected,
            "LATEST_VERSION_SNAPSHOT_STALE",
        ):
            self.service.approve_ready_application(
                application_id=(
                    self.application.application_id
                ),
                reason="Stale approval attempt.",
                occurred_at=(
                    NOW + timedelta(seconds=12)
                ),
            )


    def test_cockpit_read_domain_surface(
        self,
    ) -> None:
        application = (
            self.service
            .get_cockpit_application(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertEqual(
            application.application_id,
            self.application.application_id,
        )

        events = (
            self.service
            .list_cockpit_application_events(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertEqual(
            events,
            (),
        )

        readiness = (
            self.service
            .get_cockpit_application_readiness(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertFalse(
            readiness.ready
        )

        materials = (
            self.service
            .list_cockpit_application_materials(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertEqual(
            materials,
            (),
        )

    def test_cockpit_read_material_graph(
        self,
    ) -> None:
        material, version = (
            self._initial_version()
        )

        materials = (
            self.service
            .list_cockpit_application_materials(
                application_id=(
                    self.application.application_id
                )
            )
        )

        self.assertEqual(
            materials[-1].material_id,
            material.material_id,
        )

        versions = (
            self.service
            .list_cockpit_material_versions(
                material_id=material.material_id
            )
        )

        self.assertEqual(
            versions[-1].material_version_id,
            version.material_version_id,
        )

        events = (
            self.service
            .list_cockpit_material_events(
                material_version_id=(
                    version.material_version_id
                )
            )
        )

        self.assertEqual(
            events[0].event_kind,
            "CREATED",
        )

    def test_cockpit_read_unknown_resources_fail_closed(
        self,
    ) -> None:
        with self.assertRaises(KeyError):
            self.service.get_cockpit_application(
                application_id=(
                    "career-application-missing"
                )
            )

        with self.assertRaises(KeyError):
            (
                self.service
                .list_cockpit_material_versions(
                    material_id=(
                        "career-material-"
                        + "0" * 24
                    )
                )
            )

        with self.assertRaises(KeyError):
            (
                self.service
                .list_cockpit_material_events(
                    material_version_id=(
                        "career-material-version-"
                        + "0" * 24
                    )
                )
            )


    def test_cockpit_material_version_forces_owner_creator(
        self,
    ) -> None:
        material = self.service.create_material(
            application_id=(
                self.application.application_id
            ),
            material_kind="APPLICATION_NOTES",
            label="cockpit-owner-version",
            created_at=(
                NOW + timedelta(seconds=30)
            ),
        )

        version = (
            self.service
            .create_cockpit_material_version(
                material_id=material.material_id,
                source_snapshot_id=(
                    self.snapshot.snapshot_id
                ),
                content_format="MARKDOWN",
                content_text="Owner draft.",
                parent_material_version_id=None,
                profile_version="profile-http",
                occurred_at=(
                    NOW + timedelta(seconds=31)
                ),
            )
        )

        self.assertEqual(
            version.material_id,
            material.material_id,
        )
        self.assertEqual(
            version.created_by_kind,
            "OWNER",
        )
        self.assertEqual(
            version.created_by_id,
            "dipen-owner",
        )

    def test_cockpit_material_version_rejects_cross_material_parent(
        self,
    ) -> None:
        parent_material, parent_version = (
            self._initial_version()
        )

        other = self.service.create_material(
            application_id=(
                self.application.application_id
            ),
            material_kind="APPLICATION_NOTES",
            label="cross-material-target",
            created_at=(
                NOW + timedelta(seconds=30)
            ),
        )

        self.assertNotEqual(
            parent_material.material_id,
            other.material_id,
        )

        with self.assertRaisesRegex(
            CareerMaterialRejected,
            "does not belong",
        ):
            (
                self.service
                .create_cockpit_material_version(
                    material_id=other.material_id,
                    source_snapshot_id=(
                        self.snapshot.snapshot_id
                    ),
                    content_format="MARKDOWN",
                    content_text="Invalid child.",
                    parent_material_version_id=(
                        parent_version
                        .material_version_id
                    ),
                    profile_version=None,
                    occurred_at=(
                        NOW + timedelta(seconds=31)
                    ),
                )
            )

        self.assertEqual(
            self.repository.list_material_versions(
                other.material_id
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
