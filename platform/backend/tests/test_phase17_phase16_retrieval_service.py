from __future__ import annotations

import hashlib
from datetime import (
    datetime,
    timezone,
)

import pytest

from agents.cancellation import (
    CooperativeCancellationRequested,
)
from gateway.internet_transport import (
    InternetRetrievalResult,
    InternetTransportError,
)
from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
)
from gateway.research_operations_repository import (
    ResearchOperationsEvent,
)
from gateway.research_retrieval_repository import (
    PersistedResearchRetrievalRecord,
)
from gateway.research_retrieval_service import (
    TRANSIENT_RETRY_BACKOFF_SECONDS,
    Phase16ExplicitRetrievalFailure,
    Phase16ExplicitRetrievalService,
    Phase16ExplicitRetrievalSuccess,
)


NOW = datetime(
    2026,
    8,
    20,
    21,
    30,
    tzinfo=timezone.utc,
)

URL = (
    "https://boards-api.greenhouse.io/"
    "v1/boards/acme/jobs"
)

BODY = (
    b'{"jobs":[],"meta":{"total":0}}'
)


def _request(
    *,
    source_kinds=(
        "public_web",
    ),
):
    return research_request_factory.build(
        ResearchRequestIntent(
            objective=(
                "Retrieve public Greenhouse jobs"
            ),
            source_kinds=source_kinds,
            max_sources=1,
        )
    )


def _retrieval(
    *,
    content_type: str = "application/json",
) -> InternetRetrievalResult:
    body = BODY

    return InternetRetrievalResult(
        requested_url=URL,
        final_url=URL,
        method="GET",
        status_code=200,
        reason="OK",
        content_type=content_type,
        content_length=len(body),
        body=body,
        body_sha256=hashlib.sha256(
            body
        ).hexdigest(),
        byte_count=len(body),
        hops=(),
    )


class FakeRetriever:
    def __init__(
        self,
        *actions,
    ) -> None:
        self.actions = list(actions)

        self.calls: list[
            tuple[str, str]
        ] = []

    async def retrieve(
        self,
        url: str,
        *,
        method: str,
    ):
        self.calls.append(
            (
                url,
                method,
            )
        )

        if not self.actions:
            raise AssertionError(
                "FakeRetriever has no action"
            )

        action = self.actions.pop(0)

        if isinstance(
            action,
            BaseException,
        ):
            raise action

        return action


class FakeRepository:
    def __init__(self) -> None:
        self.records = []

    def persist(
        self,
        evidence,
    ) -> PersistedResearchRetrievalRecord:
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


class FakeOperationsRepository:
    def __init__(self) -> None:
        self.events: list[
            ResearchOperationsEvent
        ] = []

    def persist(
        self,
        event: ResearchOperationsEvent,
    ) -> ResearchOperationsEvent:
        self.events.append(
            event
        )

        return event


def _service(
    retriever,
    repository,
    operations=None,
    *,
    sleep_calls=None,
):
    if sleep_calls is None:
        sleep_calls = []

    async def fake_sleep(
        seconds: float,
    ) -> None:
        sleep_calls.append(
            seconds
        )

    return Phase16ExplicitRetrievalService(
        retriever=retriever,
        repository_factory=(
            lambda: repository
        ),
        operations_repository=operations,
        now_provider=lambda: NOW,
        timer_provider=lambda: 10.0,
        sleep_provider=fake_sleep,
    )


@pytest.mark.asyncio
async def test_success_returns_same_execution_content_and_evidence() -> None:
    retriever = FakeRetriever(
        _retrieval()
    )

    repository = FakeRepository()

    operations = (
        FakeOperationsRepository()
    )

    service = _service(
        retriever,
        repository,
        operations,
    )

    result = (
        await service.retrieve_explicit_url(
            request=_request(),
            url=URL,
        )
    )

    assert isinstance(
        result,
        Phase16ExplicitRetrievalSuccess,
    )

    assert result.outcome == "succeeded"

    assert result.retrieval.final_url == URL

    assert (
        result.content.source_url
        == result.retrieval.final_url
    )

    assert (
        result.evidence.content_evidence_id
        == result.content.evidence_id
    )

    assert (
        result.evidence.normalized_text_sha256
        == result.content.normalized_text_sha256
    )

    assert (
        result.persisted.evidence.evidence_id
        == result.evidence.evidence_id
    )

    assert len(repository.records) == 1

    assert len(operations.events) == 1

    assert (
        operations.events[0].outcome
        == "succeeded"
    )


