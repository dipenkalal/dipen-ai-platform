from __future__ import annotations

import ast
import hashlib
import json
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from career.connectors.contracts import (
    CareerConnectorParseInput,
)
from career.connectors.lever import (
    LEVER_CONNECTOR_ID,
    LEVER_POSTINGS_API_HOST,
    LeverConnectorParseError,
    LeverJobSiteConnector,
)


NOW = datetime(
    2026,
    8,
    20,
    23,
    30,
    tzinfo=timezone.utc,
)

SITE = "acme"
EMPLOYER = "Acme"

URL = (
    "https://api.lever.co/"
    "v0/postings/acme?mode=json"
)

RESEARCH_ID = (
    "research-retrieval-"
    "111111111111111111111111"
)

CONTENT_ID = (
    "internet-content-"
    "222222222222222222222222"
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "career"
    / "lever_postings.json"
)


def _fixture_text() -> str:
    return FIXTURE.read_text(
        encoding="utf-8"
    )


def _parse_input(
    *,
    text: str | None = None,
    source_url: str = URL,
    media_type: str = "application/json",
) -> CareerConnectorParseInput:
    if text is None:
        text = _fixture_text()

    digest = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    return CareerConnectorParseInput(
        research_evidence_id=(
            RESEARCH_ID
        ),
        content_evidence_id=(
            CONTENT_ID
        ),
        source_url=(
            source_url
        ),
        media_type=(
            media_type
        ),
        normalized_text=(
            text
        ),
        normalized_text_sha256=(
            digest
        ),
        observed_at=(
            NOW
        ),
        phase16_normalized_evidence=True,
        metadata_is_job_truth=False,
        application_authority_granted=False,
    )


def _connector() -> LeverJobSiteConnector:
    return LeverJobSiteConnector(
        site_name=SITE,
        employer_name=EMPLOYER,
    )


def test_descriptor_contract() -> None:
    connector = _connector()
    descriptor = connector.descriptor

    assert (
        LEVER_POSTINGS_API_HOST
        == "api.lever.co"
    )

    assert (
        LEVER_CONNECTOR_ID
        == "career-connector-lever-postings-api-v1"
    )

    assert (
        descriptor.connector_id
        == LEVER_CONNECTOR_ID
    )

    assert (
        descriptor.connector_kind
        == "lever"
    )

    assert (
        descriptor.display_name
        == "Lever Postings API"
    )

    assert descriptor.priority == 2

    assert (
        descriptor.response_media_types
        == (
            "application/json",
        )
    )

    assert (
        descriptor.connector_owns_network
        is False
    )

    assert (
        descriptor.credentials_required
        is False
    )

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


def test_exact_global_json_list_url() -> None:
    connector = _connector()

    assert connector.site_name == "acme"
    assert connector.employer_name == "Acme"

    assert (
        connector.jobs_url
        == URL
    )


def test_valid_fixture_parses_two_candidates() -> None:
    result = (
        _connector()
        .parse_candidates(
            _parse_input()
        )
    )

    assert result.candidate_count == 2
    assert len(result.candidates) == 2

    assert {
        candidate.source_job_id
        for candidate in result.candidates
    } == {
        (
            "1a111111-1111-4111-"
            "8111-111111111111"
        ),
        (
            "2b222222-2222-4222-"
            "8222-222222222222"
        ),
    }


def test_core_lever_field_mapping() -> None:
    result = (
        _connector()
        .parse_candidates(
            _parse_input()
        )
    )

    by_id = {
        candidate.source_job_id:
            candidate
        for candidate in result.candidates
    }

    first = by_id[
        (
            "1a111111-1111-4111-"
            "8111-111111111111"
        )
    ]

    assert (
        first.title_hint
        == "Junior Cloud Engineer"
    )

    assert (
        first.location_hint
        == "Toronto, Ontario, Canada"
    )

    assert (
        first.detail_url
        == (
            "https://jobs.lever.co/acme/"
            "1a111111-1111-4111-"
            "8111-111111111111"
        )
    )

    assert (
        first.apply_url_hint
        == first.detail_url + "/apply"
    )


