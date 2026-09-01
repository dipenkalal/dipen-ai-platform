from __future__ import annotations

import hashlib

from datetime import (
    datetime,
    timezone,
)

import pytest

from gateway.internet_transport import (
    InternetRetrievalResult,
    InternetTransportError,
)

from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
)

from gateway.research_retrieval_repository import (
    PersistedResearchRetrievalRecord,
)

from gateway.research_retrieval_service import (
    Phase16ExplicitRetrievalFailure,
    Phase16ExplicitRetrievalService,
    Phase16ExplicitRetrievalSuccess,
)

from gateway.workday_cxs_request import (
    build_workday_cxs_jobs_body,
    validate_workday_cxs_jobs_body,
)


NOW = datetime(
    2026,
    8,
    25,
    20,
    45,
    tzinfo=timezone.utc,
)

URL = (
    "https://bmo.wd3.myworkdayjobs.com/"
    "wday/cxs/bmo/Campus/jobs"
)

BODY = (
    b'{"total":1,"jobPostings":['
    b'{"title":"Cloud/AI Platform Engineer",'
    b'"externalPath":"/job/test"}]}'
)


def research_request():

    return (
        research_request_factory.build(
            ResearchRequestIntent(
                objective=(
                    "Retrieve bounded public "
                    "Workday CXS jobs."
                ),
                source_kinds=(
                    "public_web",
                ),
                max_sources=1,
            )
        )
    )


def post_body():

    return (
        build_workday_cxs_jobs_body()
    )


def retrieval():

    request_sha = (
        validate_workday_cxs_jobs_body(
            post_body()
        )
    )

    return InternetRetrievalResult(
        requested_url=URL,
        final_url=URL,
        method="POST",
        request_body_sha256=(
            request_sha
        ),
        status_code=200,
        reason="OK",
        content_type="application/json",
        content_length=len(BODY),
        body=BODY,
        body_sha256=(
            hashlib.sha256(
                BODY
            ).hexdigest()
        ),
        byte_count=len(BODY),
        hops=(),
    )


class FakeRetriever:

    def __init__(
        self,
        *actions,
    ):

        self.actions = list(actions)

        self.workday_calls = []
        self.get_calls = []

    async def retrieve(
        self,
        url,
        *,
        method,
    ):

        self.get_calls.append(
            (
                url,
                method,
            )
        )

        raise AssertionError(
            "GET path must not execute."
        )

    async def retrieve_workday_cxs_jobs(
        self,
        url,
        *,
        request_body,
    ):

        self.workday_calls.append(
            (
                url,
                request_body,
            )
        )

        if not self.actions:
            raise AssertionError(
                "No fake action."
            )

        action = (
            self.actions.pop(0)
        )

        if isinstance(
            action,
            BaseException,
        ):
            raise action

        return action


class Repository:

    def __init__(self):
        self.records = []

    def persist(
        self,
        evidence,
    ):

        record = (
            PersistedResearchRetrievalRecord(
                evidence=evidence,
                evidence_sha256=(
                    evidence.evidence_sha256
                ),
                stored_at=NOW,
            )
        )

        self.records.append(
            record
        )

        return record


def service(
    retriever,
    repository,
):

    return (
        Phase16ExplicitRetrievalService(
            retriever=retriever,
            repository_factory=(
                lambda:
                    repository
            ),
            now_provider=(
                lambda:
                    NOW
            ),
            timer_provider=(
                lambda:
                    10.0
            ),
        )
    )


@pytest.mark.asyncio
async def test_success():

    fake = FakeRetriever(
        retrieval()
    )

    repo = Repository()

    result = await (
        service(
            fake,
            repo,
        )
        .retrieve_workday_cxs_jobs(
            request=(
                research_request()
            ),
            url=URL,
            request_body=(
                post_body()
            ),
        )
    )

    assert isinstance(
        result,
        Phase16ExplicitRetrievalSuccess,
    )

    sha = (
        validate_workday_cxs_jobs_body(
            post_body()
        )
    )

    assert (
        result.retrieval.method
        == "POST"
    )

    assert (
        result.evidence.method
        == "POST"
    )

    assert (
        result.evidence
        .request_body_sha256
        == sha
    )

    assert (
        len(repo.records)
        == 1
    )

    assert (
        fake.get_calls
        == []
    )


@pytest.mark.asyncio
async def test_transport_failure():

    fake = FakeRetriever(
        InternetTransportError(
            "workday-post-http-error",
            "HTTP error.",
        )
    )

    repo = Repository()

    result = await (
        service(
            fake,
            repo,
        )
        .retrieve_workday_cxs_jobs(
            request=(
                research_request()
            ),
            url=URL,
            request_body=(
                post_body()
            ),
        )
    )

    assert isinstance(
        result,
        Phase16ExplicitRetrievalFailure,
    )

    assert (
        result.evidence.method
        == "POST"
    )

    assert (
        result.evidence
        .request_body_sha256
        == validate_workday_cxs_jobs_body(
            post_body()
        )
    )


@pytest.mark.asyncio
async def test_invalid_body_never_reaches_transport():

    fake = FakeRetriever(
        retrieval()
    )

    repo = Repository()

    with pytest.raises(
        ValueError
    ):

        await (
            service(
                fake,
                repo,
            )
            .retrieve_workday_cxs_jobs(
                request=(
                    research_request()
                ),
                url=URL,
                request_body=(
                    b'{"limit":100}'
                ),
            )
        )

    assert (
        fake.workday_calls
        == []
    )

    assert repo.records == []


def test_get_api_remains_separate():

    import inspect

    get_sig = inspect.signature(
        Phase16ExplicitRetrievalService
        .retrieve_explicit_url
    )

    post_sig = inspect.signature(
        Phase16ExplicitRetrievalService
        .retrieve_workday_cxs_jobs
    )

    assert (
        "request_body"
        not in get_sig.parameters
    )

    assert (
        "request_body"
        in post_sig.parameters
    )
