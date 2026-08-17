from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import tarfile
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engineering.codex_execution_contract import (
    CodexExecutionReceipt,
    CodexExecutionTicket,
    CodexRunnerObservation,
    codex_execution_validator,
)
from engineering.engineering_agent_service import EngineeringWorkOrder
from engineering.guardian_execution_admission import EngineeringGuardianAdmission

CODEX_CLI_VERSION = "codex-cli 0.146.0"


class CodexRunnerConfig(BaseModel):
    """Pinned local runner configuration for one Phase 11 Codex surface."""

    model_config = ConfigDict(frozen=True)

    codex_binary: Path
    codex_home: Path
    source_repo: Path
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    workspace_root: Path
    expected_version: str = CODEX_CLI_VERSION
    require_bwrap: bool = True

    @model_validator(mode="after")
    def validate_paths(self) -> CodexRunnerConfig:
        source = self.source_repo.resolve()
        workspace = self.workspace_root.resolve()
        if workspace == source or source in workspace.parents:
            raise ValueError("Codex workspace root must be outside the source repository")
        if self.codex_home.resolve() == workspace:
            raise ValueError("Codex auth home cannot be the workspace root")
        return self


class CodexProcessResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    exit_code: int
    stdout: bytes = b""
    stderr: bytes = b""
    timed_out: bool = False


class CodexCommandExecutor(Protocol):
    def run(
        self,
        *,
        argv: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
        stdin: bytes | None,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> CodexProcessResult: ...


class WorkspaceMaterializer(Protocol):
    def materialize(
        self,
        *,
        source_repo: Path,
        source_commit: str,
        workspace: Path,
        env: Mapping[str, str],
    ) -> None: ...


class SubprocessCodexCommandExecutor:
    """Run a fixed argv without a shell and capture output through temp files."""

    def run(
        self,
        *,
        argv: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str],
        stdin: bytes | None,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> CodexProcessResult:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=dict(env),
                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )
            timed_out = False
            try:
                process.communicate(input=stdin, timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)

            stdout_file.seek(0)
            stderr_file.seek(0)
            limit = max_output_bytes + 1
            stdout = stdout_file.read(limit)
            remaining = max(limit - len(stdout), 0)
            stderr = stderr_file.read(remaining)
            exit_code = process.returncode if process.returncode is not None else 124
            if timed_out and exit_code == 0:
                exit_code = 124
            return CodexProcessResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                timed_out=timed_out,
            )


