from __future__ import annotations

import hashlib
import json

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path
from types import (
    SimpleNamespace,
)

import pytest

import career.automation_runner as core

from career.connectors.contracts import (
    CareerDiscoveryCandidate,
)

from career.discovery_router import (
    resolve_discovery_route,
)

from career.workday_automation_runner import (
    CONNECTOR_ID,
    WorkdaySiteSpec,
    build_verified_detail,
    load_sites,
    parse_listing_bundle,
    workday_role_relevant,
)


NOW = datetime(
    2026,
    8,
    25,
    23,
    0,
    tzinfo=timezone.utc,
)

RESEARCH_ID = (
    "research-retrieval-"
    + "a" * 24
)

CONTENT_ID = (
    "internet-content-"
    + "b" * 24
)


def spec() -> WorkdaySiteSpec:

    return WorkdaySiteSpec(
        host=(
            "bmo.wd3."
            "myworkdayjobs.com"
        ),
        tenant="bmo",
        site="Campus",
        employer_name="BMO",
        locale="en-US",
        search_text="",
        max_pages=25,
    )


def listing_bundle():

    payload = {
        "total": 2,
        "jobPostings": [
            {
                "title":
                    "Cloud/AI Platform Engineer",

                "locationsText":
                    "Toronto, ON, CAN",

                "postedOn":
                    "Posted 8 Days Ago",

                "externalPath":
                    (
                        "/job/Toronto-ON-CAN/"
                        "Cloud-AI-Platform-Engineer_"
                        "R260023188-1"
                    ),
            },
            {
                "title":
                    "Investment Banking Analyst",

                "locationsText":
                    "Toronto, ON, CAN",

                "externalPath":
                    (
                        "/job/Toronto-ON-CAN/"
                        "Investment-Banking-Analyst_"
                        "R260000001"
                    ),
            },
        ],
    }

    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    sha = hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()

    return SimpleNamespace(
        retrieval_evidence=(
            SimpleNamespace(
                method="POST",
                request_body_sha256=(
                    "d" * 64
                ),
                evidence_id=(
                    RESEARCH_ID
                ),
                observed_at=NOW,
            )
        ),
        content_evidence=(
            SimpleNamespace(
                evidence_id=(
                    CONTENT_ID
                ),
                media_type=(
                    "application/json"
                ),
                normalized_text=text,
                normalized_text_sha256=(
                    sha
                ),
            )
        ),
    )


def detail_bundle():

    payload = {
        "jobPostingInfo": {
            "title":
                "Cloud/AI Platform Engineer",

            "location":
                "Toronto, ON, CAN",

            "jobReqId":
                "R260023188",

            "postedOn":
                "Posted 8 Days Ago",

            "startDate":
                "2026-08-17",

            "timeType":
                "Full time",

            "externalUrl":
                (
                    "https://bmo.wd3."
                    "myworkdayjobs.com/"
                    "Campus/job/"
                    "Toronto-ON-CAN/"
                    "Cloud-AI-Platform-Engineer_"
                    "R260023188-1"
                ),

            "jobDescription":
                (
                    "<p>Build cloud platforms "
                    "using Terraform and Kubernetes "
                    "in a hybrid environment.</p>"
                ),
        }
    }

    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    sha = hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()

    return SimpleNamespace(
        retrieval_evidence=(
            SimpleNamespace(
                method="GET",
                evidence_id=(
                    "research-retrieval-"
                    + "e" * 24
                ),
                observed_at=NOW,
            )
        ),
        content_evidence=(
            SimpleNamespace(
                normalized_text=text,
                normalized_text_sha256=(
                    sha
                ),
            )
        ),
    )


class FakeAdapter:

    def __init__(
        self,
    ):
        self.calls = []

    async def retrieve_public_url(
        self,
        *,
        objective,
        url,
    ):

        self.calls.append(
            (
                objective,
                url,
            )
        )

        return detail_bundle()


def test_workday_platform_engineer_supplement():

    title = (
        "Cloud/AI Platform Engineer"
    )

    assert (
        core.candidate_role_relevant(
            title
        )
        is False
    )

    assert (
        workday_role_relevant(
            title
        )
        is True
    )


def test_workday_supplement_does_not_admit_banking():

    assert (
        workday_role_relevant(
            "Investment Banking Analyst"
        )
        is False
    )


def test_existing_shared_role_still_admitted():

    title = (
        "DevOps Engineer"
    )

    assert (
        core.candidate_role_relevant(
            title
        )
        is True
    )

    assert (
        workday_role_relevant(
            title
        )
        is True
    )


