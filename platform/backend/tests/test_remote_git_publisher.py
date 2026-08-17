from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from engineering.git_delivery_contract import GitDeliveryPlan, GitDeliveryReceipt
from engineering.local_git_delivery import LocalGitDeliveryResult
from engineering.remote_git_publication import remote_git_publication_service
from engineering.remote_git_publisher import (
    DAP_GITHUB_SSH_URL,
    EXPECTED_GH_VERSION,
    CommandResult,
    RemoteGitPublisher,
    RemoteGitPublisherConfig,
)

SOURCE_COMMIT = "1" * 40
LOCAL_COMMIT = "2" * 40
DELIVERY_BRANCH = "engineering/phase11-publisher-test-0123456789ab"
BASE_BRANCH = "phase11/autonomous-engineering-agent"


def delivery_plan() -> GitDeliveryPlan:
    return GitDeliveryPlan(
        delivery_id="git-delivery-publisher-test",
        base_branch=BASE_BRANCH,
        delivery_branch=DELIVERY_BRANCH,
        source_commit=SOURCE_COMMIT,
        work_order_id="engineering-work-publisher-test",
        work_order_sha256="a" * 64,
        ticket_id="codex-ticket-publisher-test",
        ticket_sha256="b" * 64,
        guardian_admission_id="guardian-admission-publisher-test",
        guardian_admission_sha256="c" * 64,
        execution_receipt_sha256="d" * 64,
        changed_files=("platform/backend/engineering/example.py",),
        commit_message="engineering: deliver publisher test",
    )


def local_result(tmp_path: Path, plan: GitDeliveryPlan) -> LocalGitDeliveryResult:
    repo = tmp_path / "delivery"
    repo.mkdir()
    receipt = GitDeliveryReceipt(
        delivery_id=plan.delivery_id,
        delivery_plan_sha256=plan.canonical_hash(),
        disposition="succeeded",
        commit_created=True,
        commit_sha=LOCAL_COMMIT,
        committed_files=plan.changed_files,
        findings=(),
    )
    return LocalGitDeliveryResult(
        receipt=receipt,
        delivery_repo=repo,
        delivery_branch=plan.delivery_branch,
        commit_sha=LOCAL_COMMIT,
        source_commit=plan.source_commit,
        remote_count=0,
    )


class FakeRunner:
    def __init__(
        self,
        *,
        remote_sha: str | None = None,
        pr_exists: bool = False,
        pr_is_draft: bool = True,
        gh_version: str = EXPECTED_GH_VERSION,
    ) -> None:
        self.remote_sha = remote_sha
        self.pr_exists = pr_exists
        self.pr_is_draft = pr_is_draft
        self.gh_version = gh_version
        self.commands: list[tuple[str, ...]] = []
        self.environments: list[dict[str, str]] = []

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout_seconds: int,
    ) -> CommandResult:
        del cwd, timeout_seconds
        self.commands.append(argv)
        self.environments.append(dict(env))

        if argv == ("/usr/bin/git", "remote"):
            return CommandResult(returncode=0, stdout="")
        if argv == ("/usr/bin/git", "branch", "--show-current"):
            return CommandResult(returncode=0, stdout=DELIVERY_BRANCH + "\n")
        if argv == ("/usr/bin/git", "rev-parse", "HEAD"):
            return CommandResult(returncode=0, stdout=LOCAL_COMMIT + "\n")
        if argv == ("/usr/bin/gh", "--version"):
            return CommandResult(returncode=0, stdout=self.gh_version + "\n")
        if argv == (
            "/usr/bin/gh",
            "auth",
            "status",
            "--active",
            "--hostname",
            "github.com",
        ):
            return CommandResult(returncode=0)
        if argv[:3] == ("/usr/bin/git", "ls-remote", "--heads"):
            if self.remote_sha is None:
                return CommandResult(returncode=0, stdout="")
            return CommandResult(
                returncode=0,
                stdout=f"{self.remote_sha}\trefs/heads/{DELIVERY_BRANCH}\n",
            )
        if argv[:3] == ("/usr/bin/git", "push", "--porcelain"):
            self.remote_sha = LOCAL_COMMIT
            return CommandResult(returncode=0, stdout="ok\n")
        if argv[:3] == ("/usr/bin/gh", "pr", "list"):
            if not self.pr_exists:
                return CommandResult(returncode=0, stdout="[]\n")
            payload = [
                {
                    "number": 123,
                    "isDraft": self.pr_is_draft,
                    "baseRefName": BASE_BRANCH,
                    "headRefName": DELIVERY_BRANCH,
                    "url": "https://github.com/dipenkalal/dipen-ai-platform/pull/123",
                }
            ]
            return CommandResult(returncode=0, stdout=json.dumps(payload))
        if argv[:3] == ("/usr/bin/gh", "pr", "create"):
            self.pr_exists = True
            return CommandResult(
                returncode=0,
                stdout="https://github.com/dipenkalal/dipen-ai-platform/pull/123\n",
            )
        return CommandResult(returncode=1, stderr=f"unexpected command: {argv!r}")


