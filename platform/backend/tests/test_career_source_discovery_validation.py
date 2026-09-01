import hashlib
import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace

import pytest

from career.ats_identification import (
    identify_career_url,
)
from career.source_discovery import (
    DiscoveryState,
)
from career.source_discovery_generation import (
    generate_discovery_candidate,
)
from career.source_discovery_validation import (
    SourceDiscoveryValidationError,
    build_listing_validation_request,
    detail_url_from_listing,
    validate_endpoint_candidate,
)


NOW = datetime(
    2026, 9, 1, 4, 0,
    tzinfo=timezone.utc,
)


def candidate(url, employer="Employer"):
    return generate_discovery_candidate(
        employer_name=employer,
        identification=identify_career_url(url),
        discovery_research_evidence_id=(
            "research-retrieval-"
            "111111111111111111111111"
        ),
        observed_at=NOW,
    )


def bundle(
    url,
    payload,
    *,
    method="GET",
    evidence_suffix="222222222222222222222222",
    observed_at=None,
    owner="phase16-research-gateway",
    truncated=False,
):
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    sha = hashlib.sha256(
        text.encode()
    ).hexdigest()

    content_id = (
        "internet-content-"
        "aaaaaaaaaaaaaaaaaaaaaaaa"
    )

    return SimpleNamespace(
        network_execution_owner=owner,
        career_truth_mutation_allowed=False,
        application_authority_granted=False,
        browser_authority_granted=False,
        retrieval_evidence=SimpleNamespace(
            evidence_id=(
                "research-retrieval-"
                + evidence_suffix
            ),
            outcome="succeeded",
            stage="completed",
            method=method,
            requested_url=url,
            final_url=url,
            content_evidence_id=content_id,
            normalized_text_sha256=sha,
            observed_at=(
                observed_at
                or NOW + timedelta(minutes=1)
            ),
        ),
        content_evidence=SimpleNamespace(
            evidence_id=content_id,
            media_type="application/json",
            normalized_text=text,
            normalized_text_sha256=sha,
            truncated=truncated,
        ),
    )


@pytest.mark.parametrize(
    ("career_url", "expected_url", "transport"),
    [
        (
            "https://job-boards.greenhouse.io/lush",
            "https://boards-api.greenhouse.io"
            "/v1/boards/lush/jobs",
            "GET",
        ),
        (
            "https://jobs.lever.co/shyftlabs",
            "https://api.lever.co"
            "/v0/postings/shyftlabs?mode=json",
            "GET",
        ),
        (
            "https://jobs.ashbyhq.com/sentry",
            "https://api.ashbyhq.com"
            "/posting-api/job-board/sentry"
            "?includeCompensation=false",
            "GET",
        ),
        (
            "https://careers.smartrecruiters.com/ServiceNow",
            "https://api.smartrecruiters.com"
            "/v1/companies/ServiceNow/postings"
            "?destination=PUBLIC&limit=100&offset=0",
            "GET",
        ),
        (
            "https://td.wd3.myworkdayjobs.com/TD_Bank_Careers",
            "https://td.wd3.myworkdayjobs.com"
            "/wday/cxs/td/TD_Bank_Careers/jobs",
            "WORKDAY_CXS_POST",
        ),
    ],
)
def test_listing_requests_are_exact(
    career_url,
    expected_url,
    transport,
):
    value = build_listing_validation_request(
        candidate(career_url)
    )

    assert value.url == expected_url
    assert value.transport == transport


@pytest.mark.parametrize(
    ("career_url", "payload", "expected"),
    [
        (
            "https://job-boards.greenhouse.io/lush",
            {"jobs": [{"id": 123}]},
            "https://boards-api.greenhouse.io"
            "/v1/boards/lush/jobs/123",
        ),
        (
            "https://jobs.lever.co/shyftlabs",
            [{"id": "abc"}],
            "https://api.lever.co"
            "/v0/postings/shyftlabs/abc",
        ),
        (
            "https://jobs.ashbyhq.com/sentry",
            {
                "jobs": [
                    {
                        "jobUrl":
                        "https://jobs.ashbyhq.com/sentry/abc"
                    }
                ]
            },
            "https://jobs.ashbyhq.com/sentry/abc",
        ),
        (
            "https://careers.smartrecruiters.com/ServiceNow",
            {"content": [{"uuid": "abc"}]},
            "https://api.smartrecruiters.com"
            "/v1/companies/ServiceNow/postings/abc",
        ),
        (
            "https://td.wd3.myworkdayjobs.com/TD_Bank_Careers",
            {
                "jobPostings": [
                    {
                        "externalPath":
                        "/job/Toronto/Cloud-Role_R123"
                    }
                ]
            },
            "https://td.wd3.myworkdayjobs.com"
            "/wday/cxs/td/TD_Bank_Careers"
            "/job/Toronto/Cloud-Role_R123",
        ),
    ],
)
def test_detail_derivation_is_deterministic(
    career_url,
    payload,
    expected,
):
    source = candidate(career_url)
    request = build_listing_validation_request(
        source
    )

    value = detail_url_from_listing(
        source,
        bundle(
            request.url,
            payload,
            method=(
                "POST"
                if request.transport
                == "WORKDAY_CXS_POST"
                else "GET"
            ),
        ),
    )

    assert value == expected


