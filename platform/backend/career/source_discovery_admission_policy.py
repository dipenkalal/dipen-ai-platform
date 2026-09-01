"""Phase 19.3H deterministic admission-readiness policy.

This policy may classify a DETAIL_PROVEN discovery candidate as
ADMISSION_READY.

It owns no persistence, networking, career_sources mutation,
application action, or final source-admission authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from career.provider_identity import (
    supported_provider_kinds,
)
from career.source_discovery import (
    CareerSourceDiscoveryCandidate,
    DiscoveryState,
    transition_candidate,
)


ADMISSION_READINESS_POLICY_ID = (
    "career-source-admission-readiness-v1"
)


class SourceAdmissionPolicyError(
    ValueError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class AdmissionReadinessDecision:
    policy_id: str
    eligible: bool
    reason_codes: tuple[str, ...]


def evaluate_admission_readiness(
    candidate:
        CareerSourceDiscoveryCandidate,
) -> AdmissionReadinessDecision:
    reasons: list[str] = []

    if (
        candidate.state
        is not DiscoveryState.DETAIL_PROVEN
    ):
        reasons.append(
            "state-not-detail-proven"
        )

    if (
        candidate.provider_kind
        not in supported_provider_kinds()
    ):
        reasons.append(
            "unsupported-provider"
        )

    if (
        candidate.provider_identity_key
        is None
        or candidate.provider_identity_json
        is None
        or candidate.provider_identity_sha256
        is None
    ):
        reasons.append(
            "provider-identity-incomplete"
        )

    if (
        candidate.canonical_career_url
        is None
    ):
        reasons.append(
            "canonical-career-url-missing"
        )

    if (
        candidate.discovery_research_evidence_id
        is None
    ):
        reasons.append(
            "discovery-evidence-missing"
        )

    if (
        candidate.listing_research_evidence_id
        is None
    ):
        reasons.append(
            "listing-evidence-missing"
        )

    if (
        candidate.detail_research_evidence_id
        is None
    ):
        reasons.append(
            "detail-evidence-missing"
        )

    if (
        candidate.last_error_code
        is not None
    ):
        reasons.append(
            "candidate-has-error"
        )

    if (
        candidate.admitted_source_id
        is not None
    ):
        reasons.append(
            "source-binding-already-present"
        )

    return AdmissionReadinessDecision(
        policy_id=(
            ADMISSION_READINESS_POLICY_ID
        ),
        eligible=not reasons,
        reason_codes=tuple(
            sorted(
                set(reasons)
            )
        ),
    )


def advance_to_admission_ready(
    candidate:
        CareerSourceDiscoveryCandidate,
    *,
    at: datetime,
) -> CareerSourceDiscoveryCandidate:
    decision = (
        evaluate_admission_readiness(
            candidate
        )
    )

    if not decision.eligible:
        joined = ",".join(
            decision.reason_codes
        )

        raise SourceAdmissionPolicyError(
            "candidate is not admission-ready: "
            + joined
        )

    return transition_candidate(
        candidate,
        DiscoveryState.ADMISSION_READY,
        at=at,
    )
