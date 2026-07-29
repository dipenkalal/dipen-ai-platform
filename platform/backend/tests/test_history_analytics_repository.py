import json
from contextlib import contextmanager

import pytest
from history.analytics_repository import AgentAnalyticsRepository


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return FakeCursor()


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
    return AgentAnalyticsRepository(fake_db)


def usage_json(
    tokens=100,
    latency=50.5,
):
    return json.dumps(
        {
            "total_tokens": tokens,
            "latency_ms": latency,
        }
    )


def test_repository_initializes_database(fake_db):
    AgentAnalyticsRepository(fake_db)

    assert fake_db.initialized is True


def test_get_overview_returns_aggregated_metrics(
    repository,
    fake_db,
):
    totals_row = {
        "total_runs": 5,
        "completed_runs": 3,
        "failed_runs": 1,
        "running_runs": 1,
        "cancelled_runs": 0,
        "runs_today": 2,
    }

    most_used_row = {
        "agent_id": "knowledge-agent",
        "run_count": 3,
    }

    usage_rows = [
        {
            "usage_json": usage_json(
                tokens=100,
                latency=50.0,
            )
        },
        {
            "usage_json": usage_json(
                tokens=200,
                latency=150.0,
            )
        },
        {
            "usage_json": json.dumps(
                {
                    "total_tokens": 50,
                }
            )
        },
    ]

    class OverviewConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*) AS total_runs" in sql:
                return FakeCursor(row=totals_row)

            if "GROUP BY agent_id" in sql:
                return FakeCursor(row=most_used_row)

            if "SELECT usage_json" in sql:
                return FakeCursor(rows=usage_rows)

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = OverviewConnection()

    result = repository.get_overview()

    assert result.total_runs == 5
    assert result.completed_runs == 3
    assert result.failed_runs == 1
    assert result.running_runs == 1
    assert result.cancelled_runs == 0
    assert result.success_rate == 60.0
    assert result.average_latency_ms == 100.0
    assert result.total_tokens == 350
    assert result.runs_today == 2
    assert result.most_used_agent == "knowledge-agent"

    assert len(fake_db.connection_obj.calls) == 3


def test_get_overview_handles_empty_database(
    repository,
    fake_db,
):
    class EmptyOverviewConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*) AS total_runs" in sql:
                return FakeCursor(row=None)

            if "GROUP BY agent_id" in sql:
                return FakeCursor(row=None)

            if "SELECT usage_json" in sql:
                return FakeCursor(rows=[])

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = EmptyOverviewConnection()

    result = repository.get_overview()

    assert result.total_runs == 0
    assert result.completed_runs == 0
    assert result.failed_runs == 0
    assert result.running_runs == 0
    assert result.cancelled_runs == 0
    assert result.success_rate == 0.0
    assert result.average_latency_ms == 0.0
    assert result.total_tokens == 0
    assert result.runs_today == 0
    assert result.most_used_agent is None


def test_get_overview_handles_invalid_usage_values(
    repository,
    fake_db,
):
    totals_row = {
        "total_runs": "bad",
        "completed_runs": None,
        "failed_runs": "invalid",
        "running_runs": None,
        "cancelled_runs": "2",
        "runs_today": "1",
    }

    usage_rows = [
        {
            "usage_json": json.dumps(
                {
                    "total_tokens": "invalid",
                    "latency_ms": "bad",
                }
            )
        },
        {
            "usage_json": None,
        },
        {
            "usage_json": "not-json",
        },
        {
            "usage_json": json.dumps(["not", "a", "dictionary"]),
        },
    ]

    class InvalidOverviewConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*) AS total_runs" in sql:
                return FakeCursor(row=totals_row)

            if "GROUP BY agent_id" in sql:
                return FakeCursor(
                    row={
                        "agent_id": 123,
                        "run_count": 1,
                    }
                )

            if "SELECT usage_json" in sql:
                return FakeCursor(rows=usage_rows)

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = InvalidOverviewConnection()

    result = repository.get_overview()

    assert result.total_runs == 0
    assert result.completed_runs == 0
    assert result.failed_runs == 0
    assert result.running_runs == 0
    assert result.cancelled_runs == 2
    assert result.success_rate == 0.0
    assert result.average_latency_ms == 0.0
    assert result.total_tokens == 0
    assert result.runs_today == 1
    assert result.most_used_agent == "123"


