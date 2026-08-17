from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agents.truth_schemas import TaskLedgerRecord
from engineering.engineering_audit_evidence import (
    EngineeringAuditEvidence,
    EngineeringCheckResult,
    EngineeringPolicyDecision,
)
from engineering.engineering_audit_repository import PersistedEngineeringAuditRecord
from engineering.engineering_owner_review import (
    EngineeringOwnerReviewDecisionRequest,
    engineering_owner_review_service,
)


def engineering_task() -> TaskLedgerRecord:
    now = datetime.now(timezone.utc)
    return TaskLedgerRecord(
        task_id="phase11i-task",
        task_type="agent",
        objective="Repair one bounded file and deliver a draft pull request.",
        status="completed",
        requested_by="dipen-owner",
        assigned_agent_ids=["engineering-agent"],
        source_run_id="phase11i-delegation",
        parent_task_id="phase11i-parent",
        created_at=now,
        updated_at=now,
        completed_at=now,
    )


def successful_evidence(*, outcome: str = "succeeded") -> EngineeringAuditEvidence:
    values: dict[str, object] = {
        "evidence_id": "engineering-evidence-phase11i",
        "source_execution_id": "phase11i-execution",
        "source_delegation_id": "phase11i-delegation",
        "source_parent_task_id": "phase11i-parent",
        "source_task_id": "phase11i-task",
        "source_task_sha256": "a" * 64,
        "source_admission_sha256": "b" * 64,
        "work_order_id": "engineering-work-order-phase11i",
        "work_order_sha256": "c" * 64,
        "ticket_id": "codex-ticket-phase11i",
        "ticket_sha256": "d" * 64,
        "guardian_admission_id": "guardian-admission-phase11i",
        "guardian_admission_sha256": "e" * 64,
        "guardian_risk_class": "non_privileged_workspace",
        "executor_runtime_identity": "codex-cli 0.146.0",
        "command_sha256": "f" * 64,
        "allowed_paths": ("platform/backend/example.py",),
        "admitted_actions": ("workspace_file_write", "codex_execution"),
        "policy_decisions": (
            EngineeringPolicyDecision(
                policy_id="phase11i-owner-review-required",
                authority="owner",
                decision="require",
                detail="Owner review is required before any later merge action.",
            ),
        ),
        "execution_receipt_sha256": "1" * 64,
        "execution_disposition": "succeeded",
        "execution_exit_code": 0,
        "changed_files": ("platform/backend/example.py",),
        "diff_sha256": "2" * 64,
        "checks": (
            EngineeringCheckResult(
                name="pytest",
                category="test",
                status="passed",
                source="DAP test gate",
                detail="All targeted tests passed.",
            ),
        ),
        "delivery_id": "git-delivery-phase11i",
        "delivery_plan_sha256": "3" * 64,
        "delivery_receipt_sha256": "4" * 64,
        "commit_sha": "5" * 40,
        "publication_id": "git-publication-phase11i",
        "publication_plan_sha256": "6" * 64,
        "publication_receipt_sha256": "7" * 64,
        "delivery_branch": "engineering/phase11i-example",
        "remote_commit_sha": "5" * 40,
        "draft_pull_request_number": 88,
        "draft_pull_request_url": "https://github.com/dipenkalal/dipen-ai-platform/pull/88",
        "draft_pull_request_is_draft": True,
        "outcome": outcome,
        "terminal_stage": "post_publication_checks",
    }
    if outcome != "succeeded":
        values.update(
            {
                "command_sha256": None,
                "execution_receipt_sha256": None,
                "execution_disposition": "failed",
                "changed_files": (),
                "diff_sha256": None,
                "checks": (),
                "delivery_id": None,
                "delivery_plan_sha256": None,
                "delivery_receipt_sha256": None,
                "commit_sha": None,
                "publication_id": None,
                "publication_plan_sha256": None,
                "publication_receipt_sha256": None,
                "delivery_branch": None,
                "remote_commit_sha": None,
                "draft_pull_request_number": None,
                "draft_pull_request_url": None,
                "draft_pull_request_is_draft": False,
                "failure_information": "Execution failed before delivery.",
            }
        )
    return EngineeringAuditEvidence.model_validate(values)


def persisted_record(evidence: EngineeringAuditEvidence) -> PersistedEngineeringAuditRecord:
    return PersistedEngineeringAuditRecord(
        evidence=evidence,
        evidence_sha256=evidence.canonical_hash(),
        stored_at=datetime.now(timezone.utc),
    )


def test_build_package_is_concise_deterministic_and_nonexecuting() -> None:
    task = engineering_task()
    record = persisted_record(successful_evidence())

    package = engineering_owner_review_service.build_package(task=task, record=record)
    replay = engineering_owner_review_service.build_package(task=task, record=record)

    assert package == replay
    assert package.objective == task.objective
    assert package.changed_files == ("platform/backend/example.py",)
    assert package.draft_pull_request_number == 88
    assert package.owner_action_required == "approve_or_reject"
    assert package.approval_effect == "record_review_only"
    assert package.risk_level == "low_non_privileged_workspace"
    assert package.git_write_authority_granted is False
    assert package.merge_authority_granted is False
    assert package.deployment_authority_granted is False
    assert package.guardian_authority_granted is False
    assert package.task_ledger_mutation_allowed is False


def test_approve_decision_records_review_without_merge_authority() -> None:
    package = engineering_owner_review_service.build_package(
        task=engineering_task(),
        record=persisted_record(successful_evidence()),
    )
    request = EngineeringOwnerReviewDecisionRequest(
        decision="approve",
        reason="Reviewed checks and changed files.",
    )

    decision = engineering_owner_review_service.decide(package=package, request=request)

    assert decision.decision == "approve"
    assert decision.owner_id == "dipen-owner"
    assert decision.review_recorded is True
    assert decision.owner_merge_action_still_required is True
    assert decision.git_write_performed is False
    assert decision.pull_request_merged is False
    assert decision.main_merge_performed is False
    assert decision.deployment_performed is False
    assert decision.guardian_contacted is False
    assert decision.task_ledger_mutated is False


def test_reject_requires_owner_reason() -> None:
    with pytest.raises(ValidationError):
        EngineeringOwnerReviewDecisionRequest(decision="reject", reason="")


def test_failed_evidence_is_not_reviewable() -> None:
    record = persisted_record(successful_evidence(outcome="failed"))

    with pytest.raises(ValueError, match="only successful engineering evidence"):
        engineering_owner_review_service.build_package(
            task=engineering_task(),
            record=record,
        )
