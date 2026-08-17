from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engineering.git_delivery_contract import DAP_REPOSITORY_FULL_NAME
from engineering.local_git_delivery import LocalGitDeliveryResult
from engineering.remote_git_publication import (
    RemoteGitPublicationObservation,
    RemoteGitPublicationPlan,
    RemoteGitPublicationReceipt,
    remote_git_publication_service,
)

DAP_GITHUB_SSH_URL = "git@github.com:dipenkalal/dipen-ai-platform.git"
EXPECTED_GH_VERSION = "gh version 2.97.0"
EXPECTED_GIT_BINARY = Path("/usr/bin/git")
EXPECTED_GH_BINARY = Path("/usr/bin/gh")
_SAFE_PATH = "/usr/bin:/bin"


class CommandResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout_seconds: int,
    ) -> CommandResult: ...


class SubprocessCommandRunner:
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout_seconds: int,
    ) -> CommandResult:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            shell=False,
            timeout=timeout_seconds,
            text=True,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class RemoteGitPublisherConfig(BaseModel):
    """Host-only transport configuration for DAP remote publication."""

    model_config = ConfigDict(frozen=True)

    home_dir: Path
    gh_config_dir: Path
    git_binary: Path = EXPECTED_GIT_BINARY
    gh_binary: Path = EXPECTED_GH_BINARY
    timeout_seconds: int = Field(default=60, ge=10, le=180)

    @model_validator(mode="after")
    def validate_fixed_transport(self) -> RemoteGitPublisherConfig:
        home = self.home_dir.resolve()
        gh_config = self.gh_config_dir.resolve()
        if self.git_binary.resolve() != EXPECTED_GIT_BINARY:
            raise ValueError("Phase 11 remote publisher requires /usr/bin/git")
        if self.gh_binary.resolve() != EXPECTED_GH_BINARY:
            raise ValueError("Phase 11 remote publisher requires /usr/bin/gh")
        if gh_config != (home / ".config" / "gh").resolve():
            raise ValueError("GitHub CLI config must be the host user's ~/.config/gh")
        return self


class GitHubPullRequestSnapshot(BaseModel):
    """Typed subset of gh PR JSON used by the DAP publisher."""

    model_config = ConfigDict(frozen=True)

    number: int = Field(ge=1)
    is_draft: bool = Field(alias="isDraft")
    base_ref_name: str = Field(alias="baseRefName", min_length=1)
    head_ref_name: str = Field(alias="headRefName", min_length=1)
    url: str = Field(min_length=8)


class RemoteGitPublisherResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    receipt: RemoteGitPublicationReceipt
    publication_id: str
    publication_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    delivery_branch: str
    remote_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    pull_request_number: int = Field(ge=1)
    pull_request_url: str
    branch_reused: bool
    draft_pull_request_reused: bool
    gh_version: str
    github_credentials_exposed_to_codex: bool = False
    github_credentials_exposed_to_ruflo: bool = False
    force_push_performed: bool = False
    main_merge_performed: bool = False
    deployment_performed: bool = False


