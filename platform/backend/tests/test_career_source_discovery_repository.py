from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
import sqlite3

import pytest

from career.provider_identity import (
    canonicalize_provider_identity,
)

from career.source_discovery import (
    CareerSourceDiscoveryCandidate,
    DiscoveryState,
    DiscoveryTransitionError,
)

from career.source_discovery_repository import (
    CareerSourceDiscoveryRepository,
    DiscoveryRepositoryAuthorityError,
    DiscoveryRepositoryConflictError,
    DiscoveryRepositoryError,
)


BASE = datetime(
    2026,
    8,
    31,
    7,
    0,
    tzinfo=timezone.utc,
)


SCHEMA = """
CREATE TABLE
career_source_discovery_candidates (

    discovery_candidate_id TEXT PRIMARY KEY,

    provider_identity_key TEXT UNIQUE,

    employer_name TEXT NOT NULL,

    provider_kind TEXT,

    canonical_career_url TEXT,

    provider_identity_json TEXT,

    provider_identity_sha256 TEXT,

    state TEXT NOT NULL,

    discovery_research_evidence_id TEXT,

    listing_research_evidence_id TEXT,

    detail_research_evidence_id TEXT,

    last_error_code TEXT,

    first_seen_at TEXT NOT NULL,

    last_seen_at TEXT NOT NULL,

    state_changed_at TEXT NOT NULL,

    admitted_source_id TEXT,

    created_at TEXT NOT NULL,

    updated_at TEXT NOT NULL
);
"""


@pytest.fixture
def repository():

    connection = sqlite3.connect(
        ":memory:"
    )

    connection.executescript(
        SCHEMA
    )

    repo = (
        CareerSourceDiscoveryRepository(
            connection
        )
    )

    try:
        yield repo
    finally:
        connection.close()


