from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from agents.schemas import AgentStep, AgentUsage
from agents.truth_repository import AgentTruthRepository
from gateway.internet_transport import InternetRetrievalHop, InternetRetrievalResult
from gateway.research_contract import (
    ResearchRequest,
    ResearchRequestFactory,
    ResearchRequestIntent,
)
from gateway.research_retrieval_evidence import ResearchRetrievalEvidenceFactory
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from gateway.research_workspace import ResearchWorkspaceService
from gateway.untrusted_internet_content import UntrustedInternetContentNormalizer
from history.schemas import AgentRunRecord, AgentRunSummary

OBSERVED_AT = datetime(2026, 8, 18, 15, 0, tzinfo=timezone.utc)
OBJECTIVE = "Inspect attributable public-web evidence in the owner workspace."


class FakeRunRepository:
    def __init__(self, records: list[AgentRunRecord]) -> None:
        self.records = {record.run_id: record for record in records}
        self.list_calls = 0

    def get(self, run_id: str) -> AgentRunRecord | None:
        return self.records.get(run_id)

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        agent_id: str | None = None,
        status: str | None = None,
        model: str | None = None,
        search: str | None = None,
    ) -> tuple[list[AgentRunSummary], int]:
        del limit, offset, status, model, search
        self.list_calls += 1
        records = [
            record
            for record in self.records.values()
            if agent_id is None or record.agent_id == agent_id
        ]
        records.sort(key=lambda record: record.started_at, reverse=True)
        summaries = [
            AgentRunSummary(
                run_id=record.run_id,
                agent_id=record.agent_id,
                objective=record.objective,
                model=record.model,
                provider=record.provider,
                status=record.status,
                answer_preview=record.answer,
                error=record.error,
                step_count=len(record.steps),
                source_count=len(record.sources),
                total_tokens=record.usage.total_tokens,
                latency_ms=record.usage.latency_ms,
                started_at=record.started_at,
                completed_at=record.completed_at,
                created_at=record.created_at,
            )
            for record in records
        ]
        return summaries, len(summaries)


def _truth(tmp_path: Path) -> AgentTruthRepository:
    return AgentTruthRepository(tmp_path / "truth.db")


def _request() -> ResearchRequest:
    return ResearchRequestFactory().build(
        ResearchRequestIntent(
            objective=OBJECTIVE,
            source_kinds=("public_web",),
            max_sources=2,
        )
    )


def _success(request: ResearchRequest):
    body = b"<html><title>Workspace Source</title><body>Public evidence.</body></html>"
    body_sha256 = hashlib.sha256(body).hexdigest()
    retrieval = InternetRetrievalResult(
        requested_url="https://example.com/",
        final_url="https://example.com/",
        method="GET",
        status_code=200,
        reason="OK",
        content_type="text/html",
        content_length=len(body),
        body=body,
        body_sha256=body_sha256,
        byte_count=len(body),
        hops=(
            InternetRetrievalHop(
                redirect_depth=0,
                canonical_url="https://example.com/",
                destination_admission_id="internet-destination-1234567890abcdef12345678",
                destination_admission_sha256="e" * 64,
                approved_addresses=("93.184.216.34",),
                connected_address="93.184.216.34",
                status_code=200,
            ),
        ),
    )
    content = UntrustedInternetContentNormalizer().normalize(retrieval)
    return ResearchRetrievalEvidenceFactory().build_success(
        request=request,
        retrieval=retrieval,
        content=content,
        observed_at=OBSERVED_AT,
    )


def _failure(request: ResearchRequest):
    return ResearchRetrievalEvidenceFactory().build_failure(
        request=request,
        requested_url="https://localhost/",
        method="GET",
        stage="preflight",
        error_code="destination-preflight-rejected",
        error_detail="Local hostname rejected.",
        observed_at=OBSERVED_AT,
    )


def _run(
    *,
    request: ResearchRequest,
    evidence_ids: list[str],
) -> AgentRunRecord:
    step = AgentStep(
        step_number=1,
        type="tool",
        title="Retrieve explicit public-web evidence",
        tool_id="internet.research.retrieve",
        success=True,
        input={
            "objective": OBJECTIVE,
            "urls": ["https://example.com/", "https://localhost/"],
        },
        output={
            "request_id": request.request_id,
            "sources": [
                {
                    "evidence_id": evidence_id,
                    "success": index == 0,
                }
                for index, evidence_id in enumerate(evidence_ids)
            ],
        },
        started_at=OBSERVED_AT,
        completed_at=OBSERVED_AT,
    )
    return AgentRunRecord(
        run_id="run-phase12i-1",
        agent_id="research-agent",
        objective=OBJECTIVE,
        status="completed",
        answer="Research complete.",
        steps=[step],
        sources=[{"evidence_id": evidence_ids[0], "source_kind": "public_web"}],
        usage=AgentUsage(latency_ms=12.0),
        request={
            "objective": OBJECTIVE,
            "research_urls": ["https://example.com/", "https://localhost/"],
        },
        started_at=OBSERVED_AT,
        completed_at=OBSERVED_AT,
        created_at=OBSERVED_AT,
        updated_at=OBSERVED_AT,
    )


