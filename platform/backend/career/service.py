from __future__ import annotations

from datetime import datetime
from typing import Final

from career.repository import CareerRepository
from career.schemas import (
    CareerApplication,
    CareerApplicationActorKind,
    CareerApplicationEvent,
    CareerApplicationState,
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
)


class CareerDomainError(ValueError):
    """Base error for deterministic Career policy."""


class CareerAdmissionRejected(CareerDomainError):
    """Job/snapshot cannot enter verified Career truth."""


class CareerAuthorizationRejected(CareerDomainError):
    """Actor lacks authority for requested Career action."""


class CareerTransitionRejected(CareerDomainError):
    """Application lifecycle transition is illegal."""


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
