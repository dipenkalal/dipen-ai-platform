from __future__ import annotations

import os

from datetime import (
    datetime,
    timezone,
)

import pytest

from gateway.internet_destination_policy import (
    InternetDestinationIntent,
    InternetDestinationPolicy,
    InternetDestinationRequest,
)

from gateway.internet_transport import (
    InternetTransportError,
    PinnedHTTPSFetcher,
)

from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
)

from gateway.research_retrieval_evidence import (
    ResearchRetrievalEvidenceFactory,
)

from gateway.workday_cxs_request import (
    WorkdayCXSRequestError,
    build_workday_cxs_jobs_body,
    validate_workday_cxs_jobs_body,
)


URL = (
    "https://bmo.wd3.myworkdayjobs.com/"
    "wday/cxs/bmo/Campus/jobs"
)


def body() -> bytes:

    return (
        build_workday_cxs_jobs_body()
    )


def body_sha() -> str:

    return (
        validate_workday_cxs_jobs_body(
            body()
        )
    )


def test_canonical_body():

    assert body() == (
        b'{"appliedFacets":{},'
        b'"limit":20,'
        b'"offset":0,'
        b'"searchText":""}'
    )

    assert len(
        body_sha()
    ) == 64


@pytest.mark.parametrize(
    "offset",
    (
        -20,
        1,
        21,
        2020,
    ),
)
def test_offset_boundary(
    offset,
):

    with pytest.raises(
        WorkdayCXSRequestError
    ):

        build_workday_cxs_jobs_body(
            offset=offset
        )


def test_noncanonical_body_rejected():

    with pytest.raises(
        WorkdayCXSRequestError
    ):

        validate_workday_cxs_jobs_body(
            b'{ "appliedFacets": {}, '
            b'"limit": 20, '
            b'"offset": 0, '
            b'"searchText": "" }'
        )


def test_legacy_generic_post_exact_finding_set():

    decision = (
        InternetDestinationPolicy()
        .preflight(
            InternetDestinationIntent(
                url=(
                    "https://example.com/"
                ),
                method="POST",
            )
        )
    )

    assert (
        decision.disposition
        == "rejected"
    )

    assert {
        finding.rule_id
        for finding
        in decision.findings
    } == {
        "unsupported-method"
    }


def test_generic_post_with_workday_body_still_legacy_rejection():

    decision = (
        InternetDestinationPolicy()
        .preflight(
            InternetDestinationIntent(
                url=(
                    "https://example.com/jobs"
                ),
                method="POST",
                request_body_sha256=(
                    body_sha()
                ),
            )
        )
    )

    assert (
        decision.disposition
        == "rejected"
    )

    assert {
        finding.rule_id
        for finding
        in decision.findings
    } == {
        "unsupported-method"
    }


def test_exact_workday_post_is_accepted():

    decision = (
        InternetDestinationPolicy()
        .preflight(
            InternetDestinationIntent(
                url=URL,
                method="POST",
                request_body_sha256=(
                    body_sha()
                ),
            )
        )
    )

    assert (
        decision.disposition
        == "accepted"
    )

    assert (
        decision.admission
        is not None
    )

    assert (
        decision.admission.method
        == "POST"
    )

    assert (
        decision.admission
        .request_body_sha256
        == body_sha()
    )


def test_workday_wrong_path_is_rejected():

    decision = (
        InternetDestinationPolicy()
        .preflight(
            InternetDestinationIntent(
                url=(
                    "https://bmo.wd3.myworkdayjobs.com/"
                    "wday/cxs/bmo/Campus/job/foo"
                ),
                method="POST",
                request_body_sha256=(
                    body_sha()
                ),
            )
        )
    )

    assert (
        decision.disposition
        == "rejected"
    )

    rules = {
        finding.rule_id
        for finding
        in decision.findings
    }

    assert (
        "unsupported-method"
        in rules
    )

    assert (
        "workday-post-path-rejected"
        in rules
    )


def test_workday_tenant_mismatch_is_rejected():

    decision = (
        InternetDestinationPolicy()
        .preflight(
            InternetDestinationIntent(
                url=(
                    "https://bmo.wd3.myworkdayjobs.com/"
                    "wday/cxs/other/Campus/jobs"
                ),
                method="POST",
                request_body_sha256=(
                    body_sha()
                ),
            )
        )
    )

    assert (
        decision.disposition
        == "rejected"
    )

    assert (
        "workday-post-tenant-mismatch"
        in {
            finding.rule_id
            for finding
            in decision.findings
        }
    )