def test_load_sites_supports_multiple_sites(
    tmp_path: Path,
):

    config = (
        tmp_path
        / "sites.json"
    )

    config.write_text(
        json.dumps(
            {
                "sites": [
                    {
                        "host":
                            (
                                "bmo.wd3."
                                "myworkdayjobs.com"
                            ),
                        "tenant":
                            "bmo",
                        "site":
                            "Campus",
                        "employer_name":
                            "BMO",
                        "enabled":
                            True,
                    },
                    {
                        "host":
                            (
                                "example."
                                "myworkdayjobs.com"
                            ),
                        "tenant":
                            "example",
                        "site":
                            "Careers",
                        "employer_name":
                            "Example Employer",
                        "enabled":
                            True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    sites = load_sites(
        config
    )

    assert len(sites) == 2

    assert (
        sites[0].listing_url
        == (
            "https://bmo.wd3."
            "myworkdayjobs.com/"
            "wday/cxs/bmo/"
            "Campus/jobs"
        )
    )


def test_tenant_must_match_host(
    tmp_path: Path,
):

    config = (
        tmp_path
        / "bad.json"
    )

    config.write_text(
        json.dumps(
            {
                "sites": [
                    {
                        "host":
                            (
                                "bmo.wd3."
                                "myworkdayjobs.com"
                            ),
                        "tenant":
                            "other",
                        "site":
                            "Campus",
                        "employer_name":
                            "BMO",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="tenant",
    ):
        load_sites(
            config
        )


def test_listing_parse_builds_generic_candidate():

    page = parse_listing_bundle(
        bundle=listing_bundle(),
        spec=spec(),
        offset=0,
    )

    assert page.total == 2
    assert len(
        page.candidates
    ) == 2

    candidate = (
        page.candidates[0]
    )

    assert isinstance(
        candidate,
        CareerDiscoveryCandidate,
    )

    assert (
        candidate.connector_id
        == CONNECTOR_ID
    )

    assert (
        candidate.connector_kind
        == "generic_employer"
    )

    assert (
        candidate.employer_name
        == "BMO"
    )

    assert (
        candidate.title_hint
        == "Cloud/AI Platform Engineer"
    )

    assert (
        candidate.location_hint
        == "Toronto, ON, CAN"
    )

    assert (
        candidate.detail_url
        == (
            "https://bmo.wd3."
            "myworkdayjobs.com/"
            "wday/cxs/bmo/"
            "Campus/job/"
            "Cloud-AI-Platform-Engineer_"
            "R260023188-1"
        )
    )

    assert (
        candidate.apply_url_hint
        == (
            "https://bmo.wd3."
            "myworkdayjobs.com/"
            "en-US/Campus/"
            "job/"
            "Cloud-AI-Platform-Engineer_"
            "R260023188-1"
        )
    )


@pytest.mark.asyncio
async def test_verified_detail_uses_phase16_get():

    candidate = (
        parse_listing_bundle(
            bundle=(
                listing_bundle()
            ),
            spec=spec(),
            offset=0,
        )
        .candidates[0]
    )

    adapter = FakeAdapter()

    detail = (
        await build_verified_detail(
            adapter=adapter,
            candidate=candidate,
        )
    )

    assert detail is not None

    assert len(
        adapter.calls
    ) == 1

    assert (
        adapter.calls[0][1]
        == candidate.detail_url
    )

    assert (
        detail.canonical_job_url
        == candidate.detail_url
    )

    assert (
        detail.canonical_apply_url
        == (
            "https://bmo.wd3."
            "myworkdayjobs.com/"
            "Campus/job/"
            "Toronto-ON-CAN/"
            "Cloud-AI-Platform-Engineer_"
            "R260023188-1"
        )
    )

    assert (
        detail.canonical_apply_url
        != candidate.apply_url_hint
    )

    assert (
        detail.title
        == "Cloud/AI Platform Engineer"
    )

    assert (
        detail.location_text
        == "Toronto, ON, CAN"
    )

    assert (
        detail.work_mode
        == "HYBRID"
    )

    assert (
        "Terraform"
        in detail.description_text
    )

    assert (
        detail.application_authority_granted
        is False
    )


def test_workday_route_is_generic_phase16():

    route = resolve_discovery_route(
        "workday",
        {
            "host":
                (
                    "bmo.wd3."
                    "myworkdayjobs.com"
                ),
            "tenant":
                "bmo",
            "site":
                "Campus",
        },
    )

    assert (
        route.route_kind
        == "GENERIC_PHASE16_FALLBACK"
    )

    assert (
        route.connector_module
        is None
    )

    assert (
        route.phase16_network_owner
        is True
    )

    assert (
        route.network_request_created_by_router
        is False
    )
