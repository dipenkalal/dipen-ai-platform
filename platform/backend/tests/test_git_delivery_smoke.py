from engineering.codex_smoke import PHASE11_BRANCH, SMOKE_CONTENT, SMOKE_TARGET


def test_phase11e_smoke_reuses_single_file_codex_fixture() -> None:
    assert PHASE11_BRANCH == "phase11/autonomous-engineering-agent"
    assert SMOKE_TARGET == "platform/backend/engineering/phase11c2_smoke_artifact.txt"
    assert SMOKE_CONTENT == "PHASE11C_CODEX_SMOKE_OK\n"