def _table_exists(truth: AgentTruthRepository, table: str) -> bool:
    with truth.connection() as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    return row is not None


def test_read_only_workspace_does_not_create_missing_evidence_table(tmp_path: Path) -> None:
    truth = _truth(tmp_path)
    retrieval = ResearchRetrievalRepository(truth, initialize=False)
    runs = FakeRunRepository([])
    service = ResearchWorkspaceService(
        retrieval_repository=retrieval,
        run_repository=runs,
    )

    assert _table_exists(truth, "research_retrieval_evidence") is False

    response = service.list_evidence(limit=25)

    assert response.items == []
    assert response.total == 0
    assert response.workspace_mode == "read_only"
    assert response.network_authority_granted is False
    assert response.mutation_authority_granted is False
    assert response.search_candidate_metadata_included is False
    assert runs.list_calls == 0
    assert _table_exists(truth, "research_retrieval_evidence") is False


def test_workspace_correlates_evidence_to_research_agent_history_without_mutation(
    tmp_path: Path,
) -> None:
    truth = _truth(tmp_path)
    write_repository = ResearchRetrievalRepository(truth)
    request = _request()
    success = _success(request)
    failure = _failure(request)
    write_repository.persist(success)
    write_repository.persist(failure)

    before_tasks, before_total = truth.list_tasks()
    runs = FakeRunRepository(
        [_run(request=request, evidence_ids=[success.evidence_id, failure.evidence_id])]
    )
    service = ResearchWorkspaceService(
        retrieval_repository=ResearchRetrievalRepository(truth, initialize=False),
        run_repository=runs,
    )

    response = service.list_evidence(limit=100)
    after_tasks, after_total = truth.list_tasks()

    assert response.total == 2
    assert response.succeeded == 1
    assert response.failed == 1
    assert response.cancelled == 0
    assert response.workspace_mode == "read_only"
    assert before_tasks == after_tasks == []
    assert before_total == after_total == 0

    by_id = {item.evidence.evidence_id: item for item in response.items}
    for evidence in (success, failure):
        item = by_id[evidence.evidence_id]
        assert item.provenance_kind == "internet_evidence"
        assert item.provenance_label == "Internet Evidence"
        assert item.knowledge_record is False
        assert item.search_candidate_metadata_included is False
        assert item.ui_network_authority_granted is False
        assert item.ui_mutation_authority_granted is False
        assert item.run is not None
        assert item.run.run_id == "run-phase12i-1"
        assert item.run.objective == OBJECTIVE
        assert item.run.provenance_source == "agent_run_history"


def test_workspace_detail_preserves_immutable_evidence_and_handles_missing_id(
    tmp_path: Path,
) -> None:
    truth = _truth(tmp_path)
    write_repository = ResearchRetrievalRepository(truth)
    request = _request()
    success = _success(request)
    stored = write_repository.persist(success)
    runs = FakeRunRepository([_run(request=request, evidence_ids=[success.evidence_id])])
    service = ResearchWorkspaceService(
        retrieval_repository=ResearchRetrievalRepository(truth, initialize=False),
        run_repository=runs,
    )

    item = service.get_evidence(success.evidence_id)

    assert item is not None
    assert item.evidence == stored.evidence
    assert item.evidence.evidence_sha256 == success.evidence_sha256
    assert item.stored_at == stored.stored_at.isoformat()
    assert service.get_evidence("research-retrieval-does-not-exist") is None


def test_workspace_limit_is_bounded(tmp_path: Path) -> None:
    service = ResearchWorkspaceService(
        retrieval_repository=ResearchRetrievalRepository(_truth(tmp_path), initialize=False),
        run_repository=FakeRunRepository([]),
    )

    for invalid_limit in (0, 501):
        try:
            service.list_evidence(limit=invalid_limit)
        except ValueError as error:
            assert "between 1 and 500" in str(error)
        else:
            raise AssertionError("invalid workspace limit should fail")
