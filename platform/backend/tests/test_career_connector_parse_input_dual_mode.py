from __future__ import annotations

import hashlib
import json
from datetime import (
    datetime,
    timezone,
)

import pytest
from pydantic import ValidationError

from career.connectors.contracts import (
    CareerConnectorParseInput,
)
from gateway.structured_json_projection import (
    LEVER_LIST_PROFILE_ID,
    project_structured_json,
)

OBSERVED_AT = datetime(
    2026,
    8,
    24,
    12,
    0,
    tzinfo=timezone.utc,
)

RESEARCH_EVIDENCE_ID = "research-retrieval-0123456789abcdef01234567"

CONTENT_EVIDENCE_ID = "internet-content-0123456789abcdef01234567"

SOURCE_URL = "https://api.lever.co/v0/postings/example?mode=json"


def _sha(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _legacy_input() -> CareerConnectorParseInput:
    parser_text = '[{"id":"legacy"}]'

    return CareerConnectorParseInput(
        research_evidence_id=(RESEARCH_EVIDENCE_ID),
        content_evidence_id=(CONTENT_EVIDENCE_ID),
        source_url=SOURCE_URL,
        media_type="application/json",
        parser_text=parser_text,
        parser_text_sha256=(_sha(parser_text)),
        source_body_sha256=("1" * 64),
        observed_at=OBSERVED_AT,
    )


def _structured_evidence():
    body = json.dumps(
        [
            {
                "id": "job-one",
                "text": "Cloud Engineer",
                "hostedUrl": ("https://jobs.lever.co/example/job-one"),
                "applyUrl": ("https://jobs.lever.co/example/job-one/apply"),
                "categories": {
                    "location": "Canada",
                },
                "descriptionPlain": ("not present in projection"),
            }
        ],
        separators=(",", ":"),
    ).encode("utf-8")

    return project_structured_json(
        profile_id=(LEVER_LIST_PROFILE_ID),
        body=body,
        research_evidence_id=(RESEARCH_EVIDENCE_ID),
        source_url=SOURCE_URL,
        source_body_sha256=(hashlib.sha256(body).hexdigest()),
        source_byte_count=len(body),
        source_content_type=("application/json"),
        observed_at=OBSERVED_AT,
    )


def _structured_input(
    **updates,
) -> CareerConnectorParseInput:
    evidence = _structured_evidence()

    payload = {
        "parser_input_kind": "phase16_structured_json_projection",
        "parser_text": evidence.projection_text,
        "parser_text_sha256": evidence.projection_sha256,
        "research_evidence_id": evidence.research_evidence_id,
        "source_body_sha256": evidence.source_body_sha256,
        "source_url": evidence.source_url,
        "media_type": evidence.source_content_type,
        "observed_at": evidence.observed_at,
        "projection_evidence_id": evidence.projection_evidence_id,
        "complete_document_parse": evidence.complete_document_parse,
        "source_record_count": evidence.source_record_count,
        "projected_record_count": evidence.projected_record_count,
        "projection_truncated": evidence.projection_truncated,
    }

    payload.update(updates)

    return CareerConnectorParseInput(**payload)


def test_legacy_mode_uses_frozen_shared_fields() -> None:
    parsed = _legacy_input()

    assert parsed.parser_input_kind == "phase16_normalized_content"

    assert parsed.parser_text
    assert parsed.parser_text_sha256

    assert parsed.source_body_sha256 == "1" * 64

    assert parsed.content_evidence_id == CONTENT_EVIDENCE_ID

    assert parsed.projection_evidence_id is None


def test_structured_mode_uses_projection_as_shared_parser_text() -> None:
    parsed = _structured_input()

    evidence = _structured_evidence()

    assert parsed.parser_input_kind == "phase16_structured_json_projection"

    assert parsed.parser_text == evidence.projection_text

    assert parsed.parser_text_sha256 == evidence.projection_sha256

    assert parsed.source_body_sha256 == evidence.source_body_sha256

    assert parsed.content_evidence_id is None

    assert parsed.projection_evidence_id == evidence.projection_evidence_id

    assert parsed.complete_document_parse is True

    assert parsed.projection_truncated is False

    assert parsed.source_record_count == parsed.projected_record_count


def test_frozen_model_fields_exclude_old_mode_specific_text_fields() -> None:
    fields = CareerConnectorParseInput.model_fields

    assert "parser_text" in fields
    assert "parser_text_sha256" in fields
    assert "source_body_sha256" in fields

    assert "normalized_text" not in fields

    assert "normalized_text_sha256" not in fields

    assert "projection_text" not in fields
    assert "projection_sha256" not in fields

    assert "phase16_normalized_evidence" not in fields


def test_model_dump_uses_only_canonical_shared_fields() -> None:
    parsed = _legacy_input()

    dumped = parsed.model_dump()

    assert "parser_text" in dumped

    assert "parser_text_sha256" in dumped

    assert "source_body_sha256" in dumped

    assert "normalized_text" not in dumped

    assert "normalized_text_sha256" not in dumped

    assert "phase16_normalized_evidence" not in dumped


def test_legacy_constructor_aliases_remain_temporarily_accepted() -> None:
    parser_text = '[{"id":"legacy"}]'

    parsed = CareerConnectorParseInput(
        research_evidence_id=(RESEARCH_EVIDENCE_ID),
        content_evidence_id=(CONTENT_EVIDENCE_ID),
        source_url=SOURCE_URL,
        media_type="application/json",
        normalized_text=parser_text,
        normalized_text_sha256=(_sha(parser_text)),
        source_body_sha256=("2" * 64),
        observed_at=OBSERVED_AT,
        phase16_normalized_evidence=True,
    )

    assert parsed.parser_text == parser_text

    assert parsed.parser_text_sha256 == _sha(parser_text)

    assert parsed.normalized_text == parsed.parser_text

    assert parsed.normalized_text_sha256 == parsed.parser_text_sha256

    assert parsed.phase16_normalized_evidence is True


def test_structured_mode_rejects_legacy_content_binding() -> None:
    with pytest.raises(
        ValidationError,
        match="legacy content_evidence_id",
    ):
        _structured_input(content_evidence_id=(CONTENT_EVIDENCE_ID))


def test_legacy_mode_rejects_projection_binding() -> None:
    legacy = _legacy_input()

    payload = legacy.model_dump()

    payload["projection_evidence_id"] = "structured-projection-test"

    with pytest.raises(
        ValidationError,
        match="projection-only",
    ):
        CareerConnectorParseInput(**payload)


def test_structured_mode_rejects_incomplete_projection() -> None:
    with pytest.raises(
        ValidationError,
        match="incomplete",
    ):
        _structured_input(projection_evidence_id=None)


def test_shared_parser_hash_guard_applies_to_legacy_mode() -> None:
    parser_text = "legacy"

    with pytest.raises(
        ValidationError,
        match="parser_text_sha256",
    ):
        CareerConnectorParseInput(
            research_evidence_id=(RESEARCH_EVIDENCE_ID),
            content_evidence_id=(CONTENT_EVIDENCE_ID),
            source_url=SOURCE_URL,
            media_type="application/json",
            parser_text=parser_text,
            parser_text_sha256=("0" * 64),
            source_body_sha256=("1" * 64),
            observed_at=OBSERVED_AT,
        )


def test_shared_parser_hash_guard_applies_to_projection_mode() -> None:
    with pytest.raises(
        ValidationError,
        match="parser_text_sha256",
    ):
        _structured_input(parser_text_sha256=("0" * 64))


def test_source_body_sha256_is_required_shared_binding() -> None:
    payload = _legacy_input().model_dump()

    del payload["source_body_sha256"]

    with pytest.raises(
        ValidationError,
    ):
        CareerConnectorParseInput(**payload)


def test_structured_mode_rejects_record_count_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="record counts must match",
    ):
        _structured_input(projected_record_count=2)


