from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from career.connectors.contracts import (
    CareerConnectorParseInput,
)
from career.connectors.smartrecruiters import (
    SMARTRECRUITERS_CONNECTOR_ID,
    SmartRecruitersConnectorParseError,
    SmartRecruitersPostingConnector,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "career" / "smartrecruiters_postings.json"
)

NOW = datetime(
    2026,
    8,
    21,
    12,
    0,
    tzinfo=timezone.utc,
)


def _connector() -> SmartRecruitersPostingConnector:
    return SmartRecruitersPostingConnector(
        company_identifier="acme",
        employer_name="Acme",
    )


def _fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _parse_text(
    text: str,
    *,
    source_url: str | None = None,
    media_type: str = "application/json",
) -> CareerConnectorParseInput:
    connector = _connector()

    return CareerConnectorParseInput(
        source_body_sha256=("1" * 64),
        research_evidence_id=("research-retrieval-0123456789abcdef01234567"),
        content_evidence_id=("internet-content-0123456789abcdef01234567"),
        source_url=(source_url if source_url is not None else connector.jobs_url),
        media_type=media_type,
        normalized_text=text,
        normalized_text_sha256=(hashlib.sha256(text.encode("utf-8")).hexdigest()),
        observed_at=NOW,
        phase16_normalized_evidence=True,
        metadata_is_job_truth=False,
        application_authority_granted=False,
    )


def _parse_payload(
    payload: object,
) -> CareerConnectorParseInput:
    return _parse_text(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def test_descriptor_contract() -> None:
    descriptor = _connector().descriptor

    assert descriptor.connector_id == SMARTRECRUITERS_CONNECTOR_ID
    assert descriptor.connector_kind == "smartrecruiters"
    assert descriptor.connector_owns_network is False
    assert descriptor.credentials_required is False
    assert descriptor.application_submission_supported is False
    assert descriptor.browser_authority_granted is False
    assert descriptor.candidate_metadata_is_job_truth is False


def test_postings_url_is_public_anonymous_and_bounded() -> None:
    assert _connector().jobs_url == (
        "https://api.smartrecruiters.com/"
        "v1/companies/acme/postings?"
        "destination=PUBLIC&limit=100&offset=0"
    )


def test_fixture_maps_active_public_postings() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    assert result.candidate_count == 2
    assert len(result.candidates) == 2

    assert [candidate.title_hint for candidate in result.candidates] == [
        "Cloud Platform Engineer",
        "Junior DevOps Engineer",
    ]


def test_explicit_inactive_posting_is_excluded() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    assert result.candidate_count == 2

    assert all(
        candidate.source_job_id != "33333333-3333-4333-8333-333333333333"
        for candidate in result.candidates
    )


def test_missing_active_is_accepted_under_active_list_contract() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    ids = {candidate.source_job_id for candidate in result.candidates}

    assert "22222222-2222-4222-8222-222222222222" in ids


def test_uuid_is_canonical_source_job_id() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    first = result.candidates[0]

    assert first.source_job_id == ("11111111-1111-4111-8111-111111111111")

    assert first.source_job_id != "legacy-provider-id-1"


def test_company_identifier_must_match_connector() -> None:
    payload = _fixture_payload()

    payload["content"][0]["company"]["identifier"] = "other-company"

    with pytest.raises(SmartRecruitersConnectorParseError):
        _connector().parse_candidates(_parse_payload(payload))


def test_missing_or_malformed_uuid_is_rejected() -> None:
    for value in (
        None,
        "",
        "not-a-uuid",
    ):
        payload = _fixture_payload()

        if value is None:
            payload["content"][0].pop(
                "uuid",
                None,
            )
        else:
            payload["content"][0]["uuid"] = value

        with pytest.raises(SmartRecruitersConnectorParseError):
            _connector().parse_candidates(_parse_payload(payload))


def test_released_date_maps_to_posted_at_hint_only() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    first = result.candidates[0]

    assert first.posted_at_hint == datetime(
        2026,
        8,
        20,
        14,
        30,
        tzinfo=timezone.utc,
    )

    assert first.source_updated_at_hint is None
    assert first.freshness_verified is False


def test_missing_released_date_remains_unverified() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    second = result.candidates[1]

    assert second.posted_at_hint is None
    assert second.source_updated_at_hint is None
    assert second.freshness_verified is False


def test_posting_url_is_preferred_as_detail_url() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    first = result.candidates[0]

    assert first.detail_url == (
        "https://jobs.smartrecruiters.com/acme/11111111-1111-4111-8111-111111111111"
    )


def test_ref_is_detail_url_fallback() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    second = result.candidates[1]

    assert second.detail_url == (
        "https://api.smartrecruiters.com/"
        "v1/companies/acme/postings/"
        "22222222-2222-4222-8222-222222222222"
    )


def test_public_detail_url_is_final_detail_fallback() -> None:
    payload = _fixture_payload()

    row = payload["content"][0]
    row.pop("postingUrl", None)
    row.pop("ref", None)

    result = _connector().parse_candidates(_parse_payload(payload))

    first = result.candidates[0]

    assert first.detail_url == (
        "https://api.smartrecruiters.com/"
        "v1/companies/acme/postings/"
        "11111111-1111-4111-8111-111111111111"
    )


def test_apply_url_is_optional_navigation_metadata_only() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    first, second = result.candidates

    assert first.apply_url_hint == (
        "https://jobs.smartrecruiters.com/"
        "acme/"
        "11111111-1111-4111-8111-111111111111/"
        "apply"
    )

    assert second.apply_url_hint is None
    assert first.application_authority_granted is False
    assert second.application_authority_granted is False


def test_location_object_is_normalized_deterministically() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    first, second = result.candidates

    assert first.location_hint == ("Toronto, ON, CA (Remote)")

    assert second.location_hint == ("Vancouver, BC, CA")


def test_result_and_candidates_fail_closed_for_truth_and_authority() -> None:
    result = _connector().parse_candidates(_parse_payload(_fixture_payload()))

    assert result.metadata_is_job_truth is False
    assert result.production_truth_mutation_allowed is False
    assert result.application_authority_granted is False

    for candidate in result.candidates:
        assert candidate.metadata_is_job_truth is False
        assert candidate.freshness_verified is False
        assert candidate.eligible_for_scoring is False
        assert candidate.eligible_for_shortlist is False
        assert candidate.application_authority_granted is False


def test_non_object_root_is_rejected() -> None:
    with pytest.raises(SmartRecruitersConnectorParseError):
        _connector().parse_candidates(_parse_payload([]))


def test_missing_or_non_array_content_is_rejected() -> None:
    for payload in (
        {},
        {"content": {}},
    ):
        with pytest.raises(SmartRecruitersConnectorParseError):
            _connector().parse_candidates(_parse_payload(payload))


def test_non_object_content_row_is_rejected() -> None:
    with pytest.raises(SmartRecruitersConnectorParseError):
        _connector().parse_candidates(_parse_payload({"content": ["invalid-row"]}))


def test_invalid_date_or_https_url_fails_closed() -> None:
    mutations = [
        (
            "releasedDate",
            "not-a-date",
        ),
        (
            "postingUrl",
            "http://example.com/posting",
        ),
        (
            "applyUrl",
            "http://example.com/apply",
        ),
        (
            "ref",
            "http://example.com/ref",
        ),
    ]

    for field, value in mutations:
        payload = copy.deepcopy(_fixture_payload())

        payload["content"][0][field] = value

        with pytest.raises(SmartRecruitersConnectorParseError):
            _connector().parse_candidates(_parse_payload(payload))
