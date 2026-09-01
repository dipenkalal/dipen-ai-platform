from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from career.ingestion import (
    CareerVerifiedIngestionResult,
)
from career.repository import CareerRepository
from career.schemas import (
    CareerFreshnessState,
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerLifecycleState,
)


FRESHNESS_WINDOW = timedelta(
    hours=72
)


class CareerEligibilityError(ValueError):
    """Verified Career truth cannot be safely adjudicated."""


@dataclass(frozen=True)
class CareerEligibilityDecision:
    freshness_state: CareerFreshnessState
    lifecycle_state: CareerLifecycleState
    surface_eligible: bool
    reason: str


@dataclass(frozen=True)
class CareerEligibilityResult:
    job: CareerJobPosting
    snapshot: CareerJobSnapshot
    evidence_link: CareerJobEvidenceLink
    decision: CareerEligibilityDecision


def _require_aware(
    value: datetime | None,
    *,
    label: str,
) -> None:
    if value is None:
        return

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise CareerEligibilityError(
            f"{label} must be timezone-aware"
        )


def classify_verified_freshness(
    *,
    posted_at: datetime | None,
    closing_at: datetime | None,
    observed_at: datetime,
) -> CareerEligibilityDecision:
    """
    Deterministically adjudicate freshness/lifecycle.

    This function performs no persistence and owns no network
    or application authority.
    """

    _require_aware(
        posted_at,
        label="posted_at",
    )
    _require_aware(
        closing_at,
        label="closing_at",
    )
    _require_aware(
        observed_at,
        label="observed_at",
    )

    if (
        posted_at is not None
        and closing_at is not None
        and closing_at < posted_at
    ):
        raise CareerEligibilityError(
            "closing_at cannot precede posted_at"
        )

    if (
        posted_at is not None
        and posted_at > observed_at
    ):
        raise CareerEligibilityError(
            "future posted_at must fail closed"
        )

    if (
        closing_at is not None
        and closing_at <= observed_at
    ):
        return CareerEligibilityDecision(
            freshness_state="EXPIRED",
            lifecycle_state="EXPIRED",
            surface_eligible=False,
            reason="CLOSING_TIME_REACHED",
        )

    if posted_at is None:
        return CareerEligibilityDecision(
            freshness_state="UNKNOWN",
            lifecycle_state="ACTIVE",
            surface_eligible=False,
            reason="POSTED_AT_UNPROVEN",
        )

    age = (
        observed_at
        - posted_at
    )

    if age <= FRESHNESS_WINDOW:
        return CareerEligibilityDecision(
            freshness_state="WITHIN_72H",
            lifecycle_state="ACTIVE",
            surface_eligible=True,
            reason="POSTED_WITHIN_72H",
        )

    return CareerEligibilityDecision(
        freshness_state="OLDER_THAN_72H",
        lifecycle_state="ACTIVE",
        surface_eligible=False,
        reason="POSTED_OLDER_THAN_72H",
    )


def _same_observation_except_freshness(
    left: CareerJobSnapshot,
    right: CareerJobSnapshot,
) -> bool:
    left_payload = left.model_dump(
        mode="python",
        exclude={
            "snapshot_id",
            "freshness_state",
        },
    )

    right_payload = right.model_dump(
        mode="python",
        exclude={
            "snapshot_id",
            "freshness_state",
        },
    )

    return (
        left_payload
        == right_payload
    )


def _adjudicated_snapshot(
    *,
    snapshot: CareerJobSnapshot,
    freshness_state: CareerFreshnessState,
) -> CareerJobSnapshot:
    if (
        snapshot.freshness_state
        == freshness_state
    ):
        return snapshot

    return CareerJobSnapshot.build(
        job_id=snapshot.job_id,
        source_id=snapshot.source_id,
        title=snapshot.title,
        employer_name=(
            snapshot.employer_name
        ),
        description_text=(
            snapshot.description_text
        ),
        freshness_state=(
            freshness_state
        ),
        normalized_text_sha256=(
            snapshot
            .normalized_text_sha256
        ),
        observed_at=(
            snapshot.observed_at
        ),
        location_text=(
            snapshot.location_text
        ),
        work_mode=snapshot.work_mode,
        employment_type=(
            snapshot.employment_type
        ),
        posted_at=snapshot.posted_at,
        closing_at=snapshot.closing_at,
        salary_text=snapshot.salary_text,
        requirements=snapshot.requirements,
    )


