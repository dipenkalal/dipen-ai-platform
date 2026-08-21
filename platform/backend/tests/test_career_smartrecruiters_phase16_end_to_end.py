from __future__ import annotations
import hashlib
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
import pytest
from gateway.internet_transport import (
    InternetRetrievalResult,
)
from gateway.research_retrieval_repository import (
    PersistedResearchRetrievalRecord,
)
from gateway.research_retrieval_service import (
    Phase16ExplicitRetrievalService,
)
from career.connectors.smartrecruiters import (
    SMARTRECRUITERS_CONNECTOR_ID,
    SmartRecruitersPostingConnector,
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
    23,
    59,
    tzinfo=timezone.utc,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "career"
    / "smartrecruiters_postings.json"
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

def _connector() -> SmartRecruitersPostingConnector:
    return SmartRecruitersPostingConnector(
        company_identifier="acme",
        employer_name="Acme",
    )

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
async def test_smartrecruiters_fixture_flows_phase16_to_career_candidates() -> None:
    orchestrator, retriever, repository = _chain(_fixture_retrieval())
    connector = _connector()
    result = await orchestrator.retrieve_candidates(connector=connector, objective='Discover public SmartRecruiters jobs', source_url=connector.jobs_url)

    assert retriever.calls == [
        (
            connector.jobs_url,
            "GET",
        )
    ]

    assert len(repository.records) == 1

    evidence = repository.records[0].evidence

    assert evidence.outcome == "succeeded"
    assert evidence.stage == "completed"
    assert evidence.method == "GET"

    assert (
        evidence.requested_url
        == connector.jobs_url
    )

    assert (
        evidence.final_url
        == connector.jobs_url
    )

    assert (
        result.connector_id
        == SMARTRECRUITERS_CONNECTOR_ID
    )

    assert (
        result.source_url
        == connector.jobs_url
    )

    assert result.candidate_count == 2

    assert [
        candidate.title_hint
        for candidate
        in result.candidates
    ] == ['Cloud Platform Engineer', 'Junior DevOps Engineer']

    assert [
        candidate.source_job_id
        for candidate
        in result.candidates
    ] == ['11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222']

    by_id = {
        candidate.source_job_id:
            candidate
        for candidate
        in result.candidates
    }

    assert (
        by_id[
            '11111111-1111-4111-8111-111111111111'
        ].detail_url
        == 'https://jobs.smartrecruiters.com/acme/11111111-1111-4111-8111-111111111111'
    )

    assert (
        by_id[
            '22222222-2222-4222-8222-222222222222'
        ].detail_url
        == 'https://api.smartrecruiters.com/v1/companies/acme/postings/22222222-2222-4222-8222-222222222222'
    )

    assert (
        '33333333-3333-4333-8333-333333333333'
        not in by_id
    )

@pytest.mark.asyncio
async def test_smartrecruiters_e2e_preserves_phase16_evidence_binding() -> None:
    orchestrator, _retriever, repository = _chain(_fixture_retrieval())
    connector = _connector()
    result = await orchestrator.retrieve_candidates(connector=connector, objective='Discover public SmartRecruiters jobs', source_url=connector.jobs_url)
    assert len(repository.records) == 1
    persisted = repository.records[0]
    evidence = persisted.evidence
    assert result.research_evidence_id == evidence.evidence_id
    assert result.content_evidence_id == evidence.content_evidence_id
    assert result.normalized_text_sha256 == evidence.normalized_text_sha256
    assert result.observed_at == evidence.observed_at
    assert result.source_url == evidence.requested_url
    for candidate in result.candidates:
        assert candidate.discovery_research_evidence_id == evidence.evidence_id
        assert candidate.discovery_content_evidence_id == evidence.content_evidence_id
        assert candidate.discovery_normalized_text_sha256 == evidence.normalized_text_sha256
        assert candidate.observed_at == evidence.observed_at

@pytest.mark.asyncio
async def test_smartrecruiters_e2e_preserves_released_date_and_truth_fail_closed() -> None:
    orchestrator, _retriever, _repository = _chain(_fixture_retrieval())
    connector = _connector()
    result = await orchestrator.retrieve_candidates(connector=connector, objective='Discover public SmartRecruiters jobs', source_url=connector.jobs_url)

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

    assert result.candidate_count == 2

    by_id = {
        candidate.source_job_id:
            candidate
        for candidate
        in result.candidates
    }

    timestamp_candidate = by_id[
        '11111111-1111-4111-8111-111111111111'
    ]

    no_timestamp_candidate = by_id[
        '22222222-2222-4222-8222-222222222222'
    ]

    expected_released_at = (
        datetime.fromisoformat(
            '2026-08-20T14:30:00.000Z'
            .replace(
                "Z",
                "+00:00",
            )
        )
    )

    assert (
        timestamp_candidate.posted_at_hint
        == expected_released_at
    )

    assert (
        no_timestamp_candidate.posted_at_hint
        is None
    )

    assert (
        timestamp_candidate.apply_url_hint
        == 'https://jobs.smartrecruiters.com/acme/11111111-1111-4111-8111-111111111111/apply'
    )

    assert (
        no_timestamp_candidate.apply_url_hint
        is None
    )

    assert (
        timestamp_candidate.location_hint
        == 'Toronto, ON, CA (Remote)'
    )

    assert (
        no_timestamp_candidate.location_hint
        == 'Vancouver, BC, CA'
    )

    for candidate in result.candidates:

        assert (
            candidate.source_updated_at_hint
            is None
        )

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
async def test_smartrecruiters_e2e_rejects_truncated_or_invalid_structured_evidence() -> None:
    good = _fixture_retrieval()
    invalid_body = b'{"broken":'
    invalid = good.model_copy(update={'body': invalid_body, 'body_sha256': hashlib.sha256(invalid_body).hexdigest(), 'byte_count': len(invalid_body), 'content_length': len(invalid_body)})
    orchestrator, retriever, repository = _chain(invalid)
    connector = _connector()
    with pytest.raises(CareerPhase16RetrievalAdapterError, match='json-normalization-failed'):
        await orchestrator.retrieve_candidates(connector=connector, objective='Discover public SmartRecruiters jobs', source_url=connector.jobs_url)
    assert retriever.calls == [(connector.jobs_url, 'GET')]
    assert len(repository.records) == 1
    evidence = repository.records[0].evidence
    assert evidence.outcome == 'failed'
    assert evidence.stage == 'content-normalization'
    assert evidence.error_code == 'json-normalization-failed'
