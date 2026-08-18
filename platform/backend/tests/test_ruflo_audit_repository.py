from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from engineering.ruflo_adapter_contract import RufloArtifactPin, RufloPolicyFinding
from engineering.ruflo_audit_evidence import RufloAuditEvidence
from engineering.ruflo_audit_repository import (
    RufloAuditPersistenceConflict,
    RufloAuditRepository,
)


def _evidence(*, evidence_id: str = "ruflo-audit-test-001", message: str = "safe") -> RufloAuditEvidence:
    return RufloAuditEvidence(
        evidence_id=evidence_id,
        source_execution_id="execution-test-001",
        source_delegation_id="delegation-test-001",
        source_parent_task_id="parent-test-001",
        source_task_id="task-test-001",
        source_task_sha256="1" * 64,
        source_admission_sha256="2" * 64,
        source_handoff_sha256="3" * 64,
        request_id="ruflo-request-test-001",
        request_sha256="4" * 64,
        adapter_artifact=RufloArtifactPin(),
        source_receipt_sha256="5" * 64,
        candidate_disposition="accepted",
        candidate_artifact_sha256="6" * 64,
        upstream_valid=True,
        dap_policy_findings=[
            RufloPolicyFinding(
                rule_id="phase10-safe",
                blocked=False,
                detail="DAP policy accepted validation-only guidance.",
            )
        ],
        message=message,
    )


def _task() -> TaskLedgerRecord:
    now = datetime.now(timezone.utc)
    return TaskLedgerRecord(
        task_id="task-test-001",
        task_type="agent",
        objective="Review a bounded engineering candidate.",
        status="assigned",
        requested_by="dipen-owner",
        assigned_agent_ids=["system-agent"],
        source_run_id="delegation-test-001",
        parent_task_id="parent-test-001",
        created_at=now,
        updated_at=now,
    )


def _repo(tmp_path: Path) -> tuple[AgentTruthRepository, RufloAuditRepository]:
    truth = AgentTruthRepository(tmp_path / "agent-truth.db")
    return truth, RufloAuditRepository(truth)


def test_persist_round_trip_is_immutable_and_additive(tmp_path: Path) -> None:
    truth, repository = _repo(tmp_path)
    task_before = truth.upsert_task(_task())
    evidence = _evidence()

    stored = repository.persist(evidence)
    reread = repository.get(evidence.evidence_id)
    task_after = truth.get_task(task_before.task_id)

    assert reread == stored
    assert stored.evidence == evidence
    assert stored.evidence_sha256 == evidence.canonical_hash()
    assert stored.evidence_persisted is True
    assert stored.task_ledger_mutated is False
    assert task_after == task_before


def test_identical_replay_returns_same_stored_record(tmp_path: Path) -> None:
    _, repository = _repo(tmp_path)
    evidence = _evidence()

    first = repository.persist(evidence)
    second = repository.persist(evidence)

    assert second == first
    assert repository.list_for_task(evidence.source_task_id) == [first]


def test_same_evidence_id_with_different_content_is_rejected(tmp_path: Path) -> None:
    _, repository = _repo(tmp_path)
    repository.persist(_evidence())

    with pytest.raises(RufloAuditPersistenceConflict):
        repository.persist(_evidence(message="tampered evidence"))


def test_task_index_returns_only_matching_evidence(tmp_path: Path) -> None:
    _, repository = _repo(tmp_path)
    first = repository.persist(_evidence(evidence_id="ruflo-audit-test-001"))
    other = _evidence(evidence_id="ruflo-audit-test-002").model_copy(
        update={"source_task_id": "task-other-001"}
    )
    repository.persist(other)

    assert repository.list_for_task("task-test-001") == [first]
    assert repository.list_for_task("missing-task") == []
