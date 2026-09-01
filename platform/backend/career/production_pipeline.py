from __future__ import annotations

from collections.abc import (
    Callable,
    Iterable,
    Mapping,
)
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from career.connectors.contracts import (
    CareerDiscoveryCandidate,
)
from career.discovery_router import (
    FAIL_CLOSED,
    DiscoveryRouteDecision,
    resolve_discovery_route,
)
from career.eligibility import (
    CareerEligibilityResult,
    classify_verified_freshness,
    adjudicate_verified_ingestion,
)
from career.ingestion import (
    CareerVerifiedIngestionService,
    CareerVerifiedJobDetail,
)
from career.notify_delivery import (
    CareerDeliveryReceipt,
    CareerNotifyDigest,
    build_notify_digest,
    deliver_notify_digest,
)
from career.repository import CareerRepository
from career.scoring import (
    CareerScoredJob,
    CareerScoringProfile,
    build_shortlist,
    persist_scored_job,
    score_verified_job,
)
from career.shadow_activation import (
    ShadowCapturedChunk,
    ShadowCaptureSender,
)


MAX_PRODUCTION_CANARY_CANDIDATES = 3
MAX_PRODUCTION_CANARY_SHORTLIST = 3


DiscoverCallable = Callable[
    [DiscoveryRouteDecision],
    Iterable[CareerDiscoveryCandidate],
]

VerifyCallable = Callable[
    [
        CareerDiscoveryCandidate,
        DiscoveryRouteDecision,
    ],
    CareerVerifiedJobDetail,
]


class CareerProductionCanaryError(
    ValueError
):
    """Production Career canary failed closed."""


@dataclass(frozen=True)
class CareerProductionCanaryCounts:
    discovered: int
    verified_details: int
    ingested: int
    eligible_fresh_active: int
    scored: int
    shortlisted: int
    digest_entries: int
    captured_chunks: int


@dataclass(frozen=True)
class CareerProductionCanaryResult:
    run_id: str
    route: DiscoveryRouteDecision
    eligibility: tuple[
        CareerEligibilityResult,
        ...
    ]
    scored: tuple[
        CareerScoredJob,
        ...
    ]
    shortlist: tuple[
        CareerScoredJob,
        ...
    ]
    digest: CareerNotifyDigest
    receipt: CareerDeliveryReceipt
    captured_chunks: tuple[
        ShadowCapturedChunk,
        ...
    ]
    counts: CareerProductionCanaryCounts


def _require_callable(
    value: object,
    *,
    label: str,
) -> None:
    if not callable(value):
        raise CareerProductionCanaryError(
            f"{label} must be callable"
        )


def _validate_limit(
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value
        > MAX_PRODUCTION_CANARY_SHORTLIST
    ):
        raise CareerProductionCanaryError(
            "production canary shortlist limit "
            "must be 1 through 3"
        )

    return value


def _candidate_tuple(
    value: object,
) -> tuple[
    CareerDiscoveryCandidate,
    ...
]:
    if isinstance(
        value,
        (
            str,
            bytes,
            bytearray,
        ),
    ):
        raise CareerProductionCanaryError(
            "discovery output must be a candidate collection"
        )

    try:
        candidates = tuple(
            value  # type: ignore[arg-type]
        )
    except TypeError as error:
        raise CareerProductionCanaryError(
            "discovery output must be iterable"
        ) from error

    if (
        len(candidates)
        > MAX_PRODUCTION_CANARY_CANDIDATES
    ):
        raise CareerProductionCanaryError(
            "production canary discovered "
            "more than three candidates"
        )

    if any(
        not isinstance(
            item,
            CareerDiscoveryCandidate,
        )
        for item in candidates
    ):
        raise CareerProductionCanaryError(
            "discovery returned a non-Career candidate"
        )

    return candidates


def _preflight_verified_detail(
    *,
    repository: CareerRepository,
    candidate: CareerDiscoveryCandidate,
    detail: CareerVerifiedJobDetail,
    route: DiscoveryRouteDecision,
) -> None:
    """
    Read-only validation performed for every candidate before
    the first Career write of the run.
    """

    if (
        detail.canonical_job_url
        != candidate.detail_url
    ):
        raise CareerProductionCanaryError(
            "verified detail URL does not match candidate"
        )

    if (
        detail.employer_name
        != candidate.employer_name
    ):
        raise CareerProductionCanaryError(
            "verified detail employer does not match candidate"
        )

    if (
        route.provider_kind
        in {
            "greenhouse",
            "lever",
            "ashby",
            "smartrecruiters",
        }
        and candidate.connector_kind
        != route.provider_kind
    ):
        raise CareerProductionCanaryError(
            "candidate connector does not match provider route"
        )

    if (
        route.provider_kind
        == "workday"
        and candidate.connector_kind
        not in {
            "workday",
            "generic_employer",
        }
    ):
        raise CareerProductionCanaryError(
            "Workday candidate connector is invalid"
        )

    projection = (
        repository
        .get_research_evidence_projection(
            detail.research_evidence_id
        )
    )

    if projection is None:
        raise CareerProductionCanaryError(
            "verified detail evidence is missing"
        )

    if (
        projection.get("outcome")
        != "succeeded"
    ):
        raise CareerProductionCanaryError(
            "verified detail evidence did not succeed"
        )

    if (
        projection.get(
            "normalized_text_sha256"
        )
        != detail.normalized_text_sha256
    ):
        raise CareerProductionCanaryError(
            "verified detail evidence hash mismatch"
        )

    if (
        projection.get("final_url")
        != detail.canonical_job_url
    ):
        raise CareerProductionCanaryError(
            "verified detail evidence URL mismatch"
        )

    # Pure classification here ensures chronology failures
    # happen before any Career persistence for the run.
    classify_verified_freshness(
        posted_at=detail.posted_at,
        closing_at=detail.closing_at,
        observed_at=detail.observed_at,
    )