class RemoteGitPublisher:
    """Publish one immutable DAP engineering commit and one draft PR."""

    def __init__(
        self,
        *,
        config: RemoteGitPublisherConfig,
        runner: CommandRunner | None = None,
    ) -> None:
        self.config = config
        self.runner = runner or SubprocessCommandRunner()

    def publish(
        self,
        *,
        plan: RemoteGitPublicationPlan,
        local_result: LocalGitDeliveryResult,
    ) -> RemoteGitPublisherResult:
        self._validate_plan(plan=plan, local_result=local_result)
        repo = local_result.delivery_repo.resolve()
        if not repo.is_dir():
            raise ValueError("local delivery repository is unavailable")

        env = self._environment()
        self._validate_local_repository(
            plan=plan,
            local_result=local_result,
            env=env,
        )
        gh_version = self._gh_version(repo=repo, env=env)
        self._require_gh_auth(repo=repo, env=env)

        before_sha = self._remote_branch_sha(
            repo=repo,
            env=env,
            branch=plan.delivery_branch,
        )
        branch_pushed = False
        branch_reused = False
        if before_sha is None:
            self._run_git(
                repo,
                env,
                "push",
                "--porcelain",
                DAP_GITHUB_SSH_URL,
                f"{plan.local_commit_sha}:refs/heads/{plan.delivery_branch}",
            )
            branch_pushed = True
        elif before_sha == plan.local_commit_sha:
            branch_reused = True
        else:
            raise RuntimeError(
                "deterministic engineering branch already exists at another commit"
            )

        remote_sha = self._remote_branch_sha(
            repo=repo,
            env=env,
            branch=plan.delivery_branch,
        )
        if remote_sha != plan.local_commit_sha:
            raise RuntimeError("remote engineering branch verification failed")

        existing_prs = self._open_head_pull_requests(
            repo=repo,
            env=env,
            plan=plan,
        )
        pr_created = False
        pr_reused = False
        if len(existing_prs) > 1:
            raise RuntimeError("multiple open pull requests exist for engineering branch")
        if existing_prs:
            pr = self._validate_exact_draft_pr(plan=plan, snapshot=existing_prs[0])
            pr_reused = True
        else:
            self._run_gh(
                repo,
                env,
                "pr",
                "create",
                "--repo",
                plan.repository_full_name,
                "--base",
                plan.base_branch,
                "--head",
                plan.delivery_branch,
                "--title",
                plan.pull_request_title,
                "--body",
                plan.pull_request_body,
                "--draft",
            )
            pr_created = True
            created_prs = self._open_head_pull_requests(
                repo=repo,
                env=env,
                plan=plan,
            )
            if len(created_prs) != 1:
                raise RuntimeError("draft pull request creation verification failed")
            pr = self._validate_exact_draft_pr(plan=plan, snapshot=created_prs[0])

        observation = RemoteGitPublicationObservation(
            publication_id=plan.publication_id,
            publication_plan_sha256=plan.canonical_hash(),
            remote_branch_pushed=branch_pushed,
            remote_branch_reused=branch_reused,
            remote_commit_sha=remote_sha,
            draft_pull_request_created=pr_created,
            draft_pull_request_reused=pr_reused,
            pull_request_number=pr.number,
            pull_request_is_draft=pr.is_draft,
            pull_request_base=pr.base_ref_name,
            pull_request_head=pr.head_ref_name,
        )
        receipt = remote_git_publication_service.validate_observation(
            plan=plan,
            observation=observation,
        )
        if receipt.disposition != "succeeded":
            raise RuntimeError("remote publication failed DAP post-publication validation")

        return RemoteGitPublisherResult(
            receipt=receipt,
            publication_id=plan.publication_id,
            publication_plan_sha256=plan.canonical_hash(),
            delivery_branch=plan.delivery_branch,
            remote_commit_sha=remote_sha,
            pull_request_number=pr.number,
            pull_request_url=pr.url,
            branch_reused=branch_reused,
            draft_pull_request_reused=pr_reused,
            gh_version=gh_version,
        )

    @staticmethod
    def _validate_plan(
        *,
        plan: RemoteGitPublicationPlan,
        local_result: LocalGitDeliveryResult,
    ) -> None:
        if plan.repository_full_name != DAP_REPOSITORY_FULL_NAME:
            raise ValueError("remote publisher repository changed")
        if not plan.dap_remote_branch_push_allowed:
            raise ValueError("remote publication plan does not authorize branch publication")
        if not plan.dap_draft_pull_request_allowed:
            raise ValueError("remote publication plan does not authorize a draft PR")
        if not plan.network_access_required or not plan.dap_managed_github_credentials_required:
            raise ValueError("remote publication plan lacks DAP transport requirements")
        prohibited = {
            "credentials-to-codex": plan.github_credentials_exposed_to_codex,
            "credentials-to-ruflo": plan.github_credentials_exposed_to_ruflo,
            "codex-git": plan.codex_git_authority,
            "ruflo-git": plan.ruflo_git_authority,
            "force-push": plan.force_push_allowed,
            "protected-branch-update": plan.protected_branch_update_allowed,
            "auto-merge": plan.pull_request_auto_merge_allowed,
            "main-merge": plan.main_merge_allowed,
            "tag": plan.tag_allowed,
            "release": plan.release_allowed,
            "deployment": plan.deployment_allowed,
        }
        enabled = [name for name, value in prohibited.items() if value]
        if enabled:
            raise ValueError(
                "remote publisher received prohibited authority: " + ", ".join(enabled)
            )
        if local_result.receipt.disposition != "succeeded":
            raise ValueError("remote publisher requires a successful local delivery")
        if local_result.commit_sha != plan.local_commit_sha:
            raise ValueError("remote publisher local commit changed")
        if local_result.delivery_branch != plan.delivery_branch:
            raise ValueError("remote publisher local branch changed")
        if local_result.remote_count != 0:
            raise ValueError("remote publisher requires a local repository with no remotes")

    def _validate_local_repository(
        self,
        *,
        plan: RemoteGitPublicationPlan,
        local_result: LocalGitDeliveryResult,
        env: Mapping[str, str],
    ) -> None:
        repo = local_result.delivery_repo.resolve()
        remotes = self._run_git(repo, env, "remote")
        if remotes:
            raise RuntimeError("local delivery repository unexpectedly has a remote")
        branch = self._run_git(repo, env, "branch", "--show-current")
        if branch != plan.delivery_branch:
            raise RuntimeError("local delivery branch changed before publication")
        head = self._run_git(repo, env, "rev-parse", "HEAD")
        if head != plan.local_commit_sha:
            raise RuntimeError("local delivery HEAD changed before publication")

    def _gh_version(self, *, repo: Path, env: Mapping[str, str]) -> str:
        result = self._run(
            (str(self.config.gh_binary), "--version"),
            cwd=repo,
            env=env,
        )
        lines = result.stdout.splitlines()
        first_line = lines[0] if lines else ""
        if first_line != EXPECTED_GH_VERSION:
            raise RuntimeError(
                f"GitHub CLI version drift: expected {EXPECTED_GH_VERSION!r}, observed {first_line!r}"
            )
        return first_line

    def _require_gh_auth(self, *, repo: Path, env: Mapping[str, str]) -> None:
        self._run_gh(
            repo,
            env,
            "auth",
            "status",
            "--active",
            "--hostname",
            "github.com",
        )

    def _remote_branch_sha(
        self,
        *,
        repo: Path,
        env: Mapping[str, str],
        branch: str,
    ) -> str | None:
        output = self._run_git(
            repo,
            env,
            "ls-remote",
            "--heads",
            DAP_GITHUB_SSH_URL,
            f"refs/heads/{branch}",
        )
        if not output:
            return None
        lines = [line for line in output.splitlines() if line.strip()]
        if len(lines) != 1:
            raise RuntimeError("remote engineering branch lookup was ambiguous")
        parts = lines[0].split()
        if len(parts) != 2 or parts[1] != f"refs/heads/{branch}":
            raise RuntimeError("remote engineering branch lookup returned an unexpected ref")
        sha = parts[0]
        if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
            raise RuntimeError("remote engineering branch returned an invalid commit SHA")
        return sha

    def _open_head_pull_requests(
        self,
        *,
        repo: Path,
        env: Mapping[str, str],
        plan: RemoteGitPublicationPlan,
    ) -> list[GitHubPullRequestSnapshot]:
        output = self._run_gh(
            repo,
            env,
            "pr",
            "list",
            "--repo",
            plan.repository_full_name,
            "--head",
            plan.delivery_branch,
            "--state",
            "open",
            "--limit",
            "10",
            "--json",
            "number,isDraft,baseRefName,headRefName,url",
        )
        try:
            payload = json.loads(output or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError("GitHub CLI returned invalid pull request JSON") from exc
        if not isinstance(payload, list):
            raise RuntimeError("GitHub CLI returned an unexpected pull request payload")
        try:
            return [GitHubPullRequestSnapshot.model_validate(item) for item in payload]
        except Exception as exc:
            raise RuntimeError("GitHub CLI pull request payload failed validation") from exc

    @staticmethod
    def _validate_exact_draft_pr(
        *,
        plan: RemoteGitPublicationPlan,
        snapshot: GitHubPullRequestSnapshot,
    ) -> GitHubPullRequestSnapshot:
        if not snapshot.is_draft:
            raise RuntimeError("existing engineering pull request is not draft")
        if (
            snapshot.base_ref_name != plan.base_branch
            or snapshot.head_ref_name != plan.delivery_branch
        ):
            raise RuntimeError("existing engineering pull request head/base changed")
        if not snapshot.url.startswith("https://github.com/"):
            raise RuntimeError("GitHub pull request URL is invalid")
        return snapshot

    def _environment(self) -> dict[str, str]:
        home = self.config.home_dir.resolve()
        env = {
            "PATH": _SAFE_PATH,
            "HOME": str(home),
            "GH_CONFIG_DIR": str(self.config.gh_config_dir.resolve()),
            "GH_PROMPT_DISABLED": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false",
            "GIT_SSH_COMMAND": (
                "/usr/bin/ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "
                "-o ConnectTimeout=10"
            ),
        }
        for key in ("LANG", "LC_ALL"):
            if (value := os.environ.get(key)) is not None:
                env[key] = value
        if (ssh_auth_sock := os.environ.get("SSH_AUTH_SOCK")) is not None:
            env["SSH_AUTH_SOCK"] = ssh_auth_sock
        return env

    def _run_git(
        self,
        repo: Path,
        env: Mapping[str, str],
        *args: str,
    ) -> str:
        result = self._run(
            (str(self.config.git_binary), *args),
            cwd=repo,
            env=env,
        )
        return result.stdout.strip()

    def _run_gh(
        self,
        repo: Path,
        env: Mapping[str, str],
        *args: str,
    ) -> str:
        result = self._run(
            (str(self.config.gh_binary), *args),
            cwd=repo,
            env=env,
        )
        return result.stdout.strip()

    def _run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> CommandResult:
        result = self.runner.run(
            argv,
            cwd=cwd,
            env=env,
            timeout_seconds=self.config.timeout_seconds,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"DAP remote publication command failed: {stderr}")
        return result
