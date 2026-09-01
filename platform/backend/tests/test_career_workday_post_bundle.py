from __future__ import annotations

import hashlib
from datetime import (
    datetime,
    timezone,
)

import pytest
from pydantic import ValidationError

from career.retrieval import (
    CareerPhase16RetrievalBundle,
)

from gateway.internet_transport import (
    InternetRetrievalResult,
)

from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
)

from gateway.research_retrieval_evidence import (
    ResearchRetrievalEvidenceFactory,
)

from gateway.research_retrieval_service import (
    build_phase16_structured_content_normalizer,
)

from gateway.workday_cxs_request import (
    build_workday_cxs_jobs_body,
    validate_workday_cxs_jobs_body,
)


WORKDAY_URL = (
    "https://bmo.wd3.myworkdayjobs.com/"
    "wday/cxs/bmo/Campus/jobs"
)

GET_URL = (
    "https://example.com/jobs"
)

NOW = datetime(
    2026,
    8,
    25,
    21,
    55,
    tzinfo=timezone.utc,
)


def request():

    return research_request_factory.build(
        ResearchRequestIntent(
            objective=(
                "Offline Career bundle "
                "contract validation."
            ),
            source_kinds=(
                "public_web",
            ),
            max_sources=1,
        )
    )


def workday_request_sha():

    return validate_workday_cxs_jobs_body(
        build_workday_cxs_jobs_body()
    )


def real_pair(
    *,
    method: str,
    url: str,
    request_body_sha256: str | None = None,
    content_type: str = "application/json",
):

    if content_type == "application/json":
        body = (
            b'{"jobPostings":[],"total":0}'
        )
    else:
        body = (
            b"<html><body>jobs</body></html>"
        )

    retrieval = InternetRetrievalResult(
        requested_url=url,
        final_url=url,
        method=method,
        request_body_sha256=(
            request_body_sha256
        ),
        status_code=200,
        reason="OK",
        content_type=content_type,
        content_length=len(body),
        body=body,
        body_sha256=(
            hashlib.sha256(
                body
            ).hexdigest()
        ),
        byte_count=len(body),
        hops=(),
    )

    normalizer = (
        build_phase16_structured_content_normalizer()
    )

    content = normalizer.normalize(
        retrieval
    )

    evidence = (
        ResearchRetrievalEvidenceFactory()
        .build_success(
            request=request(),
            retrieval=retrieval,
            content=content,
            observed_at=NOW,
        )
    )

    return evidence, content


def bundle(
    *,
    method: str,
    url: str,
    request_body_sha256: str | None = None,
    content_type: str = "application/json",
):

    evidence, content = real_pair(
        method=method,
        url=url,
        request_body_sha256=(
            request_body_sha256
        ),
        content_type=(
            content_type
        ),
    )

    return CareerPhase16RetrievalBundle(
        requested_url=url,
        retrieval_evidence=evidence,
        content_evidence=content,
    )


def test_existing_get_contract_remains_admitted():

    value = bundle(
        method="GET",
        url=GET_URL,
    )

    assert (
        value.retrieval_evidence.method
        == "GET"
    )

    assert (
        value.network_execution_owner
        == "phase16-research-gateway"
    )


def test_exact_workday_post_bundle_is_admitted():

    value = bundle(
        method="POST",
        url=WORKDAY_URL,
        request_body_sha256=(
            workday_request_sha()
        ),
    )

    assert (
        value.retrieval_evidence.method
        == "POST"
    )

    assert (
        value.retrieval_evidence
        .request_body_sha256
        == workday_request_sha()
    )

    assert (
        value.career_truth_mutation_allowed
        is False
    )

    assert (
        value.application_authority_granted
        is False
    )

    assert (
        value.browser_authority_granted
        is False
    )


@pytest.mark.parametrize(
    "url",
    (
        (
            "https://example.com/"
            "wday/cxs/example/Campus/jobs"
        ),
        (
            "https://bmo.wd3.myworkdayjobs.com/"
            "wday/cxs/other/Campus/jobs"
        ),
        (
            "https://bmo.wd3.myworkdayjobs.com/"
            "wday/cxs/bmo/Campus/job/foo"
        ),
        (
            "https://bmo.wd3.myworkdayjobs.com/"
            "wday/cxs/bmo/Campus/jobs?x=1"
        ),
    ),
)
def test_nonsealed_post_destinations_rejected(
    url,
):

    with pytest.raises(
        ValidationError
    ):
        bundle(
            method="POST",
            url=url,
            request_body_sha256=(
                workday_request_sha()
            ),
        )


def test_workday_post_non_json_rejected():

    with pytest.raises(
        ValidationError,
        match="application/json",
    ):
        bundle(
            method="POST",
            url=WORKDAY_URL,
            request_body_sha256=(
                workday_request_sha()
            ),
            content_type="text/html",
        )


def test_head_bundle_remains_rejected():

    with pytest.raises(
        ValidationError,
        match=(
            "GET or bounded Workday"
        ),
    ):
        bundle(
            method="HEAD",
            url=GET_URL,
        )


def test_post_without_body_binding_rejected_by_real_evidence_contract():

    with pytest.raises(
        ValidationError,
        match=(
            "request-body SHA-256"
            "|request body"
            "|POST"
        ),
    ):
        bundle(
            method="POST",
            url=WORKDAY_URL,
            request_body_sha256=None,
        )