def test_get_overview_rounds_average_latency(
    repository,
    fake_db,
):
    totals_row = {
        "total_runs": 2,
        "completed_runs": 2,
        "failed_runs": 0,
        "running_runs": 0,
        "cancelled_runs": 0,
        "runs_today": 2,
    }

    usage_rows = [
        {
            "usage_json": usage_json(
                tokens=10,
                latency=10.123,
            )
        },
        {
            "usage_json": usage_json(
                tokens=20,
                latency=20.456,
            )
        },
    ]

    class RoundedOverviewConnection(FakeConnection):
        def execute(self, sql, params=()):
            if "COUNT(*) AS total_runs" in sql:
                return FakeCursor(row=totals_row)

            if "GROUP BY agent_id" in sql:
                return FakeCursor(
                    row={
                        "agent_id": "system-agent",
                        "run_count": 2,
                    }
                )

            if "SELECT usage_json" in sql:
                return FakeCursor(rows=usage_rows)

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = RoundedOverviewConnection()

    result = repository.get_overview()

    assert result.average_latency_ms == 15.29
    assert result.success_rate == 100.0


def test_get_agents_returns_aggregated_agent_metrics(
    repository,
    fake_db,
):
    aggregate_rows = [
        {
            "agent_id": "knowledge-agent",
            "runs": 3,
            "completed_runs": 2,
            "failed_runs": 1,
            "last_used_at": "2025-01-03T10:00:00Z",
        },
        {
            "agent_id": "system-agent",
            "runs": 2,
            "completed_runs": 2,
            "failed_runs": 0,
            "last_used_at": "2025-01-02T10:00:00Z",
        },
    ]

    usage_rows = [
        {
            "agent_id": "knowledge-agent",
            "usage_json": usage_json(
                tokens=100,
                latency=50.0,
            ),
        },
        {
            "agent_id": "knowledge-agent",
            "usage_json": usage_json(
                tokens=200,
                latency=150.0,
            ),
        },
        {
            "agent_id": "knowledge-agent",
            "usage_json": json.dumps(
                {
                    "total_tokens": 50,
                }
            ),
        },
        {
            "agent_id": "system-agent",
            "usage_json": usage_json(
                tokens=75,
                latency=25.0,
            ),
        },
    ]

    class AgentsConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*) AS runs" in sql:
                return FakeCursor(rows=aggregate_rows)

            if "SELECT" in sql and "usage_json" in sql:
                return FakeCursor(rows=usage_rows)

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = AgentsConnection()

    result = repository.get_agents(limit=25)

    assert len(result) == 2

    knowledge = result[0]

    assert knowledge.agent_id == "knowledge-agent"
    assert knowledge.runs == 3
    assert knowledge.completed_runs == 2
    assert knowledge.failed_runs == 1
    assert knowledge.success_rate == 66.67
    assert knowledge.average_latency_ms == 100.0
    assert knowledge.total_tokens == 350
    assert knowledge.last_used_at.isoformat().startswith("2025-01-03T10:00:00")

    system = result[1]

    assert system.agent_id == "system-agent"
    assert system.runs == 2
    assert system.completed_runs == 2
    assert system.failed_runs == 0
    assert system.success_rate == 100.0
    assert system.average_latency_ms == 25.0
    assert system.total_tokens == 75
    assert system.last_used_at.isoformat().startswith("2025-01-02T10:00:00")

    aggregate_sql, aggregate_params = fake_db.connection_obj.calls[0]

    assert "GROUP BY agent_id" in aggregate_sql
    assert "LIMIT ?" in aggregate_sql
    assert aggregate_params == (25,)


def test_get_agents_handles_empty_results(
    repository,
    fake_db,
):
    class EmptyAgentsConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))

            if "COUNT(*) AS runs" in sql:
                return FakeCursor(rows=[])

            if "usage_json" in sql:
                return FakeCursor(rows=[])

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = EmptyAgentsConnection()

    result = repository.get_agents()

    assert result == []

    aggregate_sql, aggregate_params = fake_db.connection_obj.calls[0]

    assert aggregate_params == (100,)


