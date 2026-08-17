from pathlib import Path

import pytest
from pydantic import ValidationError

from engineering.git_delivery_contract import GitDeliveryPlan, GitDeliveryReceipt
from engineering.local_git_delivery import LocalGitDeliveryResult
from engineering.remote_git_publication import (
    RemoteGitPublicationObservation,
    RemoteGitPublicationPlan,
    remote_git_publication_service,
)


SOURCE_COMMIT = "1" * 40
LOCAL_COMMIT = "2" * 40


def delivery_plan(**overrides: object) -> GitDeliveryPlan:
    payload = {
        "delivery_id": "git-delivery-phase11e-test",
        "base_branch": "phase11/autonomous-engineering-agent",
        "delivery_branch": "engineering/phase11-test-0123456789ab",
        "source_commit": SOURCE_COMMIT,
        "work_order_id": "engineering-work-test",
        "work_order_sha256": "b" * 64,
        "ticket_id": "codex-ticket-test",
        "ticket_sha256": "c" * 64,
        "guardian_admission_id": "guardian-admission-test",
        "guardian_admission_sha256": "d" * 64,
        "execution_receipt_sha256": "e" * 64,
        "changed_files": ("platform/backend/engineering/example.py",),
        "commit_message": "engineering: deliver phase11-test",
    }
    payload.update(overrides)
    return GitDeliveryPlan(**payload)


def local_result(
    plan: GitDeliveryPlan,
    **overrides: object,
) -> LocalGitDeliveryResult:
    receipt = GitDeliveryReceipt(
        delivery_id=plan.delivery_id,
        delivery_plan_sha256=plan.canonical_hash(),
        disposition="succeeded",
        commit_created=True,
        commit_sha=LOCAL_COMMIT,
        committed_files=plan.changed_files,
        findings=(),
    )
    payload = {
        "receipt": receipt,
        "delivery_repo": Path("/tmp/phase11e-delivery"),
        "delivery_branch": plan.delivery_branch,
        "commit_sha": LOCAL_COMMIT,
        "source_commit": plan.source_commit,
        "remote_count": 0,
    }
    payload.update(overrides)
    return LocalGitDeliveryResult(**payload)


def publication_plan() -> RemoteGitPublicationPlan:
    plan = delivery_plan()
    result = local_result(plan)
    return remote_git_publication_service.prepare(
        delivery_plan=plan,
        local_result=result,
    )


def success_observation(
    plan: RemoteGitPublicationPlan,
    **overrides: object,
) -> RemoteGitPublicationObservation:
    payload = {
        "publication_id": plan.publication_id,
        "publication_plan_sha256": plan.canonical_hash(),
        "remote_branch_pushed": True,
        "remote_commit_sha": plan.local_commit_sha,
        "draft_pull_request_created": True,
        "pull_request_number": 123,
        "pull_request_is_draft": True,
        "pull_request_base": plan.base_branch,
        "pull_request_head": plan.delivery_branch,
    }
    payload.update(overrides)
    return RemoteGitPublicationObservation(**payload)


def test_prepare_grants_only_dap_remote_branch_and_draft_pr_authority() -> None:
    plan = publication_plan()

    assert plan.publication_id.startswith("git-publication-")
    assert plan.repository_full_name == "dipenkalal/dipen-ai-platform"
    assert plan.delivery_branch.startswith("engineering/")
    assert plan.dap_remote_branch_push_allowed is True
    assert plan.dap_draft_pull_request_allowed is True
    assert plan.network_access_required is True
    assert plan.dap_managed_github_credentials_required is True
    assert plan.owner_review_required is True
    assert plan.github_credentials_exposed_to_codex is False
    assert plan.github_credentials_exposed_to_ruflo is False
    assert plan.codex_git_authority is False
    assert plan.ruflo_git_authority is False
    assert plan.force_push_allowed is False
    assert plan.protected_branch_update_allowed is False
    assert plan.pull_request_auto_merge_allowed is False
    assert plan.main_merge_allowed is False
    assert plan.tag_allowed is False
    assert plan.release_allowed is False
    assert plan.deployment_allowed is False


def test_prepare_is_deterministic() -> None:
    first = publication_plan()
    second = publication_plan()
    assert first == second
    assert first.canonical_hash() == second.canonical_hash()


def test_prepare_rejects_protected_base_branch() -> None:
    plan = delivery_plan(base_branch="main")
    result = local_result(plan)
    with pytest.raises(ValueError, match="protected base branch"):
        remote_git_publication_service.prepare(
            delivery_plan=plan,
            local_result=result,
        )