def test_structured_mode_requires_application_json() -> None:
    with pytest.raises(
        ValidationError,
        match="requires application/json",
    ):
        _structured_input(media_type="text/plain")


def test_structured_mode_rejects_legacy_normalized_marker() -> None:
    evidence = _structured_evidence()

    with pytest.raises(
        ValidationError,
        match="compatibility marker",
    ):
        CareerConnectorParseInput(
            parser_input_kind=("phase16_structured_json_projection"),
            parser_text=(evidence.projection_text),
            parser_text_sha256=(evidence.projection_sha256),
            research_evidence_id=(evidence.research_evidence_id),
            source_body_sha256=(evidence.source_body_sha256),
            source_url=(evidence.source_url),
            media_type=(evidence.source_content_type),
            observed_at=(evidence.observed_at),
            projection_evidence_id=(evidence.projection_evidence_id),
            complete_document_parse=True,
            source_record_count=1,
            projected_record_count=1,
            projection_truncated=False,
            phase16_normalized_evidence=True,
        )


def test_parse_input_remains_non_authoritative() -> None:
    parsed = _structured_input()

    assert parsed.metadata_is_job_truth is False

    assert parsed.application_authority_granted is False

    with pytest.raises(
        ValidationError,
    ):
        CareerConnectorParseInput.model_validate(
            {
                **parsed.model_dump(),
                "metadata_is_job_truth": True,
            }
        )

    with pytest.raises(
        ValidationError,
    ):
        CareerConnectorParseInput.model_validate(
            {
                **parsed.model_dump(),
                "application_authority_granted": True,
            }
        )