def test_no_timestamp_or_freshness_inference() -> None:
    result = (
        _connector()
        .parse_candidates(
            _parse_input()
        )
    )

    for candidate in result.candidates:
        assert (
            candidate.posted_at_hint
            is None
        )

        assert (
            candidate.source_updated_at_hint
            is None
        )

        assert (
            candidate.freshness_verified
            is False
        )


def test_discovery_authority_remains_closed() -> None:
    result = (
        _connector()
        .parse_candidates(
            _parse_input()
        )
    )

    assert (
        result.metadata_is_job_truth
        is False
    )

    assert (
        result.production_truth_mutation_allowed
        is False
    )

    assert (
        result.application_authority_granted
        is False
    )

    for candidate in result.candidates:
        assert (
            candidate.metadata_is_job_truth
            is False
        )

        assert (
            candidate.freshness_verified
            is False
        )

        assert (
            candidate.eligible_for_scoring
            is False
        )

        assert (
            candidate.eligible_for_shortlist
            is False
        )

        assert (
            candidate.application_authority_granted
            is False
        )


def test_apply_url_is_navigation_hint_only() -> None:
    result = (
        _connector()
        .parse_candidates(
            _parse_input()
        )
    )

    assert (
        result.candidates[0]
        .apply_url_hint
        is not None
    )

    assert (
        result.candidates[0]
        .application_authority_granted
        is False
    )

    assert (
        result.application_authority_granted
        is False
    )


def test_invalid_json_rejected() -> None:
    with pytest.raises(
        LeverConnectorParseError,
        match="not valid JSON",
    ):
        _connector().parse_candidates(
            _parse_input(
                text="{not-json",
            )
        )


def test_non_array_payload_rejected() -> None:
    with pytest.raises(
        LeverConnectorParseError,
        match="root must be an array",
    ):
        _connector().parse_candidates(
            _parse_input(
                text=json.dumps(
                    {
                        "data": [],
                    }
                ),
            )
        )


def test_wrong_media_type_rejected() -> None:
    with pytest.raises(
        LeverConnectorParseError,
        match="must be application/json",
    ):
        _connector().parse_candidates(
            _parse_input(
                media_type="text/html",
            )
        )


def test_cross_site_source_provenance_rejected() -> None:
    with pytest.raises(
        LeverConnectorParseError,
        match="does not match",
    ):
        _connector().parse_candidates(
            _parse_input(
                source_url=(
                    "https://api.lever.co/"
                    "v0/postings/other"
                    "?mode=json"
                ),
            )
        )


def test_malformed_posting_rejected_deterministically() -> None:
    payload = json.loads(
        _fixture_text()
    )

    payload.append(
        {
            "text":
                "Missing identifier",

            "categories": {
                "location":
                    "Toronto, Ontario, Canada",
            },

            "hostedUrl": (
                "https://jobs.lever.co/"
                "acme/missing-id"
            ),
        }
    )

    with pytest.raises(
        LeverConnectorParseError,
        match=r"postings\[2\]\.id",
    ):
        _connector().parse_candidates(
            _parse_input(
                text=json.dumps(
                    payload
                ),
            )
        )


def test_invalid_site_name_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="site_name",
    ):
        LeverJobSiteConnector(
            site_name="../../bad",
            employer_name="Bad",
        )


def test_connector_has_no_network_database_browser_or_submission_authority() -> None:
    path = Path(
        "career/connectors/lever.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    forbidden_roots = {
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "ssl",
        "urllib",
        "sqlite3",
        "subprocess",
        "playwright",
        "selenium",
        "paramiko",
        "docker",
        "gateway",
        "tools",
    }

    violations = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                root = (
                    alias.name
                    .split(".", 1)[0]
                )

                if root in forbidden_roots:
                    violations.append(
                        alias.name
                    )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            module = node.module or ""

            root = module.split(
                ".",
                1,
            )[0]

            if root in forbidden_roots:
                violations.append(
                    module
                )

    assert violations == []

    connector_class = next(
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "LeverJobSiteConnector"
        )
    )

    forbidden_methods = {
        "fetch",
        "request",
        "post",
        "submit",
        "apply",
        "send",
        "upload",
        "execute",
    }

    methods = {
        node.name.lower()
        for node in connector_class.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    assert (
        methods
        & forbidden_methods
    ) == set()
