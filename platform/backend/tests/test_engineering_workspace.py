from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from engineering.engineering_audit_evidence import (
    EngineeringAuditEvidence,
    EngineeringPolicyDecision,
)
from engineering.engineering_audit_repository import EngineeringAuditRepository
from engineering.engineering_workspace import EngineeringWorkspaceService


def task(
    *,
    task_id: str,
    status: str,
    assigned_agent_ids: list[str] | None = None,
) -> TaskLedgerRecord:
    now = datetime.now(timezone.utc)
    return TaskLedgerRecord(
        task_id=task_id,
        task_type="agent",
        objective=f"Inspect engineering task {task_id}.",
        status=status,
        requested_by="dipen-owner",
        assigned_agent_ids=assigned_agent_ids or ["engineering-agent"],
        source_run_id=f"delegation-{task_id}",
        parent_task_id=f"parent-{task_id}",
        created_at=now,
        updated_at=now,
    )


def cancelled_evidence(task_id: str) -> EngineeringAuditEvidence:
    return EngineeringAuditEvidence(
        evidence_id=f"engineering-audit-{task_id}",
        source_execution_id=f"execution-{task_id}",
        source_delegation_id=f"delegation-{task_id}",
        source_parent_task_id=f"parent-{task_id}",
        source_task_id=task_id,
        source_task_sha256="1" * 64,
        source_admission_sha256="2" * 64,
        work_order_id=f"engineering-work-{task_id}",
        work_order_sha256="3" * 64,
        ticket_id=f"codex-ticket-{task_id}",
        ticket_sha256="4" * 64,
        guardian_admission_id=f"guardian-admission-{task_id}",
        guardian_admission_sha256="5" * 64,
        guardian_risk_class="non_privileged_workspace",
        executor_runtime_identity="codex-cli 0.146.0",
        allowed_paths=("platform/backend/example.py",),
        admitted_actions=("codex.workspace_execute",),
        policy_decisions=(
            EngineeringPolicyDecision(
                policy_id="owner-review-required",
                authority="owner",
                decision="require",
                detail="Owner review remains required.",
            ),
        ),
        execution_disposition="not_started",
        outcome="cancelled",
        terminal_stage="codex_execution",
        cancellation_information="Cancelled before Codex execution.",
    )


def service(tmp_path: Path) -> tuple[AgentTruthRepository, EngineeringWorkspaceService]:
    truth = AgentTruthRepository(tmp_path / "agent-truth.db")
    return truth, EngineeringWorkspaceService(truth)


def test_workspace_lists_only_engineering_tasks_and_is_read_only(tmp_path: Path) -> None:
    truth, workspace = service(tmp_path)
    truth.upsert_task(task(task_id="engineering-queued", status="assigned"))
    truth.upsert_task(
        task(
            task_id="other-agent",
            status="running",
            assigned_agent_ids=["system-agent"],
        )
    )

    response = workspace.list_workspace()

    assert response.read_only is True
    assert response.execution_controls_exposed is False
    assert response.summary.total == 1
    assert response.summary.queued == 1
    assert response.items[0].task.task_id == "engineering-queued"
    assert response.items[0].provenance_state == "evidence_unavailable"
    assert response.items[0].ui_execution_authority is False
    assert response.items[0].ui_guardian_authority is False
    assert response.items[0].ui_merge_authority is False
    assert response.items[0].ui_deployment_authority is False


def test_terminal_evidence_enriches_but_does_not_override_task_truth(
    tmp_path: Path,
) -> None:
    truth, workspace = service(tmp_path)
    canonical = truth.upsert_task(task(task_id="engineering-failed", status="cancelled"))
    EngineeringAuditRepository(truth).persist(cancelled_evidence(canonical.task_id))

    item = workspace.get_item(canonical.task_id)

    assert item.workspace_state == "failed"
    assert item.provenance_state == "consistent"
    assert item.work_order_id == f"engineering-work-{canonical.task_id}"
    assert item.evidence_count == 1
    assert item.latest_evidence is not None
    assert item.latest_evidence.evidence.outcome == "cancelled"
    assert item.task == canonical
    assert truth.get_task(canonical.task_id) == canonical


def test_terminal_evidence_mismatch_is_flagged_for_reconciliation(tmp_path: Path) -> None:
    truth, workspace = service(tmp_path)
    canonical = truth.upsert_task(task(task_id="engineering-running", status="running"))
    EngineeringAuditRepository(truth).persist(cancelled_evidence(canonical.task_id))

    item = workspace.get_item(canonical.task_id)

    assert item.workspace_state == "active"
    assert item.provenance_state == "requires_reconciliation"
    assert workspace.list_workspace().summary.requires_reconciliation == 1


def test_unknown_or_non_engineering_task_is_not_exposed(tmp_path: Path) -> None:
    truth, workspace = service(tmp_path)
    truth.upsert_task(
        task(
            task_id="system-task",
            status="assigned",
            assigned_agent_ids=["system-agent"],
        )
    )

    with pytest.raises(KeyError, match="Engineering task not found"):
        workspace.get_item("system-task")
    with pytest.raises(KeyError, match="Engineering task not found"):
        workspace.get_item("missing-task")