def test_workday_requires_body_binding():

    decision = (
        InternetDestinationPolicy()
        .preflight(
            InternetDestinationIntent(
                url=URL,
                method="POST",
            )
        )
    )

    assert (
        decision.disposition
        == "rejected"
    )

    assert (
        "workday-post-body-binding-required"
        in {
            finding.rule_id
            for finding
            in decision.findings
        }
    )


def test_get_admission_hash_unchanged():

    expected = os.environ[
        "EXPECTED_GET_ADMISSION_SHA"
    ]

    decision = (
        InternetDestinationPolicy()
        .evaluate(
            InternetDestinationRequest(
                url=(
                    "https://example.com/"
                    "jobs?x=1"
                ),
                method="GET",
                resolved_addresses=(
                    "8.8.8.8",
                ),
            )
        )
    )

    assert (
        decision.disposition
        == "accepted"
    )

    assert (
        decision.admission
        is not None
    )

    assert (
        decision.admission
        .admission_sha256
        == expected
    )

    assert (
        decision.admission
        .request_body_sha256
        is None
    )


def test_real_http_crlf():

    decision = (
        InternetDestinationPolicy()
        .evaluate(
            InternetDestinationRequest(
                url=URL,
                method="POST",
                request_body_sha256=(
                    body_sha()
                ),
                resolved_addresses=(
                    "8.8.8.8",
                ),
            )
        )
    )

    assert (
        decision.disposition
        == "accepted"
    )

    assert (
        decision.admission
        is not None
    )

    request = (
        PinnedHTTPSFetcher
        ._build_request(
            decision.admission,
            request_body=body(),
        )
    )

    assert request.startswith(
        b"POST /wday/cxs/bmo/Campus/jobs "
        b"HTTP/1.1\r\n"
    )

    assert (
        b"\r\nHost: "
        in request
    )

    assert (
        b"\r\nContent-Type: "
        b"application/json\r\n"
        in request
    )

    assert (
        b"\r\n\r\n"
        in request
    )

    assert (
        b"\\r\\n"
        not in request
    )

    headers, payload = (
        request.split(
            b"\r\n\r\n",
            1,
        )
    )

    assert (
        payload
        == body()
    )

    assert (
        b"Authorization:"
        not in headers
    )

    assert (
        b"Cookie:"
        not in headers
    )


def test_request_body_hash_mismatch_rejected():

    decision = (
        InternetDestinationPolicy()
        .evaluate(
            InternetDestinationRequest(
                url=URL,
                method="POST",
                request_body_sha256=(
                    body_sha()
                ),
                resolved_addresses=(
                    "8.8.8.8",
                ),
            )
        )
    )

    assert (
        decision.admission
        is not None
    )

    altered = (
        build_workday_cxs_jobs_body(
            offset=20
        )
    )

    with pytest.raises(
        InternetTransportError
    ) as exc:

        PinnedHTTPSFetcher._build_request(
            decision.admission,
            request_body=(
                altered
            ),
        )

    assert (
        exc.value.code
        == "request-body-hash-mismatch"
    )


def test_post_failure_evidence_binds_body():

    request = (
        research_request_factory
        .build(
            ResearchRequestIntent(
                objective=(
                    "Offline bounded Workday "
                    "POST evidence contract."
                ),
                source_kinds=(
                    "public_web",
                ),
                max_sources=1,
            )
        )
    )

    evidence = (
        ResearchRetrievalEvidenceFactory()
        .build_failure(
            request=request,
            requested_url=URL,
            method="POST",
            request_body_sha256=(
                body_sha()
            ),
            stage="response",
            error_code=(
                "offline-test"
            ),
            error_detail=(
                "Offline contract test."
            ),
            observed_at=(
                datetime.now(
                    timezone.utc
                )
            ),
        )
    )

    assert (
        evidence.method
        == "POST"
    )

    assert (
        evidence.request_body_sha256
        == body_sha()
    )

    assert (
        evidence.canonical_hash()
        == evidence.evidence_sha256
    )


def test_get_evidence_hash_compatibility():

    request = (
        research_request_factory
        .build(
            ResearchRequestIntent(
                objective=(
                    "Offline GET compatibility."
                ),
                source_kinds=(
                    "public_web",
                ),
                max_sources=1,
            )
        )
    )

    evidence = (
        ResearchRetrievalEvidenceFactory()
        .build_failure(
            request=request,
            requested_url=(
                "https://example.com/"
            ),
            method="GET",
            stage="response",
            error_code=(
                "offline-test"
            ),
            error_detail=(
                "Offline compatibility."
            ),
            observed_at=(
                datetime.now(
                    timezone.utc
                )
            ),
        )
    )

    assert (
        evidence.request_body_sha256
        is None
    )

    assert (
        evidence.canonical_hash()
        == evidence.evidence_sha256
    )
