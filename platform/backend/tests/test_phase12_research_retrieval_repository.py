from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from gateway.internet_transport import InternetRetrievalHop, InternetRetrievalResult
from gateway.research_contract import ResearchRequestFactory, ResearchRequestIntent
from gateway.research_retrieval_evidence import ResearchRetrievalEvidenceFactory
from gateway.research_retrieval_repository import (
    ResearchRetrievalPersistenceConflict,
    ResearchRetrievalRepository,
)
from gateway.untrusted_internet_content import UntrustedInternetContentNormalizer

OBSERVED_AT = datetime(2026, 8, 18, 2, 30, tzinfo=timezone.utc)


def _truth(tmp_path: Path) -> AgentTruthRepository:
    return AgentTruthRepository(tmp_path / "truth.db")


def _task() -> TaskLedgerRecord:
    return TaskLedgerRecord(
        task_id="task-research-1",
        task_type="agent",
        objective="Research a public source.",
        status="completed",
        requested_by="owner",
        assigned_agent_ids=["research-agent"],
        created_at=OBSERVED_AT,
        updated_at=OBSERVED_AT,
        started_at=OBSERVED_AT,
        completed_at=OBSERVED_AT,
    )


def _request(*, task_bound: bool = True):
    kwargs: dict[str, object] = {
        "objective": "Research a public source with citations.",
        "source_kinds": ("public_web",),
    }
    if task_bound:
        kwargs.update(
            canonical_task_id="task-research-1",
            canonical_admission_sha256="d" * 64,
        )
    return ResearchRequestFactory().build(ResearchRequestIntent(**kwargs))


def _success_evidence(*, task_bound: bool = True, observed_at: datetime = OBSERVED_AT):
    body = b"<html><title>Source</title><body>Attributable public evidence.</body></html>"
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
        request=_request(task_bound=task_bound),
        retrieval=retrieval,
        content=content,
        observed_at=observed_at,
    )


def test_persist_task_bound_evidence_without_mutating_canonical_task(tmp_path: Path) -> None:
    truth = _truth(tmp_path)
    original_task = truth.upsert_task(_task())
    repository = ResearchRetrievalRepository(truth)
    evidence = _success_evidence()

    stored = repository.persist(evidence)

    assert stored.evidence == evidence
    assert stored.evidence_sha256 == evidence.evidence_sha256
    assert stored.evidence_persisted is True
    assert stored.task_ledger_mutated is False
    assert stored.knowledge_mutated is False
    assert truth.get_task(original_task.task_id) == original_task
    assert repository.get(evidence.evidence_id) == stored
    assert repository.list_for_task("task-research-1") == [stored]
    assert repository.list_for_request(evidence.request_id) == [stored]


def test_standalone_research_evidence_does_not_require_task_creation(tmp_path: Path) -> None:
    truth = _truth(tmp_path)
    repository = ResearchRetrievalRepository(truth)
    evidence = _success_evidence(task_bound=False)

    before, before_total = truth.list_tasks()
    stored = repository.persist(evidence)
    after, after_total = truth.list_tasks()

    assert stored.evidence.canonical_task_id is None
    assert before == after == []
    assert before_total == after_total == 0


def test_task_bound_evidence_requires_existing_canonical_task(tmp_path: Path) -> None:
    truth = _truth(tmp_path)
    repository = ResearchRetrievalRepository(truth)

    with pytest.raises(ValueError, match="existing canonical DAP task"):
        repository.persist(_success_evidence())


def test_idempotent_replay_returns_original_stored_record(tmp_path: Path) -> None:
    truth = _truth(tmp_path)
    truth.upsert_task(_task())
    repository = ResearchRetrievalRepository(truth)
    evidence = _success_evidence()

    first = repository.persist(evidence)
    second = repository.persist(evidence)

    assert second == first
    with truth.connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM research_retrieval_evidence"
        ).fetchone()["count"]
    assert count == 1


def test_conflicting_reuse_of_evidence_id_fails_closed(tmp_path: Path) -> None:
    truth = _truth(tmp_path)
    truth.upsert_task(_task())
    repository = ResearchRetrievalRepository(truth)
    first = _success_evidence(observed_at=OBSERVED_AT)
    second = _success_evidence(observed_at=OBSERVED_AT + timedelta(seconds=1))
    conflicting = second.model_copy(update={"evidence_id": first.evidence_id})

    repository.persist(first)
    with pytest.raises(ResearchRetrievalPersistenceConflict):
        repository.persist(conflicting)


def test_tampered_hash_is_rejected_before_storage(tmp_path: Path) -> None:
    truth = _truth(tmp_path)
    truth.upsert_task(_task())
    repository = ResearchRetrievalRepository(truth)
    evidence = _success_evidence().model_copy(update={"evidence_sha256": "0" * 64})

    with pytest.raises(ValueError, match="hash does not match"):
        repository.persist(evidence)


def test_failure_and_cancellation_evidence_are_persisted_and_queryable(tmp_path: Path) -> None:
    truth = _truth(tmp_path)
    repository = ResearchRetrievalRepository(truth)
    request = _request(task_bound=False)
    factory = ResearchRetrievalEvidenceFactory()
    failure = factory.build_failure(
        request=request,
        requested_url="https://localhost/",
        method="GET",
        stage="preflight",
        error_code="destination-preflight-rejected",
        error_detail="Local hostname rejected.",
        observed_at=OBSERVED_AT,
    )
    cancelled = factory.build_cancelled(
        request=request,
        requested_url="https://example.com/slow",
        method="HEAD",
        error_detail="Owner cancelled the research retrieval.",
        observed_at=OBSERVED_AT + timedelta(seconds=1),
    )

    repository.persist(failure)
    repository.persist(cancelled)
    records = repository.list_for_request(request.request_id)

    assert [record.evidence.outcome for record in records] == ["failed", "cancelled"]
    assert records[0].evidence.citation is None
    assert records[1].evidence.error_code == "cancelled"


def test_recent_limit_is_bounded(tmp_path: Path) -> None:
    repository = ResearchRetrievalRepository(_truth(tmp_path))

    with pytest.raises(ValueError, match="between 1 and 500"):
        repository.list_recent(limit=0)
    with pytest.raises(ValueError, match="between 1 and 500"):
        repository.list_recent(limit=501)