def test_prepare_rejects_non_engineering_branch() -> None:
    plan = delivery_plan(delivery_branch="feature/not-dap-owned")
    result = local_result(plan)
    with pytest.raises(ValueError, match="DAP engineering branch"):
        remote_git_publication_service.prepare(
            delivery_plan=plan,
            local_result=result,
        )


def test_prepare_rejects_local_result_with_remote() -> None:
    plan = delivery_plan()
    result = local_result(plan, remote_count=1)
    with pytest.raises(ValueError, match="network-free local delivery"):
        remote_git_publication_service.prepare(
            delivery_plan=plan,
            local_result=result,
        )


def test_prepare_rejects_tampered_local_commit_receipt() -> None:
    plan = delivery_plan()
    result = local_result(plan)
    tampered_receipt = result.receipt.model_copy(update={"commit_sha": "3" * 40})
    tampered_result = result.model_copy(update={"receipt": tampered_receipt})
    with pytest.raises(ValueError, match="commit receipt changed"):
        remote_git_publication_service.prepare(
            delivery_plan=plan,
            local_result=tampered_result,
        )


def test_validate_accepts_exact_branch_push_and_new_draft_pr() -> None:
    plan = publication_plan()
    receipt = remote_git_publication_service.validate_observation(
        plan=plan,
        observation=success_observation(plan),
    )

    assert receipt.disposition == "succeeded"
    assert receipt.remote_commit_sha == plan.local_commit_sha
    assert receipt.pull_request_number == 123
    assert receipt.branch_reused is False
    assert receipt.draft_pull_request_reused is False
    assert receipt.findings == ()


def test_validate_accepts_exact_idempotent_branch_and_draft_pr_reuse() -> None:
    plan = publication_plan()
    observation = success_observation(
        plan,
        remote_branch_pushed=False,
        remote_branch_reused=True,
        draft_pull_request_created=False,
        draft_pull_request_reused=True,
    )
    receipt = remote_git_publication_service.validate_observation(
        plan=plan,
        observation=observation,
    )

    assert receipt.disposition == "succeeded"
    assert receipt.branch_reused is True
    assert receipt.draft_pull_request_reused is True


@pytest.mark.parametrize(
    ("field", "value", "rule_id"),
    [
        ("remote_commit_sha", "4" * 40, "remote-commit-mismatch"),
        ("pull_request_is_draft", False, "pr-not-draft"),
        ("pull_request_base", "main", "pr-base-mismatch"),
        ("pull_request_head", "engineering/other", "pr-head-mismatch"),
        ("force_push_performed", True, "force-push"),
        ("protected_branch_updated", True, "protected-branch-update"),
        ("pull_request_auto_merge_enabled", True, "auto-merge"),
        ("main_merge_performed", True, "main-merge"),
        ("tag_created", True, "tag-created"),
        ("release_created", True, "release-created"),
        ("deployment_performed", True, "deployment"),
        ("github_credentials_exposed_to_codex", True, "credentials-to-codex"),
        ("github_credentials_exposed_to_ruflo", True, "credentials-to-ruflo"),
    ],
)
def test_validate_rejects_remote_boundary_violation(
    field: str,
    value: object,
    rule_id: str,
) -> None:
    plan = publication_plan()
    receipt = remote_git_publication_service.validate_observation(
        plan=plan,
        observation=success_observation(plan, **{field: value}),
    )

    assert receipt.disposition == "rejected"
    assert rule_id in {finding.rule_id for finding in receipt.findings}


def test_validate_rejects_ambiguous_branch_outcome() -> None:
    plan = publication_plan()
    receipt = remote_git_publication_service.validate_observation(
        plan=plan,
        observation=success_observation(
            plan,
            remote_branch_pushed=True,
            remote_branch_reused=True,
        ),
    )
    assert receipt.disposition == "rejected"
    assert "remote-branch-outcome" in {finding.rule_id for finding in receipt.findings}


def test_validate_rejects_ambiguous_pr_outcome() -> None:
    plan = publication_plan()
    receipt = remote_git_publication_service.validate_observation(
        plan=plan,
        observation=success_observation(
            plan,
            draft_pull_request_created=True,
            draft_pull_request_reused=True,
        ),
    )
    assert receipt.disposition == "rejected"
    assert "draft-pr-outcome" in {finding.rule_id for finding in receipt.findings}


def test_publication_plan_is_immutable() -> None:
    plan = publication_plan()
    with pytest.raises(ValidationError):
        plan.force_push_allowed = True
