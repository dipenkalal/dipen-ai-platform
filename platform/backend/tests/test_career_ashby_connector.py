from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import career.connectors as connector_exports
from career.connectors.ashby import (
    ASHBY_CONNECTOR_ID,
    AshbyConnectorParseError,
    AshbyJobBoardConnector,
)
from career.connectors.contracts import (
    CareerConnectorParseInput,
)


_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "career"
    / "ashby_job_board.json"
)


def _fixture_text() -> str:
    return _FIXTURE.read_text(
        encoding="utf-8"
    )


def _connector() -> AshbyJobBoardConnector:
    return AshbyJobBoardConnector(
        job_board_name="acme",
        employer_name="Acme",
    )


def _parse_input(
    text: str | None = None,
    *,
    source_url: str | None = None,
    media_type: str = "application/json",
) -> CareerConnectorParseInput:
    if text is None:
        text = _fixture_text()

    normalized_sha = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    return CareerConnectorParseInput(
        research_evidence_id=(
            "research-retrieval-"
            "0123456789abcdef01234567"
        ),
        content_evidence_id=(
            "internet-content-"
            "89abcdef0123456701234567"
        ),
        source_url=(
            source_url
            or _connector().jobs_url
        ),
        media_type=media_type,
        normalized_text=text,
        normalized_text_sha256=normalized_sha,
        observed_at=datetime(
            2026,
            8,
            20,
            15,
            0,
            tzinfo=timezone.utc,
        ),
        phase16_normalized_evidence=True,
        metadata_is_job_truth=False,
        application_authority_granted=False,
    )


def test_descriptor_contract() -> None:
    connector = _connector()
    descriptor = connector.descriptor

    assert (
        ASHBY_CONNECTOR_ID
        == "career-connector-ashby-job-board-v1"
    )

    assert (
        descriptor.connector_id
        == ASHBY_CONNECTOR_ID
    )

    assert descriptor.connector_kind == "ashby"

    assert descriptor.response_media_types == (
        "application/json",
    )

    assert descriptor.connector_owns_network is False
    assert descriptor.credentials_required is False

    assert (
        descriptor.application_submission_supported
        is False
    )

    assert (
        descriptor.browser_authority_granted
        is False
    )

    assert (
        descriptor.candidate_metadata_is_job_truth
        is False
    )

    assert (
        connector_exports.ASHBY_CONNECTOR_ID
        == ASHBY_CONNECTOR_ID
    )

    assert (
        connector_exports.AshbyJobBoardConnector
        is AshbyJobBoardConnector
    )

    assert (
        connector_exports.AshbyConnectorParseError
        is AshbyConnectorParseError
    )


def test_public_job_board_url_contract() -> None:
    connector = _connector()

    assert (
        connector.jobs_url
        == (
            "https://api.ashbyhq.com/"
            "posting-api/job-board/acme"
            "?includeCompensation=false"
        )
    )


def test_valid_listed_jobs_parse() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    assert result.candidate_count == 2
    assert len(result.candidates) == 2

    assert [
        candidate.title_hint
        for candidate in result.candidates
    ] == [
        "Junior Cloud Engineer",
        "Cloud Support Associate",
    ]


def test_unlisted_job_is_excluded() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    assert all(
        candidate.title_hint
        != "Internal Direct Link Role"
        for candidate in result.candidates
    )


def test_missing_isListed_is_excluded() -> None:
    payload = json.loads(
        _fixture_text()
    )

    payload["jobs"].append(
        {
            "title": "Missing Listing State",
            "jobUrl": (
                "https://jobs.ashbyhq.com/"
                "acme/"
                "44444444-4444-4444-8444-444444444444"
            ),
        }
    )

    text = json.dumps(
        payload,
        sort_keys=True,
    )

    result = _connector().parse_candidates(
        _parse_input(text)
    )

    assert result.candidate_count == 2

    assert all(
        candidate.title_hint
        != "Missing Listing State"
        for candidate in result.candidates
    )


def test_job_url_is_documented_source_identity() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    candidate = result.candidates[0]

    assert (
        candidate.source_job_id
        == candidate.detail_url
    )

    assert candidate.source_job_id == (
        "https://jobs.ashbyhq.com/"
        "acme/"
        "11111111-1111-4111-8111-111111111111"
    )

    assert candidate.source_identity_key.startswith(
        "career-source-key-"
    )


