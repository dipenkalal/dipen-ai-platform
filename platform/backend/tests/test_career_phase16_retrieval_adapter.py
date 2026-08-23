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
from gateway.research_retrieval_repository import (
    PersistedResearchRetrievalRecord,
)
from gateway.research_retrieval_service import (
    Phase16ExplicitRetrievalService,
)

from career.phase16_retrieval_adapter import (
    CareerPhase16RetrievalAdapter,
    CareerPhase16RetrievalAdapterError,
)
from career.retrieval import (
    CareerPhase16RetrievalBundle,
)


NOW = datetime(
    2026,
    8,
    20,
    22,
    0,
    tzinfo=timezone.utc,
)

URL = (
    "https://boards-api.greenhouse.io/"
    "v1/boards/acme/jobs"
)

BODY = (
    b'{"jobs":[],"meta":{"total":0}}'
)


def _retrieval() -> InternetRetrievalResult:
    return InternetRetrievalResult(
        requested_url=URL,
        final_url=URL,
        method="GET",
        status_code=200,
        reason="OK",
        content_type="application/json",
        content_length=len(BODY),
        body=BODY,
        body_sha256=hashlib.sha256(
            BODY
        ).hexdigest(),
        byte_count=len(BODY),
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
                "FakeRetriever has no action."
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


class BombService:
    async def retrieve_explicit_url(
        self,
        *,
        request,
        url,
    ):
        raise AssertionError(
            "Phase16 service must not be "
            "called for rejected adapter input."
        )


def _adapter(
    *actions,
):
    repository = FakeRepository()

    service = (
        Phase16ExplicitRetrievalService(
            retriever=FakeRetriever(
                *actions
            ),
            repository_factory=(
                lambda: repository
            ),
            now_provider=lambda: NOW,
            timer_provider=lambda: 1.0,
        )
    )

    return (
        CareerPhase16RetrievalAdapter(
            service=service
        ),
        repository,
    )


@pytest.mark.asyncio
async def test_success_returns_phase16_bound_bundle() -> None:
    adapter, repository = _adapter(
        _retrieval()
    )

    bundle = (
        await adapter.retrieve_public_url(
            objective=(
                "Retrieve public Greenhouse jobs"
            ),
            url=URL,
        )
    )

    assert isinstance(
        bundle,
        CareerPhase16RetrievalBundle,
    )

    assert bundle.requested_url == URL

    assert (
        bundle.retrieval_evidence
        .content_evidence_id
        == bundle.content_evidence
        .evidence_id
    )

    assert (
        bundle.retrieval_evidence
        .normalized_text_sha256
        == bundle.content_evidence
        .normalized_text_sha256
    )

    assert len(repository.records) == 1


@pytest.mark.asyncio
async def test_success_bundle_preserves_zero_career_authority() -> None:
    adapter, _repository = _adapter(
        _retrieval()
    )

    bundle = (
        await adapter.retrieve_public_url(
            objective="Retrieve public jobs",
            url=URL,
        )
    )

    assert (
        bundle.network_execution_owner
        == "phase16-research-gateway"
    )

    assert (
        bundle.career_truth_mutation_allowed
        is False
    )

    assert (
        bundle.application_authority_granted
        is False
    )

    assert (
        bundle.browser_authority_granted
        is False
    )


@pytest.mark.asyncio
async def test_phase16_failure_fails_closed_without_bundle() -> None:
    adapter, repository = _adapter(
        InternetTransportError(
            "destination-preflight-rejected",
            "Destination rejected.",
        )
    )

    with pytest.raises(
        CareerPhase16RetrievalAdapterError,
        match=(
            "destination-preflight-rejected"
        ),
    ):
        await adapter.retrieve_public_url(
            objective="Retrieve public jobs",
            url=URL,
        )

    assert len(repository.records) == 1

    assert (
        repository.records[0]
        .evidence.outcome
        == "failed"
    )


@pytest.mark.asyncio
async def test_short_objective_is_rejected_before_phase16() -> None:
    adapter = (
        CareerPhase16RetrievalAdapter(
            service=BombService()
        )
    )

    with pytest.raises(
        ValueError,
        match="at least 3",
    ):
        await adapter.retrieve_public_url(
            objective=" x ",
            url=URL,
        )


@pytest.mark.asyncio
async def test_empty_url_is_rejected_before_phase16() -> None:
    adapter = (
        CareerPhase16RetrievalAdapter(
            service=BombService()
        )
    )

    with pytest.raises(
        ValueError,
        match="URL is required",
    ):
        await adapter.retrieve_public_url(
            objective="Retrieve public jobs",
            url="",
        )


@pytest.mark.asyncio
async def test_cancellation_is_propagated_from_phase16() -> None:
    adapter, repository = _adapter(
        CooperativeCancellationRequested(
            "phase17-c4b3-test"
        )
    )

    with pytest.raises(
        CooperativeCancellationRequested,
    ):
        await adapter.retrieve_public_url(
            objective="Retrieve public jobs",
            url=URL,
        )

    assert len(repository.records) == 1

    assert (
        repository.records[0]
        .evidence.outcome
        == "cancelled"
    )



def test_default_adapter_uses_phase16_structured_profile() -> None:
    adapter = (
        CareerPhase16RetrievalAdapter()
    )

    assert (
        adapter
        ._service
        ._normalizer
        ._limits
        .max_normalized_chars
        == 1_000_000
    )


@pytest.mark.asyncio
async def test_structured_content_truncation_fails_closed_before_bundle() -> None:
    import hashlib
    import json

    from gateway.internet_transport import (
        InternetRetrievalResult,
    )
    from gateway.research_retrieval_service import (
        Phase16ExplicitRetrievalService,
        build_phase16_structured_content_normalizer,
    )

    payload = {
        "blob": "X" * 1_010_000,
    }

    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    retrieval = InternetRetrievalResult(
        requested_url=URL,
        final_url=URL,
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

    repository = FakeRepository()

    service = (
        Phase16ExplicitRetrievalService(
            retriever=FakeRetriever(
                retrieval
            ),
            normalizer=(
                build_phase16_structured_content_normalizer()
            ),
            repository_factory=(
                lambda: repository
            ),
            now_provider=lambda: NOW,
            timer_provider=lambda: 1.0,
        )
    )

    adapter = (
        CareerPhase16RetrievalAdapter(
            service=service
        )
    )

    with pytest.raises(
        CareerPhase16RetrievalAdapterError,
        match="truncated",
    ):
        await adapter.retrieve_public_url(
            objective="Retrieve bounded structured jobs",
            url=URL,
        )

    assert len(repository.records) == 1

    assert (
        repository.records[0]
        .evidence.outcome
        == "succeeded"
    )
