from __future__ import annotations

import hashlib
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from pydantic import ValidationError

from career.connectors.contracts import (
    CareerConnector,
    CareerConnectorDescriptor,
    CareerConnectorParseInput,
    CareerConnectorResult,
    CareerDiscoveryCandidate,
)


NOW = datetime(
    2026,
    8,
    20,
    20,
    30,
    tzinfo=timezone.utc,
)

NORMALIZED_TEXT = (
    '{\n'
    '  "jobs": [\n'
    '    {"id": "123", "title": "Junior Cloud Engineer"}\n'
    "  ]\n"
    "}"
)

NORMALIZED_SHA = hashlib.sha256(
    NORMALIZED_TEXT.encode("utf-8")
).hexdigest()

RESEARCH_EVIDENCE_ID = (
    "research-retrieval-"
    "111111111111111111111111"
)

CONTENT_EVIDENCE_ID = (
    "internet-content-"
    "222222222222222222222222"
)


def _parse_input() -> CareerConnectorParseInput:
    return CareerConnectorParseInput(
        research_evidence_id=RESEARCH_EVIDENCE_ID,
        content_evidence_id=CONTENT_EVIDENCE_ID,
        source_url=(
            "https://api.example.test/jobs"
        ),
        media_type="application/json",
        normalized_text=NORMALIZED_TEXT,
        normalized_text_sha256=NORMALIZED_SHA,
        observed_at=NOW,
    )


def _candidate(
    *,
    observed_at: datetime = NOW,
    title: str = "Junior Cloud Engineer",
) -> CareerDiscoveryCandidate:
    return CareerDiscoveryCandidate.build(
        connector_id=(
            "career-connector-greenhouse"
        ),
        connector_kind="greenhouse",
        employer_name="Acme",
        source_job_id="123",
        title_hint=title,
        location_hint="Ontario, Canada",
        detail_url=(
            "https://jobs.example.test/acme/123"
        ),
        apply_url_hint=(
            "https://jobs.example.test/"
            "acme/123/apply"
        ),
        posted_at_hint=(
            NOW - timedelta(hours=5)
        ),
        discovery_research_evidence_id=(
            RESEARCH_EVIDENCE_ID
        ),
        discovery_content_evidence_id=(
            CONTENT_EVIDENCE_ID
        ),
        discovery_normalized_text_sha256=(
            NORMALIZED_SHA
        ),
        observed_at=observed_at,
    )


def test_descriptor_is_read_only_and_non_authoritative() -> None:
    descriptor = CareerConnectorDescriptor(
        connector_id=(
            "career-connector-greenhouse"
        ),
        connector_kind="greenhouse",
        display_name="Greenhouse",
        priority=1,
        response_media_types=(
            "application/json",
        ),
    )

    assert descriptor.connector_owns_network is False
    assert descriptor.credentials_required is False
    assert (
        descriptor.application_submission_supported
        is False
    )
    assert descriptor.browser_authority_granted is False
    assert (
        descriptor.candidate_metadata_is_job_truth
        is False
    )


def test_descriptor_rejects_unsealed_vendor_json() -> None:
    with pytest.raises(
        ValidationError,
        match="outside the sealed Phase-16",
    ):
        CareerConnectorDescriptor(
            connector_id=(
                "career-connector-greenhouse"
            ),
            connector_kind="greenhouse",
            display_name="Greenhouse",
            priority=1,
            response_media_types=(
                "application/vnd.example+json",
            ),
        )


def test_parse_input_requires_matching_content_hash() -> None:
    parsed = _parse_input()

    assert (
        parsed.normalized_text_sha256
        == NORMALIZED_SHA
    )
    assert parsed.metadata_is_job_truth is False
    assert (
        parsed.application_authority_granted
        is False
    )


def test_parse_input_rejects_hash_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="does not match normalized_text",
    ):
        CareerConnectorParseInput(
            research_evidence_id=(
                RESEARCH_EVIDENCE_ID
            ),
            content_evidence_id=(
                CONTENT_EVIDENCE_ID
            ),
            source_url=(
                "https://api.example.test/jobs"
            ),
            media_type="application/json",
            normalized_text=NORMALIZED_TEXT,
            normalized_text_sha256="0" * 64,
            observed_at=NOW,
        )