def _run_id(
    *,
    route: DiscoveryRouteDecision,
    candidates: tuple[
        CareerDiscoveryCandidate,
        ...
    ],
    scored: tuple[
        CareerScoredJob,
        ...
    ],
    digest: CareerNotifyDigest,
) -> str:
    payload = {
        "provider_kind":
            route.provider_kind,

        "route_kind":
            route.route_kind,

        "candidate_ids": [
            item.candidate_id
            for item in candidates
        ],

        "assessment_ids": [
            item.assessment.assessment_id
            for item in scored
        ],

        "digest_id":
            digest.digest_id,
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return (
        "career-production-canary-"
        + hashlib.sha256(
            encoded
        ).hexdigest()[:24]
    )


def run_production_canary(
    *,
    repository: CareerRepository,
    provider_kind: str,
    provider_target: Mapping[
        str,
        Any,
    ],
    discover: DiscoverCallable,
    verify: VerifyCallable,
    profile: CareerScoringProfile,
    shortlist_limit: int = (
        MAX_PRODUCTION_CANARY_SHORTLIST
    ),
) -> CareerProductionCanaryResult:
    """
    Owner-invoked bounded Career production orchestration.

    Network transport is injected through discover/verify.
    Notification transport is never injected here: the
    canary always uses ShadowCaptureSender.
    """

    _require_callable(
        discover,
        label="discover",
    )

    _require_callable(
        verify,
        label="verify",
    )

    limit = _validate_limit(
        shortlist_limit
    )

    route = resolve_discovery_route(
        provider_kind,
        provider_target,
    )

    if route.route_kind == FAIL_CLOSED:
        raise CareerProductionCanaryError(
            "provider route failed closed: "
            + route.reason
        )

    candidates = _candidate_tuple(
        discover(route)
    )

    # Verify every detail and its existing Phase-16 evidence
    # before permitting the first Career write.
    verified_inputs: list[
        tuple[
            CareerDiscoveryCandidate,
            CareerVerifiedJobDetail,
        ]
    ] = []

    for candidate in candidates:
        detail = verify(
            candidate,
            route,
        )

        if not isinstance(
            detail,
            CareerVerifiedJobDetail,
        ):
            raise CareerProductionCanaryError(
                "verify stage returned invalid detail"
            )

        _preflight_verified_detail(
            repository=repository,
            candidate=candidate,
            detail=detail,
            route=route,
        )

        verified_inputs.append(
            (
                candidate,
                detail,
            )
        )

    ingestion_service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    eligibility_results: list[
        CareerEligibilityResult
    ] = []

    scored_results: list[
        CareerScoredJob
    ] = []

    for (
        candidate,
        detail,
    ) in verified_inputs:

        ingested = (
            ingestion_service
            .ingest_verified_candidate(
                candidate=candidate,
                detail=detail,
                provider_kind=(
                    route.provider_kind
                ),
                route_kind=(
                    route.route_kind
                ),
            )
        )

        eligibility = (
            adjudicate_verified_ingestion(
                repository,
                ingested,
            )
        )

        eligibility_results.append(
            eligibility
        )

        if not (
            eligibility
            .decision
            .surface_eligible
        ):
            continue

        scored = score_verified_job(
            job=eligibility.job,
            snapshot=(
                eligibility.snapshot
            ),
            evidence_link=(
                eligibility.evidence_link
            ),
            profile=profile,
        )

        scored = persist_scored_job(
            repository,
            scored,
        )

        scored_results.append(
            scored
        )

    scored_tuple = tuple(
        scored_results
    )

    shortlist = build_shortlist(
        scored_tuple,
        limit=limit,
    )

    digest = build_notify_digest(
        shortlist
    )

    capture = ShadowCaptureSender()

    receipt = deliver_notify_digest(
        digest,
        capture,
    )

    captured = capture.chunks

    counts = (
        CareerProductionCanaryCounts(
            discovered=len(candidates),
            verified_details=len(
                verified_inputs
            ),
            ingested=len(
                eligibility_results
            ),
            eligible_fresh_active=sum(
                1
                for item
                in eligibility_results
                if (
                    item
                    .decision
                    .surface_eligible
                )
            ),
            scored=len(
                scored_tuple
            ),
            shortlisted=len(
                shortlist
            ),
            digest_entries=(
                digest.entry_count
            ),
            captured_chunks=len(
                captured
            ),
        )
    )

    return CareerProductionCanaryResult(
        run_id=_run_id(
            route=route,
            candidates=candidates,
            scored=scored_tuple,
            digest=digest,
        ),
        route=route,
        eligibility=tuple(
            eligibility_results
        ),
        scored=scored_tuple,
        shortlist=tuple(
            shortlist
        ),
        digest=digest,
        receipt=receipt,
        captured_chunks=captured,
        counts=counts,
    )
