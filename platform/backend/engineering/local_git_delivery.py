from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engineering.codex_runner import CodexRunResult
from engineering.git_delivery_contract import (
    GitDeliveryObservation,
    GitDeliveryPlan,
    GitDeliveryReceipt,
    git_delivery_service,
)


class LocalGitDeliveryConfig(BaseModel):
    """Host paths used by the DAP-owned, network-free Git commit builder."""

    model_config = ConfigDict(frozen=True)

    source_repo: Path
    delivery_root: Path
    author_name: str = Field(default="DAP Engineering Agent", min_length=2, max_length=120)
    author_email: str = Field(default="engineering-agent@dap.local", min_length=3, max_length=200)

    @model_validator(mode="after")
    def validate_paths(self) -> LocalGitDeliveryConfig:
        source = self.source_repo.resolve()
        root = self.delivery_root.resolve()
        if root == source or source in root.parents:
            raise ValueError("Git delivery root must be outside the source repository")
        return self


class LocalGitDeliveryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    receipt: GitDeliveryReceipt
    delivery_repo: Path
    delivery_branch: str
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    remote_count: int = Field(ge=0)


class LocalGitDeliveryBuilder:
    """Create one local review commit without remote Git or GitHub authority."""

    _safe_path = "/usr/local/bin:/usr/bin:/bin"

    def __init__(self, *, config: LocalGitDeliveryConfig) -> None:
        self.config = config

    def build(
        self,
        *,
        plan: GitDeliveryPlan,
        run_result: CodexRunResult,
    ) -> LocalGitDeliveryResult:
        self._validate_plan_and_result(plan=plan, run_result=run_result)
        source_repo = self.config.source_repo.resolve()
        delivery_root = self.config.delivery_root.resolve()
        workspace = run_result.workspace.resolve()
        if not workspace.is_dir():
            raise ValueError("Codex delivery workspace is unavailable")
        if not source_repo.is_dir():
            raise ValueError("DAP source repository is unavailable")

        delivery_root.mkdir(parents=True, exist_ok=True)
        delivery_repo = delivery_root / plan.delivery_id
        if delivery_repo.exists():
            raise ValueError("local Git delivery repository already exists")

        env = self._environment()
        self._git(
            source_repo.parent,
            env,
            "clone",
            "--no-hardlinks",
            "--no-checkout",
            str(source_repo),
            str(delivery_repo),
        )
        try:
            self._git(delivery_repo, env, "remote", "remove", "origin")
            self._git(delivery_repo, env, "checkout", "--detach", plan.source_commit)
            self._git(delivery_repo, env, "switch", "-c", plan.delivery_branch)
            self._apply_changed_files(
                workspace=workspace,
                delivery_repo=delivery_repo,
                changed_files=plan.changed_files,
            )
            observed_paths = self._status_paths(delivery_repo=delivery_repo, env=env)
            if tuple(sorted(observed_paths)) != tuple(sorted(plan.changed_files)):
                raise RuntimeError("local Git workspace changes differ from DAP delivery plan")

            self._git(delivery_repo, env, "add", "--", *plan.changed_files)
            staged_paths = self._staged_paths(delivery_repo=delivery_repo, env=env)
            if tuple(sorted(staged_paths)) != tuple(sorted(plan.changed_files)):
                raise RuntimeError("staged Git files differ from DAP delivery plan")

            self._git(
                delivery_repo,
                env,
                "-c",
                f"user.name={self.config.author_name}",
                "-c",
                f"user.email={self.config.author_email}",
                "commit",
                "--no-gpg-sign",
                "-m",
                plan.commit_message,
            )
            commit_sha = self._git(delivery_repo, env, "rev-parse", "HEAD")
            parent_sha = self._git(delivery_repo, env, "rev-parse", "HEAD^")
            branch = self._git(delivery_repo, env, "branch", "--show-current")
            committed_files = tuple(
                sorted(
                    path
                    for path in self._git(
                        delivery_repo,
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
            remotes = tuple(
                remote
                for remote in self._git(delivery_repo, env, "remote").splitlines()
                if remote
            )

            if parent_sha != plan.source_commit:
                raise RuntimeError("local Git delivery commit parent changed")
            if branch != plan.delivery_branch:
                raise RuntimeError("local Git delivery branch changed")
            if committed_files != tuple(sorted(plan.changed_files)):
                raise RuntimeError("local Git delivery commit contents differ from plan")
            if remotes:
                raise RuntimeError("local Git delivery repository unexpectedly retains a remote")

            observation = GitDeliveryObservation(
                plan_id=plan.delivery_id,
                plan_sha256=plan.canonical_hash(),
                commit_created=True,
                commit_sha=commit_sha,
                committed_files=committed_files,
                local_branch_created=True,
            )
            receipt = git_delivery_service.validate_observation(
                plan=plan,
                observation=observation,
            )
            if receipt.disposition != "succeeded":
                raise RuntimeError("local Git delivery failed DAP post-delivery validation")

            return LocalGitDeliveryResult(
                receipt=receipt,
                delivery_repo=delivery_repo,
                delivery_branch=branch,
                commit_sha=commit_sha,
                source_commit=plan.source_commit,
                remote_count=len(remotes),
            )
        except Exception:
            shutil.rmtree(delivery_repo, ignore_errors=True)
            raise

    def cleanup(self, delivery_repo: Path) -> None:
        root = self.config.delivery_root.resolve()
        target = delivery_repo.resolve()
        if root not in target.parents:
            raise ValueError("refusing to clean a path outside the Git delivery root")
        shutil.rmtree(target, ignore_errors=False)

    @staticmethod
    def _validate_plan_and_result(
        *,
        plan: GitDeliveryPlan,
        run_result: CodexRunResult,
    ) -> None:
        if not plan.commit_allowed:
            raise ValueError("Git delivery plan does not permit a local commit")
        prohibited_authority = {
            "remote push": plan.delivery_branch_push_allowed,
            "draft PR": plan.draft_pull_request_allowed,
            "Codex Git": plan.codex_git_authority,
            "Ruflo Git": plan.ruflo_git_authority,
            "force push": plan.force_push_allowed,
            "main merge": plan.main_merge_allowed,
            "tag": plan.tag_allowed,
            "release": plan.release_allowed,
            "deployment": plan.deployment_allowed,
        }
        enabled = [name for name, value in prohibited_authority.items() if value]
        if enabled:
            raise ValueError(
                "11E.2 local Git builder received prohibited authority: "
                + ", ".join(enabled)
            )
        if plan.source_commit != run_result.source_commit:
            raise ValueError("Git delivery plan source commit does not match Codex result")
        if plan.changed_files != run_result.receipt.changed_files:
            raise ValueError("Git delivery plan changed-file list does not match Codex result")
        if plan.execution_receipt_sha256 != _canonical_hash(run_result.receipt):
            raise ValueError("Git delivery plan execution receipt hash mismatch")
        if run_result.receipt.disposition != "succeeded" or not run_result.receipt.delivery_allowed:
            raise ValueError("Codex result is not delivery eligible")

    @staticmethod
    def _apply_changed_files(
        *,
        workspace: Path,
        delivery_repo: Path,
        changed_files: tuple[str, ...],
    ) -> None:
        for relative in changed_files:
            parts = PurePosixPath(relative).parts
            if not parts or any(part in {"", ".", ".."} for part in parts):
                raise ValueError("Git delivery received unsafe changed-file path")
            source = workspace.joinpath(*parts)
            target = delivery_repo.joinpath(*parts)
            if workspace not in source.resolve(strict=False).parents:
                raise ValueError("Git delivery source path escaped Codex workspace")
            if delivery_repo not in target.resolve(strict=False).parents:
                raise ValueError("Git delivery target path escaped local repository")
            if source.is_symlink():
                raise ValueError("Git delivery refuses changed symlinks")
            if source.is_dir():
                raise ValueError("Git delivery expects file-level changed paths")
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            else:
                if target.is_dir():
                    raise ValueError("Git delivery refuses directory deletion through file scope")
                target.unlink(missing_ok=True)

    def _status_paths(self, *, delivery_repo: Path, env: Mapping[str, str]) -> tuple[str, ...]:
        output = self._git(
            delivery_repo,
            env,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        paths: list[str] = []
        for line in output.splitlines():
            if not line:
                continue
            path = line[3:]
            if " -> " in path:
                raise RuntimeError("local Git delivery refuses rename observations")
            paths.append(path)
        return tuple(sorted(paths))

    def _staged_paths(self, *, delivery_repo: Path, env: Mapping[str, str]) -> tuple[str, ...]:
        output = self._git(
            delivery_repo,
            env,
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
        )
        return tuple(sorted(path for path in output.splitlines() if path))

    def _environment(self) -> dict[str, str]:
        env = {
            "PATH": self._safe_path,
            "HOME": str(self.config.delivery_root.resolve()),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false",
        }
        for key in ("LANG", "LC_ALL"):
            if (value := os.environ.get(key)) is not None:
                env[key] = value
        return env

    @staticmethod
    def _git(cwd: Path, env: Mapping[str, str], *args: str) -> str:
        result = subprocess.run(
            ("git", *args),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=60,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed: {result.stderr.strip()}"
            )
        return result.stdout.strip()


def _canonical_hash(model: BaseModel) -> str:
    encoded = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
