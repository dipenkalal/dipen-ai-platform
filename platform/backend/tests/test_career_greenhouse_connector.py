from __future__ import annotations

import copy
import hashlib
import json
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from career.connectors.contracts import (
    CareerConnector,
    CareerConnectorParseInput,
)
from career.connectors.greenhouse import (
    GREENHOUSE_CONNECTOR_ID,
    GREENHOUSE_MAX_JOBS,
    GreenhouseConnectorParseError,
    GreenhouseJobBoardConnector,
)


NOW = datetime(
    2026,
    8,
    20,
    20,
    45,
    tzinfo=timezone.utc,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "career"
    / "greenhouse_jobs.json"
)

RESEARCH_EVIDENCE_ID = (
    "research-retrieval-"
    "111111111111111111111111"
)

CONTENT_EVIDENCE_ID = (
    "internet-content-"
    "222222222222222222222222"
)


def _fixture_payload() -> dict:
    return json.loads(
        FIXTURE.read_text(
            encoding="utf-8"
        )
    )


def _normalized(
    payload: object,
) -> str:
    return json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )


def _connector() -> GreenhouseJobBoardConnector:
    return GreenhouseJobBoardConnector(
        board_token="acme",
        employer_name="Acme",
    )


def _parse_input(
    payload: object | None = None,
    *,
    source_url: str | None = None,
    media_type: str = "application/json",
) -> CareerConnectorParseInput:
    if payload is None:
        payload = _fixture_payload()

    normalized = _normalized(payload)

    return CareerConnectorParseInput(
        research_evidence_id=(
            RESEARCH_EVIDENCE_ID
        ),
        content_evidence_id=(
            CONTENT_EVIDENCE_ID
        ),
        source_url=(
            source_url
            or _connector().jobs_url
        ),
        media_type=media_type,
        normalized_text=normalized,
        normalized_text_sha256=(
            hashlib.sha256(
                normalized.encode("utf-8")
            ).hexdigest()
        ),
        observed_at=NOW,
    )


def test_descriptor_has_no_network_or_submission_authority() -> None:
    connector = _connector()

    descriptor = connector.descriptor

    assert isinstance(
        connector,
        CareerConnector,
    )

    assert (
        descriptor.connector_id
        == GREENHOUSE_CONNECTOR_ID
    )

    assert descriptor.connector_kind == "greenhouse"

    assert descriptor.response_media_types == (
        "application/json",
    )

    assert descriptor.connector_owns_network is False

    assert (
        descriptor.application_submission_supported
        is False
    )

    assert descriptor.credentials_required is False


def test_jobs_url_is_public_read_endpoint_shape() -> None:
    connector = _connector()

    assert connector.jobs_url == (
        "https://boards-api.greenhouse.io/"
        "v1/boards/acme/jobs"
    )


def test_fixture_parses_jobs_and_skips_prospect_post() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    assert result.candidate_count == 2

    assert [
        item.source_job_id
        for item in result.candidates
    ] == [
        "900001",
        "900002",
    ]


def test_greenhouse_updated_at_is_not_posted_at() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    first = result.candidates[0]

    assert first.posted_at_hint is None

    assert (
        first.source_updated_at_hint
        is not None
    )

    assert (
        first.source_updated_at_hint.isoformat()
        == "2026-08-20T15:00:00-04:00"
    )

    assert first.freshness_verified is False


def test_candidate_location_and_detail_url_are_preserved() -> None:
    result = _connector().parse_candidates(
        _parse_input()
    )

    first = result.candidates[0]

    assert (
        first.location_hint
        == "Toronto, Ontario, Canada"
    )

    assert first.detail_url == (
        "https://boards.greenhouse.io/"
        "acme/jobs/900001"
    )

    assert first.apply_url_hint is None


def test_candidate_provenance_is_bound_to_phase16_input() -> None:
    parse_input = _parse_input()

    result = _connector().parse_candidates(
        parse_input
    )

    for candidate in result.candidates:
        assert (
            candidate
            .discovery_research_evidence_id
            == parse_input.research_evidence_id
        )

        assert (
            candidate
            .discovery_content_evidence_id
            == parse_input.content_evidence_id
        )

        assert (
            candidate
            .discovery_normalized_text_sha256
            == parse_input.normalized_text_sha256
        )

        assert candidate.observed_at == NOW

        assert candidate.metadata_is_job_truth is False
        assert candidate.eligible_for_scoring is False
        assert candidate.eligible_for_shortlist is False


def test_repeated_parse_is_deterministic() -> None:
    connector = _connector()
    parse_input = _parse_input()

    first = connector.parse_candidates(
        parse_input
    )

    second = connector.parse_candidates(
        parse_input
    )

    assert first == second
    assert first.result_id == second.result_id


def test_wrong_greenhouse_source_url_is_rejected() -> None:
    with pytest.raises(
        GreenhouseConnectorParseError,
        match="source URL",
    ):
        _connector().parse_candidates(
            _parse_input(
                source_url=(
                    "https://boards-api.greenhouse.io/"
                    "v1/boards/other/jobs"
                )
            )
        )


def test_non_json_media_type_is_rejected() -> None:
    with pytest.raises(
        GreenhouseConnectorParseError,
        match="application/json",
    ):
        _connector().parse_candidates(
            _parse_input(
                media_type="text/plain"
            )
        )


def test_meta_total_mismatch_fails_closed() -> None:
    payload = _fixture_payload()

    payload["meta"]["total"] = 999

    with pytest.raises(
        GreenhouseConnectorParseError,
        match="does not match",
    ):
        _connector().parse_candidates(
            _parse_input(payload)
        )


def test_board_job_ceiling_fails_closed() -> None:
    payload = _fixture_payload()

    payload["meta"]["total"] = (
        GREENHOUSE_MAX_JOBS + 1
    )

    with pytest.raises(
        GreenhouseConnectorParseError,
        match="bounded job ceiling",
    ):
        _connector().parse_candidates(
            _parse_input(payload)
        )


def test_missing_required_job_title_fails_closed() -> None:
    payload = _fixture_payload()

    payload["jobs"][0]["title"] = None

    with pytest.raises(
        GreenhouseConnectorParseError,
        match=r"jobs\[0\]\.title",
    ):
        _connector().parse_candidates(
            _parse_input(payload)
        )


def test_insecure_greenhouse_absolute_url_fails_closed() -> None:
    payload = copy.deepcopy(
        _fixture_payload()
    )

    payload["jobs"][0]["absolute_url"] = (
        "http://boards.greenhouse.io/"
        "acme/jobs/900001"
    )

    with pytest.raises(
        GreenhouseConnectorParseError,
        match="must use https",
    ):
        _connector().parse_candidates(
            _parse_input(payload)
        )


def test_invalid_updated_at_fails_closed() -> None:
    payload = _fixture_payload()

    payload["jobs"][0]["updated_at"] = (
        "not-a-timestamp"
    )

    with pytest.raises(
        GreenhouseConnectorParseError,
        match="ISO-8601",
    ):
        _connector().parse_candidates(
            _parse_input(payload)
        )


def test_invalid_board_token_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="board_token",
    ):
        GreenhouseJobBoardConnector(
            board_token="../secret",
            employer_name="Acme",
        )
