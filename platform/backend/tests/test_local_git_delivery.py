import subprocess
from pathlib import Path

import pytest

from engineering.codex_execution_contract import (
    CodexExecutionReceipt,
    EngineeringExecutionLimits,
    engineering_execution_policy,
)
from engineering.codex_runner import CodexRunResult
from engineering.codex_smoke import SMOKE_CONTENT, SMOKE_TARGET, build_smoke_work_order
from engineering.git_delivery_contract import git_delivery_service
from engineering.guardian_execution_admission import (
    engineering_guardian_admission_service,
)
from engineering.local_git_delivery import (
    LocalGitDeliveryBuilder,
    LocalGitDeliveryConfig,
)

BASE_BRANCH = "phase11/autonomous-engineering-agent"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def source_repo(root: Path) -> tuple[Path, str]:
    repo = root / "source"
    repo.mkdir()
    git(repo, "init")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(
        repo,
        "-c",
        "user.name=DAP Test",
        "-c",
        "user.email=dap-test@example.invalid",
        "commit",
        "--no-gpg-sign",
        "-m",
        "base",
    )
    return repo, git(repo, "rev-parse", "HEAD")


def delivery_chain(root: Path):
    repo, commit = source_repo(root)
    workspace = root / "workspace"
    artifact = workspace / SMOKE_TARGET
    artifact.parent.mkdir(parents=True)
    artifact.write_text(SMOKE_CONTENT, encoding="utf-8")

    work_order = build_smoke_work_order()
    ticket = engineering_execution_policy.issue_ticket(
        work_order=work_order,
        workspace_id="phase11e-local-git-test",
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
        workspace=workspace,
        command_sha256="b" * 64,
        source_commit=commit,
        guardian_admission_id=admission.admission_id,
        guardian_admission_sha256=admission.canonical_hash(),
    )
    plan = git_delivery_service.prepare(
        work_order=work_order,
        ticket=ticket,
        guardian_admission=admission,
        run_result=run_result,
        base_branch=BASE_BRANCH,
    )
    return repo, workspace, run_result, plan


def test_builder_creates_exact_local_commit_without_remote(tmp_path: Path) -> None:
    repo, _, run_result, plan = delivery_chain(tmp_path)
    delivery_root = tmp_path / "deliveries"
    builder = LocalGitDeliveryBuilder(
        config=LocalGitDeliveryConfig(
            source_repo=repo,
            delivery_root=delivery_root,
        )
    )

    result = builder.build(plan=plan, run_result=run_result)

    assert result.receipt.disposition == "succeeded"
    assert result.receipt.committed_files == (SMOKE_TARGET,)
    assert result.delivery_branch == plan.delivery_branch
    assert result.source_commit == plan.source_commit
    assert result.remote_count == 0
    assert git(result.delivery_repo, "rev-parse", "HEAD^") == plan.source_commit
    assert git(result.delivery_repo, "branch", "--show-current") == plan.delivery_branch
    assert git(result.delivery_repo, "remote") == ""
    assert (result.delivery_repo / SMOKE_TARGET).read_text(encoding="utf-8") == SMOKE_CONTENT
    assert git(result.delivery_repo, "status", "--porcelain") == ""

    builder.cleanup(result.delivery_repo)
    assert not result.delivery_repo.exists()


def test_builder_rejects_plan_that_gains_remote_authority(tmp_path: Path) -> None:
    repo, _, run_result, plan = delivery_chain(tmp_path)
    unsafe = plan.model_copy(update={"delivery_branch_push_allowed": True})
    builder = LocalGitDeliveryBuilder(
        config=LocalGitDeliveryConfig(
            source_repo=repo,
            delivery_root=tmp_path / "deliveries",
        )
    )

    with pytest.raises(ValueError, match="prohibited authority"):
        builder.build(plan=unsafe, run_result=run_result)


def test_builder_rejects_changed_file_outside_plan(tmp_path: Path) -> None:
    repo, workspace, run_result, plan = delivery_chain(tmp_path)
    extra = workspace / "unexpected.txt"
    extra.write_text("unexpected\n", encoding="utf-8")
    tampered_receipt = run_result.receipt.model_copy(
        update={"changed_files": (SMOKE_TARGET, "unexpected.txt")}
    )
    tampered_result = run_result.model_copy(update={"receipt": tampered_receipt})
    builder = LocalGitDeliveryBuilder(
        config=LocalGitDeliveryConfig(
            source_repo=repo,
            delivery_root=tmp_path / "deliveries",
        )
    )

    with pytest.raises(ValueError, match="changed-file list"):
        builder.build(plan=plan, run_result=tampered_result)


def test_builder_cleans_failed_delivery_repository(tmp_path: Path) -> None:
    repo, workspace, run_result, plan = delivery_chain(tmp_path)
    artifact = workspace / SMOKE_TARGET
    artifact.unlink()
    artifact.mkdir()
    delivery_root = tmp_path / "deliveries"
    builder = LocalGitDeliveryBuilder(
        config=LocalGitDeliveryConfig(
            source_repo=repo,
            delivery_root=delivery_root,
        )
    )

    with pytest.raises(ValueError, match="file-level"):
        builder.build(plan=plan, run_result=run_result)

    assert not (delivery_root / plan.delivery_id).exists()


def test_cleanup_refuses_path_outside_delivery_root(tmp_path: Path) -> None:
    repo, _, _, _ = delivery_chain(tmp_path)
    builder = LocalGitDeliveryBuilder(
        config=LocalGitDeliveryConfig(
            source_repo=repo,
            delivery_root=tmp_path / "deliveries",
        )
    )

    with pytest.raises(ValueError, match="outside"):
        builder.cleanup(tmp_path / "not-a-delivery")