def test_get_agents_handles_invalid_usage_and_counts(
    repository,
    fake_db,
):
    aggregate_rows = [
        {
            "agent_id": 123,
            "runs": "invalid",
            "completed_runs": None,
            "failed_runs": "bad",
            "last_used_at": "2025-01-01T00:00:00Z",
        }
    ]

    usage_rows = [
        {
            "agent_id": 123,
            "usage_json": json.dumps(
                {
                    "total_tokens": "bad",
                    "latency_ms": "invalid",
                }
            ),
        },
        {
            "agent_id": 123,
            "usage_json": None,
        },
        {
            "agent_id": 123,
            "usage_json": "not-json",
        },
    ]

    class InvalidAgentsConnection(FakeConnection):
        def execute(self, sql, params=()):
            if "COUNT(*) AS runs" in sql:
                return FakeCursor(rows=aggregate_rows)

            if "usage_json" in sql:
                return FakeCursor(rows=usage_rows)

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = InvalidAgentsConnection()

    result = repository.get_agents()

    assert len(result) == 1

    agent = result[0]

    assert agent.agent_id == "123"
    assert agent.runs == 0
    assert agent.completed_runs == 0
    assert agent.failed_runs == 0
    assert agent.success_rate == 0.0
    assert agent.average_latency_ms == 0.0
    assert agent.total_tokens == 0


def test_get_agents_handles_missing_usage_for_agent(
    repository,
    fake_db,
):
    aggregate_rows = [
        {
            "agent_id": "orchestrator-agent",
            "runs": 1,
            "completed_runs": 0,
            "failed_runs": 1,
            "last_used_at": "2025-01-04T10:00:00Z",
        }
    ]

    class MissingUsageConnection(FakeConnection):
        def execute(self, sql, params=()):
            if "COUNT(*) AS runs" in sql:
                return FakeCursor(rows=aggregate_rows)

            if "usage_json" in sql:
                return FakeCursor(rows=[])

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = MissingUsageConnection()

    result = repository.get_agents(limit=1)

    assert len(result) == 1

    agent = result[0]

    assert agent.agent_id == "orchestrator-agent"
    assert agent.runs == 1
    assert agent.completed_runs == 0
    assert agent.failed_runs == 1
    assert agent.success_rate == 0.0
    assert agent.average_latency_ms == 0.0
    assert agent.total_tokens == 0


def test_get_agents_rounds_average_latency(
    repository,
    fake_db,
):
    aggregate_rows = [
        {
            "agent_id": "knowledge-agent",
            "runs": 2,
            "completed_runs": 1,
            "failed_runs": 1,
            "last_used_at": "2025-01-05T10:00:00Z",
        }
    ]

    usage_rows = [
        {
            "agent_id": "knowledge-agent",
            "usage_json": usage_json(
                tokens=10,
                latency=10.111,
            ),
        },
        {
            "agent_id": "knowledge-agent",
            "usage_json": usage_json(
                tokens=20,
                latency=20.222,
            ),
        },
    ]

    class RoundedAgentsConnection(FakeConnection):
        def execute(self, sql, params=()):
            if "COUNT(*) AS runs" in sql:
                return FakeCursor(rows=aggregate_rows)

            if "usage_json" in sql:
                return FakeCursor(rows=usage_rows)

            raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db.connection_obj = RoundedAgentsConnection()

    result = repository.get_agents()

    assert result[0].average_latency_ms == 15.17
    assert result[0].success_rate == 50.0


