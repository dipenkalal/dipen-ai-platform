from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from career.connectors.contracts import (
    CareerDiscoveryCandidate,
)
from career.repository import CareerRepository
from career.schemas import (
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerSource,
    CareerWorkMode,
)


ResolvedCareerProvider = Literal[
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "workday",
]

CareerIngestionRoute = Literal[
    "PROVIDER_SPECIFIC_CONNECTOR",
    "GENERIC_PHASE16_FALLBACK",
]


_PROVIDER_SPECIFIC = frozenset(
    {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
    }
)


class CareerVerifiedIngestionError(
    RuntimeError
):
    """Fail-closed verified-ingestion error."""


def _require_aware(
    value: datetime | None,
    field_name: str,
) -> None:

    if value is None:
        return

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )


def _canonical_digest(
    payload: object,
) -> str:

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _stable_id(
    prefix: str,
    payload: object,
) -> str:

    return (
        prefix
        + "-"
        + _canonical_digest(
            payload
        )[:24]
    )


def _https_origin(
    value: str,
) -> str:

    parsed = urlsplit(
        value
    )

    if (
        parsed.scheme.lower()
        != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise CareerVerifiedIngestionError(
            "Verified Career URL must use "
            "credential-free HTTPS."
        )

    try:
        port = parsed.port
    except ValueError as error:
        raise CareerVerifiedIngestionError(
            "Verified Career URL contains "
            "an invalid port."
        ) from error

    if port not in {
        None,
        443,
    }:
        raise CareerVerifiedIngestionError(
            "Verified Career URL may only "
            "use HTTPS port 443."
        )

    return (
        "https://"
        + parsed.hostname.lower()
    )


class CareerVerifiedJobDetail(BaseModel):
    """
    Evidence-bound job-detail projection supplied to
    the offline Career ingestion layer.

    The object carries no network, scoring, shortlist,
    application, or freshness-verification authority.
    """

    model_config = ConfigDict(
        frozen=True
    )

    research_evidence_id: str = Field(
        pattern=(
            r"^research-retrieval-"
            r"[0-9a-f]{24}$"
        )
    )

    canonical_job_url: str = Field(
        min_length=8,
        max_length=4000,
    )

    canonical_apply_url: str | None = Field(
        default=None,
        max_length=4000,
    )

    title: str = Field(
        min_length=1,
        max_length=500,
    )

    employer_name: str = Field(
        min_length=1,
        max_length=300,
    )

    description_text: str = Field(
        min_length=1
    )

    normalized_text_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    observed_at: datetime

    location_text: str | None = Field(
        default=None,
        max_length=500,
    )

    work_mode: CareerWorkMode | None = None

    employment_type: str | None = Field(
        default=None,
        max_length=200,
    )

    posted_at: datetime | None = None

    closing_at: datetime | None = None

    salary_text: str | None = None

    requirements: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    metadata_is_job_truth_without_evidence: Literal[
        False
    ] = False

    freshness_verified: Literal[
        False
    ] = False

    scoring_authority_granted: Literal[
        False
    ] = False

    shortlist_authority_granted: Literal[
        False
    ] = False

    application_authority_granted: Literal[
        False
    ] = False

    @model_validator(
        mode="after"
    )
    def validate_detail(
        self,
    ) -> CareerVerifiedJobDetail:

        for name in (
            "observed_at",
            "posted_at",
            "closing_at",
        ):

            _require_aware(
                getattr(
                    self,
                    name,
                ),
                name,
            )

        for name in (
            "canonical_job_url",
            "title",
            "employer_name",
            "description_text",
        ):

            value = getattr(
                self,
                name,
            )

            if value != value.strip():
                raise ValueError(
                    f"{name} must already be normalized"
                )

        _https_origin(
            self.canonical_job_url
        )

        if (
            self.canonical_apply_url
            is not None
        ):
            if (
                self.canonical_apply_url
                != self.canonical_apply_url.strip()
            ):
                raise ValueError(
                    "canonical_apply_url must "
                    "already be normalized"
                )

            _https_origin(
                self.canonical_apply_url
            )

        return self


class CareerVerifiedIngestionResult(
    BaseModel
):

    model_config = ConfigDict(
        frozen=True
    )

    provider_kind: ResolvedCareerProvider

    route_kind: CareerIngestionRoute

    candidate_id: str

    source_id: str

    job_id: str

    snapshot_id: str

    evidence_link_id: str

    verification_state: Literal[
        "VERIFIED"
    ] = "VERIFIED"

    freshness_state: Literal[
        "UNKNOWN"
    ] = "UNKNOWN"

    fit_scoring_performed: Literal[
        False
    ] = False

    shortlist_performed: Literal[
        False
    ] = False

    application_submitted: Literal[
        False
    ] = False


class CareerVerifiedIngestionService:
    """
    Reconcile evidence-bound job detail into Career
    persistence.

    This layer owns no network transport and grants no
    scoring, shortlist, or application authority.
    """

    def __init__(
        self,
        repository: CareerRepository,
    ) -> None:

        self._repository = repository

    def ingest_verified_candidate(
        self,
        *,
        candidate: CareerDiscoveryCandidate,
        detail: CareerVerifiedJobDetail | None,
        provider_kind: ResolvedCareerProvider | str,
        route_kind: CareerIngestionRoute | str,
    ) -> CareerVerifiedIngestionResult:

        if detail is None:
            raise CareerVerifiedIngestionError(
                "Candidate-only ingestion may not "
                "claim VERIFIED state."
            )

        self._validate_candidate_boundary(
            candidate
        )

        provider = self._validate_route(
            candidate=candidate,
            provider_kind=provider_kind,
            route_kind=route_kind,
        )

        self._validate_detail_binding(
            candidate=candidate,
            detail=detail,
        )

        self._validate_existing_evidence(
            detail
        )

        source = self._build_source(
            candidate=candidate,
            detail=detail,
            provider_kind=provider,
        )

        stored_source = (
            self._repository.upsert_source(
                source
            )
        )

        job_id = self._job_id(
            candidate=candidate,
            provider_kind=provider,
        )

        existing_job = (
            self._repository.get_job(
                job_id
            )
        )

        baseline_job = (
            self._build_baseline_job(
                candidate=candidate,
                detail=detail,
                existing=existing_job,
                job_id=job_id,
            )
        )

        self._repository.upsert_job(
            baseline_job
        )

        snapshot = (
            self._reconcile_snapshot(
                candidate=candidate,
                detail=detail,
                source_id=(
                    stored_source.source_id
                ),
                job_id=job_id,
                existing_job=existing_job,
            )
        )

        evidence_link = (
            CareerJobEvidenceLink.build(
                job_id=job_id,
                snapshot_id=(
                    snapshot.snapshot_id
                ),
                research_evidence_id=(
                    detail.research_evidence_id
                ),
                evidence_role="JOB_DETAIL",
                linked_at=detail.observed_at,
            )
        )

        stored_link = (
            self._repository
            .persist_evidence_link(
                evidence_link
            )
        )

        finalized = self._finalize_verified_job(
            baseline=baseline_job,
            snapshot=snapshot,
            detail=detail,
        )

        stored_job = (
            self._repository.upsert_job(
                finalized
            )
        )

        if (
            stored_job.verification_state
            != "VERIFIED"
        ):
            raise CareerVerifiedIngestionError(
                "Verified Career ingestion did not "
                "persist VERIFIED state."
            )

        if (
            stored_job.current_snapshot_id
            != snapshot.snapshot_id
        ):
            raise CareerVerifiedIngestionError(
                "Verified Career job current snapshot "
                "does not match reconciled snapshot."
            )

        return CareerVerifiedIngestionResult(
            provider_kind=provider,
            route_kind=route_kind,
            candidate_id=(
                candidate.candidate_id
            ),
            source_id=(
                stored_source.source_id
            ),
            job_id=stored_job.job_id,
            snapshot_id=(
                snapshot.snapshot_id
            ),
            evidence_link_id=(
                stored_link.link_id
            ),
        )

    @staticmethod
    def _validate_candidate_boundary(
        candidate: CareerDiscoveryCandidate,
    ) -> None:

        if candidate.metadata_is_job_truth:
            raise CareerVerifiedIngestionError(
                "Discovery candidate metadata may "
                "not be treated as job truth."
            )

        if candidate.freshness_verified:
            raise CareerVerifiedIngestionError(
                "Discovery candidate may not carry "
                "verified freshness."
            )

        if candidate.eligible_for_scoring:
            raise CareerVerifiedIngestionError(
                "Discovery candidate may not grant "
                "scoring authority."
            )

        if candidate.eligible_for_shortlist:
            raise CareerVerifiedIngestionError(
                "Discovery candidate may not grant "
                "shortlist authority."
            )

        if (
            candidate
            .application_authority_granted
        ):
            raise CareerVerifiedIngestionError(
                "Discovery candidate may not grant "
                "application authority."
            )

    @staticmethod
    def _validate_route(
        *,
        candidate: CareerDiscoveryCandidate,
        provider_kind: str,
        route_kind: str,
    ) -> ResolvedCareerProvider:

        allowed_providers = (
            _PROVIDER_SPECIFIC
            | {
                "workday",
            }
        )

        if (
            provider_kind
            not in allowed_providers
        ):
            raise CareerVerifiedIngestionError(
                "Unknown Career provider route "
                "must fail closed."
            )

        if (
            provider_kind
            in _PROVIDER_SPECIFIC
        ):

            if (
                route_kind
                != "PROVIDER_SPECIFIC_CONNECTOR"
            ):
                raise CareerVerifiedIngestionError(
                    "Provider-specific Career source "
                    "must use provider-specific route."
                )

            if (
                candidate.connector_kind
                != provider_kind
            ):
                raise CareerVerifiedIngestionError(
                    "Candidate connector kind does not "
                    "match resolved provider."
                )

        elif provider_kind == "workday":

            if (
                route_kind
                != "GENERIC_PHASE16_FALLBACK"
            ):
                raise CareerVerifiedIngestionError(
                    "Workday must use the frozen "
                    "generic Phase-16 fallback."
                )

            if (
                candidate.connector_kind
                not in {
                    "workday",
                    "generic_employer",
                }
            ):
                raise CareerVerifiedIngestionError(
                    "Workday fallback candidate "
                    "connector identity is invalid."
                )

        return provider_kind  # type: ignore[return-value]

    @staticmethod
    def _validate_detail_binding(
        *,
        candidate: CareerDiscoveryCandidate,
        detail: CareerVerifiedJobDetail,
    ) -> None:

        if (
            detail.canonical_job_url
            != candidate.detail_url
        ):
            raise CareerVerifiedIngestionError(
                "Evidence-bound job URL does not "
                "match discovery candidate detail URL."
            )

        if (
            detail.employer_name
            != candidate.employer_name
        ):
            raise CareerVerifiedIngestionError(
                "Evidence-bound employer does not "
                "match discovery candidate employer."
            )

    def _validate_existing_evidence(
        self,
        detail: CareerVerifiedJobDetail,
    ) -> None:

        projection = (
            self._repository
            .get_research_evidence_projection(
                detail.research_evidence_id
            )
        )

        if projection is None:
            raise CareerVerifiedIngestionError(
                "Verified state requires existing "
                "Phase-16 research evidence."
            )

        if (
            projection.get("outcome")
            != "succeeded"
        ):
            raise CareerVerifiedIngestionError(
                "Verified state requires successful "
                "Phase-16 research evidence."
            )

        if (
            projection.get(
                "normalized_text_sha256"
            )
            != detail.normalized_text_sha256
        ):
            raise CareerVerifiedIngestionError(
                "Evidence normalized-content hash "
                "does not match verified job detail."
            )

        if (
            projection.get("final_url")
            != detail.canonical_job_url
        ):
            raise CareerVerifiedIngestionError(
                "Evidence final URL does not match "
                "verified job detail URL."
            )

    @staticmethod
    def _source_id(
        *,
        candidate: CareerDiscoveryCandidate,
        detail: CareerVerifiedJobDetail,
        provider_kind: str,
    ) -> str:

        payload = {
            "provider_kind":
                provider_kind,

            "connector_kind":
                candidate.connector_kind,

            "employer_name":
                candidate.employer_name,

            "canonical_base_url":
                _https_origin(
                    detail.canonical_job_url
                ),
        }

        return _stable_id(
            "career-source",
            payload,
        )

    @staticmethod
    def _job_id(
        *,
        candidate: CareerDiscoveryCandidate,
        provider_kind: str,
    ) -> str:

        payload = {
            "provider_kind":
                provider_kind,

            "employer_name":
                candidate.employer_name,

            "source_job_id":
                candidate.source_job_id,

            "detail_url":
                candidate.detail_url,
        }

        return _stable_id(
            "career-job",
            payload,
        )

    def _build_source(
        self,
        *,
        candidate: CareerDiscoveryCandidate,
        detail: CareerVerifiedJobDetail,
        provider_kind: str,
    ) -> CareerSource:

        source_id = self._source_id(
            candidate=candidate,
            detail=detail,
            provider_kind=provider_kind,
        )

        existing = (
            self._repository.get_source(
                source_id
            )
        )

        first_seen = min(
            candidate.observed_at,
            detail.observed_at,
        )

        created_at = (
            existing.created_at
            if existing is not None
            else first_seen
        )

        updated_at = max(
            (
                existing.updated_at
                if existing is not None
                else created_at
            ),
            detail.observed_at,
            candidate.observed_at,
        )

        prior_verified = (
            existing.last_verified_at
            if existing is not None
            else None
        )

        last_verified_at = max(
            value
            for value in (
                prior_verified,
                detail.observed_at,
            )
            if value is not None
        )

        structured = (
            provider_kind
            in _PROVIDER_SPECIFIC
        )

        return CareerSource(
            source_id=source_id,
            display_name=(
                candidate.employer_name
                + " / "
                + provider_kind
            ),
            employer_name=(
                candidate.employer_name
            ),
            source_kind=(
                "official_structured_ats"
                if structured
                else "official_employer_career"
            ),
            connector_kind=(
                candidate.connector_kind
            ),
            trust_tier=(
                3
                if structured
                else 2
            ),
            canonical_base_url=(
                _https_origin(
                    detail.canonical_job_url
                )
            ),
            state="active",
            last_verified_at=(
                last_verified_at
            ),
            last_error_code=None,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _build_baseline_job(
        *,
        candidate: CareerDiscoveryCandidate,
        detail: CareerVerifiedJobDetail,
        existing: CareerJobPosting | None,
        job_id: str,
    ) -> CareerJobPosting:

        first_observed = min(
            candidate.observed_at,
            detail.observed_at,
        )

        if existing is None:

            first_seen_at = first_observed
            created_at = first_observed
            current_snapshot_id = None
            verification_state = "RETRIEVED"
            lifecycle_state = "UNKNOWN"

        else:

            first_seen_at = (
                existing.first_seen_at
            )

            created_at = (
                existing.created_at
            )

            current_snapshot_id = (
                existing.current_snapshot_id
            )

            verification_state = (
                existing.verification_state
            )

            lifecycle_state = (
                existing.lifecycle_state
            )

        last_seen_at = max(
            (
                existing.last_seen_at
                if existing is not None
                else first_seen_at
            ),
            candidate.observed_at,
            detail.observed_at,
        )

        updated_at = max(
            (
                existing.updated_at
                if existing is not None
                else created_at
            ),
            candidate.observed_at,
            detail.observed_at,
        )

        return CareerJobPosting(
            job_id=job_id,
            employer_name=(
                detail.employer_name
            ),
            requisition_id=(
                candidate.source_job_id
            ),
            canonical_job_url=(
                detail.canonical_job_url
            ),
            canonical_apply_url=(
                detail.canonical_apply_url
            ),
            current_snapshot_id=(
                current_snapshot_id
            ),
            verification_state=(
                verification_state
            ),
            lifecycle_state=(
                lifecycle_state
            ),
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _reconcile_snapshot(
        self,
        *,
        candidate: CareerDiscoveryCandidate,
        detail: CareerVerifiedJobDetail,
        source_id: str,
        job_id: str,
        existing_job: CareerJobPosting | None,
    ) -> CareerJobSnapshot:

        if (
            existing_job is not None
            and existing_job.current_snapshot_id
            is not None
        ):

            current = (
                self._repository.get_snapshot(
                    existing_job
                    .current_snapshot_id
                )
            )

            if (
                current is not None
                and self._snapshot_matches_detail(
                    snapshot=current,
                    detail=detail,
                    source_id=source_id,
                    job_id=job_id,
                )
            ):
                return current

        snapshot = CareerJobSnapshot.build(
            job_id=job_id,
            source_id=source_id,
            title=detail.title,
            employer_name=(
                detail.employer_name
            ),
            description_text=(
                detail.description_text
            ),
            freshness_state="UNKNOWN",
            normalized_text_sha256=(
                detail.normalized_text_sha256
            ),
            observed_at=(
                detail.observed_at
            ),
            location_text=(
                detail.location_text
            ),
            work_mode=detail.work_mode,
            employment_type=(
                detail.employment_type
            ),
            posted_at=detail.posted_at,
            closing_at=detail.closing_at,
            salary_text=detail.salary_text,
            requirements=detail.requirements,
        )

        return (
            self._repository.persist_snapshot(
                snapshot
            )
        )

    @staticmethod
    def _snapshot_matches_detail(
        *,
        snapshot: CareerJobSnapshot,
        detail: CareerVerifiedJobDetail,
        source_id: str,
        job_id: str,
    ) -> bool:

        return all(
            (
                snapshot.job_id
                == job_id,

                snapshot.source_id
                == source_id,

                snapshot.title
                == detail.title,

                snapshot.employer_name
                == detail.employer_name,

                snapshot.location_text
                == detail.location_text,

                snapshot.work_mode
                == detail.work_mode,

                snapshot.employment_type
                == detail.employment_type,

                snapshot.description_text
                == detail.description_text,

                snapshot.posted_at
                == detail.posted_at,

                snapshot.closing_at
                == detail.closing_at,

                snapshot.freshness_state
                == "UNKNOWN",

                snapshot.salary_text
                == detail.salary_text,

                snapshot.requirements
                == detail.requirements,

                snapshot.normalized_text_sha256
                == detail.normalized_text_sha256,
            )
        )

    @staticmethod
    def _finalize_verified_job(
        *,
        baseline: CareerJobPosting,
        snapshot: CareerJobSnapshot,
        detail: CareerVerifiedJobDetail,
    ) -> CareerJobPosting:

        return CareerJobPosting(
            job_id=baseline.job_id,
            employer_name=(
                baseline.employer_name
            ),
            requisition_id=(
                baseline.requisition_id
            ),
            canonical_job_url=(
                baseline.canonical_job_url
            ),
            canonical_apply_url=(
                baseline.canonical_apply_url
            ),
            current_snapshot_id=(
                snapshot.snapshot_id
            ),
            verification_state="VERIFIED",
            lifecycle_state=(
                baseline.lifecycle_state
            ),
            first_seen_at=(
                baseline.first_seen_at
            ),
            last_seen_at=max(
                baseline.last_seen_at,
                detail.observed_at,
            ),
            created_at=(
                baseline.created_at
            ),
            updated_at=max(
                baseline.updated_at,
                detail.observed_at,
            ),
        )