class GitArchiveWorkspaceMaterializer:
    """Create a tracked-file-only snapshot with no Git metadata or untracked secrets."""

    def materialize(
        self,
        *,
        source_repo: Path,
        source_commit: str,
        workspace: Path,
        env: Mapping[str, str],
    ) -> None:
        if workspace.exists():
            raise ValueError("Codex workspace already exists")
        workspace.mkdir(parents=True, mode=0o700)

        verification = subprocess.run(
            ("git", "rev-parse", "--verify", f"{source_commit}^{{commit}}"),
            cwd=source_repo,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
        resolved = verification.stdout.decode("utf-8", errors="replace").strip()
        if verification.returncode != 0 or resolved != source_commit:
            raise ValueError("source commit is not available exactly in the DAP repository")

        archive_path = workspace.parent / f".{workspace.name}.tar"
        try:
            archive = subprocess.run(
                ("git", "archive", "--format=tar", f"--output={archive_path}", source_commit),
                cwd=source_repo,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=60,
            )
            if archive.returncode != 0:
                raise RuntimeError("git archive failed while materializing Codex workspace")
            self._extract_regular_files(archive_path=archive_path, workspace=workspace)
        finally:
            archive_path.unlink(missing_ok=True)

    @staticmethod
    def _extract_regular_files(*, archive_path: Path, workspace: Path) -> None:
        with tarfile.open(archive_path, mode="r") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or not path.parts
                    or any(part in {"", ".", ".."} for part in path.parts)
                ):
                    raise ValueError("git archive contains an unsafe path")
                target = workspace.joinpath(*path.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise ValueError("Codex snapshot refuses links and special files")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("git archive member could not be read")
                with source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                target.chmod(member.mode & 0o777)


class CodexRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    receipt: CodexExecutionReceipt
    workspace: Path
    command_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    guardian_admission_id: str
    guardian_admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stdout_tail: str = ""
    stderr_tail: str = ""
    timed_out: bool = False


class BoundedCodexRunner:
    """Execute Codex only after DAP proves a non-privileged Guardian boundary."""

    _parent_env_keys = (
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
    )

    def __init__(
        self,
        *,
        config: CodexRunnerConfig,
        executor: CodexCommandExecutor | None = None,
        materializer: WorkspaceMaterializer | None = None,
    ) -> None:
        self.config = config
        self.executor = executor or SubprocessCodexCommandExecutor()
        self.materializer = materializer or GitArchiveWorkspaceMaterializer()

    def execute(
        self,
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
    ) -> CodexRunResult:
        self._validate_binding(work_order=work_order, ticket=ticket)
        self._validate_guardian_admission(
            work_order=work_order,
            ticket=ticket,
            admission=guardian_admission,
        )
        parent_env = self._parent_environment()
        self._preflight(parent_env)

        workspace = self.config.workspace_root.resolve() / ticket.workspace_id
        self.materializer.materialize(
            source_repo=self.config.source_repo.resolve(),
            source_commit=self.config.source_commit,
            workspace=workspace,
            env=parent_env,
        )
        before = self._snapshot(workspace)
        prompt = self._prompt(work_order=work_order, ticket=ticket)
        argv = self.command_argv(workspace=workspace)
        result = self.executor.run(
            argv=argv,
            cwd=workspace,
            env=parent_env,
            stdin=prompt.encode("utf-8"),
            timeout_seconds=ticket.limits.timeout_seconds,
            max_output_bytes=ticket.limits.max_output_bytes,
        )
        after = self._snapshot(workspace)
        changed_files = sorted(
            path for path in set(before) | set(after) if before.get(path) != after.get(path)
        )
        output_bytes = len(result.stdout) + len(result.stderr)
        observation = CodexRunnerObservation(
            exit_code=result.exit_code,
            changed_files=changed_files,
            output_bytes=output_bytes,
            subprocess_spawned=True,
            network_attempted=False,
            privileged_access_attempted=False,
            git_metadata_modified=any(
                path == ".git" or path.startswith(".git/") for path in changed_files
            ),
            external_repository_modified=False,
            guardian_access_attempted=any(
                path == "platform/guardian" or path.startswith("platform/guardian/")
                for path in changed_files
            ),
            production_secret_access_attempted=False,
        )
        receipt = codex_execution_validator.evaluate(ticket=ticket, observation=observation)
        if result.timed_out and receipt.disposition == "succeeded":
            raise RuntimeError("timed-out Codex run cannot be accepted")

        return CodexRunResult(
            receipt=receipt,
            workspace=workspace,
            command_sha256=self._command_hash(argv),
            source_commit=self.config.source_commit,
            guardian_admission_id=guardian_admission.admission_id,
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            stdout_tail=self._tail(result.stdout),
            stderr_tail=self._tail(result.stderr),
            timed_out=result.timed_out,
        )

    def command_argv(self, *, workspace: Path) -> tuple[str, ...]:
        return (
            str(self.config.codex_binary),
            "exec",
            "--sandbox",
            "workspace-write",
            "--ephemeral",
            "--ignore-user-config",
            "--strict-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--json",
            "-c",
            'approval_policy="on-request"',
            "-c",
            'approvals_reviewer="user"',
            "-c",
            "sandbox_workspace_write.network_access=false",
            "-c",
            "sandbox_workspace_write.exclude_slash_tmp=true",
            "-c",
            "sandbox_workspace_write.exclude_tmpdir_env_var=true",
            "-c",
            'shell_environment_policy.inherit="none"',
            "-c",
            "shell_environment_policy.ignore_default_excludes=false",
            "-c",
            'web_search="disabled"',
            "-c",
            "features.skill_mcp_dependency_install=false",
            "-c",
            "feedback.enabled=false",
            "--cd",
            str(workspace),
            "-",
        )

    def cleanup(self, workspace: Path) -> None:
        resolved_root = self.config.workspace_root.resolve()
        resolved_workspace = workspace.resolve()
        if resolved_root not in resolved_workspace.parents:
            raise ValueError("refusing to clean a path outside the Codex workspace root")
        shutil.rmtree(resolved_workspace, ignore_errors=False)

    def _preflight(self, env: Mapping[str, str]) -> None:
        if not self.config.codex_binary.is_file() or not os.access(
            self.config.codex_binary, os.X_OK
        ):
            raise RuntimeError("pinned Codex executable is unavailable")
        if not self.config.codex_home.is_dir():
            raise RuntimeError("Codex authentication home is unavailable")
        if self.config.require_bwrap and shutil.which("bwrap", path=env.get("PATH")) is None:
            raise RuntimeError("bubblewrap is required for the Phase 11 Linux Codex runner")

        version = self.executor.run(
            argv=(str(self.config.codex_binary), "--version"),
            cwd=self.config.source_repo.resolve(),
            env=env,
            stdin=None,
            timeout_seconds=15,
            max_output_bytes=4096,
        )
        observed = version.stdout.decode("utf-8", errors="replace").strip()
        if version.exit_code != 0 or observed != self.config.expected_version:
            raise RuntimeError(
                "Codex CLI version drift detected: "
                f"expected {self.config.expected_version!r}, observed {observed!r}"
            )

    def _parent_environment(self) -> dict[str, str]:
        env = {
            key: value
            for key in self._parent_env_keys
            if (value := os.environ.get(key)) is not None
        }
        env["CODEX_HOME"] = str(self.config.codex_home.resolve())
        env.setdefault("HOME", str(self.config.codex_home.resolve().parent))
        env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
        return env

    @staticmethod
    def _validate_binding(
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
    ) -> None:
        if ticket.work_order_id != work_order.work_order_id:
            raise ValueError("Codex ticket belongs to a different engineering work order")
        if ticket.work_order_sha256 != work_order.canonical_hash():
            raise ValueError("Codex ticket does not match the engineering work order hash")
        if ticket.allowed_paths != work_order.allowed_paths:
            raise ValueError("Codex ticket path scope differs from the work order")
        if ticket.sandbox_mode != "workspace-write" or ticket.approval_policy != "on-request":
            raise ValueError("Codex ticket does not use the Phase 11 sandbox policy")

    @staticmethod
    def _validate_guardian_admission(
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        admission: EngineeringGuardianAdmission,
    ) -> None:
        if admission.work_order_id != work_order.work_order_id:
            raise ValueError("Guardian admission belongs to another work order")
        if admission.work_order_sha256 != work_order.canonical_hash():
            raise ValueError("Guardian admission work-order hash mismatch")
        if admission.ticket_id != ticket.ticket_id:
            raise ValueError("Guardian admission belongs to another Codex ticket")
        if admission.ticket_sha256 != ticket.canonical_hash():
            raise ValueError("Guardian admission ticket hash mismatch")
        if admission.risk_class != "non_privileged_workspace":
            raise ValueError("Guardian admission risk class is not non-privileged")
        if not admission.codex_execution_admitted or not admission.execution_may_proceed:
            raise ValueError("Guardian admission does not permit Codex execution")
        if (
            admission.guardian_service_contact_required
            or admission.guardian_service_contacted
            or admission.guardian_broker_contact_allowed
            or admission.root_authorization_required
            or admission.root_authorization_granted
        ):
            raise ValueError("Codex execution cannot carry Guardian/root authority")

    @staticmethod
    def _snapshot(workspace: Path) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for path in sorted(workspace.rglob("*")):
            relative = path.relative_to(workspace).as_posix()
            if path.is_symlink():
                snapshot[relative] = "SYMLINK"
                continue
            if not path.is_file():
                continue
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            snapshot[relative] = digest.hexdigest()
        return snapshot

    @staticmethod
    def _prompt(
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
    ) -> str:
        criteria = "\n".join(f"- {item}" for item in work_order.acceptance_criteria)
        paths = "\n".join(f"- {item}" for item in ticket.allowed_paths)
        constraints = "\n".join(f"- {item}" for item in work_order.constraints)
        return (
            "You are a subordinate DAP Engineering Agent operating inside a disposable "
            "snapshot. DAP retains all task, approval, Git, Guardian, merge, and deployment "
            "authority.\n\n"
            f"Objective:\n{work_order.objective}\n\n"
            f"Acceptance criteria:\n{criteria}\n\n"
            f"Allowed files (the complete mutation allowlist):\n{paths}\n\n"
            f"Additional constraints:\n{constraints or '- none'}\n\n"
            "Hard execution rules:\n"
            "- Modify only the allowlisted files.\n"
            "- Do not use network access, web search, MCP, plugins, or package installation.\n"
            "- Do not invoke git, sudo, su, docker, systemctl, service managers, or Guardian.\n"
            "- Do not inspect paths outside this workspace or seek credentials/secrets.\n"
            "- Do not create commits, branches, pull requests, releases, merges, or deployments.\n"
            "- Run only local tests/checks needed for this bounded change.\n"
            "- If the task cannot be completed inside these rules, stop and explain why.\n"
        )

    @staticmethod
    def _command_hash(argv: tuple[str, ...]) -> str:
        return hashlib.sha256("\0".join(argv).encode()).hexdigest()

    @staticmethod
    def _tail(payload: bytes, limit: int = 16_384) -> str:
        return payload[-limit:].decode("utf-8", errors="replace")


bounded_codex_runner_type = BoundedCodexRunner
