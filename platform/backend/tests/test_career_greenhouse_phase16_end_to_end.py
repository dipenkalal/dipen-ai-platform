from __future__ import annotations

import hashlib
import json
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

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

from career.connectors.greenhouse import (
    GreenhouseJobBoardConnector,
)
from career.phase16_retrieval_adapter import (
    CareerPhase16RetrievalAdapter,
    CareerPhase16RetrievalAdapterError,
)
from career.retrieval import (
    CareerRetrievalOrchestrator,
)


NOW = datetime(
    2026,
    8,
    20,
    22,
    15,
    tzinfo=timezone.utc,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "career"
    / "greenhouse_jobs.json"
)


def _connector() -> GreenhouseJobBoardConnector:
    return GreenhouseJobBoardConnector(
        board_token="acme",
        employer_name="Acme",
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
        self.records: list[
            PersistedResearchRetrievalRecord
        ] = []

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


def _fixture_retrieval(
) -> InternetRetrievalResult:
    connector = _connector()

    body = FIXTURE.read_bytes()

    return InternetRetrievalResult(
        requested_url=connector.jobs_url,
        final_url=connector.jobs_url,
        method="GET",
        status_code=200,
        reason="OK",
        content_type="application/json",
        content_length=len(body),
        body=body,
        body_sha256=hashlib.sha256(
            body
        ).hexdigest(),
        byte_count=len(body),
        hops=(),
    )


def _chain(
    *actions,
):
    retriever = FakeRetriever(
        *actions
    )

    repository = FakeRepository()

    phase16 = (
        Phase16ExplicitRetrievalService(
            retriever=retriever,
            repository_factory=(
                lambda: repository
            ),
            now_provider=lambda: NOW,
            timer_provider=lambda: 1.0,
        )
    )

    adapter = (
        CareerPhase16RetrievalAdapter(
            service=phase16
        )
    )

    orchestrator = (
        CareerRetrievalOrchestrator(
            adapter
        )
    )

    return (
        orchestrator,
        retriever,
        repository,
    )


@pytest.mark.asyncio
async def test_full_greenhouse_phase16_career_chain() -> None:
    (
        orchestrator,
        retriever,
        repository,
    ) = _chain(
        _fixture_retrieval()
    )

    connector = _connector()

    result = (
        await orchestrator.retrieve_candidates(
            connector=connector,
            objective=(
                "Discover public Greenhouse jobs"
            ),
            source_url=connector.jobs_url,
        )
    )

    assert retriever.calls == [
        (
            connector.jobs_url,
            "GET",
        )
    ]

    assert len(repository.records) == 1

    persisted = repository.records[0]
    evidence = persisted.evidence

    assert evidence.outcome == "succeeded"
    assert evidence.stage == "completed"
    assert evidence.method == "GET"

    assert evidence.requested_url == connector.jobs_url
    assert evidence.final_url == connector.jobs_url

    assert (
        result.research_evidence_id
        == evidence.evidence_id
    )

    assert (
        result.content_evidence_id
        == evidence.content_evidence_id
    )

    assert (
        result.normalized_text_sha256
        == evidence.normalized_text_sha256
    )

    assert (
        result.observed_at
        == evidence.observed_at
    )

    assert result.source_url == connector.jobs_url

    assert result.candidate_count == 2

    assert [
        candidate.source_job_id
        for candidate in result.candidates
    ] == [
        "900001",
        "900002",
    ]


@pytest.mark.asyncio
async def test_full_chain_preserves_greenhouse_fixture_semantics() -> None:
    payload = json.loads(
        FIXTURE.read_text(
            encoding="utf-8"
        )
    )

    assert payload["meta"]["total"] == 3

    (
        orchestrator,
        _retriever,
        _repository,
    ) = _chain(
        _fixture_retrieval()
    )

    connector = _connector()

    result = (
        await orchestrator.retrieve_candidates(
            connector=connector,
            objective=(
                "Discover public Greenhouse jobs"
            ),
            source_url=connector.jobs_url,
        )
    )

    # One fixture item is a prospect post
    # and must remain skipped.
    assert result.candidate_count == 2

    by_id = {
        candidate.source_job_id:
            candidate
        for candidate in result.candidates
    }

    assert set(by_id) == {
        "900001",
        "900002",
    }

    assert (
        by_id["900001"].title_hint
        == "Junior Cloud Engineer"
    )

    assert (
        by_id["900002"].title_hint
        == "Cloud Support Engineer"
    )


@pytest.mark.asyncio
async def test_full_chain_result_remains_non_authoritative() -> None:
    (
        orchestrator,
        _retriever,
        _repository,
    ) = _chain(
        _fixture_retrieval()
    )

    connector = _connector()

    result = (
        await orchestrator.retrieve_candidates(
            connector=connector,
            objective=(
                "Discover public Greenhouse jobs"
            ),
            source_url=connector.jobs_url,
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


@pytest.mark.asyncio
async def test_phase16_failure_stops_before_greenhouse_parse() -> None:
    (
        orchestrator,
        retriever,
        repository,
    ) = _chain(
        InternetTransportError(
            "destination-preflight-rejected",
            "Destination rejected.",
        )
    )

    connector = _connector()

    with pytest.raises(
        CareerPhase16RetrievalAdapterError,
        match="destination-preflight-rejected",
    ):
        await orchestrator.retrieve_candidates(
            connector=connector,
            objective=(
                "Discover public Greenhouse jobs"
            ),
            source_url=connector.jobs_url,
        )

    assert retriever.calls == [
        (
            connector.jobs_url,
            "GET",
        )
    ]

    assert len(repository.records) == 1

    assert (
        repository.records[0]
        .evidence.outcome
        == "failed"
    )
