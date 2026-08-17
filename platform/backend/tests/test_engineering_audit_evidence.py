from pathlib import Path

import pytest

from engineering.codex_execution_contract import (
    CodexExecutionReceipt,
    EngineeringExecutionLimits,
    engineering_execution_policy,
)
from engineering.codex_runner import CodexRunResult
from engineering.codex_smoke import SMOKE_TARGET, build_smoke_work_order
from engineering.engineering_audit_evidence import (
    EngineeringCheckResult,
    engineering_audit_evidence_service,
)
from engineering.engineering_diff_evidence import EngineeringDiffEvidence
from engineering.git_delivery_contract import (
    GitDeliveryObservation,
    git_delivery_service,
)
from engineering.guardian_execution_admission import (
    engineering_guardian_admission_service,
)
from engineering.local_git_delivery import LocalGitDeliveryResult
from engineering.remote_git_publication import (
    RemoteGitPublicationObservation,
    remote_git_publication_service,
)
from engineering.remote_git_publisher import RemoteGitPublisherResult

SOURCE_COMMIT = "1" * 40
LOCAL_COMMIT = "2" * 40
BASE_BRANCH = "phase11/autonomous-engineering-agent"


def chain(tmp_path: Path, *, execution_disposition: str = "succeeded"):
    work_order = build_smoke_work_order()
    ticket = engineering_execution_policy.issue_ticket(
        work_order=work_order,
        workspace_id="phase11f-audit-test",
        limits=EngineeringExecutionLimits(
            timeout_seconds=180,
            max_changed_files=1,
            max_output_bytes=262_144,
        ),
    )
    admission = engineering_guardian_admission_service.admit(
        work_order=work_order,
        ticket=ticket,
    )
    succeeded = execution_disposition == "succeeded"
    receipt = CodexExecutionReceipt(
        ticket_id=ticket.ticket_id,
        ticket_sha256=ticket.canonical_hash(),
        work_order_id=work_order.work_order_id,
        disposition=execution_disposition,
        exit_code=0 if succeeded else 1,
        changed_files=(SMOKE_TARGET,) if succeeded else (),
        findings=(),
        execution_started=True,
        delivery_allowed=succeeded,
        message="Phase 11F execution receipt.",
    )
    run_result = CodexRunResult(
        receipt=receipt,
        workspace=tmp_path / "workspace",
        command_sha256="a" * 64,
        source_commit=SOURCE_COMMIT,
        guardian_admission_id=admission.admission_id,
        guardian_admission_sha256=admission.canonical_hash(),
    )
    return work_order, ticket, admission, run_result


def success_chain(tmp_path: Path):
    work_order, ticket, admission, run_result = chain(tmp_path)
    delivery_plan = git_delivery_service.prepare(
        work_order=work_order,
        ticket=ticket,
        guardian_admission=admission,
        run_result=run_result,
        base_branch=BASE_BRANCH,
    )
    delivery_receipt = git_delivery_service.validate_observation(
        plan=delivery_plan,
        observation=GitDeliveryObservation(
            plan_id=delivery_plan.delivery_id,
            plan_sha256=delivery_plan.canonical_hash(),
            commit_created=True,
            commit_sha=LOCAL_COMMIT,
            committed_files=(SMOKE_TARGET,),
            local_branch_created=True,
        ),
    )
    local_result = LocalGitDeliveryResult(
        receipt=delivery_receipt,
        delivery_repo=tmp_path / "delivery",
        delivery_branch=delivery_plan.delivery_branch,
        commit_sha=LOCAL_COMMIT,
        source_commit=SOURCE_COMMIT,
        remote_count=0,
    )
    diff_evidence = EngineeringDiffEvidence(
        commit_sha=LOCAL_COMMIT,
        parent_sha=SOURCE_COMMIT,
        changed_files=(SMOKE_TARGET,),
        diff_sha256="d" * 64,
    )
    publication_plan = remote_git_publication_service.prepare(
        delivery_plan=delivery_plan,
        local_result=local_result,
    )
    publication_receipt = remote_git_publication_service.validate_observation(
        plan=publication_plan,
        observation=RemoteGitPublicationObservation(
            publication_id=publication_plan.publication_id,
            publication_plan_sha256=publication_plan.canonical_hash(),
            remote_branch_pushed=True,
            remote_commit_sha=LOCAL_COMMIT,
            draft_pull_request_created=True,
            pull_request_number=63,
            pull_request_is_draft=True,
            pull_request_base=BASE_BRANCH,
            pull_request_head=delivery_plan.delivery_branch,
        ),
    )
    publisher_result = RemoteGitPublisherResult(
        receipt=publication_receipt,
        publication_id=publication_plan.publication_id,
        publication_plan_sha256=publication_plan.canonical_hash(),
        delivery_branch=delivery_plan.delivery_branch,
        remote_commit_sha=LOCAL_COMMIT,
        pull_request_number=63,
        pull_request_url="https://github.com/dipenkalal/dipen-ai-platform/pull/63",
        branch_reused=False,
        draft_pull_request_reused=False,
        gh_version="gh version 2.97.0 (2026-07-31)",
    )
    checks = (
        EngineeringCheckResult(
            name="phase11-engineering",
            category="ci",
            status="passed",
            source="github-actions",
            detail="Phase 11 Engineering Agent workflow passed.",
        ),
        EngineeringCheckResult(
            name="repository-ci",
            category="ci",
            status="passed",
            source="github-actions",
            detail="Repository CI passed.",
        ),
    )
    return (
        work_order,
        ticket,
        admission,
        run_result,
        delivery_plan,
        local_result,
        diff_evidence,
        publication_plan,
        publisher_result,
        checks,
    )


