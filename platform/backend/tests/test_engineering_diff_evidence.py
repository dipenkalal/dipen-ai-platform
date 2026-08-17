import hashlib
import subprocess
from pathlib import Path

import pytest

from engineering.engineering_diff_evidence import EngineeringDiffEvidenceCapture
from engineering.git_delivery_contract import GitDeliveryReceipt
from engineering.local_git_delivery import LocalGitDeliveryResult


def git(repo: Path, *args: str, text: bool = True):
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=30,
        text=text,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip() if text else result.stdout


def delivery_result(tmp_path: Path) -> LocalGitDeliveryResult:
    repo = tmp_path / "delivery"
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
    source_commit = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-c", "engineering/phase11f-diff-test")
    target = repo / "artifact.txt"
    target.write_text("evidence\n", encoding="utf-8")
    git(repo, "add", "artifact.txt")
    git(
        repo,
        "-c",
        "user.name=DAP Test",
        "-c",
        "user.email=dap-test@example.invalid",
        "commit",
        "--no-gpg-sign",
        "-m",
        "engineering evidence",
    )
    commit_sha = git(repo, "rev-parse", "HEAD")
    receipt = GitDeliveryReceipt(
        delivery_id="git-delivery-phase11f-diff-test",
        delivery_plan_sha256="a" * 64,
        disposition="succeeded",
        commit_created=True,
        commit_sha=commit_sha,
        committed_files=("artifact.txt",),
        findings=(),
        message="Local Git delivery passed.",
    )
    return LocalGitDeliveryResult(
        receipt=receipt,
        delivery_repo=repo,
        delivery_branch="engineering/phase11f-diff-test",
        commit_sha=commit_sha,
        source_commit=source_commit,
        remote_count=0,
    )


def test_capture_hashes_exact_binary_commit_diff(tmp_path: Path) -> None:
    result = delivery_result(tmp_path)
    evidence = EngineeringDiffEvidenceCapture().capture(result)
    expected = git(
        result.delivery_repo,
        "diff",
        "--binary",
        "--no-ext-diff",
        "--no-color",
        "HEAD^",
        "HEAD",
        text=False,
    )

    assert evidence.commit_sha == result.commit_sha
    assert evidence.parent_sha == result.source_commit
    assert evidence.changed_files == ("artifact.txt",)
    assert evidence.diff_sha256 == hashlib.sha256(expected).hexdigest()


def test_capture_rejects_tampered_local_commit(tmp_path: Path) -> None:
    result = delivery_result(tmp_path).model_copy(update={"commit_sha": "f" * 40})
    with pytest.raises(RuntimeError, match="commit differs"):
        EngineeringDiffEvidenceCapture().capture(result)


def test_capture_rejects_result_with_remote(tmp_path: Path) -> None:
    result = delivery_result(tmp_path).model_copy(update={"remote_count": 1})
    with pytest.raises(ValueError, match="network-free"):
        EngineeringDiffEvidenceCapture().capture(result)