def adjudicate_verified_ingestion(
    repository: CareerRepository,
    result: CareerVerifiedIngestionResult,
) -> CareerEligibilityResult:
    """
    Bridge sealed VERIFIED ingestion into lifecycle/freshness
    truth without mutating immutable snapshot content.
    """

    job = repository.get_job(
        result.job_id
    )

    if job is None:
        raise CareerEligibilityError(
            "verified ingestion job is missing"
        )

    if (
        job.verification_state
        != "VERIFIED"
    ):
        raise CareerEligibilityError(
            "eligibility requires VERIFIED job truth"
        )

    ingested_snapshot = (
        repository.get_snapshot(
            result.snapshot_id
        )
    )

    if ingested_snapshot is None:
        raise CareerEligibilityError(
            "verified ingestion snapshot is missing"
        )

    if (
        ingested_snapshot.job_id
        != job.job_id
    ):
        raise CareerEligibilityError(
            "ingested snapshot job mismatch"
        )

    original_link = (
        repository.get_evidence_link(
            result.evidence_link_id
        )
    )

    if original_link is None:
        raise CareerEligibilityError(
            "verified ingestion evidence link is missing"
        )

    if (
        original_link.job_id
        != job.job_id
        or original_link.snapshot_id
        != ingested_snapshot.snapshot_id
        or original_link.evidence_role
        != "JOB_DETAIL"
    ):
        raise CareerEligibilityError(
            "verified ingestion evidence binding is invalid"
        )

    if job.current_snapshot_id is None:
        raise CareerEligibilityError(
            "verified job has no current snapshot"
        )

    current = repository.get_snapshot(
        job.current_snapshot_id
    )

    if current is None:
        raise CareerEligibilityError(
            "current Career snapshot is missing"
        )

    if (
        current.snapshot_id
        != ingested_snapshot.snapshot_id
        and not _same_observation_except_freshness(
            current,
            ingested_snapshot,
        )
    ):
        raise CareerEligibilityError(
            "current snapshot diverged from verified ingestion"
        )

    decision = (
        classify_verified_freshness(
            posted_at=current.posted_at,
            closing_at=current.closing_at,
            observed_at=current.observed_at,
        )
    )

    target_snapshot = (
        _adjudicated_snapshot(
            snapshot=current,
            freshness_state=(
                decision.freshness_state
            ),
        )
    )

    if (
        target_snapshot.snapshot_id
        != current.snapshot_id
    ):
        target_snapshot = (
            repository.persist_snapshot(
                target_snapshot
            )
        )

    if (
        target_snapshot.snapshot_id
        == original_link.snapshot_id
    ):
        target_link = original_link

    else:
        target_link = (
            CareerJobEvidenceLink.build(
                job_id=job.job_id,
                snapshot_id=(
                    target_snapshot
                    .snapshot_id
                ),
                research_evidence_id=(
                    original_link
                    .research_evidence_id
                ),
                evidence_role="FRESHNESS",
                linked_at=(
                    target_snapshot
                    .observed_at
                ),
            )
        )

        target_link = (
            repository
            .persist_evidence_link(
                target_link
            )
        )

    payload = job.model_dump(
        mode="python"
    )

    payload.update(
        {
            "current_snapshot_id":
                target_snapshot.snapshot_id,

            "lifecycle_state":
                decision.lifecycle_state,

            "updated_at":
                max(
                    job.updated_at,
                    target_snapshot.observed_at,
                ),
        }
    )

    updated_job = (
        CareerJobPosting
        .model_validate(
            payload
        )
    )

    if updated_job != job:
        updated_job = (
            repository.upsert_job(
                updated_job
            )
        )

    return CareerEligibilityResult(
        job=updated_job,
        snapshot=target_snapshot,
        evidence_link=target_link,
        decision=decision,
    )
