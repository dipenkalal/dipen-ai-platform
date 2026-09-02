from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from typing import Final

from career.repository import CareerRepository
from career.schemas import (
    CareerApplication,
    CareerApplicationActorKind,
    CareerApplicationApproval,
    CareerApplicationApprovalBlocker,
    CareerApplicationEvent,
    CareerApplicationMaterial,
    CareerApplicationMaterialEvent,
    CareerApplicationMaterialVersion,
    CareerApplicationReadiness,
    CareerApplicationReadinessBlocker,
    CareerApplicationState,
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerMaterialActorKind,
    CareerMaterialContentFormat,
    CareerMaterialCreatorKind,
    CareerMaterialKind,
    CareerMaterialProvenance,
)


class CareerDomainError(ValueError):
    """Base error for deterministic Career policy."""


class CareerAdmissionRejected(CareerDomainError):
    """Job/snapshot cannot enter verified Career truth."""


class CareerAuthorizationRejected(CareerDomainError):
    """Actor lacks authority for requested Career action."""


class CareerTransitionRejected(CareerDomainError):
    """Application lifecycle transition is illegal."""


class CareerMaterialRejected(CareerDomainError):
    """Material Lab operation violates frozen v2 policy."""


APPLICATION_TRANSITIONS: Final[
    dict[
        CareerApplicationState,
        frozenset[CareerApplicationState],
    ]
] = {
    "SHORTLISTED": frozenset(
        {
            "PREPARING",
            "WITHDRAWN",
            "CLOSED",
        }
    ),
    "PREPARING": frozenset(
        {
            "READY_FOR_REVIEW",
            "SHORTLISTED",
            "WITHDRAWN",
            "CLOSED",
        }
    ),
    "READY_FOR_REVIEW": frozenset(
        {
            "OWNER_APPROVED",
            "PREPARING",
            "WITHDRAWN",
            "CLOSED",
        }
    ),
    "OWNER_APPROVED": frozenset(
        {
            "APPLIED_CONFIRMED",
            "READY_FOR_REVIEW",
            "WITHDRAWN",
            "CLOSED",
        }
    ),
    "APPLIED_CONFIRMED": frozenset(
        {
            "INTERVIEW",
            "REJECTED",
            "WITHDRAWN",
            "OFFER",
            "CLOSED",
        }
    ),
    "INTERVIEW": frozenset(
        {
            "REJECTED",
            "WITHDRAWN",
            "OFFER",
            "CLOSED",
        }
    ),
    "REJECTED": frozenset(
        {
            "CLOSED",
        }
    ),
    "WITHDRAWN": frozenset(
        {
            "CLOSED",
        }
    ),
    "OFFER": frozenset(
        {
            "WITHDRAWN",
            "CLOSED",
        }
    ),
    "CLOSED": frozenset(),
}


DETERMINISTIC_SYSTEM_TRANSITIONS: Final[
    frozenset[
        tuple[
            CareerApplicationState,
            CareerApplicationState,
        ]
    ]
] = frozenset(
    {
        (
            "SHORTLISTED",
            "PREPARING",
        ),
        (
            "PREPARING",
            "READY_FOR_REVIEW",
        ),
    }
)