def publisher(tmp_path: Path, runner: FakeRunner) -> RemoteGitPublisher:
    home = tmp_path / "home"
    (home / ".config" / "gh").mkdir(parents=True)
    return RemoteGitPublisher(
        config=RemoteGitPublisherConfig(
            home_dir=home,
            gh_config_dir=home / ".config" / "gh",
        ),
        runner=runner,
    )


def publication_fixture(tmp_path: Path):
    plan = delivery_plan()
    result = local_result(tmp_path, plan)
    publication = remote_git_publication_service.prepare(
        delivery_plan=plan,
        local_result=result,
    )
    return plan, result, publication


def test_publisher_creates_only_exact_branch_and_draft_pr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GH_TOKEN", "must-not-be-inherited")
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-be-inherited")
    _, local, publication = publication_fixture(tmp_path)
    fake = FakeRunner()

    result = publisher(tmp_path, fake).publish(
        plan=publication,
        local_result=local,
    )

    assert result.receipt.disposition == "succeeded"
    assert result.remote_commit_sha == LOCAL_COMMIT
    assert result.pull_request_number == 123
    assert result.branch_reused is False
    assert result.draft_pull_request_reused is False
    assert result.github_credentials_exposed_to_codex is False
    assert result.github_credentials_exposed_to_ruflo is False
    assert result.force_push_performed is False
    assert result.main_merge_performed is False
    assert result.deployment_performed is False

    push_commands = [argv for argv in fake.commands if argv[:2] == ("/usr/bin/git", "push")]
    assert push_commands == [
        (
            "/usr/bin/git",
            "push",
            "--porcelain",
            DAP_GITHUB_SSH_URL,
            f"{LOCAL_COMMIT}:refs/heads/{DELIVERY_BRANCH}",
        )
    ]
    pr_create = [argv for argv in fake.commands if argv[:3] == ("/usr/bin/gh", "pr", "create")]
    assert len(pr_create) == 1
    assert "--draft" in pr_create[0]
    assert "--force" not in {token for argv in fake.commands for token in argv}
    assert "merge" not in {token for argv in fake.commands for token in argv}
    assert all("GH_TOKEN" not in env and "GITHUB_TOKEN" not in env for env in fake.environments)


def test_publisher_reuses_exact_branch_and_exact_draft_pr(tmp_path: Path) -> None:
    _, local, publication = publication_fixture(tmp_path)
    fake = FakeRunner(remote_sha=LOCAL_COMMIT, pr_exists=True)

    result = publisher(tmp_path, fake).publish(
        plan=publication,
        local_result=local,
    )

    assert result.receipt.disposition == "succeeded"
    assert result.branch_reused is True
    assert result.draft_pull_request_reused is True
    assert not any(argv[:2] == ("/usr/bin/git", "push") for argv in fake.commands)
    assert not any(argv[:3] == ("/usr/bin/gh", "pr", "create") for argv in fake.commands)


def test_publisher_refuses_existing_branch_at_other_commit(tmp_path: Path) -> None:
    _, local, publication = publication_fixture(tmp_path)
    fake = FakeRunner(remote_sha="3" * 40)

    with pytest.raises(RuntimeError, match="already exists at another commit"):
        publisher(tmp_path, fake).publish(plan=publication, local_result=local)

    assert not any(argv[:2] == ("/usr/bin/git", "push") for argv in fake.commands)
    assert not any(argv[:3] == ("/usr/bin/gh", "pr", "create") for argv in fake.commands)


def test_publisher_refuses_existing_ready_for_review_pr(tmp_path: Path) -> None:
    _, local, publication = publication_fixture(tmp_path)
    fake = FakeRunner(remote_sha=LOCAL_COMMIT, pr_exists=True, pr_is_draft=False)

    with pytest.raises(RuntimeError, match="is not draft"):
        publisher(tmp_path, fake).publish(plan=publication, local_result=local)

    assert not any(argv[:3] == ("/usr/bin/gh", "pr", "create") for argv in fake.commands)


def test_publisher_refuses_gh_version_drift(tmp_path: Path) -> None:
    _, local, publication = publication_fixture(tmp_path)
    fake = FakeRunner(gh_version="gh version 9.9.9")

    with pytest.raises(RuntimeError, match="GitHub CLI version drift"):
        publisher(tmp_path, fake).publish(plan=publication, local_result=local)

    assert not any(argv[:2] == ("/usr/bin/git", "push") for argv in fake.commands)


def test_config_rejects_nonfixed_git_or_gh_binary(tmp_path: Path) -> None:
    home = tmp_path / "home"
    gh_config = home / ".config" / "gh"
    gh_config.mkdir(parents=True)

    with pytest.raises(ValidationError, match="/usr/bin/git"):
        RemoteGitPublisherConfig(
            home_dir=home,
            gh_config_dir=gh_config,
            git_binary=Path("/tmp/git"),
        )
    with pytest.raises(ValidationError, match="/usr/bin/gh"):
        RemoteGitPublisherConfig(
            home_dir=home,
            gh_config_dir=gh_config,
            gh_binary=Path("/tmp/gh"),
        )


def test_config_rejects_external_gh_config_directory(tmp_path: Path) -> None:
    home = tmp_path / "home"
    with pytest.raises(ValidationError, match="~/.config/gh"):
        RemoteGitPublisherConfig(
            home_dir=home,
            gh_config_dir=tmp_path / "other-gh-config",
        )
