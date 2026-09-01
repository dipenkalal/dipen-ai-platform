from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from career.provider_identity import (
    canonicalize_provider_identity,
)
from career.source_discovery import (
    CareerSourceDiscoveryCandidate,
    DiscoveryDomainError,
    DiscoveryState,
    DiscoveryTransitionError,
    allowed_transitions,
    can_transition,
    transition_candidate,
)


BASE = datetime(
    2026,
    8,
    31,
    4,
    30,
    tzinfo=timezone.utc,
)


def discovered(
    **changes,
):
    values = {
        "discovery_candidate_id":
            "career-discovery-test-1",
        "employer_name":
            "Example Employer",
        "state":
            DiscoveryState.DISCOVERED,
        "first_seen_at": BASE,
        "last_seen_at": BASE,
        "state_changed_at": BASE,
        "created_at": BASE,
        "updated_at": BASE,
    }

    values.update(changes)

    return CareerSourceDiscoveryCandidate(
        **values
    )


def workday_identity():
    result = canonicalize_provider_identity(
        "workday",
        {
            "host":
                "example.wd3.myworkdayjobs.com",
            "tenant":
                "example",
            "site":
                "Careers",
        },
    )

    return {
        "provider_kind": "workday",
        "provider_identity_key":
            result.provider_identity_key,
        "provider_identity_json":
            result.canonical_json,
        "provider_identity_sha256":
            result.identity_sha256,
        "canonical_career_url":
            "https://example.wd3.myworkdayjobs.com/Careers",
    }


def endpoint_candidate():
    base = discovered(
        state=DiscoveryState.ATS_IDENTIFIED,
        provider_kind="workday",
    )

    return transition_candidate(
        base,
        DiscoveryState.ENDPOINT_CANDIDATE,
        at=BASE + timedelta(seconds=1),
        **workday_identity(),
    )


def listing_proven():
    return transition_candidate(
        endpoint_candidate(),
        DiscoveryState.LISTING_PROVEN,
        at=BASE + timedelta(seconds=2),
        listing_research_evidence_id=
            "research-listing-1",
    )


def detail_proven():
    return transition_candidate(
        listing_proven(),
        DiscoveryState.DETAIL_PROVEN,
        at=BASE + timedelta(seconds=3),
        detail_research_evidence_id=
            "research-detail-1",
    )


def admission_ready():
    return transition_candidate(
        detail_proven(),
        DiscoveryState.ADMISSION_READY,
        at=BASE + timedelta(seconds=4),
    )


def test_state_enum_is_frozen():
    assert {
        item.value
        for item in DiscoveryState
    } == {
        "discovered",
        "ats_identified",
        "endpoint_candidate",
        "listing_proven",
        "detail_proven",
        "admission_ready",
        "admitted",
        "degraded",
        "rejected",
        "disabled",
    }


def test_discovered_without_provider_is_valid():
    candidate = discovered()

    assert (
        candidate.state
        == DiscoveryState.DISCOVERED
    )

    assert candidate.provider_kind is None
    assert candidate.provider_identity_key is None


def test_ats_identified_requires_provider_kind():
    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ATS_IDENTIFIED
        )


def test_ats_identified_without_endpoint_is_valid():
    candidate = discovered(
        state=DiscoveryState.ATS_IDENTIFIED,
        provider_kind="workday",
    )

    assert candidate.provider_identity_key is None


def test_endpoint_candidate_requires_identity():
    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            provider_kind="workday",
            canonical_career_url=
                "https://example.com",
        )


def test_endpoint_candidate_requires_url():
    identity = workday_identity()
    identity.pop("canonical_career_url")

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )


def test_legacy_provider_key_namespace_rejected():
    identity = workday_identity()

    identity[
        "provider_identity_key"
    ] = (
        "career-source-key-"
        + "a" * 24
    )

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )


def test_partial_provider_identity_rejected():
    identity = workday_identity()

    identity[
        "provider_identity_sha256"
    ] = None

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )


def test_provider_sha_mismatch_rejected():
    identity = workday_identity()

    identity[
        "provider_identity_sha256"
    ] = "a" * 64

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )


def test_provider_json_must_be_canonical():
    identity = workday_identity()

    payload = (
        identity[
            "provider_identity_json"
        ]
    )

    identity[
        "provider_identity_json"
    ] = " " + payload

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )


def test_provider_kind_mismatch_rejected():
    identity = workday_identity()

    identity["provider_kind"] = "lever"

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )


def test_listing_proven_requires_listing_evidence():
    candidate = endpoint_candidate()

    with pytest.raises(
        DiscoveryDomainError
    ):
        CareerSourceDiscoveryCandidate(
            discovery_candidate_id=
                candidate.discovery_candidate_id,
            employer_name=
                candidate.employer_name,
            state=
                DiscoveryState.LISTING_PROVEN,
            first_seen_at=
                candidate.first_seen_at,
            last_seen_at=
                candidate.last_seen_at,
            state_changed_at=
                candidate.state_changed_at,
            created_at=
                candidate.created_at,
            updated_at=
                candidate.updated_at,
            provider_kind=
                candidate.provider_kind,
            provider_identity_key=
                candidate.provider_identity_key,
            provider_identity_json=
                candidate.provider_identity_json,
            provider_identity_sha256=
                candidate.provider_identity_sha256,
            canonical_career_url=
                candidate.canonical_career_url,
        )