@pytest.mark.asyncio
async def test_success_exposes_raw_normalized_content_not_prompt_envelope() -> None:
    repository = FakeRepository()

    service = _service(
        FakeRetriever(
            _retrieval()
        ),
        repository,
    )

    result = (
        await service.retrieve_explicit_url(
            request=_request(),
            url=URL,
        )
    )

    assert isinstance(
        result,
        Phase16ExplicitRetrievalSuccess,
    )

    assert result.content.normalized_text

    assert (
        "DAP UNTRUSTED INTERNET EVIDENCE"
        not in result.content.normalized_text
    )

    assert (
        hashlib.sha256(
            result.content.normalized_text.encode(
                "utf-8"
            )
        ).hexdigest()
        == result.content.normalized_text_sha256
    )


@pytest.mark.asyncio
async def test_one_transient_retry_preserves_phase16_policy() -> None:
    retriever = FakeRetriever(
        InternetTransportError(
            "dns-timeout",
            "DNS timed out.",
        ),
        _retrieval(),
    )

    repository = FakeRepository()

    operations = (
        FakeOperationsRepository()
    )

    sleep_calls = []

    service = _service(
        retriever,
        repository,
        operations,
        sleep_calls=sleep_calls,
    )

    result = (
        await service.retrieve_explicit_url(
            request=_request(),
            url=URL,
        )
    )

    assert isinstance(
        result,
        Phase16ExplicitRetrievalSuccess,
    )

    assert result.attempt_count == 2
    assert result.transient_retry_count == 1
    assert result.recovered_after_retry is True

    assert (
        result.retry_trigger_error_code
        == "dns-timeout"
    )

    assert sleep_calls == [
        TRANSIENT_RETRY_BACKOFF_SECONDS
    ]

    assert len(retriever.calls) == 2

    assert len(operations.events) == 1

    event = operations.events[0]

    assert event.outcome == "succeeded"
    assert event.attempt_count == 2
    assert event.transient_retry_count == 1
    assert event.recovered_after_retry is True
    assert event.error_code == "dns-timeout"


@pytest.mark.asyncio
async def test_nontransient_transport_failure_persists_terminal_evidence() -> None:
    retriever = FakeRetriever(
        InternetTransportError(
            "destination-preflight-rejected",
            "Destination rejected.",
        )
    )

    repository = FakeRepository()

    operations = (
        FakeOperationsRepository()
    )

    service = _service(
        retriever,
        repository,
        operations,
    )

    result = (
        await service.retrieve_explicit_url(
            request=_request(),
            url=URL,
        )
    )

    assert isinstance(
        result,
        Phase16ExplicitRetrievalFailure,
    )

    assert result.outcome == "failed"

    assert (
        result.error_code
        == "destination-preflight-rejected"
    )

    assert result.evidence.outcome == "failed"
    assert result.evidence.stage == "preflight"

    assert len(repository.records) == 1
    assert len(operations.events) == 1

    assert (
        operations.events[0].outcome
        == "failed"
    )

    assert (
        operations.events[0].stage
        == "preflight"
    )


@pytest.mark.asyncio
async def test_content_normalization_failure_is_terminal_and_persisted() -> None:
    repository = FakeRepository()

    operations = (
        FakeOperationsRepository()
    )

    service = _service(
        FakeRetriever(
            _retrieval(
                content_type="application/pdf"
            )
        ),
        repository,
        operations,
    )

    result = (
        await service.retrieve_explicit_url(
            request=_request(),
            url=URL,
        )
    )

    assert isinstance(
        result,
        Phase16ExplicitRetrievalFailure,
    )

    assert (
        result.error_code
        == "content-type-not-normalizable"
    )

    assert (
        result.evidence.stage
        == "content-normalization"
    )

    assert len(repository.records) == 1
    assert len(operations.events) == 1

    assert (
        operations.events[0].stage
        == "content-normalization"
    )