def test_get_recent_returns_recent_runs(
    repository,
    fake_db,
):
    rows = [
        {
            "run_id": "run-1",
            "agent_id": "knowledge-agent",
            "objective": "Explain batteries",
            "model": "llama3",
            "provider": "ollama",
            "status": "completed",
            "usage_json": usage_json(
                tokens=150,
                latency=200.5,
            ),
            "started_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T00:01:00Z",
        },
        {
            "run_id": "run-2",
            "agent_id": "system-agent",
            "objective": "Check system health",
            "model": "qwen2.5",
            "provider": "ollama",
            "status": "failed",
            "usage_json": json.dumps(
                {
                    "latency_ms": 75,
                }
            ),
            "started_at": "2025-01-02T00:00:00Z",
            "completed_at": "2025-01-02T00:00:30Z",
        },
    ]

    class RecentConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            return FakeCursor(rows=rows)

    fake_db.connection_obj = RecentConnection()

    result = repository.get_recent(limit=5)

    assert len(result) == 2

    first = result[0]

    assert first.run_id == "run-1"
    assert first.agent_id == "knowledge-agent"
    assert first.objective == "Explain batteries"
    assert first.model == "llama3"
    assert first.provider == "ollama"
    assert first.status == "completed"
    assert first.total_tokens == 150
    assert first.latency_ms == 200.5
    assert first.started_at.isoformat().startswith("2025-01-01T00:00:00")
    assert first.completed_at.isoformat().startswith("2025-01-01T00:01:00")

    second = result[1]

    assert second.run_id == "run-2"
    assert second.status == "failed"
    assert second.total_tokens is None
    assert second.latency_ms == 75.0

    sql, params = fake_db.connection_obj.calls[0]

    assert "ORDER BY started_at DESC" in sql
    assert "LIMIT ?" in sql
    assert params == (5,)


def test_get_recent_handles_empty_results(
    repository,
    fake_db,
):
    class EmptyRecentConnection(FakeConnection):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            return FakeCursor(rows=[])

    fake_db.connection_obj = EmptyRecentConnection()

    result = repository.get_recent()

    assert result == []

    _, params = fake_db.connection_obj.calls[0]

    assert params == (10,)


def test_get_recent_handles_invalid_usage_values(
    repository,
    fake_db,
):
    rows = [
        {
            "run_id": "run-invalid",
            "agent_id": "knowledge-agent",
            "objective": "Invalid usage",
            "model": "llama3",
            "provider": "ollama",
            "status": "completed",
            "usage_json": json.dumps(
                {
                    "total_tokens": "bad",
                    "latency_ms": "invalid",
                }
            ),
            "started_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T00:00:30Z",
        },
        {
            "run_id": "run-no-usage",
            "agent_id": "system-agent",
            "objective": "Missing usage",
            "model": "qwen2.5",
            "provider": "ollama",
            "status": "running",
            "usage_json": None,
            "started_at": "2025-01-02T00:00:00Z",
            "completed_at": "2025-01-02T00:00:30Z",
        },
    ]

    class InvalidRecentConnection(FakeConnection):
        def execute(self, sql, params=()):
            return FakeCursor(rows=rows)

    fake_db.connection_obj = InvalidRecentConnection()

    result = repository.get_recent()

    assert result[0].total_tokens == 0
    assert result[0].latency_ms == 0.0

    assert result[1].total_tokens is None
    assert result[1].latency_ms == 0.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, {}),
        ("", {}),
        ("not-json", {}),
        (json.dumps(["item"]), {}),
        (json.dumps({"total_tokens": 10}), {"total_tokens": 10}),
    ],
)
def test_load_usage(
    value,
    expected,
):
    assert AgentAnalyticsRepository._load_usage(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 0),
        (5, 5),
        ("10", 10),
        (10.9, 10),
        ("invalid", 0),
        (object(), 0),
    ],
)
def test_as_int(
    value,
    expected,
):
    assert AgentAnalyticsRepository._as_int(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 0.0),
        (5, 5.0),
        ("10.5", 10.5),
        ("invalid", 0.0),
        (object(), 0.0),
    ],
)
def test_as_float(
    value,
    expected,
):
    assert AgentAnalyticsRepository._as_float(value) == expected


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (3, 5, 60.0),
        (1, 3, 33.33),
        (0, 5, 0.0),
        (5, 0, 0.0),
        (5, -1, 0.0),
    ],
)
def test_percentage(
    numerator,
    denominator,
    expected,
):
    assert (
        AgentAnalyticsRepository._percentage(
            numerator,
            denominator,
        )
        == expected
    )