class FakeGateway:
    def __init__(
        self,
        listing,
        detail,
    ):
        self.listing = listing
        self.detail = detail
        self.calls = []

    async def retrieve_public_url(
        self,
        *,
        objective,
        url,
    ):
        self.calls.append(
            ("GET", url)
        )

        if url == self.detail.retrieval_evidence.requested_url:
            return self.detail

        return self.listing

    async def retrieve_workday_cxs_jobs(
        self,
        *,
        objective,
        url,
        offset=0,
        search_text="",
    ):
        self.calls.append(
            ("POST", url, offset, search_text)
        )
        return self.listing


@pytest.mark.asyncio
async def test_get_provider_reaches_detail_proven_only():
    source = candidate(
        "https://careers.smartrecruiters.com/ServiceNow"
    )

    request = build_listing_validation_request(
        source
    )

    listing = bundle(
        request.url,
        {"content": [{"uuid": "job-1"}]},
    )

    detail_url = (
        "https://api.smartrecruiters.com"
        "/v1/companies/ServiceNow/postings/job-1"
    )

    detail = bundle(
        detail_url,
        {"name": "Cloud Engineer"},
        evidence_suffix=(
            "333333333333333333333333"
        ),
        observed_at=NOW + timedelta(minutes=2),
    )

    result = await validate_endpoint_candidate(
        source,
        FakeGateway(
            listing,
            detail,
        ),
    )

    assert (
        result.candidate.state
        is DiscoveryState.DETAIL_PROVEN
    )

    assert (
        result.candidate
        .listing_research_evidence_id
        == listing.retrieval_evidence.evidence_id
    )

    assert (
        result.candidate
        .detail_research_evidence_id
        == detail.retrieval_evidence.evidence_id
    )

    assert (
        result.candidate.admitted_source_id
        is None
    )


@pytest.mark.asyncio
async def test_workday_uses_bounded_post_then_get():
    source = candidate(
        "https://td.wd3.myworkdayjobs.com/TD_Bank_Careers"
    )

    request = build_listing_validation_request(
        source
    )

    listing = bundle(
        request.url,
        {
            "jobPostings": [
                {
                    "externalPath":
                    "/job/Toronto/Test_R1"
                }
            ]
        },
        method="POST",
    )

    detail_url = (
        "https://td.wd3.myworkdayjobs.com"
        "/wday/cxs/td/TD_Bank_Careers"
        "/job/Toronto/Test_R1"
    )

    detail = bundle(
        detail_url,
        {"jobPostingInfo": {"title": "Test"}},
        evidence_suffix=(
            "333333333333333333333333"
        ),
        observed_at=NOW + timedelta(minutes=2),
    )

    gateway = FakeGateway(
        listing,
        detail,
    )

    result = await validate_endpoint_candidate(
        source,
        gateway,
    )

    assert gateway.calls == [
        (
            "POST",
            request.url,
            0,
            "",
        ),
        (
            "GET",
            detail_url,
        ),
    ]

    assert (
        result.candidate.state
        is DiscoveryState.DETAIL_PROVEN
    )


@pytest.mark.asyncio
async def test_wrong_network_owner_fails_closed():
    source = candidate(
        "https://jobs.lever.co/shyftlabs"
    )

    request = build_listing_validation_request(
        source
    )

    listing = bundle(
        request.url,
        [{"id": "job"}],
        owner="career-direct-http",
    )

    detail = bundle(
        "https://api.lever.co"
        "/v0/postings/shyftlabs/job",
        {},
    )

    with pytest.raises(
        SourceDiscoveryValidationError,
        match="Phase16",
    ):
        await validate_endpoint_candidate(
            source,
            FakeGateway(
                listing,
                detail,
            ),
        )

    assert (
        source.state
        is DiscoveryState.ENDPOINT_CANDIDATE
    )


@pytest.mark.asyncio
async def test_truncated_listing_is_not_proof():
    source = candidate(
        "https://jobs.ashbyhq.com/sentry"
    )

    request = build_listing_validation_request(
        source
    )

    listing = bundle(
        request.url,
        {
            "jobs": [
                {
                    "jobUrl":
                    "https://jobs.ashbyhq.com/sentry/job"
                }
            ]
        },
        truncated=True,
    )

    detail = bundle(
        "https://jobs.ashbyhq.com/sentry/job",
        {},
    )

    with pytest.raises(
        SourceDiscoveryValidationError,
        match="truncated",
    ):
        await validate_endpoint_candidate(
            source,
            FakeGateway(
                listing,
                detail,
            ),
        )


def test_listing_proof_cannot_start_from_discovered():
    value = candidate(
        "https://jobs.lever.co/"
    )

    assert (
        value.state
        is DiscoveryState.ATS_IDENTIFIED
    )

    with pytest.raises(
        SourceDiscoveryValidationError,
    ):
        build_listing_validation_request(
            value
        )


def test_validator_source_has_no_higher_state_names():
    from pathlib import Path

    text = Path(
        "career/source_discovery_validation.py"
    ).read_text()

    assert "ADMISSION_READY" not in text
    assert "ADMITTED" not in text