def discovered(
    *,
    candidate_id="discovery-1",
    employer="Example Employer",
):

    return CareerSourceDiscoveryCandidate(
        discovery_candidate_id=
            candidate_id,

        employer_name=employer,

        state=
            DiscoveryState.DISCOVERED,

        first_seen_at=BASE,
        last_seen_at=BASE,
        state_changed_at=BASE,
        created_at=BASE,
        updated_at=BASE,
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

    return dict(
        provider_kind="workday",
        provider_identity_key=
            result.provider_identity_key,
        provider_identity_json=
            result.canonical_json,
        provider_identity_sha256=
            result.identity_sha256,
        canonical_career_url=
            "https://example.wd3.myworkdayjobs.com/Careers",
    )


def endpoint_candidate(
    *,
    candidate_id="endpoint-1",
    employer="Endpoint Employer",
):

    identity = workday_identity()

    return CareerSourceDiscoveryCandidate(
        discovery_candidate_id=
            candidate_id,

        employer_name=employer,

        state=
            DiscoveryState.ENDPOINT_CANDIDATE,

        first_seen_at=BASE,
        last_seen_at=BASE,
        state_changed_at=BASE,
        created_at=BASE,
        updated_at=BASE,

        **identity,
    )


def test_insert_and_get(repository):

    candidate = discovered()

    repository.insert(
        candidate
    )

    loaded = repository.get(
        candidate.discovery_candidate_id
    )

    assert loaded == candidate


def test_get_missing_returns_none(
    repository,
):

    assert (
        repository.get("missing")
        is None
    )


def test_list_by_state(repository):

    repository.insert(
        discovered(
            candidate_id="a",
            employer="A",
        )
    )

    repository.insert(
        discovered(
            candidate_id="b",
            employer="B",
        )
    )

    rows = repository.list_by_state(
        DiscoveryState.DISCOVERED
    )

    assert [
        row.discovery_candidate_id
        for row in rows
    ] == ["a", "b"]


def test_list_limit_validation(
    repository,
):

    with pytest.raises(ValueError):
        repository.list_by_state(
            DiscoveryState.DISCOVERED,
            limit=0,
        )

    with pytest.raises(ValueError):
        repository.list_by_state(
            DiscoveryState.DISCOVERED,
            limit=1001,
        )


def test_insert_duplicate_provider_identity_fails(
    repository,
):

    first = endpoint_candidate(
        candidate_id="endpoint-a",
        employer="A",
    )

    second = endpoint_candidate(
        candidate_id="endpoint-b",
        employer="B",
    )

    repository.insert(first)

    with pytest.raises(
        DiscoveryRepositoryError
    ):
        repository.insert(second)


def test_transition_discovered_to_ats(
    repository,
):

    candidate = discovered()

    repository.insert(candidate)

    transitioned = (
        repository.transition(
            candidate.discovery_candidate_id,
            DiscoveryState.ATS_IDENTIFIED,
            expected_state=
                candidate.state,
            expected_updated_at=
                candidate.updated_at,
            at=
                BASE
                + timedelta(seconds=1),
            provider_kind="workday",
        )
    )

    assert (
        transitioned.state
        == DiscoveryState.ATS_IDENTIFIED
    )

    loaded = repository.get(
        candidate.discovery_candidate_id
    )

    assert loaded == transitioned


def test_transition_full_pre_admission_path(
    repository,
):

    candidate = discovered()

    repository.insert(candidate)

    candidate = repository.transition(
        candidate.discovery_candidate_id,
        DiscoveryState.ATS_IDENTIFIED,
        expected_state=candidate.state,
        expected_updated_at=
            candidate.updated_at,
        at=BASE + timedelta(seconds=1),
        provider_kind="workday",
    )

    candidate = repository.transition(
        candidate.discovery_candidate_id,
        DiscoveryState.ENDPOINT_CANDIDATE,
        expected_state=candidate.state,
        expected_updated_at=
            candidate.updated_at,
        at=BASE + timedelta(seconds=2),
        **workday_identity(),
    )

    candidate = repository.transition(
        candidate.discovery_candidate_id,
        DiscoveryState.LISTING_PROVEN,
        expected_state=candidate.state,
        expected_updated_at=
            candidate.updated_at,
        at=BASE + timedelta(seconds=3),
        listing_research_evidence_id=
            "listing-evidence",
    )

    candidate = repository.transition(
        candidate.discovery_candidate_id,
        DiscoveryState.DETAIL_PROVEN,
        expected_state=candidate.state,
        expected_updated_at=
            candidate.updated_at,
        at=BASE + timedelta(seconds=4),
        detail_research_evidence_id=
            "detail-evidence",
    )

    candidate = repository.transition(
        candidate.discovery_candidate_id,
        DiscoveryState.ADMISSION_READY,
        expected_state=candidate.state,
        expected_updated_at=
            candidate.updated_at,
        at=BASE + timedelta(seconds=5),
    )

    assert (
        candidate.state
        == DiscoveryState.ADMISSION_READY
    )


def test_illegal_transition_propagates(
    repository,
):

    candidate = discovered()

    repository.insert(candidate)

    with pytest.raises(
        DiscoveryTransitionError
    ):
        repository.transition(
            candidate.discovery_candidate_id,
            DiscoveryState.ENDPOINT_CANDIDATE,
            expected_state=
                candidate.state,
            expected_updated_at=
                candidate.updated_at,
            at=
                BASE
                + timedelta(seconds=1),
            **workday_identity(),
        )


def test_expected_state_conflict(
    repository,
):

    candidate = discovered()

    repository.insert(candidate)

    with pytest.raises(
        DiscoveryRepositoryConflictError
    ):
        repository.transition(
            candidate.discovery_candidate_id,
            DiscoveryState.ATS_IDENTIFIED,
            expected_state=
                DiscoveryState.ATS_IDENTIFIED,
            expected_updated_at=
                candidate.updated_at,
            at=
                BASE
                + timedelta(seconds=1),
            provider_kind="workday",
        )

    assert (
        repository.get(
            candidate.discovery_candidate_id
        )
        == candidate
    )


def test_expected_timestamp_conflict(
    repository,
):

    candidate = discovered()

    repository.insert(candidate)

    with pytest.raises(
        DiscoveryRepositoryConflictError
    ):
        repository.transition(
            candidate.discovery_candidate_id,
            DiscoveryState.ATS_IDENTIFIED,
            expected_state=
                candidate.state,
            expected_updated_at=
                BASE
                + timedelta(seconds=99),
            at=
                BASE
                + timedelta(seconds=1),
            provider_kind="workday",
        )

    assert (
        repository.get(
            candidate.discovery_candidate_id
        )
        == candidate
    )


def test_missing_candidate_conflict(
    repository,
):

    with pytest.raises(
        DiscoveryRepositoryConflictError
    ):
        repository.transition(
            "missing",
            DiscoveryState.ATS_IDENTIFIED,
            expected_state=
                DiscoveryState.DISCOVERED,
            expected_updated_at=BASE,
            at=
                BASE
                + timedelta(seconds=1),
            provider_kind="workday",
        )


def test_repository_refuses_admitted_insert(
    repository,
):

    candidate = endpoint_candidate()

    # Build legal pre-admission path in memory.
    from career.source_discovery import (
        transition_candidate,
    )

    candidate = transition_candidate(
        candidate,
        DiscoveryState.LISTING_PROVEN,
        at=BASE + timedelta(seconds=1),
        listing_research_evidence_id=
            "listing",
    )

    candidate = transition_candidate(
        candidate,
        DiscoveryState.DETAIL_PROVEN,
        at=BASE + timedelta(seconds=2),
        detail_research_evidence_id=
            "detail",
    )

    candidate = transition_candidate(
        candidate,
        DiscoveryState.ADMISSION_READY,
        at=BASE + timedelta(seconds=3),
    )

    candidate = transition_candidate(
        candidate,
        DiscoveryState.ADMITTED,
        at=BASE + timedelta(seconds=4),
        admitted_source_id=
            "career-source-manual",
    )

    with pytest.raises(
        DiscoveryRepositoryAuthorityError
    ):
        repository.insert(candidate)


def test_repository_refuses_admitted_transition(
    repository,
):

    candidate = endpoint_candidate()

    repository.insert(candidate)

    candidate = repository.transition(
        candidate.discovery_candidate_id,
        DiscoveryState.LISTING_PROVEN,
        expected_state=candidate.state,
        expected_updated_at=
            candidate.updated_at,
        at=BASE + timedelta(seconds=1),
        listing_research_evidence_id=
            "listing",
    )

    candidate = repository.transition(
        candidate.discovery_candidate_id,
        DiscoveryState.DETAIL_PROVEN,
        expected_state=candidate.state,
        expected_updated_at=
            candidate.updated_at,
        at=BASE + timedelta(seconds=2),
        detail_research_evidence_id=
            "detail",
    )

    candidate = repository.transition(
        candidate.discovery_candidate_id,
        DiscoveryState.ADMISSION_READY,
        expected_state=candidate.state,
        expected_updated_at=
            candidate.updated_at,
        at=BASE + timedelta(seconds=3),
    )

    with pytest.raises(
        DiscoveryRepositoryAuthorityError
    ):
        repository.transition(
            candidate.discovery_candidate_id,
            DiscoveryState.ADMITTED,
            expected_state=candidate.state,
            expected_updated_at=
                candidate.updated_at,
            at=
                BASE
                + timedelta(seconds=4),
            admitted_source_id=
                "career-source-manual",
        )

    persisted = repository.get(
        candidate.discovery_candidate_id
    )

    assert (
        persisted.state
        == DiscoveryState.ADMISSION_READY
    )

    assert (
        persisted.admitted_source_id
        is None
    )


def test_repository_does_not_commit_insert(
    repository,
):

    candidate = discovered()

    repository.insert(candidate)

    assert (
        repository.connection.in_transaction
        is True
    )

    repository.connection.rollback()

    assert (
        repository.get(
            candidate.discovery_candidate_id
        )
        is None
    )