def test_success_evidence_binds_complete_phase11_chain(tmp_path: Path) -> None:
    values = success_chain(tmp_path)
    evidence = engineering_audit_evidence_service.build_success(
        work_order=values[0],
        ticket=values[1],
        guardian_admission=values[2],
        run_result=values[3],
        delivery_plan=values[4],
        local_result=values[5],
        diff_evidence=values[6],
        publication_plan=values[7],
        publisher_result=values[8],
        checks=values[9],
    )

    assert evidence.evidence_id.startswith("engineering-audit-")
    assert evidence.outcome == "succeeded"
    assert evidence.source_task_sha256 == values[0].source_task_sha256
    assert evidence.source_admission_sha256 == values[0].source_admission_sha256
    assert evidence.work_order_sha256 == values[0].canonical_hash()
    assert evidence.ticket_sha256 == values[1].canonical_hash()
    assert evidence.guardian_admission_sha256 == values[2].canonical_hash()
    assert evidence.command_sha256 == values[3].command_sha256
    assert evidence.allowed_paths == values[0].allowed_paths
    assert evidence.changed_files == (SMOKE_TARGET,)
    assert evidence.diff_sha256 == "d" * 64
    assert evidence.commit_sha == LOCAL_COMMIT
    assert evidence.draft_pull_request_number == 63
    assert evidence.draft_pull_request_is_draft is True
    assert evidence.task_ledger_mutated is False
    assert evidence.main_merge_performed is False
    assert evidence.deployment_performed is False
    assert len(evidence.canonical_hash()) == 64


def test_success_evidence_is_deterministic(tmp_path: Path) -> None:
    values = success_chain(tmp_path)
    kwargs = {
        "work_order": values[0],
        "ticket": values[1],
        "guardian_admission": values[2],
        "run_result": values[3],
        "delivery_plan": values[4],
        "local_result": values[5],
        "diff_evidence": values[6],
        "publication_plan": values[7],
        "publisher_result": values[8],
        "checks": values[9],
    }
    first = engineering_audit_evidence_service.build_success(**kwargs)
    second = engineering_audit_evidence_service.build_success(**kwargs)
    assert second == first
    assert second.canonical_hash() == first.canonical_hash()


def test_success_evidence_rejects_failed_check(tmp_path: Path) -> None:
    values = success_chain(tmp_path)
    failed = (
        EngineeringCheckResult(
            name="repository-ci",
            category="ci",
            status="failed",
            source="github-actions",
        ),
    )
    with pytest.raises(ValueError, match="non-failing checks"):
        engineering_audit_evidence_service.build_success(
            work_order=values[0],
            ticket=values[1],
            guardian_admission=values[2],
            run_result=values[3],
            delivery_plan=values[4],
            local_result=values[5],
            diff_evidence=values[6],
            publication_plan=values[7],
            publisher_result=values[8],
            checks=failed,
        )


def test_success_evidence_rejects_diff_bound_to_other_commit(tmp_path: Path) -> None:
    values = success_chain(tmp_path)
    tampered = values[6].model_copy(update={"commit_sha": "3" * 40})
    with pytest.raises(ValueError, match="diff evidence commit"):
        engineering_audit_evidence_service.build_success(
            work_order=values[0],
            ticket=values[1],
            guardian_admission=values[2],
            run_result=values[3],
            delivery_plan=values[4],
            local_result=values[5],
            diff_evidence=tampered,
            publication_plan=values[7],
            publisher_result=values[8],
            checks=values[9],
        )


def test_execution_failure_evidence_records_terminal_information(tmp_path: Path) -> None:
    work_order, ticket, admission, run_result = chain(
        tmp_path,
        execution_disposition="failed",
    )
    evidence = engineering_audit_evidence_service.build_execution_failure(
        work_order=work_order,
        ticket=ticket,
        guardian_admission=admission,
        run_result=run_result,
        failure_information="Codex exited with status 1.",
    )

    assert evidence.outcome == "failed"
    assert evidence.terminal_stage == "codex_execution"
    assert evidence.failure_information == "Codex exited with status 1."
    assert evidence.commit_sha is None
    assert evidence.draft_pull_request_number is None


def test_cancellation_evidence_records_reason_without_execution(tmp_path: Path) -> None:
    work_order, ticket, admission, _ = chain(tmp_path)
    evidence = engineering_audit_evidence_service.build_cancelled_before_execution(
        work_order=work_order,
        ticket=ticket,
        guardian_admission=admission,
        cancellation_information="Owner cancelled before executor launch.",
    )

    assert evidence.outcome == "cancelled"
    assert evidence.execution_disposition == "not_started"
    assert evidence.command_sha256 is None
    assert evidence.cancellation_information == "Owner cancelled before executor launch."
