import json
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from history.repository import AgentRunRepository


class FakeCursor:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows[0]

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.fetchone_result = None
        self.fetchall_result = []
        self.rowcount = 0
        self.committed = False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

        sql_upper = sql.strip().upper()

        if sql_upper.startswith("SELECT"):
            if "COUNT" in sql_upper:
                return FakeCursor(
                    rows=[self.fetchone_result] if self.fetchone_result else []
                )

            return FakeCursor(rows=self.fetchall_result)

        return FakeCursor(rowcount=self.rowcount)

    def commit(self):
        self.committed = True


class FakeDatabase:
    def __init__(self):
        self.initialized = False
        self.connection_obj = FakeConnection()

    def initialize(self):
        self.initialized = True

    @contextmanager
    def connection(self):
        yield self.connection_obj


@pytest.fixture
def fake_db():
    return FakeDatabase()


@pytest.fixture
def repository(fake_db):
    return AgentRunRepository(fake_db)


def make_request():
    return SimpleNamespace(
        provider="ollama",
        model="llama3",
        model_dump=lambda mode="json": {
            "provider": "ollama",
            "model": "llama3",
            "objective": "Explain batteries",
        },
    )


def make_response():
    usage = SimpleNamespace(
        model_dump=lambda mode="json": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "latency_ms": 200.5,
        }
    )

    step = SimpleNamespace(
        model_dump=lambda mode="json": {
            "name": "search",
            "status": "completed",
        }
    )

    return SimpleNamespace(
        run_id="run-1",
        agent_id="knowledge-agent",
        objective="Explain batteries",
        status="completed",
        answer="Battery explanation",
        started_at=datetime(2025, 1, 1, tzinfo=UTC),
        completed_at=datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
        steps=[step],
        usage=usage,
        sources=[
            {
                "id": "S1",
                "filename": "guide.pdf",
            }
        ],
    )


def make_row():
    return {
        "run_id": "run-1",
        "agent_id": "knowledge-agent",
        "objective": "Explain batteries",
        "model": "llama3",
        "provider": "ollama",
        "status": "completed",
        "answer": "Battery explanation",
        "error": None,
        "request_json": json.dumps(
            {
                "provider": "ollama",
                "model": "llama3",
            }
        ),
        "steps_json": json.dumps(
            [
                {
                    "step_number": 1,
                    "type": "tool",
                    "title": "Search knowledge base",
                    "status": "completed",
                    "started_at": "2025-01-01T00:00:00Z",
                    "completed_at": "2025-01-01T00:00:30Z",
                }
            ]
        ),
        "sources_json": json.dumps(
            [
                {
                    "id": "S1",
                }
            ]
        ),
        "usage_json": json.dumps(
            {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "latency_ms": 200.5,
            }
        ),
        "started_at": "2025-01-01T00:00:00Z",
        "completed_at": "2025-01-01T00:01:00Z",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:01:00Z",
    }


def test_repository_initializes_database(fake_db):
    AgentRunRepository(fake_db)

    assert fake_db.initialized is True


def test_save_inserts_commits_and_returns_record(
    repository,
    fake_db,
    monkeypatch,
):
    request = make_request()
    response = make_response()
    expected_record = SimpleNamespace(run_id="run-1")

    monkeypatch.setattr(
        repository,
        "get",
        lambda run_id: expected_record,
    )

    result = repository.save(
        request,
        response,
        error=None,
    )

    assert result is expected_record
    assert fake_db.connection_obj.committed is True

    sql, params = fake_db.connection_obj.calls[0]

    assert "INSERT INTO agent_runs" in sql
    assert "ON CONFLICT(run_id) DO UPDATE SET" in sql

    assert params[0] == "run-1"
    assert params[1] == "knowledge-agent"
    assert params[2] == "Explain batteries"
    assert params[3] == "llama3"
    assert params[4] == "ollama"
    assert params[5] == "completed"
    assert params[6] == "Battery explanation"
    assert params[7] is None

    request_data = json.loads(params[8])
    steps_data = json.loads(params[9])
    sources_data = json.loads(params[10])
    usage_data = json.loads(params[11])

    assert request_data["model"] == "llama3"
    assert request_data["provider"] == "ollama"

    assert steps_data == [
        {
            "name": "search",
            "status": "completed",
        }
    ]

    assert sources_data == [
        {
            "id": "S1",
            "filename": "guide.pdf",
        }
    ]

    assert usage_data["total_tokens"] == 150
    assert usage_data["latency_ms"] == 200.5

    assert params[12] == response.started_at.isoformat()
    assert params[13] == response.completed_at.isoformat()
    assert params[14] == params[15]


def test_save_includes_error(
    repository,
    fake_db,
    monkeypatch,
):
    request = make_request()
    response = make_response()

    monkeypatch.setattr(
        repository,
        "get",
        lambda run_id: SimpleNamespace(run_id=run_id),
    )

    repository.save(
        request,
        response,
        error="Gateway failed",
    )

    _, params = fake_db.connection_obj.calls[0]

    assert params[7] == "Gateway failed"