def test_published_at_maps_to_posted_at_hint() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    candidate = result.candidates[0]

    assert candidate.posted_at_hint == datetime(
        2026,
        8,
        20,
        14,
        30,
        tzinfo=timezone.utc,
    )

    assert candidate.source_updated_at_hint is None


def test_published_at_does_not_auto_verify_freshness() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    candidate = result.candidates[0]

    assert candidate.posted_at_hint is not None
    assert candidate.freshness_verified is False
    assert candidate.eligible_for_scoring is False
    assert candidate.eligible_for_shortlist is False


def test_missing_published_at_remains_none() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    candidate = result.candidates[1]

    assert candidate.posted_at_hint is None
    assert candidate.source_updated_at_hint is None
    assert candidate.freshness_verified is False


def test_invalid_published_at_fails_closed() -> None:
    payload = json.loads(
        _fixture_text()
    )

    payload["jobs"][0]["publishedAt"] = (
        "2026-08-20"
    )

    text = json.dumps(
        payload,
        sort_keys=True,
    )

    with pytest.raises(
        AshbyConnectorParseError,
        match="timezone-aware",
    ):
        _connector().parse_candidates(
            _parse_input(text)
        )


def test_evidence_binding_is_preserved() -> None:
    parse_input = _parse_input()

    result = _connector().parse_candidates(
        parse_input
    )

    assert (
        result.research_evidence_id
        == parse_input.research_evidence_id
    )

    assert (
        result.content_evidence_id
        == parse_input.content_evidence_id
    )

    assert (
        result.normalized_text_sha256
        == parse_input.normalized_text_sha256
    )

    for candidate in result.candidates:
        assert (
            candidate.discovery_research_evidence_id
            == parse_input.research_evidence_id
        )

        assert (
            candidate.discovery_content_evidence_id
            == parse_input.content_evidence_id
        )

        assert (
            candidate.discovery_normalized_text_sha256
            == parse_input.normalized_text_sha256
        )


def test_candidate_remains_non_authoritative() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    assert result.metadata_is_job_truth is False

    assert (
        result.production_truth_mutation_allowed
        is False
    )

    assert (
        result.application_authority_granted
        is False
    )

    for candidate in result.candidates:
        assert candidate.metadata_is_job_truth is False
        assert candidate.freshness_verified is False
        assert candidate.eligible_for_scoring is False
        assert candidate.eligible_for_shortlist is False

        assert (
            candidate.application_authority_granted
            is False
        )


def test_apply_url_remains_hint_only() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    first = result.candidates[0]
    second = result.candidates[1]

    assert first.apply_url_hint == (
        "https://jobs.ashbyhq.com/"
        "acme/"
        "11111111-1111-4111-8111-111111111111/"
        "application"
    )

    assert second.apply_url_hint is None

    assert (
        first.application_authority_granted
        is False
    )


def test_invalid_json_fails_closed() -> None:
    text = '{"apiVersion":"1","jobs":['

    with pytest.raises(
        AshbyConnectorParseError,
        match="not valid JSON",
    ):
        _connector().parse_candidates(
            _parse_input(text)
        )


def test_invalid_root_fails_closed() -> None:
    text = json.dumps(
        [
            {
                "apiVersion": "1",
                "jobs": [],
            }
        ]
    )

    with pytest.raises(
        AshbyConnectorParseError,
        match="root must be an object",
    ):
        _connector().parse_candidates(
            _parse_input(text)
        )


def test_unsupported_api_version_fails_closed() -> None:
    payload = json.loads(
        _fixture_text()
    )

    payload["apiVersion"] = "2"

    text = json.dumps(
        payload,
        sort_keys=True,
    )

    with pytest.raises(
        AshbyConnectorParseError,
        match="Unsupported Ashby apiVersion",
    ):
        _connector().parse_candidates(
            _parse_input(text)
        )


def test_missing_jobs_fails_closed() -> None:
    payload = json.loads(
        _fixture_text()
    )

    del payload["jobs"]

    text = json.dumps(
        payload,
        sort_keys=True,
    )

    with pytest.raises(
        AshbyConnectorParseError,
        match="missing jobs",
    ):
        _connector().parse_candidates(
            _parse_input(text)
        )


def test_malformed_listed_row_fails_closed() -> None:
    payload = json.loads(
        _fixture_text()
    )

    del payload["jobs"][0]["title"]

    text = json.dumps(
        payload,
        sort_keys=True,
    )

    with pytest.raises(
        AshbyConnectorParseError,
        match="title",
    ):
        _connector().parse_candidates(
            _parse_input(text)
        )
