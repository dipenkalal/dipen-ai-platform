from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from engineering.codex_execution_contract import (
    EngineeringExecutionLimits,
    engineering_execution_policy,
)
from engineering.codex_runner import BoundedCodexRunner, CodexRunnerConfig
from engineering.codex_smoke import (
    PHASE11_BRANCH,
    SMOKE_CONTENT,
    SMOKE_TARGET,
    build_smoke_work_order,
)
from engineering.git_delivery_contract import git_delivery_service
from engineering.guardian_execution_admission import (
    engineering_guardian_admission_service,
)
from engineering.local_git_delivery import (
    LocalGitDeliveryBuilder,
    LocalGitDeliveryConfig,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=30,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    repo = _repo_root()
    branch = _git(repo, "branch", "--show-current")
    if branch != PHASE11_BRANCH:
        raise RuntimeError(
            f"Phase 11E smoke requires branch {PHASE11_BRANCH!r}; observed {branch!r}"
        )
    if _git(repo, "status", "--porcelain"):
        raise RuntimeError("source repository must be clean before Git delivery smoke")

    source_commit = _git(repo, "rev-parse", "HEAD")
    codex_path = shutil.which("codex")
    if codex_path is None:
        raise RuntimeError("codex executable is unavailable")
    if shutil.which("bwrap") is None:
        raise RuntimeError("bubblewrap is unavailable")
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).resolve()
    if not codex_home.is_dir():
        raise RuntimeError(f"Codex auth home is unavailable: {codex_home}")

    sandbox_parent = Path(
        os.environ.get("DAP_PHASE11_SANDBOX_ROOT", "/home/dipen/dap/sandboxes")
    ).resolve()
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(
        tempfile.mkdtemp(prefix="phase11e-git-delivery-", dir=sandbox_parent)
    ).resolve()

    work_order = build_smoke_work_order()
    ticket = engineering_execution_policy.issue_ticket(
        work_order=work_order,
        workspace_id="phase11e-local-git-smoke",
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
    runner = BoundedCodexRunner(
        config=CodexRunnerConfig(
            codex_binary=Path(codex_path).resolve(),
            codex_home=codex_home,
            source_repo=repo,
            source_commit=source_commit,
            workspace_root=run_root / "codex",
        )
    )

    result = None
    delivery_result = None
    builder = None
    try:
        result = runner.execute(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=admission,
        )
        artifact = result.workspace / SMOKE_TARGET
        artifact_content = (
            artifact.read_text(encoding="utf-8") if artifact.is_file() else None
        )
        if artifact_content != SMOKE_CONTENT:
            raise RuntimeError("Codex smoke artifact content differs from expected content")

        plan = git_delivery_service.prepare(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=admission,
            run_result=result,
            base_branch=PHASE11_BRANCH,
        )
        builder = LocalGitDeliveryBuilder(
            config=LocalGitDeliveryConfig(
                source_repo=repo,
                delivery_root=run_root / "git",
            )
        )
        delivery_result = builder.build(plan=plan, run_result=result)
        parent = _git(delivery_result.delivery_repo, "rev-parse", "HEAD^")
        remotes = _git(delivery_result.delivery_repo, "remote")

        print("=== PHASE 11E LOCAL GIT DELIVERY RESULT ===")
        print(f"source_commit|{source_commit}")
        print(f"ticket_id|{ticket.ticket_id}")
        print(f"guardian_admission_id|{admission.admission_id}")
        print(f"delivery_id|{plan.delivery_id}")
        print(f"delivery_plan_sha256|{plan.canonical_hash()}")
        print(f"delivery_branch|{plan.delivery_branch}")
        print(f"commit_sha|{delivery_result.commit_sha}")
        print(f"commit_parent|{parent}")
        print("committed_files|" + ",".join(delivery_result.receipt.committed_files))
        print(f"delivery_disposition|{delivery_result.receipt.disposition}")
        print(f"local_branch_created|true")
        print(f"remote_count|{delivery_result.remote_count}")
        print(f"remote_names|{remotes or 'NONE'}")
        print("remote_branch_pushed|false")
        print("draft_pull_request_created|false")
        print("force_push_performed|false")
        print("main_merge_performed|false")
        print("tag_created|false")
        print("release_created|false")
        print("deployment_performed|false")
        print("github_credentials_exposed_to_codex|false")
        print("codex_git_authority|false")
        print("ruflo_git_authority|false")

        passed = (
            result.receipt.disposition == "succeeded"
            and result.receipt.delivery_allowed
            and result.receipt.changed_files == (SMOKE_TARGET,)
            and delivery_result.receipt.disposition == "succeeded"
            and delivery_result.receipt.committed_files == (SMOKE_TARGET,)
            and parent == source_commit
            and delivery_result.delivery_branch == plan.delivery_branch
            and delivery_result.remote_count == 0
            and remotes == ""
        )
        return 0 if passed else 1
    finally:
        if builder is not None and delivery_result is not None:
            builder.cleanup(delivery_result.delivery_repo)
        shutil.rmtree(run_root, ignore_errors=True)
        print(f"workspace_removed|{str(not run_root.exists()).lower()}")
        print(
            "source_repo_clean|"
            + str(not _git(repo, "status", "--porcelain")).lower()
        )


if __name__ == "__main__":
    raise SystemExit(main())