def test_save_raises_when_saved_record_cannot_be_read(
    repository,
    monkeypatch,
):
    monkeypatch.setattr(
        repository,
        "get",
        lambda run_id: None,
    )

    with pytest.raises(
        RuntimeError,
        match="Saved agent run could not be read",
    ):
        repository.save(
            make_request(),
            make_response(),
        )


def test_get_returns_none_when_row_does_not_exist(
    repository,
    fake_db,
):
    fake_db.connection_obj.fetchall_result = []

    result = repository.get("missing-run")

    assert result is None

    sql, params = fake_db.connection_obj.calls[0]

    assert "SELECT *" in sql
    assert "WHERE run_id = ?" in sql
    assert params == ("missing-run",)


def test_get_returns_converted_record(
    repository,
    fake_db,
    monkeypatch,
):
    row = make_row()

    class GetConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            return FakeCursor(rows=[row])

    fake_db.connection_obj = GetConnection()

    expected_record = SimpleNamespace(run_id="run-1")

    monkeypatch.setattr(
        repository,
        "_row_to_record",
        lambda returned_row: expected_record,
    )

    result = repository.get("run-1")

    assert result is expected_record


def test_list_without_filters_returns_rows_and_total(
    repository,
    fake_db,
    monkeypatch,
):
    rows = [
        make_row(),
        {
            **make_row(),
            "run_id": "run-2",
            "objective": "Explain motors",
        },
    ]

    class ListConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*)" in sql:
                return FakeCursor(rows=[{"total": 2}])

            return FakeCursor(rows=rows)

    fake_db.connection_obj = ListConnection()

    converted = [
        SimpleNamespace(run_id="run-1"),
        SimpleNamespace(run_id="run-2"),
    ]

    monkeypatch.setattr(
        repository,
        "_row_to_summary",
        lambda row: converted[0] if row["run_id"] == "run-1" else converted[1],
    )

    result, total = repository.list()

    assert result == converted
    assert total == 2

    count_sql, count_params = fake_db.connection_obj.calls[0]
    rows_sql, rows_params = fake_db.connection_obj.calls[1]

    assert "WHERE" not in count_sql
    assert "ORDER BY started_at DESC" in rows_sql
    assert count_params == []
    assert rows_params == [100, 0]


def test_list_applies_all_filters(
    repository,
    fake_db,
):
    class FilterConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*)" in sql:
                return FakeCursor(rows=[{"total": 0}])

            return FakeCursor(rows=[])

    fake_db.connection_obj = FilterConnection()

    result, total = repository.list(
        limit=25,
        offset=10,
        agent_id="knowledge-agent",
        status="completed",
        model="llama3",
        search="battery",
    )

    assert result == []
    assert total == 0

    count_sql, count_params = fake_db.connection_obj.calls[0]
    rows_sql, rows_params = fake_db.connection_obj.calls[1]

    assert "agent_id = ?" in count_sql
    assert "status = ?" in count_sql
    assert "model = ?" in count_sql
    assert "objective LIKE ?" in count_sql
    assert "answer LIKE ?" in count_sql
    assert "agent_id LIKE ?" in count_sql

    assert count_params == [
        "knowledge-agent",
        "completed",
        "llama3",
        "%battery%",
        "%battery%",
        "%battery%",
    ]

    assert rows_params == [
        "knowledge-agent",
        "completed",
        "llama3",
        "%battery%",
        "%battery%",
        "%battery%",
        25,
        10,
    ]

    assert "LIMIT ? OFFSET ?" in rows_sql


@pytest.mark.parametrize(
    ("kwargs", "expected_clause", "expected_value"),
    [
        (
            {"agent_id": "system-agent"},
            "agent_id = ?",
            "system-agent",
        ),
        (
            {"status": "failed"},
            "status = ?",
            "failed",
        ),
        (
            {"model": "qwen2.5"},
            "model = ?",
            "qwen2.5",
        ),
    ],
)
def test_list_applies_individual_filter(
    repository,
    fake_db,
    kwargs,
    expected_clause,
    expected_value,
):
    class SingleFilterConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*)" in sql:
                return FakeCursor(rows=[{"total": 0}])

            return FakeCursor(rows=[])

    fake_db.connection_obj = SingleFilterConnection()

    repository.list(**kwargs)

    count_sql, count_params = fake_db.connection_obj.calls[0]
    rows_sql, rows_params = fake_db.connection_obj.calls[1]

    assert expected_clause in count_sql
    assert expected_clause in rows_sql
    assert count_params == [expected_value]
    assert rows_params == [expected_value, 100, 0]


def test_list_applies_search_filter(
    repository,
    fake_db,
):
    class SearchConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*)" in sql:
                return FakeCursor(rows=[{"total": 0}])

            return FakeCursor(rows=[])

    fake_db.connection_obj = SearchConnection()

    repository.list(search="electric vehicle")

    count_sql, count_params = fake_db.connection_obj.calls[0]
    rows_sql, rows_params = fake_db.connection_obj.calls[1]

    assert "objective LIKE ?" in count_sql
    assert "answer LIKE ?" in count_sql
    assert "agent_id LIKE ?" in count_sql

    expected_search = "%electric vehicle%"

    assert count_params == [
        expected_search,
        expected_search,
        expected_search,
    ]

    assert rows_params == [
        expected_search,
        expected_search,
        expected_search,
        100,
        0,
    ]


