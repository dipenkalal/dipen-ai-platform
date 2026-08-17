from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from engineering.local_git_delivery import LocalGitDeliveryResult

EXPECTED_GIT_BINARY = Path("/usr/bin/git")
_SAFE_PATH = "/usr/bin:/bin"


class EngineeringDiffEvidence(BaseModel):
    """Immutable facts for the exact local delivery commit diff."""

    model_config = ConfigDict(frozen=True)

    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    changed_files: tuple[str, ...]
    diff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EngineeringDiffEvidenceCapture:
    """Capture one exact commit diff without network or repository mutation."""

    def __init__(self, *, git_binary: Path = EXPECTED_GIT_BINARY) -> None:
        if git_binary.resolve() != EXPECTED_GIT_BINARY:
            raise ValueError("Phase 11F diff evidence requires /usr/bin/git")
        self.git_binary = git_binary

    def capture(self, result: LocalGitDeliveryResult) -> EngineeringDiffEvidence:
        if result.receipt.disposition != "succeeded":
            raise ValueError("diff evidence requires a successful local Git delivery")
        if result.remote_count != 0:
            raise ValueError("diff evidence requires the network-free local delivery repository")
        repo = result.delivery_repo.resolve()
        if not repo.is_dir():
            raise ValueError("local Git delivery repository is unavailable")

        env = {"PATH": _SAFE_PATH, "GIT_CONFIG_NOSYSTEM": "1"}
        commit_sha = self._git_text(repo, env, "rev-parse", "HEAD")
        parent_sha = self._git_text(repo, env, "rev-parse", "HEAD^")
        changed_files = tuple(
            sorted(
                path
                for path in self._git_text(
                    repo,
                    env,
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    "HEAD",
                ).splitlines()
                if path
            )
        )
        diff_bytes = self._git_bytes(
            repo,
            env,
            "diff",
            "--binary",
            "--no-ext-diff",
            "--no-color",
            "HEAD^",
            "HEAD",
        )

        if commit_sha != result.commit_sha:
            raise RuntimeError("diff evidence commit differs from local delivery result")
        if parent_sha != result.source_commit:
            raise RuntimeError("diff evidence parent differs from local delivery source commit")
        if changed_files != tuple(sorted(result.receipt.committed_files)):
            raise RuntimeError("diff evidence file set differs from local delivery receipt")

        return EngineeringDiffEvidence(
            commit_sha=commit_sha,
            parent_sha=parent_sha,
            changed_files=changed_files,
            diff_sha256=hashlib.sha256(diff_bytes).hexdigest(),
        )

    def _git_text(
        self,
        cwd: Path,
        env: Mapping[str, str],
        *args: str,
    ) -> str:
        return self._git_bytes(cwd, env, *args).decode(
            "utf-8", errors="strict"
        ).strip()

    def _git_bytes(
        self,
        cwd: Path,
        env: Mapping[str, str],
        *args: str,
    ) -> bytes:
        completed = subprocess.run(
            (str(self.git_binary), *args),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            shell=False,
            timeout=30,
        )
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"fixed Git evidence command failed: {detail}")
        return completed.stdout


engineering_diff_evidence_capture = EngineeringDiffEvidenceCapture()
