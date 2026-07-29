from pathlib import Path
from unittest.mock import patch

from history.database import (
    DEFAULT_DATABASE_PATH,
    HistoryDatabase,
    get_database_path,
)


def test_get_database_path_from_environment():
    with patch.dict(
        "os.environ",
        {"DAP_AGENT_HISTORY_DB": "~/custom-history/agent-runs.db"},
        clear=False,
    ):
        result = get_database_path()

    assert result == Path("~/custom-history/agent-runs.db").expanduser()


def test_get_database_path_uses_default_when_not_configured():
    with patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        result = get_database_path()

    assert result == DEFAULT_DATABASE_PATH


def test_history_database_uses_provided_path(tmp_path):
    database_path = tmp_path / "history.db"

    database = HistoryDatabase(database_path)

    assert database.database_path == database_path


def test_history_database_uses_configured_path_when_not_provided(tmp_path):
    database_path = tmp_path / "configured.db"

    with patch.dict(
        "os.environ",
        {"DAP_AGENT_HISTORY_DB": str(database_path)},
        clear=False,
    ):
        database = HistoryDatabase()

    assert database.database_path == database_path


def test_initialize_creates_database_and_schema(tmp_path):
    database_path = tmp_path / "nested" / "agent-runs.db"
    database = HistoryDatabase(database_path)

    database.initialize()

    assert database_path.exists()

    with database.connection() as connection:
        table = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'agent_runs'
            """).fetchone()

        indexes = {row["name"] for row in connection.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                  AND tbl_name = 'agent_runs'
                """).fetchall()}

    assert table["name"] == "agent_runs"
    assert {
        "idx_agent_runs_started_at",
        "idx_agent_runs_agent_id",
        "idx_agent_runs_status",
        "idx_agent_runs_model",
    }.issubset(indexes)


def test_connection_returns_rows_as_sqlite_rows(tmp_path):
    database = HistoryDatabase(tmp_path / "history.db")
    database.initialize()

    with database.connection() as connection:
        connection.execute("""
            INSERT INTO agent_runs (
                run_id,
                agent_id,
                objective,
                model,
                provider,
                status,
                answer,
                error,
                request_json,
                steps_json,
                sources_json,
                usage_json,
                started_at,
                completed_at,
                created_at,
                updated_at
            )
            VALUES (
                'run-1',
                'coding-agent',
                'Test objective',
                'test-model',
                'ollama',
                'completed',
                'Done',
                NULL,
                '{}',
                '[]',
                '[]',
                '{}',
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:01+00:00',
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:01+00:00'
            )
            """)
        connection.commit()

        row = connection.execute(
            "SELECT run_id, agent_id FROM agent_runs"
        ).fetchone()

    assert row["run_id"] == "run-1"
    assert row["agent_id"] == "coding-agent"


def test_connection_closes_after_context_manager(tmp_path):
    database = HistoryDatabase(tmp_path / "history.db")

    with database.connection() as connection:
        connection.execute("SELECT 1")

    try:
        connection.execute("SELECT 1")
    except Exception as exc:
        assert "closed" in str(exc).lower()
    else:
        raise AssertionError("Expected the SQLite connection to be closed")