def test_list_handles_missing_total_row(
    repository,
    fake_db,
):
    class MissingTotalConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*)" in sql:
                return FakeCursor(rows=[])

            return FakeCursor(rows=[])

    fake_db.connection_obj = MissingTotalConnection()

    result, total = repository.list()

    assert result == []
    assert total == 0


def test_delete_returns_true_when_row_deleted(
    repository,
    fake_db,
):
    fake_db.connection_obj.rowcount = 1

    result = repository.delete("run-1")

    assert result is True
    assert fake_db.connection_obj.committed is True

    sql, params = fake_db.connection_obj.calls[0]

    assert "DELETE FROM agent_runs" in sql
    assert "WHERE run_id = ?" in sql
    assert params == ("run-1",)


def test_delete_returns_false_when_row_not_found(
    repository,
    fake_db,
):
    fake_db.connection_obj.rowcount = 0

    result = repository.delete("missing-run")

    assert result is False
    assert fake_db.connection_obj.committed is True


@pytest.mark.parametrize(
    ("rowcount", "expected"),
    [
        (5, 5),
        (0, 0),
        (-1, 0),
    ],
)
def test_clear_returns_non_negative_deleted_count(
    repository,
    fake_db,
    rowcount,
    expected,
):
    fake_db.connection_obj.rowcount = rowcount

    result = repository.clear()

    assert result == expected
    assert fake_db.connection_obj.committed is True

    sql, params = fake_db.connection_obj.calls[0]

    assert sql.strip() == "DELETE FROM agent_runs"
    assert params == ()


def test_row_to_record_maps_all_fields(repository):
    row = make_row()

    record = repository._row_to_record(row)

    assert record.run_id == "run-1"
    assert record.agent_id == "knowledge-agent"
    assert record.objective == "Explain batteries"
    assert record.model == "llama3"
    assert record.provider == "ollama"
    assert record.status == "completed"
    assert record.answer == "Battery explanation"
    assert record.error is None

    assert record.request == {
        "provider": "ollama",
        "model": "llama3",
    }

    assert len(record.steps) == 1

    assert record.steps[0].step_number == 1
    assert record.steps[0].type == "tool"
    assert record.steps[0].title == "Search knowledge base"
    assert record.steps[0].success is True

    assert record.sources == [
        {
            "id": "S1",
        }
    ]

    assert record.usage.prompt_tokens == 100
    assert record.usage.completion_tokens == 50
    assert record.usage.total_tokens == 150
    assert record.usage.latency_ms == 200.5

    assert record.started_at.isoformat().startswith("2025-01-01T00:00:00")
    assert record.completed_at.isoformat().startswith("2025-01-01T00:01:00")
    assert record.created_at.isoformat().startswith("2025-01-01T00:00:00")
    assert record.updated_at.isoformat().startswith("2025-01-01T00:01:00")


def test_row_to_summary_maps_counts_and_usage(repository):
    row = make_row()

    summary = repository._row_to_summary(row)

    assert summary.run_id == "run-1"
    assert summary.agent_id == "knowledge-agent"
    assert summary.objective == "Explain batteries"
    assert summary.model == "llama3"
    assert summary.provider == "ollama"
    assert summary.status == "completed"
    assert summary.answer_preview == "Battery explanation"
    assert summary.error is None
    assert summary.step_count == 1
    assert summary.source_count == 1
    assert summary.total_tokens == 150
    assert summary.latency_ms == 200.5

    assert summary.started_at.isoformat().startswith("2025-01-01T00:00:00")
    assert summary.completed_at.isoformat().startswith("2025-01-01T00:01:00")
    assert summary.created_at.isoformat().startswith("2025-01-01T00:00:00")


def test_row_to_summary_truncates_long_answer(repository):
    long_answer = "A" * 300

    row = {
        **make_row(),
        "answer": long_answer,
    }

    summary = repository._row_to_summary(row)

    assert summary.answer_preview == ("A" * 240) + "…"
    assert len(summary.answer_preview) == 241


def test_row_to_summary_handles_none_answer(repository):
    row = {
        **make_row(),
        "answer": None,
    }

    summary = repository._row_to_summary(row)

    assert summary.answer_preview == ""


def test_row_to_summary_defaults_missing_latency(repository):
    usage = {
        "total_tokens": 150,
    }

    row = {
        **make_row(),
        "usage_json": json.dumps(usage),
    }

    summary = repository._row_to_summary(row)

    assert summary.total_tokens == 150
    assert summary.latency_ms == 0.0


def test_row_to_summary_allows_missing_total_tokens(repository):
    usage = {
        "latency_ms": 125.0,
    }

    row = {
        **make_row(),
        "usage_json": json.dumps(usage),
    }

    summary = repository._row_to_summary(row)

    assert summary.total_tokens is None
    assert summary.latency_ms == 125.0
