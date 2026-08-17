from pathlib import Path

import pytest

from agents.truth_schemas import TaskLedgerRecord
from engineering.codex_execution_contract import engineering_execution_policy
from engineering.codex_runner import (
    CODEX_CLI_VERSION,
    BoundedCodexRunner,
    CodexProcessResult,
    CodexRunnerConfig,
)
from engineering.engineering_agent_service import (
    EngineeringWorkScope,
    engineering_agent_service,
)
from engineering.guardian_execution_admission import (
    engineering_guardian_admission_service,
)
from executive_office.schemas import ExecutiveExecutionResponse


class FakeMaterializer:
    def materialize(
        self,
        *,
        source_repo: Path,
        source_commit: str,
        workspace: Path,
        env,
    ) -> None:
        del source_repo, source_commit, env
        workspace.mkdir(parents=True)
        target = workspace / "platform/backend/engineering/example.py"
        target.parent.mkdir(parents=True)
        target.write_text("VALUE = 1\n", encoding="utf-8")
        test_target = workspace / "platform/backend/tests/test_example.py"
        test_target.parent.mkdir(parents=True)
        test_target.write_text("def test_example():\n    assert True\n", encoding="utf-8")


class FakeExecutor:
    def __init__(self, *, version: str = CODEX_CLI_VERSION, mutate: str | None = None):
        self.version = version
        self.mutate = mutate
        self.calls = []

    def run(
        self,
        *,
        argv,
        cwd: Path,
        env,
        stdin,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> CodexProcessResult:
        self.calls.append((argv, cwd, dict(env), stdin, timeout_seconds, max_output_bytes))
        if argv[-1] == "--version":
            return CodexProcessResult(
                exit_code=0,
                stdout=(self.version + "\n").encode(),
            )
        if self.mutate is not None:
            target = cwd / self.mutate
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("VALUE = 2\n", encoding="utf-8")
        return CodexProcessResult(exit_code=0, stdout=b'{"type":"done"}\n')


def work_order():
    task = TaskLedgerRecord(
        task_id="phase11c2-child-1",
        task_type="agent",
        objective="Implement a bounded backend change.",
        status="assigned",
        requested_by="dipen-owner",
        assigned_agent_ids=["engineering-agent"],
        source_run_id="phase11c2-delegation",
        parent_task_id="phase11c2-parent",
    )
    admission = ExecutiveExecutionResponse(
        execution_id="phase11c2-execution",
        delegation_id="phase11c2-delegation",
        parent_task_id="phase11c2-parent",
        child_task_ids=["phase11c2-child-1"],
        disposition="validated",
        state="validated",
        selected_agent_ids=["engineering-agent"],
        validation_only=True,
        admission_validated=True,
        message="Validation-only admission passed.",
    )
    return engineering_agent_service.prepare(
        task=task,
        admission=admission,
        scope=EngineeringWorkScope(
            acceptance_criteria=["Tests pass."],
            allowed_paths=[
                "platform/backend/engineering/example.py",
                "platform/backend/tests/test_example.py",
            ],
        ),
    )


def runner_config(tmp_path: Path) -> CodexRunnerConfig:
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    codex_binary = tmp_path / "codex"
    codex_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    codex_binary.chmod(0o700)
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    return CodexRunnerConfig(
        codex_binary=codex_binary,
        codex_home=codex_home,
        source_repo=source_repo,
        source_commit="a" * 40,
        workspace_root=tmp_path / "workspaces",
        require_bwrap=False,
    )


def ticket(order, *, workspace_id: str = "phase11c2-workspace"):
    return engineering_execution_policy.issue_ticket(
        work_order=order,
        workspace_id=workspace_id,
    )


def guardian_admission(order, issued):
    return engineering_guardian_admission_service.admit(
        work_order=order,
        ticket=issued,
    )


def run(runner: BoundedCodexRunner, order, issued):
    return runner.execute(
        work_order=order,
        ticket=issued,
        guardian_admission=guardian_admission(order, issued),
    )


def test_command_uses_pinned_safe_codex_0146_surface(tmp_path: Path) -> None:
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=FakeExecutor(),
        materializer=FakeMaterializer(),
    )
    workspace = tmp_path / "workspaces/run"
    argv = runner.command_argv(workspace=workspace)
    joined = " ".join(argv)

    assert argv[1:4] == ("exec", "--sandbox", "workspace-write")
    assert "--ephemeral" in argv
    assert "--ignore-user-config" in argv
    assert "--strict-config" in argv
    assert "--ignore-rules" in argv
    assert "--skip-git-repo-check" in argv
    assert "sandbox_workspace_write.network_access=false" in argv
    assert "sandbox_workspace_write.exclude_slash_tmp=true" in argv
    assert "sandbox_workspace_write.exclude_tmpdir_env_var=true" in argv
    assert 'shell_environment_policy.inherit="none"' in argv
    assert 'web_search="disabled"' in argv
    assert "features.skill_mcp_dependency_install=false" in argv
    assert 'approval_policy="on-request"' in argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in joined
    assert "--dangerously-bypass-hook-trust" not in joined
    assert "danger-full-access" not in joined
    assert "--add-dir" not in joined


