import history.analytics_service as service


def test_get_overview_returns_repository_result(monkeypatch):
    expected = service.AnalyticsOverview(
        total_runs=20,
        completed_runs=15,
        failed_runs=3,
        running_runs=1,
        cancelled_runs=1,
        success_rate=75.0,
        average_latency_ms=120.5,
        total_tokens=5000,
        runs_today=4,
        most_used_agent="research-agent",
    )

    monkeypatch.setattr(
        service.agent_analytics_repository,
        "get_overview",
        lambda: expected,
    )

    result = service.agent_analytics_service.get_overview()

    assert result is expected


def test_get_agents_returns_response(monkeypatch):
    agents = [
        {
            "agent_id": "research-agent",
            "runs": 12,
            "completed_runs": 10,
            "failed_runs": 2,
            "success_rate": 83.33,
            "average_latency_ms": 110.5,
            "total_tokens": 3200,
            "last_used_at": "2026-07-28T10:00:00Z",
        },
        {
            "agent_id": "system-agent",
            "runs": 8,
            "completed_runs": 5,
            "failed_runs": 3,
            "success_rate": 62.5,
            "average_latency_ms": 95.0,
            "total_tokens": 1800,
            "last_used_at": "2026-07-28T11:00:00Z",
        },
    ]

    captured = {}

    def fake_get_agents(*, limit):
        captured["limit"] = limit
        return agents

    monkeypatch.setattr(
        service.agent_analytics_repository,
        "get_agents",
        fake_get_agents,
    )

    response = service.agent_analytics_service.get_agents(limit=5)

    assert response.total == 2
    assert len(response.agents) == 2
    assert response.agents[0].agent_id == "research-agent"
    assert response.agents[1].agent_id == "system-agent"
    assert captured == {"limit": 5}


def test_get_recent_returns_response(monkeypatch):
    runs = [
        {
            "run_id": "run-1",
            "agent_id": "research-agent",
            "objective": "Summarise recent system activity",
            "model": "qwen",
            "provider": "ollama",
            "status": "completed",
            "total_tokens": 250,
            "latency_ms": 48.5,
            "started_at": "2026-07-28T10:00:00Z",
            "completed_at": "2026-07-28T10:00:05Z",
        },
        {
            "run_id": "run-2",
            "agent_id": "system-agent",
            "objective": "Check disk usage",
            "model": "llama",
            "provider": "ollama",
            "status": "failed",
            "total_tokens": None,
            "latency_ms": 22.0,
            "started_at": "2026-07-28T11:00:00Z",
            "completed_at": "2026-07-28T11:00:01Z",
        },
    ]

    captured = {}

    def fake_get_recent(*, limit):
        captured["limit"] = limit
        return runs

    monkeypatch.setattr(
        service.agent_analytics_repository,
        "get_recent",
        fake_get_recent,
    )

    response = service.agent_analytics_service.get_recent(limit=10)

    assert response.total == 2
    assert response.limit == 10
    assert len(response.runs) == 2
    assert response.runs[0].run_id == "run-1"
    assert response.runs[1].status == "failed"
    assert captured == {"limit": 10}


def test_get_dashboard_returns_combined_response(monkeypatch):
    overview = {
        "total_runs": 30,
        "completed_runs": 24,
        "failed_runs": 4,
        "running_runs": 1,
        "cancelled_runs": 1,
        "success_rate": 80.0,
        "average_latency_ms": 105.5,
        "total_tokens": 7400,
        "runs_today": 6,
        "most_used_agent": "research-agent",
    }

    agents = [
        {
            "agent_id": "research-agent",
            "runs": 20,
            "completed_runs": 17,
            "failed_runs": 3,
            "success_rate": 85.0,
            "average_latency_ms": 100.0,
            "total_tokens": 5000,
            "last_used_at": "2026-07-28T12:00:00Z",
        }
    ]

    recent_runs = [
        {
            "run_id": "run-3",
            "agent_id": "research-agent",
            "objective": "Build analytics dashboard",
            "model": "qwen",
            "provider": "ollama",
            "status": "completed",
            "total_tokens": 300,
            "latency_ms": 60.0,
            "started_at": "2026-07-28T12:00:00Z",
            "completed_at": "2026-07-28T12:00:04Z",
        }
    ]

    captured = {}

    def fake_get_overview():
        captured["overview_called"] = True
        return overview

    def fake_get_agents(*, limit):
        captured["agent_limit"] = limit
        return agents

    def fake_get_recent(*, limit):
        captured["recent_limit"] = limit
        return recent_runs

    monkeypatch.setattr(
        service.agent_analytics_repository,
        "get_overview",
        fake_get_overview,
    )
    monkeypatch.setattr(
        service.agent_analytics_repository,
        "get_agents",
        fake_get_agents,
    )
    monkeypatch.setattr(
        service.agent_analytics_repository,
        "get_recent",
        fake_get_recent,
    )

    response = service.agent_analytics_service.get_dashboard(
        agent_limit=3,
        recent_limit=7,
    )

    assert response.overview.total_runs == 30
    assert response.overview.most_used_agent == "research-agent"
    assert len(response.agents) == 1
    assert response.agents[0].agent_id == "research-agent"
    assert len(response.recent_runs) == 1
    assert response.recent_runs[0].run_id == "run-3"

    assert captured == {
        "overview_called": True,
        "agent_limit": 3,
        "recent_limit": 7,
    }
