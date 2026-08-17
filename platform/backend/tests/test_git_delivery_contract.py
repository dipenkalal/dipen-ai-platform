from pathlib import Path

import pytest
from pydantic import ValidationError

from engineering.codex_execution_contract import (
    CodexExecutionReceipt,
    EngineeringExecutionLimits,
    engineering_execution_policy,
)
from engineering.codex_runner import CodexRunResult
from engineering.codex_smoke import SMOKE_TARGET, build_smoke_work_order
from engineering.git_delivery_contract import (
    GitDeliveryObservation,
    git_delivery_service,
)
from engineering.guardian_execution_admission import (
    engineering_guardian_admission_service,
)

SOURCE_COMMIT = "a" * 40
BASE_BRANCH = "phase11/autonomous-engineering-agent"


def chain():
    work_order = build_smoke_work_order()
    ticket = engineering_execution_policy.issue_ticket(
        work_order=work_order,
        workspace_id="phase11e-contract-test",
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
    receipt = CodexExecutionReceipt(
        ticket_id=ticket.ticket_id,
        ticket_sha256=ticket.canonical_hash(),
        work_order_id=work_order.work_order_id,
        disposition="succeeded",
        exit_code=0,
        changed_files=(SMOKE_TARGET,),
        findings=(),
        execution_started=True,
        delivery_allowed=True,
        message="Controlled Codex observation passed the DAP execution boundary.",
    )
    run_result = CodexRunResult(
        receipt=receipt,
        workspace=Path("/tmp/phase11e-contract-workspace"),
        command_sha256="b" * 64,
        source_commit=SOURCE_COMMIT,
        guardian_admission_id=admission.admission_id,
        guardian_admission_sha256=admission.canonical_hash(),
    )
    return work_order, ticket, admission, run_result


def plan():
    work_order, ticket, admission, run_result = chain()
    return git_delivery_service.prepare(
        work_order=work_order,
        ticket=ticket,
        guardian_admission=admission,
        run_result=run_result,
        base_branch=BASE_BRANCH,
    )


def test_prepare_binds_entire_execution_chain_and_stays_local_only() -> None:
    delivery = plan()

    assert delivery.repository_full_name == "dipenkalal/dipen-ai-platform"
    assert delivery.base_branch == BASE_BRANCH
    assert delivery.delivery_branch.startswith("engineering/")
    assert delivery.source_commit == SOURCE_COMMIT
    assert delivery.changed_files == (SMOKE_TARGET,)
    assert delivery.commit_allowed is True
    assert delivery.delivery_branch_push_allowed is False
    assert delivery.draft_pull_request_allowed is False
    assert delivery.github_credentials_exposed_to_codex is False
    assert delivery.codex_git_authority is False
    assert delivery.ruflo_git_authority is False
    assert delivery.force_push_allowed is False
    assert delivery.main_merge_allowed is False
    assert delivery.tag_allowed is False
    assert delivery.release_allowed is False
    assert delivery.deployment_allowed is False
    assert len(delivery.canonical_hash()) == 64


def test_prepare_is_deterministic_for_same_chain() -> None:
    first = plan()
    second = plan()

    assert first == second
    assert first.canonical_hash() == second.canonical_hash()


@pytest.mark.parametrize("base_branch", ["main", "master", "refs/heads/dev", "bad branch", "../dev"])
def test_prepare_rejects_protected_or_unsafe_base_branch(base_branch: str) -> None:
    work_order, ticket, admission, run_result = chain()
    with pytest.raises(ValueError):
        git_delivery_service.prepare(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=admission,
            run_result=run_result,
            base_branch=base_branch,
        )


def test_prepare_rejects_failed_or_ineligible_codex_result() -> None:
    work_order, ticket, admission, run_result = chain()
    bad_receipt = run_result.receipt.model_copy(
        update={"disposition": "failed", "delivery_allowed": False, "exit_code": 1}
    )
    bad_result = run_result.model_copy(update={"receipt": bad_receipt})

    with pytest.raises(ValueError, match="not eligible"):
        git_delivery_service.prepare(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=admission,
            run_result=bad_result,
            base_branch=BASE_BRANCH,
        )


def test_prepare_rejects_tampered_guardian_binding() -> None:
    work_order, ticket, admission, run_result = chain()
    bad_result = run_result.model_copy(update={"guardian_admission_sha256": "c" * 64})

    with pytest.raises(ValueError, match="Guardian admission"):
        git_delivery_service.prepare(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=admission,
            run_result=bad_result,
            base_branch=BASE_BRANCH,
        )


def test_local_delivery_observation_accepts_exact_commit_only() -> None:
    delivery = plan()
    observation = GitDeliveryObservation(
        plan_id=delivery.delivery_id,
        plan_sha256=delivery.canonical_hash(),
        commit_created=True,
        commit_sha="d" * 40,
        committed_files=delivery.changed_files,
        local_branch_created=True,
    )

    receipt = git_delivery_service.validate_observation(
        plan=delivery,
        observation=observation,
    )

    assert receipt.disposition == "succeeded"
    assert receipt.commit_created is True
    assert receipt.commit_sha == "d" * 40
    assert receipt.committed_files == delivery.changed_files
    assert receipt.remote_branch_pushed is False
    assert receipt.draft_pull_request_created is False
    assert receipt.main_merge_performed is False
    assert receipt.deployment_performed is False
    assert receipt.findings == ()


def test_local_delivery_observation_rejects_remote_or_merge_side_effects() -> None:
    delivery = plan()
    observation = GitDeliveryObservation(
        plan_id=delivery.delivery_id,
        plan_sha256=delivery.canonical_hash(),
        commit_created=True,
        commit_sha="d" * 40,
        committed_files=delivery.changed_files,
        local_branch_created=True,
        remote_branch_pushed=True,
        main_merge_performed=True,
    )

    receipt = git_delivery_service.validate_observation(
        plan=delivery,
        observation=observation,
    )

    assert receipt.disposition == "rejected"
    assert {finding.rule_id for finding in receipt.findings} >= {
        "remote-branch-push",
        "main-merge",
    }


def test_local_delivery_observation_rejects_file_mismatch() -> None:
    delivery = plan()
    observation = GitDeliveryObservation(
        plan_id=delivery.delivery_id,
        plan_sha256=delivery.canonical_hash(),
        commit_created=True,
        commit_sha="d" * 40,
        committed_files=("platform/backend/engineering/other.py",),
        local_branch_created=True,
    )

    receipt = git_delivery_service.validate_observation(
        plan=delivery,
        observation=observation,
    )

    assert receipt.disposition == "rejected"
    assert any(
        finding.rule_id == "committed-files-mismatch"
        for finding in receipt.findings
    )


def test_delivery_plan_is_immutable() -> None:
    delivery = plan()

    with pytest.raises(ValidationError):
        delivery.main_merge_allowed = True