@pytest.mark.asyncio
async def test_cancellation_is_persisted_then_reraised() -> None:
    repository = FakeRepository()

    operations = (
        FakeOperationsRepository()
    )

    service = _service(
        FakeRetriever(
            CooperativeCancellationRequested(
                "phase17-c4b1-test"
            )
        ),
        repository,
        operations,
    )

    with pytest.raises(
        CooperativeCancellationRequested,
    ):
        await service.retrieve_explicit_url(
            request=_request(),
            url=URL,
        )

    assert len(repository.records) == 1

    evidence = (
        repository.records[0].evidence
    )

    assert evidence.outcome == "cancelled"
    assert evidence.stage == "cancelled"
    assert evidence.error_code == "cancelled"

    assert len(operations.events) == 1

    assert (
        operations.events[0].outcome
        == "cancelled"
    )


@pytest.mark.asyncio
async def test_non_public_web_request_rejected_before_retrieval() -> None:
    retriever = FakeRetriever(
        _retrieval()
    )

    repository = FakeRepository()

    service = _service(
        retriever,
        repository,
    )

    with pytest.raises(
        ValueError,
        match="public_web",
    ):
        await service.retrieve_explicit_url(
            request=_request(
                source_kinds=(
                    "knowledge",
                )
            ),
            url=URL,
        )

    assert retriever.calls == []
    assert repository.records == []


@pytest.mark.asyncio
async def test_operations_repository_is_optional_for_injected_fake_repository() -> None:
    repository = FakeRepository()

    service = _service(
        FakeRetriever(
            _retrieval()
        ),
        repository,
        None,
    )

    result = (
        await service.retrieve_explicit_url(
            request=_request(),
            url=URL,
        )
    )

    assert isinstance(
        result,
        Phase16ExplicitRetrievalSuccess,
    )

    assert len(repository.records) == 1



def test_phase17_structured_profile_preserves_large_json() -> None:
    import hashlib
    import json

    from gateway.internet_transport import (
        InternetRetrievalResult,
    )
    from gateway.research_retrieval_service import (
        MAX_MODEL_CONTEXT_CHARS_PER_SOURCE,
        STRUCTURED_CONTENT_MAX_NORMALIZED_CHARS,
        build_phase16_structured_content_normalizer,
    )

    payload = {
        "jobs": [
            {
                "id": 1,
                "title": "X" * 60_000,
            }
        ],
        "meta": {
            "total": 1,
        },
    }

    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    url = "https://example.invalid/large-structured.json"

    retrieval = InternetRetrievalResult(
        requested_url=url,
        final_url=url,
        method="GET",
        status_code=200,
        reason="OK",
        content_type="application/json",
        content_length=len(body),
        body=body,
        body_sha256=hashlib.sha256(body).hexdigest(),
        byte_count=len(body),
        hops=(),
    )

    normalizer = (
        build_phase16_structured_content_normalizer()
    )

    content = normalizer.normalize(
        retrieval
    )

    assert (
        MAX_MODEL_CONTEXT_CHARS_PER_SOURCE
        == 30_000
    )

    assert (
        STRUCTURED_CONTENT_MAX_NORMALIZED_CHARS
        == 1_000_000
    )

    assert (
        normalizer
        ._limits
        .max_normalized_chars
        == 1_000_000
    )

    assert (
        content.normalized_char_count
        > 30_000
    )

    assert content.truncated is False

    assert (
        json.loads(content.normalized_text)
        == payload
    )


def test_phase17_default_service_retains_model_context_profile() -> None:
    from gateway.research_retrieval_service import (
        MAX_MODEL_CONTEXT_CHARS_PER_SOURCE,
        Phase16ExplicitRetrievalService,
        build_phase16_structured_content_normalizer,
    )

    default_service = (
        Phase16ExplicitRetrievalService()
    )

    structured = (
        build_phase16_structured_content_normalizer()
    )

    assert (
        default_service
        ._normalizer
        ._limits
        .max_normalized_chars
        == MAX_MODEL_CONTEXT_CHARS_PER_SOURCE
        == 30_000
    )

    assert (
        structured
        ._limits
        .max_normalized_chars
        == 1_000_000
    )
