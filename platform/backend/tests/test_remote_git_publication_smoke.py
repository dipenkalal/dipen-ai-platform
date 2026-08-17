from pathlib import Path

from engineering.codex_smoke import PHASE11_BRANCH, SMOKE_TARGET
from engineering.remote_git_publisher import EXPECTED_GH_VERSION


def test_phase11e3_smoke_is_disposable_but_leaves_remote_review_artifacts() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "engineering/remote_git_publication_smoke.py"
    ).read_text(encoding="utf-8")

    assert PHASE11_BRANCH == "phase11/autonomous-engineering-agent"
    assert SMOKE_TARGET == "platform/backend/engineering/phase11c2_smoke_artifact.txt"
    assert EXPECTED_GH_VERSION == "2.97.0"
    assert "RemoteGitPublisher" in source
    assert "remote_git_publication_service.prepare" in source
    assert "builder.cleanup" in source
    assert "shutil.rmtree(run_root" in source
    assert "remote_cleanup_deferred_to_owner_control|true" in source
    assert "gh auth token" not in source
    assert "push --delete" not in source
    assert "pr close" not in source
    assert "pr merge" not in source