def test_parent_environment_does_not_forward_dap_secrets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("DAP_TELEGRAM_BOT_TOKEN", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=FakeExecutor(),
        materializer=FakeMaterializer(),
    )

    env = runner._parent_environment()

    assert env["CODEX_HOME"].endswith("codex-home")
    assert "DAP_TELEGRAM_BOT_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env


def test_successful_run_mutates_only_allowed_snapshot_file(tmp_path: Path) -> None:
    order = work_order()
    issued = ticket(order)
    executor = FakeExecutor(mutate="platform/backend/engineering/example.py")
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=executor,
        materializer=FakeMaterializer(),
    )

    result = run(runner, order, issued)

    assert result.receipt.disposition == "succeeded"
    assert result.receipt.delivery_allowed is True
    assert result.receipt.changed_files == (
        "platform/backend/engineering/example.py",
    )
    assert result.source_commit == "a" * 40
    assert len(result.command_sha256) == 64
    assert result.guardian_admission_id.startswith("guardian-admission-")
    assert len(result.guardian_admission_sha256) == 64
    assert result.timed_out is False
    assert result.workspace.exists()
    assert len(executor.calls) == 2


def test_out_of_scope_snapshot_change_is_rejected(tmp_path: Path) -> None:
    order = work_order()
    issued = ticket(order)
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=FakeExecutor(mutate="README.md"),
        materializer=FakeMaterializer(),
    )

    result = run(runner, order, issued)

    assert result.receipt.disposition == "rejected"
    assert result.receipt.delivery_allowed is False
    assert any(
        finding.rule_id == "changed-files-outside-scope"
        for finding in result.receipt.findings
    )


def test_guardian_snapshot_mutation_is_explicitly_rejected(tmp_path: Path) -> None:
    order = work_order()
    issued = ticket(order)
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=FakeExecutor(mutate="platform/guardian/broker.py"),
        materializer=FakeMaterializer(),
    )

    result = run(runner, order, issued)

    assert result.receipt.disposition == "rejected"
    assert any(
        finding.rule_id == "guardian-access-attempt"
        for finding in result.receipt.findings
    )


def test_version_drift_fails_before_materialized_execution(tmp_path: Path) -> None:
    order = work_order()
    issued = ticket(order)
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=FakeExecutor(version="codex-cli 0.147.0"),
        materializer=FakeMaterializer(),
    )

    with pytest.raises(RuntimeError, match="version drift"):
        run(runner, order, issued)


def test_work_order_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    order = work_order()
    issued = ticket(order).model_copy(update={"work_order_sha256": "0" * 64})
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=FakeExecutor(),
        materializer=FakeMaterializer(),
    )

    with pytest.raises(ValueError, match="work order hash"):
        runner.execute(
            work_order=order,
            ticket=issued,
            guardian_admission=guardian_admission(order, ticket(order)),
        )


def test_guardian_admission_hash_mismatch_fails_before_codex(tmp_path: Path) -> None:
    order = work_order()
    issued = ticket(order)
    admission = guardian_admission(order, issued).model_copy(
        update={"ticket_sha256": "0" * 64}
    )
    executor = FakeExecutor(mutate="platform/backend/engineering/example.py")
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=executor,
        materializer=FakeMaterializer(),
    )

    with pytest.raises(ValueError, match="ticket hash mismatch"):
        runner.execute(
            work_order=order,
            ticket=issued,
            guardian_admission=admission,
        )

    assert executor.calls == []


def test_cleanup_refuses_paths_outside_workspace_root(tmp_path: Path) -> None:
    runner = BoundedCodexRunner(
        config=runner_config(tmp_path),
        executor=FakeExecutor(),
        materializer=FakeMaterializer(),
    )
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(ValueError, match="outside"):
        runner.cleanup(outside)


def test_prompt_keeps_dap_authority_and_path_allowlist(tmp_path: Path) -> None:
    order = work_order()
    issued = ticket(order)
    prompt = BoundedCodexRunner._prompt(work_order=order, ticket=issued)

    assert "DAP retains all task, approval, Git, Guardian, merge, and deployment authority" in prompt
    assert "Modify only the allowlisted files" in prompt
    assert "Do not use network access" in prompt
    assert "Do not invoke git" in prompt
    assert "platform/backend/engineering/example.py" in prompt
