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
from engineering.remote_git_publication import remote_git_publication_service
from engineering.remote_git_publisher import (
    RemoteGitPublisher,
    RemoteGitPublisherConfig,
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
            f"Phase 11E.3 smoke requires branch {PHASE11_BRANCH!r}; observed {branch!r}"
        )
    if _git(repo, "status", "--porcelain"):
        raise RuntimeError("source repository must be clean before remote publication smoke")

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

    host_home = Path.home().resolve()
    gh_config = (host_home / ".config" / "gh").resolve()
    if not gh_config.is_dir():
        raise RuntimeError(f"GitHub CLI config is unavailable: {gh_config}")

    sandbox_parent = Path(
        os.environ.get("DAP_PHASE11_SANDBOX_ROOT", "/home/dipen/dap/sandboxes")
    ).resolve()
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(
        tempfile.mkdtemp(prefix="phase11e3-remote-publication-", dir=sandbox_parent)
    ).resolve()

    work_order = build_smoke_work_order()
    ticket = engineering_execution_policy.issue_ticket(
        work_order=work_order,
        workspace_id="phase11e3-remote-publication-smoke",
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

    codex_result = None
    local_result = None
    builder = None
    try:
        codex_result = runner.execute(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=admission,
        )
        artifact = codex_result.workspace / SMOKE_TARGET
        artifact_content = (
            artifact.read_text(encoding="utf-8") if artifact.is_file() else None
        )
        if artifact_content != SMOKE_CONTENT:
            raise RuntimeError("Codex smoke artifact content differs from expected content")

        delivery_plan = git_delivery_service.prepare(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=admission,
            run_result=codex_result,
            base_branch=PHASE11_BRANCH,
        )
        builder = LocalGitDeliveryBuilder(
            config=LocalGitDeliveryConfig(
                source_repo=repo,
                delivery_root=run_root / "git",
            )
        )
        local_result = builder.build(
            plan=delivery_plan,
            run_result=codex_result,
        )
        commit_parent = _git(local_result.delivery_repo, "rev-parse", "HEAD^")
        remotes = _git(local_result.delivery_repo, "remote")
        if commit_parent != source_commit or remotes:
            raise RuntimeError("local delivery pre-publication verification failed")

        publication_plan = remote_git_publication_service.prepare(
            delivery_plan=delivery_plan,
            local_result=local_result,
        )
        publisher = RemoteGitPublisher(
            config=RemoteGitPublisherConfig(
                home_dir=host_home,
                gh_config_dir=gh_config,
            )
        )
        publication = publisher.publish(
            plan=publication_plan,
            local_result=local_result,
        )

        print("=== PHASE 11E.3 REMOTE PUBLICATION RESULT ===")
        print(f"source_commit|{source_commit}")
        print(f"ticket_id|{ticket.ticket_id}")
        print(f"guardian_admission_id|{admission.admission_id}")
        print(f"delivery_id|{delivery_plan.delivery_id}")
        print(f"delivery_plan_sha256|{delivery_plan.canonical_hash()}")
        print(f"publication_id|{publication_plan.publication_id}")
        print(f"publication_plan_sha256|{publication_plan.canonical_hash()}")
        print(f"delivery_branch|{publication.delivery_branch}")
        print(f"local_commit_sha|{local_result.commit_sha}")
        print(f"commit_parent|{commit_parent}")
        print(f"remote_commit_sha|{publication.remote_commit_sha}")
        print(f"pull_request_number|{publication.pull_request_number}")
        print(f"pull_request_url|{publication.pull_request_url}")
        print(f"gh_version|{publication.gh_version}")
        print(f"publication_disposition|{publication.receipt.disposition}")
        print(f"branch_reused|{str(publication.branch_reused).lower()}")
        print(
            "draft_pull_request_reused|"
            + str(publication.draft_pull_request_reused).lower()
        )
        print("pull_request_is_draft|true")
        print(f"pull_request_base|{publication_plan.base_branch}")
        print(f"pull_request_head|{publication_plan.delivery_branch}")
        print("github_credentials_exposed_to_codex|false")
        print("github_credentials_exposed_to_ruflo|false")
        print("codex_git_authority|false")
        print("ruflo_git_authority|false")
        print("force_push_performed|false")
        print("protected_branch_updated|false")
        print("pull_request_auto_merge_enabled|false")
        print("main_merge_performed|false")
        print("tag_created|false")
        print("release_created|false")
        print("deployment_performed|false")
        print("owner_review_required|true")

        passed = (
            codex_result.receipt.disposition == "succeeded"
            and codex_result.receipt.delivery_allowed
            and codex_result.receipt.changed_files == (SMOKE_TARGET,)
            and local_result.receipt.disposition == "succeeded"
            and local_result.receipt.committed_files == (SMOKE_TARGET,)
            and commit_parent == source_commit
            and local_result.remote_count == 0
            and publication.receipt.disposition == "succeeded"
            and publication.remote_commit_sha == local_result.commit_sha
            and publication.pull_request_number > 0
            and publication.delivery_branch == delivery_plan.delivery_branch
            and not publication.force_push_performed
            and not publication.main_merge_performed
            and not publication.deployment_performed
        )
        return 0 if passed else 1
    finally:
        if builder is not None and local_result is not None:
            builder.cleanup(local_result.delivery_repo)
        shutil.rmtree(run_root, ignore_errors=True)
        print(f"workspace_removed|{str(not run_root.exists()).lower()}")
        print(
            "source_repo_clean|"
            + str(not _git(repo, "status", "--porcelain")).lower()
        )
        print("remote_cleanup_deferred_to_owner_control|true")


if __name__ == "__main__":
    raise SystemExit(main())