def test_detail_proven_requires_detail_evidence():
    candidate = listing_proven()

    with pytest.raises(
        DiscoveryDomainError
    ):
        transition_candidate(
            candidate,
            DiscoveryState.DETAIL_PROVEN,
            at=BASE + timedelta(seconds=3),
        )


def test_admitted_requires_source_id():
    with pytest.raises(
        DiscoveryDomainError
    ):
        transition_candidate(
            admission_ready(),
            DiscoveryState.ADMITTED,
            at=BASE + timedelta(seconds=5),
        )


def test_admitted_with_source_id_is_valid():
    candidate = transition_candidate(
        admission_ready(),
        DiscoveryState.ADMITTED,
        at=BASE + timedelta(seconds=5),
        admitted_source_id=
            "career-source-example",
    )

    assert (
        candidate.state
        == DiscoveryState.ADMITTED
    )

    assert (
        candidate.admitted_source_id
        == "career-source-example"
    )


def test_non_admitted_source_id_rejected():
    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            admitted_source_id=
                "career-source-example"
        )


def test_degraded_requires_explicit_error():
    candidate = endpoint_candidate()

    with pytest.raises(
        DiscoveryTransitionError
    ):
        transition_candidate(
            candidate,
            DiscoveryState.DEGRADED,
            at=BASE + timedelta(seconds=2),
        )


def test_rejected_requires_explicit_error():
    with pytest.raises(
        DiscoveryTransitionError
    ):
        transition_candidate(
            discovered(),
            DiscoveryState.REJECTED,
            at=BASE + timedelta(seconds=1),
        )


def test_degraded_recovery_clears_error():
    candidate = transition_candidate(
        endpoint_candidate(),
        DiscoveryState.DEGRADED,
        at=BASE + timedelta(seconds=2),
        last_error_code="dns-failed",
    )

    recovered = transition_candidate(
        candidate,
        DiscoveryState.ENDPOINT_CANDIDATE,
        at=BASE + timedelta(seconds=3),
    )

    assert (
        recovered.state
        == DiscoveryState.ENDPOINT_CANDIDATE
    )

    assert recovered.last_error_code is None


def test_illegal_skip_rejected():
    with pytest.raises(
        DiscoveryTransitionError
    ):
        transition_candidate(
            discovered(),
            DiscoveryState.ENDPOINT_CANDIDATE,
            at=BASE + timedelta(seconds=1),
            **workday_identity(),
        )


@pytest.mark.parametrize(
    "state",
    [
        DiscoveryState.ADMITTED,
        DiscoveryState.REJECTED,
        DiscoveryState.DISABLED,
    ],
)
def test_terminal_states_have_no_transitions(
    state,
):
    assert allowed_transitions(state) == ()


def test_expected_main_progression():
    assert can_transition(
        DiscoveryState.DISCOVERED,
        DiscoveryState.ATS_IDENTIFIED,
    )

    assert can_transition(
        DiscoveryState.ATS_IDENTIFIED,
        DiscoveryState.ENDPOINT_CANDIDATE,
    )

    assert can_transition(
        DiscoveryState.ENDPOINT_CANDIDATE,
        DiscoveryState.LISTING_PROVEN,
    )

    assert can_transition(
        DiscoveryState.LISTING_PROVEN,
        DiscoveryState.DETAIL_PROVEN,
    )

    assert can_transition(
        DiscoveryState.DETAIL_PROVEN,
        DiscoveryState.ADMISSION_READY,
    )

    assert can_transition(
        DiscoveryState.ADMISSION_READY,
        DiscoveryState.ADMITTED,
    )


def test_identity_may_not_mutate_after_established():
    candidate = endpoint_candidate()

    with pytest.raises(
        DiscoveryTransitionError
    ):
        transition_candidate(
            candidate,
            DiscoveryState.LISTING_PROVEN,
            at=BASE + timedelta(seconds=2),
            listing_research_evidence_id=
                "research-listing-1",
            provider_identity_key=
                "career-provider-key-"
                + "a" * 24,
        )


def test_transition_timestamp_may_not_go_backward():
    candidate = endpoint_candidate()

    with pytest.raises(
        DiscoveryTransitionError
    ):
        transition_candidate(
            candidate,
            DiscoveryState.LISTING_PROVEN,
            at=BASE,
            listing_research_evidence_id=
                "research-listing-1",
        )


def test_transition_updates_timestamps():
    candidate = endpoint_candidate()

    at = BASE + timedelta(seconds=2)

    updated = transition_candidate(
        candidate,
        DiscoveryState.LISTING_PROVEN,
        at=at,
        listing_research_evidence_id=
            "research-listing-1",
    )

    assert updated.state_changed_at == at
    assert updated.last_seen_at == at
    assert updated.updated_at == at


def test_naive_datetime_rejected():
    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            first_seen_at=datetime(
                2026,
                8,
                31,
                4,
                30,
            )
        )


def test_http_canonical_url_rejected():
    identity = workday_identity()

    identity[
        "canonical_career_url"
    ] = "http://example.com"

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )


def test_provider_key_whitespace_rejected():
    identity = workday_identity()

    identity[
        "provider_identity_key"
    ] = (
        " "
        + identity[
            "provider_identity_key"
        ]
    )

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )


def test_provider_sha_whitespace_rejected():
    identity = workday_identity()

    identity[
        "provider_identity_sha256"
    ] = (
        identity[
            "provider_identity_sha256"
        ]
        + " "
    )

    with pytest.raises(
        DiscoveryDomainError
    ):
        discovered(
            state=
                DiscoveryState.ENDPOINT_CANDIDATE,
            **identity,
        )
