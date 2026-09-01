"""Phase 19.3G bounded source endpoint validation.

All networking is delegated to CareerPhase16RetrievalAdapter.
This module owns no HTTP, socket, database, repository, browser,
career_sources, application, or source-admission authority.

Maximum state produced here: DETAIL_PROVEN.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import quote

from career.phase16_retrieval_adapter import (
    CareerPhase16RetrievalAdapter,
)
from career.source_discovery import (
    CareerSourceDiscoveryCandidate,
    DiscoveryState,
    transition_candidate,
)


class SourceDiscoveryValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SourceListingRequest:
    provider_kind: str
    url: str
    transport: Literal["GET", "WORKDAY_CXS_POST"]


@dataclass(frozen=True, slots=True)
class SourceDiscoveryValidationResult:
    candidate: CareerSourceDiscoveryCandidate
    listing_url: str
    detail_url: str
    listing_research_evidence_id: str
    detail_research_evidence_id: str


class Phase16SourceValidationGateway(Protocol):
    async def retrieve_public_url(
        self,
        *,
        objective: str,
        url: str,
    ):
        ...

    async def retrieve_workday_cxs_jobs(
        self,
        *,
        objective: str,
        url: str,
        offset: int = 0,
        search_text: str = "",
    ):
        ...


def _identity(
    candidate: CareerSourceDiscoveryCandidate,
) -> dict[str, str]:
    if (
        candidate.provider_identity_json is None
        or candidate.provider_kind is None
    ):
        raise SourceDiscoveryValidationError(
            "endpoint candidate lacks provider identity"
        )

    try:
        value = json.loads(
            candidate.provider_identity_json
        )
    except json.JSONDecodeError as exc:
        raise SourceDiscoveryValidationError(
            "provider identity JSON is invalid"
        ) from exc

    if not isinstance(value, dict):
        raise SourceDiscoveryValidationError(
            "provider identity must be an object"
        )

    if not all(
        isinstance(k, str) and isinstance(v, str)
        for k, v in value.items()
    ):
        raise SourceDiscoveryValidationError(
            "provider identity fields must be strings"
        )

    return value


def build_listing_validation_request(
    candidate: CareerSourceDiscoveryCandidate,
) -> SourceListingRequest:
    if candidate.state is not DiscoveryState.ENDPOINT_CANDIDATE:
        raise SourceDiscoveryValidationError(
            "listing validation requires ENDPOINT_CANDIDATE"
        )

    identity = _identity(candidate)
    kind = candidate.provider_kind

    if kind == "greenhouse":
        token = quote(
            identity["board_token"],
            safe="",
        )

        return SourceListingRequest(
            provider_kind=kind,
            url=(
                "https://boards-api.greenhouse.io"
                f"/v1/boards/{token}/jobs"
            ),
            transport="GET",
        )

    if kind == "lever":
        site = quote(
            identity["site"],
            safe="",
        )

        return SourceListingRequest(
            provider_kind=kind,
            url=(
                "https://api.lever.co"
                f"/v0/postings/{site}?mode=json"
            ),
            transport="GET",
        )

    if kind == "ashby":
        board = quote(
            identity["board"],
            safe="",
        )

        return SourceListingRequest(
            provider_kind=kind,
            url=(
                "https://api.ashbyhq.com"
                f"/posting-api/job-board/{board}"
                "?includeCompensation=false"
            ),
            transport="GET",
        )

    if kind == "smartrecruiters":
        company = quote(
            identity["company_identifier"],
            safe="",
        )

        return SourceListingRequest(
            provider_kind=kind,
            url=(
                "https://api.smartrecruiters.com"
                f"/v1/companies/{company}/postings"
                "?destination=PUBLIC&limit=100&offset=0"
            ),
            transport="GET",
        )

    if kind == "workday":
        host = identity["host"]
        tenant = quote(
            identity["tenant"],
            safe="",
        )
        site = quote(
            identity["site"],
            safe="",
        )

        return SourceListingRequest(
            provider_kind=kind,
            url=(
                f"https://{host}"
                f"/wday/cxs/{tenant}/{site}/jobs"
            ),
            transport="WORKDAY_CXS_POST",
        )

    raise SourceDiscoveryValidationError(
        f"unsupported provider kind: {kind!r}"
    )


def _assert_phase16_bundle(
    bundle,
    *,
    requested_url: str,
    expected_method: str,
) -> None:
    if (
        getattr(
            bundle,
            "network_execution_owner",
            None,
        )
        != "phase16-research-gateway"
    ):
        raise SourceDiscoveryValidationError(
            "network owner is not Phase16"
        )

    for field in (
        "career_truth_mutation_allowed",
        "application_authority_granted",
        "browser_authority_granted",
    ):
        if getattr(bundle, field, None) is not False:
            raise SourceDiscoveryValidationError(
                f"unexpected authority flag: {field}"
            )

    evidence = bundle.retrieval_evidence
    content = bundle.content_evidence

    if evidence.outcome != "succeeded":
        raise SourceDiscoveryValidationError(
            "retrieval evidence did not succeed"
        )

    if evidence.stage != "completed":
        raise SourceDiscoveryValidationError(
            "retrieval evidence is not completed"
        )

    if evidence.method != expected_method:
        raise SourceDiscoveryValidationError(
            "retrieval method mismatch"
        )

    if evidence.requested_url != requested_url:
        raise SourceDiscoveryValidationError(
            "retrieval requested URL mismatch"
        )

    if evidence.final_url != requested_url:
        raise SourceDiscoveryValidationError(
            "redirected endpoint is not accepted"
        )

    if content.truncated:
        raise SourceDiscoveryValidationError(
            "truncated Phase16 content is not proof"
        )

    if (
        evidence.content_evidence_id
        != content.evidence_id
    ):
        raise SourceDiscoveryValidationError(
            "content evidence binding mismatch"
        )

    if (
        evidence.normalized_text_sha256
        != content.normalized_text_sha256
    ):
        raise SourceDiscoveryValidationError(
            "normalized content hash mismatch"
        )


def _json_content(bundle):
    content = bundle.content_evidence

    if content.media_type != "application/json":
        raise SourceDiscoveryValidationError(
            "listing proof requires application/json"
        )

    try:
        return json.loads(content.normalized_text)
    except json.JSONDecodeError as exc:
        raise SourceDiscoveryValidationError(
            "listing payload is invalid JSON"
        ) from exc


def _first_object(values):
    if not isinstance(values, list):
        raise SourceDiscoveryValidationError(
            "listing record collection is invalid"
        )

    for value in values:
        if isinstance(value, dict):
            return value

    raise SourceDiscoveryValidationError(
        "listing contains no usable record"
    )


def _required_scalar(
    value,
    field: str,
) -> str:
    if isinstance(value, bool):
        raise SourceDiscoveryValidationError(
            f"{field} is invalid"
        )

    if not isinstance(value, (str, int)):
        raise SourceDiscoveryValidationError(
            f"{field} is missing"
        )

    text = str(value).strip()

    if not text:
        raise SourceDiscoveryValidationError(
            f"{field} is empty"
        )

    return text


def _workday_slug(
    external_path: object,
) -> str:
    text = _required_scalar(
        external_path,
        "externalPath",
    )

    marker = "/job/"

    if marker not in text:
        raise SourceDiscoveryValidationError(
            "Workday externalPath lacks /job/"
        )

    slug = text.split(
        marker,
        1,
    )[1].strip("/")

    if not slug:
        raise SourceDiscoveryValidationError(
            "Workday detail slug is empty"
        )

    return slug


def detail_url_from_listing(
    candidate: CareerSourceDiscoveryCandidate,
    bundle,
) -> str:
    identity = _identity(candidate)
    payload = _json_content(bundle)
    kind = candidate.provider_kind

    if kind == "greenhouse":
        if not isinstance(payload, dict):
            raise SourceDiscoveryValidationError(
                "Greenhouse root must be object"
            )

        row = _first_object(
            payload.get("jobs")
        )

        job_id = quote(
            _required_scalar(
                row.get("id"),
                "Greenhouse job id",
            ),
            safe="",
        )

        token = quote(
            identity["board_token"],
            safe="",
        )

        return (
            "https://boards-api.greenhouse.io"
            f"/v1/boards/{token}/jobs/{job_id}"
        )

    if kind == "lever":
        row = _first_object(payload)

        job_id = quote(
            _required_scalar(
                row.get("id"),
                "Lever posting id",
            ),
            safe="",
        )

        site = quote(
            identity["site"],
            safe="",
        )

        return (
            "https://api.lever.co"
            f"/v0/postings/{site}/{job_id}"
        )

    if kind == "ashby":
        if not isinstance(payload, dict):
            raise SourceDiscoveryValidationError(
                "Ashby root must be object"
            )

        row = _first_object(
            payload.get("jobs")
        )

        value = _required_scalar(
            row.get("jobUrl"),
            "Ashby jobUrl",
        )

        if not value.startswith("https://"):
            raise SourceDiscoveryValidationError(
                "Ashby jobUrl must be HTTPS"
            )

        return value

    if kind == "smartrecruiters":
        if not isinstance(payload, dict):
            raise SourceDiscoveryValidationError(
                "SmartRecruiters root must be object"
            )

        row = _first_object(
            payload.get("content")
        )

        posting_id = quote(
            _required_scalar(
                row.get("uuid"),
                "SmartRecruiters uuid",
            ),
            safe="",
        )

        company = quote(
            identity[
                "company_identifier"
            ],
            safe="",
        )

        return (
            "https://api.smartrecruiters.com"
            f"/v1/companies/{company}"
            f"/postings/{posting_id}"
        )

    if kind == "workday":
        if not isinstance(payload, dict):
            raise SourceDiscoveryValidationError(
                "Workday root must be object"
            )

        row = _first_object(
            payload.get("jobPostings")
        )

        slug = _workday_slug(
            row.get("externalPath")
        )

        host = identity["host"]
        tenant = quote(
            identity["tenant"],
            safe="",
        )
        site = quote(
            identity["site"],
            safe="",
        )

        return (
            f"https://{host}"
            f"/wday/cxs/{tenant}/{site}"
            f"/job/{slug}"
        )

    raise SourceDiscoveryValidationError(
        "unsupported provider kind"
    )


async def validate_endpoint_candidate(
    candidate: CareerSourceDiscoveryCandidate,
    gateway: Phase16SourceValidationGateway,
) -> SourceDiscoveryValidationResult:
    request = build_listing_validation_request(
        candidate
    )

    if request.transport == "WORKDAY_CXS_POST":
        listing_bundle = (
            await gateway.retrieve_workday_cxs_jobs(
                objective=(
                    "Prove one bounded Workday "
                    "source listing through Phase16."
                ),
                url=request.url,
                offset=0,
                search_text="",
            )
        )
        expected_method = "POST"

    else:
        listing_bundle = (
            await gateway.retrieve_public_url(
                objective=(
                    "Prove one bounded public ATS "
                    "source listing through Phase16."
                ),
                url=request.url,
            )
        )
        expected_method = "GET"

    _assert_phase16_bundle(
        listing_bundle,
        requested_url=request.url,
        expected_method=expected_method,
    )

    detail_url = detail_url_from_listing(
        candidate,
        listing_bundle,
    )

    listing_evidence = (
        listing_bundle.retrieval_evidence
    )

    listing_proven = transition_candidate(
        candidate,
        DiscoveryState.LISTING_PROVEN,
        at=listing_evidence.observed_at,
        listing_research_evidence_id=(
            listing_evidence.evidence_id
        ),
    )

    detail_bundle = (
        await gateway.retrieve_public_url(
            objective=(
                "Prove one bounded public ATS "
                "detail through Phase16."
            ),
            url=detail_url,
        )
    )

    _assert_phase16_bundle(
        detail_bundle,
        requested_url=detail_url,
        expected_method="GET",
    )

    detail_evidence = (
        detail_bundle.retrieval_evidence
    )

    detail_proven = transition_candidate(
        listing_proven,
        DiscoveryState.DETAIL_PROVEN,
        at=detail_evidence.observed_at,
        detail_research_evidence_id=(
            detail_evidence.evidence_id
        ),
    )

    return SourceDiscoveryValidationResult(
        candidate=detail_proven,
        listing_url=request.url,
        detail_url=detail_url,
        listing_research_evidence_id=(
            listing_evidence.evidence_id
        ),
        detail_research_evidence_id=(
            detail_evidence.evidence_id
        ),
    )


def default_phase16_validation_gateway(
) -> CareerPhase16RetrievalAdapter:
    return CareerPhase16RetrievalAdapter()
