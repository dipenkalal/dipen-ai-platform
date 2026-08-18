from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from engineering.codex_execution_contract import engineering_execution_policy
from engineering.codex_smoke import build_smoke_work_order
from engineering.engineering_audit_evidence import engineering_audit_evidence_service
from engineering.engineering_audit_repository import (
    EngineeringAuditPersistenceConflict,
    EngineeringAuditRepository,
)
from engineering.guardian_execution_admission import (
    engineering_guardian_admission_service,
)


def cancelled_evidence():
    work_order = build_smoke_work_order()
    ticket = engineering_execution_policy.issue_ticket(
        work_order=work_order,
        workspace_id="phase11f-repository-test",
    )
    admission = engineering_guardian_admission_service.admit(
        work_order=work_order,
        ticket=ticket,
    )
    evidence = engineering_audit_evidence_service.build_cancelled_before_execution(
        work_order=work_order,
        ticket=ticket,
        guardian_admission=admission,
        cancellation_information="Cancelled before executor launch for repository test.",
    )
    return work_order, evidence


def seed_task(truth: AgentTruthRepository, task_id: str) -> TaskLedgerRecord:
    now = datetime.now(timezone.utc)
    return truth.upsert_task(
        TaskLedgerRecord(
            task_id=task_id,
            task_type="agent",
            objective="Run bounded Phase 11 engineering work.",
            status="assigned",
            requested_by="dipen-owner",
            assigned_agent_ids=["engineering-agent"],
            source_run_id="phase11c2-live-smoke-delegation",
            parent_task_id="phase11c2-live-smoke-parent",
            created_at=now,
            updated_at=now,
        )
    )


def repository(tmp_path: Path):
    truth = AgentTruthRepository(tmp_path / "agent-truth.db")
    return truth, EngineeringAuditRepository(truth)


def test_persist_round_trip_is_additive_and_does_not_mutate_task(tmp_path: Path) -> None:
    truth, audit = repository(tmp_path)
    work_order, evidence = cancelled_evidence()
    task_before = seed_task(truth, work_order.source_task_id)

    stored = audit.persist(evidence)
    reread = audit.get(evidence.evidence_id)
    task_after = truth.get_task(work_order.source_task_id)

    assert reread == stored
    assert stored.evidence == evidence
    assert stored.evidence_sha256 == evidence.canonical_hash()
    assert stored.evidence_persisted is True
    assert stored.task_ledger_mutated is False
    assert task_after == task_before


def test_identical_replay_returns_same_record(tmp_path: Path) -> None:
    truth, audit = repository(tmp_path)
    work_order, evidence = cancelled_evidence()
    seed_task(truth, work_order.source_task_id)

    first = audit.persist(evidence)
    second = audit.persist(evidence)

    assert second == first
    assert audit.list_for_task(work_order.source_task_id) == [first]
    assert audit.list_for_work_order(work_order.work_order_id) == [first]
    assert audit.list_recent() == [first]


def test_same_evidence_id_with_different_content_is_rejected(tmp_path: Path) -> None:
    truth, audit = repository(tmp_path)
    work_order, evidence = cancelled_evidence()
    seed_task(truth, work_order.source_task_id)
    audit.persist(evidence)
    tampered = evidence.model_copy(
        update={"cancellation_information": "Different immutable content."}
    )

    with pytest.raises(EngineeringAuditPersistenceConflict):
        audit.persist(tampered)


def test_unknown_canonical_task_is_rejected(tmp_path: Path) -> None:
    _, audit = repository(tmp_path)
    _, evidence = cancelled_evidence()

    with pytest.raises(ValueError, match="existing canonical DAP task"):
        audit.persist(evidence)


def test_recent_limit_is_bounded(tmp_path: Path) -> None:
    _, audit = repository(tmp_path)
    with pytest.raises(ValueError, match="between 1 and 500"):
        audit.list_recent(limit=0)
    with pytest.raises(ValueError, match="between 1 and 500"):
        audit.list_recent(limit=501)