def test_parse_input_requires_https_without_credentials() -> None:
    with pytest.raises(
        ValidationError,
        match="must use https",
    ):
        CareerConnectorParseInput(
            research_evidence_id=(
                RESEARCH_EVIDENCE_ID
            ),
            content_evidence_id=(
                CONTENT_EVIDENCE_ID
            ),
            source_url=(
                "http://api.example.test/jobs"
            ),
            media_type="application/json",
            normalized_text=NORMALIZED_TEXT,
            normalized_text_sha256=NORMALIZED_SHA,
            observed_at=NOW,
        )

    with pytest.raises(
        ValidationError,
        match="userinfo credentials",
    ):
        CareerConnectorParseInput(
            research_evidence_id=(
                RESEARCH_EVIDENCE_ID
            ),
            content_evidence_id=(
                CONTENT_EVIDENCE_ID
            ),
            source_url=(
                "https://user:secret@"
                "api.example.test/jobs"
            ),
            media_type="application/json",
            normalized_text=NORMALIZED_TEXT,
            normalized_text_sha256=NORMALIZED_SHA,
            observed_at=NOW,
        )


def test_candidate_has_stable_source_identity() -> None:
    first = _candidate()

    second = _candidate(
        observed_at=(
            NOW + timedelta(minutes=10)
        ),
        title="Junior Cloud Engineer - Updated",
    )

    assert (
        first.source_identity_key
        == second.source_identity_key
    )

    assert (
        first.candidate_id
        != second.candidate_id
    )


def test_candidate_is_permanently_non_authoritative() -> None:
    candidate = _candidate()

    assert candidate.metadata_is_job_truth is False
    assert candidate.freshness_verified is False
    assert candidate.eligible_for_scoring is False
    assert candidate.eligible_for_shortlist is False
    assert (
        candidate.application_authority_granted
        is False
    )


def test_candidate_rejects_non_https_detail_url() -> None:
    with pytest.raises(
        ValueError,
        match="detail_url must use https",
    ):
        CareerDiscoveryCandidate.build(
            connector_id=(
                "career-connector-greenhouse"
            ),
            connector_kind="greenhouse",
            employer_name="Acme",
            source_job_id="123",
            title_hint="Junior Cloud Engineer",
            detail_url=(
                "http://jobs.example.test/acme/123"
            ),
            discovery_research_evidence_id=(
                RESEARCH_EVIDENCE_ID
            ),
            discovery_content_evidence_id=(
                CONTENT_EVIDENCE_ID
            ),
            discovery_normalized_text_sha256=(
                NORMALIZED_SHA
            ),
            observed_at=NOW,
        )


def test_connector_result_binds_all_candidate_provenance() -> None:
    parse_input = _parse_input()
    candidate = _candidate()

    result = CareerConnectorResult.build(
        connector_id=(
            "career-connector-greenhouse"
        ),
        parse_input=parse_input,
        candidates=(candidate,),
    )

    assert result.candidate_count == 1
    assert result.candidates == (candidate,)
    assert result.metadata_is_job_truth is False
    assert (
        result.production_truth_mutation_allowed
        is False
    )
    assert (
        result.application_authority_granted
        is False
    )


def test_connector_result_rejects_cross_evidence_candidate() -> None:
    parse_input = _parse_input()

    wrong_candidate = (
        CareerDiscoveryCandidate.build(
            connector_id=(
                "career-connector-greenhouse"
            ),
            connector_kind="greenhouse",
            employer_name="Acme",
            source_job_id="123",
            title_hint="Junior Cloud Engineer",
            detail_url=(
                "https://jobs.example.test/acme/123"
            ),
            discovery_research_evidence_id=(
                "research-retrieval-"
                "333333333333333333333333"
            ),
            discovery_content_evidence_id=(
                CONTENT_EVIDENCE_ID
            ),
            discovery_normalized_text_sha256=(
                NORMALIZED_SHA
            ),
            observed_at=NOW,
        )
    )

    with pytest.raises(
        ValidationError,
        match="research evidence",
    ):
        CareerConnectorResult.build(
            connector_id=(
                "career-connector-greenhouse"
            ),
            parse_input=parse_input,
            candidates=(wrong_candidate,),
        )


def test_connector_protocol_has_parser_without_network_method() -> None:
    class DummyConnector:
        @property
        def descriptor(
            self,
        ) -> CareerConnectorDescriptor:
            return CareerConnectorDescriptor(
                connector_id=(
                    "career-connector-greenhouse"
                ),
                connector_kind="greenhouse",
                display_name="Greenhouse",
                priority=1,
                response_media_types=(
                    "application/json",
                ),
            )

        def parse_candidates(
            self,
            parse_input: CareerConnectorParseInput,
        ) -> CareerConnectorResult:
            candidate = _candidate()

            return CareerConnectorResult.build(
                connector_id=(
                    self.descriptor.connector_id
                ),
                parse_input=parse_input,
                candidates=(candidate,),
            )

    connector = DummyConnector()

    assert isinstance(
        connector,
        CareerConnector,
    )

    assert hasattr(
        connector,
        "parse_candidates",
    )

    assert not hasattr(
        connector,
        "fetch",
    )

    assert not hasattr(
        connector,
        "submit",
    )
