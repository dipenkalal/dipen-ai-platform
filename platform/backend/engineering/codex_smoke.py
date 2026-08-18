from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from agents.truth_schemas import TaskLedgerRecord
from engineering.codex_execution_contract import (
    EngineeringExecutionLimits,
    engineering_execution_policy,
)
from engineering.codex_runner import BoundedCodexRunner, CodexRunnerConfig
from engineering.engineering_agent_service import (
    EngineeringWorkScope,
    engineering_agent_service,
)
from engineering.guardian_execution_admission import (
    engineering_guardian_admission_service,
)
from executive_office.schemas import ExecutiveExecutionResponse

PHASE11_BRANCH = "phase11/autonomous-engineering-agent"
SMOKE_TARGET = "platform/backend/engineering/phase11c2_smoke_artifact.txt"
SMOKE_CONTENT = "PHASE11C_CODEX_SMOKE_OK\n"


def build_smoke_work_order():
    task = TaskLedgerRecord(
        task_id="phase11c2-live-smoke-child",
        task_type="agent",
        objective=(
            f"Create {SMOKE_TARGET} with exactly the text "
            f"{SMOKE_CONTENT.strip()!r} followed by one newline. Do not change "
            "any other file."
        ),
        status="assigned",
        requested_by="dipen-owner",
        assigned_agent_ids=["engineering-agent"],
        source_run_id="phase11c2-live-smoke-delegation",
        parent_task_id="phase11c2-live-smoke-parent",
    )
    admission = ExecutiveExecutionResponse(
        execution_id="phase11c2-live-smoke-execution",
        delegation_id="phase11c2-live-smoke-delegation",
        parent_task_id="phase11c2-live-smoke-parent",
        child_task_ids=[task.task_id],
        disposition="validated",
        state="validated",
        selected_agent_ids=["engineering-agent"],
        validation_only=True,
        admission_validated=True,
        message="Phase 11C.2 disposable smoke admission.",
    )
    scope = EngineeringWorkScope(
        acceptance_criteria=[
            f"Only {SMOKE_TARGET} is changed.",
            f"The file content is exactly {SMOKE_CONTENT.strip()!r} plus one newline.",
        ],
        allowed_paths=[SMOKE_TARGET],
        constraints=[
            "This is a disposable sandbox smoke test, not a production change.",
            "Do not run tests, package managers, Git, network tools, or service commands.",
        ],
    )
    return engineering_agent_service.prepare(
        task=task,
        admission=admission,
        scope=scope,
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
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    repo = _repo_root()
    branch = _git(repo, "branch", "--show-current")
    if branch != PHASE11_BRANCH:
        raise RuntimeError(
            f"Phase 11C.2 smoke requires branch {PHASE11_BRANCH!r}; observed {branch!r}"
        )

    status_before = _git(repo, "status", "--porcelain")
    if status_before:
        raise RuntimeError("source repository must be clean before the Codex smoke")

    source_commit = _git(repo, "rev-parse", "HEAD")
    codex_path = shutil.which("codex")
    if codex_path is None:
        raise RuntimeError("codex executable is unavailable")
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
    if not codex_home.is_dir():
        raise RuntimeError(f"Codex auth home is unavailable: {codex_home}")
    if shutil.which("bwrap") is None:
        raise RuntimeError("bubblewrap is unavailable")

    sandbox_parent = Path(
        os.environ.get("DAP_PHASE11_SANDBOX_ROOT", "/home/dipen/dap/sandboxes")
    ).resolve()
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(
        tempfile.mkdtemp(prefix="phase11c2-codex-", dir=sandbox_parent)
    ).resolve()

    order = build_smoke_work_order()
    ticket = engineering_execution_policy.issue_ticket(
        work_order=order,
        workspace_id="phase11c2-live-smoke",
        limits=EngineeringExecutionLimits(
            timeout_seconds=180,
            max_changed_files=1,
            max_output_bytes=262_144,
        ),
    )
    guardian_admission = engineering_guardian_admission_service.admit(
        work_order=order,
        ticket=ticket,
    )
    runner = BoundedCodexRunner(
        config=CodexRunnerConfig(
            codex_binary=Path(codex_path).resolve(),
            codex_home=codex_home,
            source_repo=repo,
            source_commit=source_commit,
            workspace_root=run_root,
        )
    )

    result = None
    try:
        result = runner.execute(
            work_order=order,
            ticket=ticket,
            guardian_admission=guardian_admission,
        )
        artifact = result.workspace / SMOKE_TARGET
        artifact_content = (
            artifact.read_text(encoding="utf-8") if artifact.is_file() else None
        )

        print("=== PHASE 11C.2 CODEX SMOKE RESULT ===")
        print(f"source_commit|{source_commit}")
        print(f"codex_path|{codex_path}")
        print("bwrap_path|" + str(shutil.which("bwrap")))
        print(f"ticket_id|{ticket.ticket_id}")
        print(f"ticket_sha256|{ticket.canonical_hash()}")
        print(f"guardian_admission_id|{guardian_admission.admission_id}")
        print(f"guardian_admission_sha256|{guardian_admission.canonical_hash()}")
        print("guardian_contact_required|false")
        print("guardian_contacted|false")
        print("root_authorization_required|false")
        print(f"command_sha256|{result.command_sha256}")
        print(f"disposition|{result.receipt.disposition}")
        print(f"delivery_allowed|{str(result.receipt.delivery_allowed).lower()}")
        print(f"exit_code|{result.receipt.exit_code}")
        print(f"timed_out|{str(result.timed_out).lower()}")
        print("changed_files|" + ",".join(result.receipt.changed_files))
        print(
            "artifact_content_exact|"
            + str(artifact_content == SMOKE_CONTENT).lower()
        )
        print(
            "git_commit_created|"
            + str(result.receipt.git_commit_created).lower()
        )
        print(
            "pull_request_created|"
            + str(result.receipt.pull_request_created).lower()
        )
        print(
            "main_merge_performed|"
            + str(result.receipt.main_merge_performed).lower()
        )
        print(
            "deployment_performed|"
            + str(result.receipt.deployment_performed).lower()
        )

        passed = (
            result.receipt.disposition == "succeeded"
            and result.receipt.delivery_allowed
            and result.receipt.changed_files == (SMOKE_TARGET,)
            and artifact_content == SMOKE_CONTENT
            and result.guardian_admission_id == guardian_admission.admission_id
            and result.guardian_admission_sha256 == guardian_admission.canonical_hash()
            and not result.timed_out
        )
        if not passed:
            print("stdout_tail|" + result.stdout_tail.replace("\n", "\\n"))
            print("stderr_tail|" + result.stderr_tail.replace("\n", "\\n"))
            return 1
        return 0
    finally:
        shutil.rmtree(run_root, ignore_errors=True)
        status_after = _git(repo, "status", "--porcelain")
        print(f"workspace_removed|{str(not run_root.exists()).lower()}")
        print(f"source_repo_clean|{str(not status_after).lower()}")


if __name__ == "__main__":
    raise SystemExit(main())