class CareerDomainService:
    """
    Deterministic policy owner above CareerRepository.

    This service grants no browser, network, submission,
    agent, Docker, systemd, Guardian, or Telegram authority.
    """

    def __init__(
        self,
        repository: CareerRepository,
    ) -> None:
        self.repository = repository

    def admit_verified_snapshot(
        self,
        *,
        snapshot: CareerJobSnapshot,
        evidence_link: CareerJobEvidenceLink,
    ) -> CareerJobPosting:
        job = self.repository.get_job(
            snapshot.job_id
        )

        if job is None:
            raise CareerAdmissionRejected(
                "Career snapshot references an "
                "unknown canonical job."
            )

        source = self.repository.get_source(
            snapshot.source_id
        )

        if source is None:
            raise CareerAdmissionRejected(
                "Career snapshot references an "
                "unknown Career source."
            )

        if source.state != "active":
            raise CareerAdmissionRejected(
                "Career source must be active for "
                "verified job admission."
            )

        if source.source_kind not in {
            "official_structured_ats",
            "official_employer_career",
        }:
            raise CareerAdmissionRejected(
                "Discovery-only sources cannot establish "
                "verified Career job truth."
            )

        if source.trust_tier not in {0, 1}:
            raise CareerAdmissionRejected(
                "Career source trust tier is not "
                "authoritative for admission."
            )

        if job.lifecycle_state != "ACTIVE":
            raise CareerAdmissionRejected(
                "Only ACTIVE canonical jobs may receive "
                "a current verified snapshot."
            )

        if job.verification_state not in {
            "RETRIEVED",
            "VERIFIED",
            "FRESHNESS_UNVERIFIED",
        }:
            raise CareerAdmissionRejected(
                "Job must have retrieved posting state "
                "before verified snapshot admission."
            )

        if snapshot.job_id != job.job_id:
            raise CareerAdmissionRejected(
                "Snapshot job identity mismatch."
            )

        if (
            snapshot.employer_name
            != job.employer_name
        ):
            raise CareerAdmissionRejected(
                "Snapshot employer does not match "
                "canonical job employer."
            )

        if evidence_link.job_id != job.job_id:
            raise CareerAdmissionRejected(
                "Evidence-link job identity mismatch."
            )

        if (
            evidence_link.snapshot_id
            != snapshot.snapshot_id
        ):
            raise CareerAdmissionRejected(
                "Evidence-link snapshot identity mismatch."
            )

        if evidence_link.evidence_role != "JOB_DETAIL":
            raise CareerAdmissionRejected(
                "Verified admission requires JOB_DETAIL "
                "retrieval evidence."
            )

        if snapshot.freshness_state == "EXPIRED":
            raise CareerAdmissionRejected(
                "Expired posting cannot be admitted "
                "as current Career truth."
            )

        projection = (
            self.repository
            .get_research_evidence_projection(
                evidence_link.research_evidence_id
            )
        )

        if projection is None:
            raise CareerAdmissionRejected(
                "Referenced Phase-16 retrieval evidence "
                "does not exist."
            )

        if projection["outcome"] != "succeeded":
            raise CareerAdmissionRejected(
                "Verified Career admission requires "
                "successful Phase-16 retrieval evidence."
            )

        evidence_hash = projection[
            "normalized_text_sha256"
        ]

        if evidence_hash is None:
            raise CareerAdmissionRejected(
                "Retrieval evidence lacks normalized "
                "content hash."
            )

        if (
            evidence_hash
            != snapshot.normalized_text_sha256
        ):
            raise CareerAdmissionRejected(
                "Career snapshot normalized content hash "
                "does not match retrieval evidence."
            )

        self.repository.persist_snapshot(
            snapshot
        )

        self.repository.persist_evidence_link(
            evidence_link
        )

        verification_state = (
            "FRESHNESS_UNVERIFIED"
            if snapshot.freshness_state == "UNKNOWN"
            else "VERIFIED"
        )

        payload = job.model_dump(
            mode="python"
        )

        payload.update(
            {
                "current_snapshot_id":
                    snapshot.snapshot_id,
                "verification_state":
                    verification_state,
                "last_seen_at":
                    max(
                        job.last_seen_at,
                        snapshot.observed_at,
                    ),
                "updated_at":
                    max(
                        job.updated_at,
                        snapshot.observed_at,
                    ),
            }
        )

        updated = CareerJobPosting.model_validate(
            payload
        )

        return self.repository.upsert_job(
            updated
        )

    def create_shortlisted_application(
        self,
        *,
        application_id: str,
        job_id: str,
        owner_id: str,
        reason: str,
        occurred_at: datetime,
        notes: str | None = None,
    ) -> CareerApplication:
        job = self.repository.get_job(job_id)

        if job is None:
            raise CareerAdmissionRejected(
                "Cannot shortlist unknown Career job."
            )

        if job.lifecycle_state != "ACTIVE":
            raise CareerAdmissionRejected(
                "Only ACTIVE jobs may be shortlisted."
            )

        if job.verification_state != "VERIFIED":
            raise CareerAdmissionRejected(
                "Shortlisting requires a VERIFIED job."
            )

        if job.current_snapshot_id is None:
            raise CareerAdmissionRejected(
                "Shortlisting requires a current "
                "verified job snapshot."
            )

        snapshot = self.repository.get_snapshot(
            job.current_snapshot_id
        )

        if snapshot is None:
            raise CareerAdmissionRejected(
                "Current Career snapshot is missing."
            )

        if snapshot.freshness_state != "WITHIN_72H":
            raise CareerAdmissionRejected(
                "Automatic Career shortlisting requires "
                "verified freshness within 72 hours."
            )

        application = CareerApplication(
            application_id=application_id,
            job_id=job.job_id,
            state="SHORTLISTED",
            notes=notes,
            created_at=occurred_at,
            updated_at=occurred_at,
        )

        event = CareerApplicationEvent.build(
            application_id=application_id,
            from_state=None,
            to_state="SHORTLISTED",
            actor_kind="OWNER",
            actor_id=owner_id,
            reason=reason,
            occurred_at=occurred_at,
        )

        return (
            self.repository
            .create_application_with_event(
                application,
                event,
            )
        )

    def transition_application(
        self,
        *,
        application_id: str,
        to_state: CareerApplicationState,
        actor_kind: CareerApplicationActorKind,
        actor_id: str,
        reason: str,
        occurred_at: datetime,
        evidence_id: str | None = None,
    ) -> CareerApplication:
        current = self.repository.get_application(
            application_id
        )

        if current is None:
            raise CareerTransitionRejected(
                "Unknown Career application."
            )

        if to_state == current.state:
            raise CareerTransitionRejected(
                "No-op Career application transition "
                "is not allowed."
            )

        allowed = APPLICATION_TRANSITIONS[
            current.state
        ]

        if to_state not in allowed:
            raise CareerTransitionRejected(
                "Illegal Career application transition: "
                f"{current.state} -> {to_state}"
            )

        pair = (
            current.state,
            to_state,
        )

        if (
            actor_kind == "DETERMINISTIC_SYSTEM"
            and pair
            not in DETERMINISTIC_SYSTEM_TRANSITIONS
        ):
            raise CareerAuthorizationRejected(
                "Deterministic system is not authorized "
                "for this application transition."
            )

        if (
            to_state == "OWNER_APPROVED"
            and actor_kind != "OWNER"
        ):
            raise CareerAuthorizationRejected(
                "OWNER_APPROVED is owner-only."
            )

        if (
            to_state == "APPLIED_CONFIRMED"
            and actor_kind != "OWNER"
        ):
            raise CareerAuthorizationRejected(
                "APPLIED_CONFIRMED is owner-only "
                "until a future submission broker "
                "is separately admitted."
            )

        payload = current.model_dump(
            mode="python"
        )

        payload["state"] = to_state
        payload["updated_at"] = occurred_at

        if to_state == "OWNER_APPROVED":
            payload[
                "owner_approved_at"
            ] = occurred_at

        if (
            current.state == "OWNER_APPROVED"
            and to_state == "READY_FOR_REVIEW"
        ):
            payload[
                "owner_approved_at"
            ] = None

        if to_state == "APPLIED_CONFIRMED":
            if current.owner_approved_at is None:
                raise CareerTransitionRejected(
                    "Application cannot be confirmed "
                    "as applied without prior owner "
                    "approval."
                )

            payload[
                "applied_confirmed_at"
            ] = occurred_at
            payload[
                "applied_confirmation_kind"
            ] = "OWNER_MANUAL"

        updated = CareerApplication.model_validate(
            payload
        )

        event = CareerApplicationEvent.build(
            application_id=application_id,
            from_state=current.state,
            to_state=to_state,
            actor_kind=actor_kind,
            actor_id=actor_id,
            reason=reason,
            evidence_id=evidence_id,
            occurred_at=occurred_at,
        )

        return (
            self.repository
            .transition_application_atomic(
                expected=current,
                updated=updated,
                event=event,
            )
        )

    def _require_material_application_state(
        self,
        *,
        material_id: str,
        required_state: CareerApplicationState,
    ) -> tuple[
        CareerApplicationMaterial,
        CareerApplication,
    ]:
        material = self.repository.get_material(
            material_id
        )

        if material is None:
            raise CareerMaterialRejected(
                "Unknown Career material."
            )

        application = self.repository.get_application(
            material.application_id
        )

        if application is None:
            raise CareerMaterialRejected(
                "Material application is missing."
            )

        if application.state != required_state:
            raise CareerMaterialRejected(
                "Material operation requires "
                f"application state {required_state}; "
                f"current state is {application.state}."
            )

        return material, application

    def _require_latest_material_version(
        self,
        version: CareerApplicationMaterialVersion,
    ) -> None:
        versions = self.repository.list_material_versions(
            version.material_id
        )

        if not versions:
            raise CareerMaterialRejected(
                "Material has no persisted versions."
            )

        latest = max(
            versions,
            key=lambda item: item.version_number,
        )

        if (
            latest.material_version_id
            != version.material_version_id
        ):
            raise CareerMaterialRejected(
                "Material review actions may only "
                "target the latest immutable version."
            )

    def create_material(
        self,
        *,
        application_id: str,
        material_kind: CareerMaterialKind,
        label: str,
        created_at: datetime,
    ) -> CareerApplicationMaterial:
        application = self.repository.get_application(
            application_id
        )

        if application is None:
            raise CareerMaterialRejected(
                "Unknown Career application."
            )

        if application.state != "PREPARING":
            raise CareerMaterialRejected(
                "New application materials may only "
                "be created while PREPARING."
            )

        material = CareerApplicationMaterial.build(
            application_id=application_id,
            material_kind=material_kind,
            label=label,
            created_at=created_at,
        )

        return self.repository.persist_material(
            material
        )

    def _build_material_provenance(
        self,
        *,
        application: CareerApplication,
        source_snapshot_id: str,
        created_by_kind: CareerMaterialCreatorKind,
        creation_mechanism: str,
        profile_version: str | None,
        model_provider: str | None,
        model_name: str | None,
        parent_material_version_id: str | None,
    ) -> CareerMaterialProvenance:
        snapshot = self.repository.get_snapshot(
            source_snapshot_id
        )

        if snapshot is None:
            raise CareerMaterialRejected(
                "Unknown source snapshot."
            )

        if snapshot.job_id != application.job_id:
            raise CareerMaterialRejected(
                "Source snapshot does not belong "
                "to application job."
            )

        job = self.repository.get_job(
            application.job_id
        )

        if job is None:
            raise CareerMaterialRejected(
                "Application job is missing."
            )

        if (
            job.current_snapshot_id
            != source_snapshot_id
        ):
            raise CareerMaterialRejected(
                "Material generation requires the "
                "job's current snapshot."
            )

        return CareerMaterialProvenance(
            application_id=application.application_id,
            job_id=application.job_id,
            snapshot_id=source_snapshot_id,
            profile_version=profile_version,
            generator_kind=created_by_kind,
            model_provider=model_provider,
            model_name=model_name,
            creation_mechanism=creation_mechanism,
            parent_material_version_id=(
                parent_material_version_id
            ),
            source_material_version_ids=(
                (
                    parent_material_version_id,
                )
                if parent_material_version_id
                else ()
            ),
        )

    def create_initial_material_version(
        self,
        *,
        material_id: str,
        source_snapshot_id: str,
        content_format: CareerMaterialContentFormat,
        content_text: str,
        created_by_kind: CareerMaterialCreatorKind,
        created_by_id: str,
        creation_mechanism: str,
        occurred_at: datetime,
        profile_version: str | None = None,
        model_provider: str | None = None,
        model_name: str | None = None,
    ) -> CareerApplicationMaterialVersion:
        material, application = (
            self._require_material_application_state(
                material_id=material_id,
                required_state="PREPARING",
            )
        )

        if self.repository.list_material_versions(
            material.material_id
        ):
            raise CareerMaterialRejected(
                "Initial material version requires "
                "an unversioned material."
            )

        provenance = self._build_material_provenance(
            application=application,
            source_snapshot_id=source_snapshot_id,
            created_by_kind=created_by_kind,
            creation_mechanism=creation_mechanism,
            profile_version=profile_version,
            model_provider=model_provider,
            model_name=model_name,
            parent_material_version_id=None,
        )

        version = CareerApplicationMaterialVersion.build(
            material_id=material.material_id,
            version_number=1,
            source_snapshot_id=source_snapshot_id,
            content_format=content_format,
            content_text=content_text,
            provenance=provenance,
            created_by_kind=created_by_kind,
            created_by_id=created_by_id,
            created_at=occurred_at,
        )

        event = CareerApplicationMaterialEvent.build(
            material_version_id=(
                version.material_version_id
            ),
            event_kind="CREATED",
            actor_kind="DAP_SYSTEM",
            actor_id="career-material-service",
            reason=(
                "Immutable material version created."
            ),
            occurred_at=occurred_at,
        )

        return (
            self.repository
            .create_material_version_with_event(
                version=version,
                event=event,
            )
        )

    def create_derived_material_version(
        self,
        *,
        parent_material_version_id: str,
        source_snapshot_id: str,
        content_format: CareerMaterialContentFormat,
        content_text: str,
        created_by_kind: CareerMaterialCreatorKind,
        created_by_id: str,
        creation_mechanism: str,
        occurred_at: datetime,
        profile_version: str | None = None,
        model_provider: str | None = None,
        model_name: str | None = None,
    ) -> CareerApplicationMaterialVersion:
        parent = self.repository.get_material_version(
            parent_material_version_id
        )

        if parent is None:
            raise CareerMaterialRejected(
                "Unknown parent material version."
            )

        material, application = (
            self._require_material_application_state(
                material_id=parent.material_id,
                required_state="PREPARING",
            )
        )

        self._require_latest_material_version(
            parent
        )

        provenance = self._build_material_provenance(
            application=application,
            source_snapshot_id=source_snapshot_id,
            created_by_kind=created_by_kind,
            creation_mechanism=creation_mechanism,
            profile_version=profile_version,
            model_provider=model_provider,
            model_name=model_name,
            parent_material_version_id=(
                parent.material_version_id
            ),
        )

        version = CareerApplicationMaterialVersion.build(
            material_id=material.material_id,
            version_number=(
                parent.version_number + 1
            ),
            source_snapshot_id=source_snapshot_id,
            parent_material_version_id=(
                parent.material_version_id
            ),
            content_format=content_format,
            content_text=content_text,
            provenance=provenance,
            created_by_kind=created_by_kind,
            created_by_id=created_by_id,
            created_at=occurred_at,
        )

        event = CareerApplicationMaterialEvent.build(
            material_version_id=(
                version.material_version_id
            ),
            event_kind="CREATED",
            actor_kind="DAP_SYSTEM",
            actor_id="career-material-service",
            reason=(
                "Derived immutable material "
                "version created."
            ),
            occurred_at=occurred_at,
        )

        return (
            self.repository
            .create_material_version_with_event(
                version=version,
                event=event,
            )
        )

    def mark_material_version_ready(
        self,
        *,
        material_version_id: str,
        actor_kind: CareerMaterialActorKind,
        actor_id: str,
        reason: str,
        occurred_at: datetime,
    ) -> CareerApplicationMaterialEvent:
        version = self.repository.get_material_version(
            material_version_id
        )

        if version is None:
            raise CareerMaterialRejected(
                "Unknown material version."
            )

        self._require_material_application_state(
            material_id=version.material_id,
            required_state="PREPARING",
        )

        self._require_latest_material_version(
            version
        )

        events = self.repository.list_material_events(
            material_version_id
        )

        kinds = {
            event.event_kind
            for event in events
        }

        if "CREATED" not in kinds:
            raise CareerMaterialRejected(
                "Material version lacks CREATED audit."
            )

        if kinds & {
            "MARKED_READY_FOR_REVIEW",
            "APPROVED",
            "REJECTED",
        }:
            raise CareerMaterialRejected(
                "Material version is already beyond "
                "draft readiness."
            )

        event = CareerApplicationMaterialEvent.build(
            material_version_id=material_version_id,
            event_kind="MARKED_READY_FOR_REVIEW",
            actor_kind=actor_kind,
            actor_id=actor_id,
            reason=reason,
            occurred_at=occurred_at,
        )

        return self.repository.persist_material_event(
            event
        )

    def _decide_material_version(
        self,
        *,
        material_version_id: str,
        decision: str,
        owner_id: str,
        reason: str,
        occurred_at: datetime,
    ) -> CareerApplicationMaterialEvent:
        if decision not in {
            "APPROVED",
            "REJECTED",
        }:
            raise CareerMaterialRejected(
                "Unsupported material review decision."
            )

        version = self.repository.get_material_version(
            material_version_id
        )

        if version is None:
            raise CareerMaterialRejected(
                "Unknown material version."
            )

        self._require_material_application_state(
            material_id=version.material_id,
            required_state="READY_FOR_REVIEW",
        )

        self._require_latest_material_version(
            version
        )

        events = self.repository.list_material_events(
            material_version_id
        )

        kinds = {
            event.event_kind
            for event in events
        }

        if "MARKED_READY_FOR_REVIEW" not in kinds:
            raise CareerMaterialRejected(
                "Owner review requires material "
                "version marked ready for review."
            )

        if kinds & {
            "APPROVED",
            "REJECTED",
        }:
            raise CareerMaterialRejected(
                "Material version already has an "
                "owner review decision."
            )

        event = CareerApplicationMaterialEvent.build(
            material_version_id=material_version_id,
            event_kind=decision,
            actor_kind="OWNER",
            actor_id=owner_id,
            reason=reason,
            occurred_at=occurred_at,
        )

        return self.repository.persist_material_event(
            event
        )

    def approve_material_version(
        self,
        *,
        material_version_id: str,
        owner_id: str,
        reason: str,
        occurred_at: datetime,
    ) -> CareerApplicationMaterialEvent:
        return self._decide_material_version(
            material_version_id=material_version_id,
            decision="APPROVED",
            owner_id=owner_id,
            reason=reason,
            occurred_at=occurred_at,
        )

    def reject_material_version(
        self,
        *,
        material_version_id: str,
        owner_id: str,
        reason: str,
        occurred_at: datetime,
    ) -> CareerApplicationMaterialEvent:
        return self._decide_material_version(
            material_version_id=material_version_id,
            decision="REJECTED",
            owner_id=owner_id,
            reason=reason,
            occurred_at=occurred_at,
        )

    def evaluate_application_readiness(
        self,
        *,
        application_id: str,
    ) -> CareerApplicationReadiness:
        application = self.repository.get_application(
            application_id
        )

        if application is None:
            raise CareerMaterialRejected(
                "Unknown Career application."
            )

        blockers: list[
            CareerApplicationReadinessBlocker
        ] = []

        if application.state != "PREPARING":
            blockers.append(
                CareerApplicationReadinessBlocker(
                    code="APPLICATION_NOT_PREPARING",
                )
            )

            return CareerApplicationReadiness(
                application_id=application_id,
                ready=False,
                blockers=tuple(blockers),
            )

        job = self.repository.get_job(
            application.job_id
        )

        if job is None:
            raise CareerMaterialRejected(
                "Application job is missing."
            )

        current_snapshot = None

        if job.current_snapshot_id is None:
            blockers.append(
                CareerApplicationReadinessBlocker(
                    code="CURRENT_SNAPSHOT_MISSING",
                )
            )
        else:
            current_snapshot = (
                self.repository.get_snapshot(
                    job.current_snapshot_id
                )
            )

            if current_snapshot is None:
                blockers.append(
                    CareerApplicationReadinessBlocker(
                        code="CURRENT_SNAPSHOT_MISSING",
                    )
                )
            elif (
                current_snapshot.job_id
                != application.job_id
            ):
                blockers.append(
                    CareerApplicationReadinessBlocker(
                        code="SNAPSHOT_JOB_MISMATCH",
                    )
                )

        materials = (
            self.repository
            .list_application_materials(
                application_id
            )
        )

        slots = {
            (
                material.material_kind,
                material.label,
            ): material
            for material in materials
        }

        primary_resume = slots.get(
            (
                "RESUME",
                "primary",
            )
        )

        if primary_resume is None:
            blockers.append(
                CareerApplicationReadinessBlocker(
                    code="PRIMARY_RESUME_MISSING",
                )
            )

        blocking_materials = []

        if primary_resume is not None:
            blocking_materials.append(
                primary_resume
            )

        primary_cover = slots.get(
            (
                "COVER_LETTER",
                "primary",
            )
        )

        if primary_cover is not None:
            blocking_materials.append(
                primary_cover
            )

        for material in blocking_materials:
            versions = (
                self.repository
                .list_material_versions(
                    material.material_id
                )
            )

            if not versions:
                blockers.append(
                    CareerApplicationReadinessBlocker(
                        code=(
                            "BLOCKING_MATERIAL_HAS_NO_VERSION"
                        ),
                        material_id=material.material_id,
                    )
                )

                continue

            latest = max(
                versions,
                key=lambda item: (
                    item.version_number
                ),
            )

            if (
                job.current_snapshot_id
                is not None
                and latest.source_snapshot_id
                != job.current_snapshot_id
            ):
                blockers.append(
                    CareerApplicationReadinessBlocker(
                        code=(
                            "LATEST_VERSION_SNAPSHOT_STALE"
                        ),
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            latest_snapshot = (
                self.repository.get_snapshot(
                    latest.source_snapshot_id
                )
            )

            if (
                latest_snapshot is None
                or latest_snapshot.job_id
                != application.job_id
            ):
                blockers.append(
                    CareerApplicationReadinessBlocker(
                        code="SNAPSHOT_JOB_MISMATCH",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            events = (
                self.repository
                .list_material_events(
                    latest.material_version_id
                )
            )

            event_kinds = {
                event.event_kind
                for event in events
            }

            if "CREATED" not in event_kinds:
                blockers.append(
                    CareerApplicationReadinessBlocker(
                        code="CREATED_EVENT_MISSING",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            if (
                "MARKED_READY_FOR_REVIEW"
                not in event_kinds
            ):
                blockers.append(
                    CareerApplicationReadinessBlocker(
                        code="READY_EVENT_MISSING",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            if "REJECTED" in event_kinds:
                blockers.append(
                    CareerApplicationReadinessBlocker(
                        code="LATEST_VERSION_REJECTED",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

        return CareerApplicationReadiness(
            application_id=application_id,
            ready=not blockers,
            blockers=tuple(blockers),
        )

    def advance_preparing_application_to_review(
        self,
        *,
        application_id: str,
        reason: str,
        occurred_at: datetime,
    ) -> CareerApplication:
        readiness = (
            self.evaluate_application_readiness(
                application_id=application_id
            )
        )

        if not readiness.ready:
            codes = ",".join(
                blocker.code
                for blocker in readiness.blockers
            )

            raise CareerMaterialRejected(
                "Application is not ready for "
                f"review: {codes}"
            )

        return self.transition_application(
            application_id=application_id,
            to_state="READY_FOR_REVIEW",
            actor_kind="DETERMINISTIC_SYSTEM",
            actor_id=(
                "career-material-readiness"
            ),
            reason=reason,
            occurred_at=occurred_at,
        )

    def create_cockpit_application(
        self,
        *,
        job_id: str,
        reason: str,
        occurred_at: datetime,
        notes: str | None = None,
    ) -> CareerApplication:
        job = self.repository.get_job(job_id)

        if job is None:
            raise CareerAdmissionRejected(
                "Cannot create Cockpit workspace "
                "for unknown Career job."
            )

        if job.lifecycle_state != "ACTIVE":
            raise CareerAdmissionRejected(
                "Only ACTIVE jobs may enter "
                "Career Cockpit."
            )

        if job.verification_state != "VERIFIED":
            raise CareerAdmissionRejected(
                "Career Cockpit requires "
                "a VERIFIED job."
            )

        if job.current_snapshot_id is None:
            raise CareerAdmissionRejected(
                "Career Cockpit requires a current "
                "verified job snapshot."
            )

        snapshot = self.repository.get_snapshot(
            job.current_snapshot_id
        )

        if snapshot is None:
            raise CareerAdmissionRejected(
                "Current Career snapshot is missing."
            )

        if snapshot.freshness_state != "WITHIN_72H":
            raise CareerAdmissionRejected(
                "Career Cockpit creation requires "
                "verified freshness within 72 hours."
            )

        application_id = (
            "career-application-"
            + uuid4().hex
        )

        application = CareerApplication(
            application_id=application_id,
            job_id=job.job_id,
            state="SHORTLISTED",
            notes=notes,
            created_at=occurred_at,
            updated_at=occurred_at,
        )

        event = CareerApplicationEvent.build(
            application_id=application_id,
            from_state=None,
            to_state="SHORTLISTED",
            actor_kind="OWNER",
            actor_id="dipen-owner",
            reason=reason,
            occurred_at=occurred_at,
        )

        return (
            self.repository
            .create_application_with_event_once_per_job(
                application,
                event,
            )
        )

    def evaluate_application_approval(
        self,
        *,
        application_id: str,
    ) -> CareerApplicationApproval:
        application = self.repository.get_application(
            application_id
        )

        if application is None:
            raise CareerMaterialRejected(
                "Unknown Career application."
            )

        blockers: list[
            CareerApplicationApprovalBlocker
        ] = []

        if application.state != "READY_FOR_REVIEW":
            blockers.append(
                CareerApplicationApprovalBlocker(
                    code=(
                        "APPLICATION_NOT_READY_FOR_REVIEW"
                    ),
                )
            )

            return CareerApplicationApproval(
                application_id=application_id,
                approved=False,
                blockers=tuple(blockers),
            )

        job = self.repository.get_job(
            application.job_id
        )

        if job is None:
            raise CareerMaterialRejected(
                "Application job is missing."
            )

        if job.current_snapshot_id is None:
            blockers.append(
                CareerApplicationApprovalBlocker(
                    code="CURRENT_SNAPSHOT_MISSING",
                )
            )
        else:
            current_snapshot = (
                self.repository.get_snapshot(
                    job.current_snapshot_id
                )
            )

            if current_snapshot is None:
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code="CURRENT_SNAPSHOT_MISSING",
                    )
                )
            elif (
                current_snapshot.job_id
                != application.job_id
            ):
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code="SNAPSHOT_JOB_MISMATCH",
                    )
                )

        materials = (
            self.repository
            .list_application_materials(
                application_id
            )
        )

        slots = {
            (
                material.material_kind,
                material.label,
            ): material
            for material in materials
        }

        primary_resume = slots.get(
            ("RESUME", "primary")
        )

        if primary_resume is None:
            blockers.append(
                CareerApplicationApprovalBlocker(
                    code="PRIMARY_RESUME_MISSING",
                )
            )

        blocking_materials = []

        if primary_resume is not None:
            blocking_materials.append(
                primary_resume
            )

        primary_cover = slots.get(
            ("COVER_LETTER", "primary")
        )

        if primary_cover is not None:
            blocking_materials.append(
                primary_cover
            )

        for material in blocking_materials:
            versions = (
                self.repository
                .list_material_versions(
                    material.material_id
                )
            )

            if not versions:
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code=(
                            "BLOCKING_MATERIAL_HAS_NO_VERSION"
                        ),
                        material_id=material.material_id,
                    )
                )
                continue

            latest = max(
                versions,
                key=lambda item: item.version_number,
            )

            if (
                job.current_snapshot_id is not None
                and latest.source_snapshot_id
                != job.current_snapshot_id
            ):
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code=(
                            "LATEST_VERSION_SNAPSHOT_STALE"
                        ),
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            latest_snapshot = (
                self.repository.get_snapshot(
                    latest.source_snapshot_id
                )
            )

            if (
                latest_snapshot is None
                or latest_snapshot.job_id
                != application.job_id
            ):
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code="SNAPSHOT_JOB_MISMATCH",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            events = (
                self.repository
                .list_material_events(
                    latest.material_version_id
                )
            )

            kinds = {
                event.event_kind
                for event in events
            }

            if "CREATED" not in kinds:
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code="CREATED_EVENT_MISSING",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            if (
                "MARKED_READY_FOR_REVIEW"
                not in kinds
            ):
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code="READY_EVENT_MISSING",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            if "APPROVED" not in kinds:
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code="APPROVED_EVENT_MISSING",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

            if "REJECTED" in kinds:
                blockers.append(
                    CareerApplicationApprovalBlocker(
                        code="LATEST_VERSION_REJECTED",
                        material_id=material.material_id,
                        material_version_id=(
                            latest.material_version_id
                        ),
                    )
                )

        return CareerApplicationApproval(
            application_id=application_id,
            approved=not blockers,
            blockers=tuple(blockers),
        )

    def approve_ready_application(
        self,
        *,
        application_id: str,
        reason: str,
        occurred_at: datetime,
    ) -> CareerApplication:
        approval = (
            self.evaluate_application_approval(
                application_id=application_id
            )
        )

        if not approval.approved:
            codes = ",".join(
                blocker.code
                for blocker in approval.blockers
            )

            raise CareerMaterialRejected(
                "Application package is not "
                f"owner-approved: {codes}"
            )

        return self.transition_application(
            application_id=application_id,
            to_state="OWNER_APPROVED",
            actor_kind="OWNER",
            actor_id="dipen-owner",
            reason=reason,
            occurred_at=occurred_at,
        )

    def get_cockpit_application(
        self,
        *,
        application_id: str,
    ) -> CareerApplication:
        application = self.repository.get_application(
            application_id
        )

        if application is None:
            raise KeyError(
                "Career application was not found."
            )

        return application

    def list_cockpit_application_events(
        self,
        *,
        application_id: str,
    ) -> tuple[CareerApplicationEvent, ...]:
        self.get_cockpit_application(
            application_id=application_id
        )

        return tuple(
            self.repository
            .list_application_events(
                application_id
            )
        )

    def get_cockpit_application_readiness(
        self,
        *,
        application_id: str,
    ) -> CareerApplicationReadiness:
        self.get_cockpit_application(
            application_id=application_id
        )

        return (
            self.evaluate_application_readiness(
                application_id=application_id
            )
        )

    def list_cockpit_application_materials(
        self,
        *,
        application_id: str,
    ) -> tuple[
        CareerApplicationMaterial,
        ...,
    ]:
        self.get_cockpit_application(
            application_id=application_id
        )

        return tuple(
            self.repository
            .list_application_materials(
                application_id
            )
        )

    def list_cockpit_material_versions(
        self,
        *,
        material_id: str,
    ) -> tuple[
        CareerApplicationMaterialVersion,
        ...,
    ]:
        material = self.repository.get_material(
            material_id
        )

        if material is None:
            raise KeyError(
                "Career application material "
                "was not found."
            )

        return tuple(
            self.repository
            .list_material_versions(
                material_id
            )
        )

    def list_cockpit_material_events(
        self,
        *,
        material_version_id: str,
    ) -> tuple[
        CareerApplicationMaterialEvent,
        ...,
    ]:
        version = (
            self.repository
            .get_material_version(
                material_version_id
            )
        )

        if version is None:
            raise KeyError(
                "Career material version "
                "was not found."
            )

        return tuple(
            self.repository
            .list_material_events(
                material_version_id
            )
        )

    def create_cockpit_material_version(
        self,
        *,
        material_id: str,
        source_snapshot_id: str,
        content_format: CareerMaterialContentFormat,
        content_text: str,
        parent_material_version_id: str | None,
        occurred_at: datetime,
        profile_version: str | None = None,
    ) -> CareerApplicationMaterialVersion:
        material = self.repository.get_material(
            material_id
        )

        if material is None:
            raise CareerMaterialRejected(
                "Unknown Career application material."
            )

        common = {
            "source_snapshot_id":
                source_snapshot_id,
            "content_format":
                content_format,
            "content_text":
                content_text,
            "created_by_kind":
                "OWNER",
            "created_by_id":
                "dipen-owner",
            "creation_mechanism":
                "career-cockpit-owner",
            "occurred_at":
                occurred_at,
            "profile_version":
                profile_version,
        }

        if parent_material_version_id is None:
            return self.create_initial_material_version(
                material_id=material.material_id,
                **common,
            )

        parent = self.repository.get_material_version(
            parent_material_version_id
        )

        if parent is None:
            raise CareerMaterialRejected(
                "Unknown parent material version."
            )

        if parent.material_id != material.material_id:
            raise CareerMaterialRejected(
                "Parent material version does not "
                "belong to requested material."
            )

        return self.create_derived_material_version(
            parent_material_version_id=(
                parent.material_version_id
            ),
            **common,
        )
