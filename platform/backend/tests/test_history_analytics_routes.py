from datetime import UTC, datetime
from unittest.mock import patch

from app import app
from fastapi.testclient import TestClient
from history.analytics_schemas import (
    AgentAnalyticsItem,
    AgentAnalyticsResponse,
    AnalyticsDashboardResponse,
    AnalyticsOverview,
    RecentAnalyticsResponse,
    RecentAnalyticsRun,
)

client = TestClient(app)


def make_agent_item() -> AgentAnalyticsItem:
    now = datetime.now(UTC)

    return AgentAnalyticsItem(
        agent_id="coding-agent",
        runs=10,
        completed_runs=8,
        failed_runs=2,
        success_rate=80.0,
        average_latency_ms=125.5,
        total_tokens=2500,
        last_used_at=now,
    )


def make_recent_run() -> RecentAnalyticsRun:
    now = datetime.now(UTC)

    return RecentAnalyticsRun(
        run_id="run-123",
        agent_id="coding-agent",
        objective="Write hello world",
        model="test-model",
        provider="ollama",
        status="completed",
        total_tokens=15,
        latency_ms=12.5,
        started_at=now,
        completed_at=now,
    )


def make_overview() -> AnalyticsOverview:
    return AnalyticsOverview(
        total_runs=10,
        completed_runs=8,
        failed_runs=2,
        running_runs=0,
        cancelled_runs=0,
        success_rate=80.0,
        average_latency_ms=125.5,
        total_tokens=2500,
        runs_today=3,
        most_used_agent="coding-agent",
    )


def test_get_analytics_overview():
    fake_response = make_overview()

    with patch(
        "history.analytics_routes.agent_analytics_service.get_overview",
        return_value=fake_response,
    ) as mocked_get:
        response = client.get("/api/v1/analytics/overview")

    assert response.status_code == 200

    body = response.json()

    assert body["total_runs"] == 10
    assert body["completed_runs"] == 8
    assert body["success_rate"] == 80.0
    assert body["most_used_agent"] == "coding-agent"

    mocked_get.assert_called_once_with()


def test_get_agent_analytics():
    item = make_agent_item()

    fake_response = AgentAnalyticsResponse(
        agents=[item],
        total=1,
    )

    with patch(
        "history.analytics_routes.agent_analytics_service.get_agents",
        return_value=fake_response,
    ) as mocked_get:
        response = client.get(
            "/api/v1/analytics/agents",
            params={"limit": 25},
        )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["agents"][0]["agent_id"] == "coding-agent"

    mocked_get.assert_called_once_with(limit=25)


def test_get_agent_analytics_uses_default_limit():
    fake_response = AgentAnalyticsResponse()

    with patch(
        "history.analytics_routes.agent_analytics_service.get_agents",
        return_value=fake_response,
    ) as mocked_get:
        response = client.get("/api/v1/analytics/agents")

    assert response.status_code == 200
    mocked_get.assert_called_once_with(limit=100)


def test_get_agent_analytics_rejects_invalid_limit():
    response = client.get(
        "/api/v1/analytics/agents",
        params={"limit": 0},
    )

    assert response.status_code == 422


def test_get_recent_analytics_runs():
    run = make_recent_run()

    fake_response = RecentAnalyticsResponse(
        runs=[run],
        total=1,
        limit=5,
    )

    with patch(
        "history.analytics_routes.agent_analytics_service.get_recent",
        return_value=fake_response,
    ) as mocked_get:
        response = client.get(
            "/api/v1/analytics/recent",
            params={"limit": 5},
        )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["limit"] == 5
    assert body["runs"][0]["run_id"] == "run-123"

    mocked_get.assert_called_once_with(limit=5)


def test_get_recent_analytics_runs_uses_default_limit():
    fake_response = RecentAnalyticsResponse()

    with patch(
        "history.analytics_routes.agent_analytics_service.get_recent",
        return_value=fake_response,
    ) as mocked_get:
        response = client.get("/api/v1/analytics/recent")

    assert response.status_code == 200
    mocked_get.assert_called_once_with(limit=10)


def test_get_recent_analytics_runs_rejects_invalid_limit():
    response = client.get(
        "/api/v1/analytics/recent",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_get_analytics_dashboard():
    overview = make_overview()
    item = make_agent_item()
    run = make_recent_run()

    fake_response = AnalyticsDashboardResponse(
        overview=overview,
        agents=[item],
        recent_runs=[run],
    )

    with patch(
        "history.analytics_routes.agent_analytics_service.get_dashboard",
        return_value=fake_response,
    ) as mocked_get:
        response = client.get(
            "/api/v1/analytics/dashboard",
            params={
                "agent_limit": 20,
                "recent_limit": 7,
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["overview"]["total_runs"] == 10
    assert body["agents"][0]["agent_id"] == "coding-agent"
    assert body["recent_runs"][0]["run_id"] == "run-123"

    mocked_get.assert_called_once_with(
        agent_limit=20,
        recent_limit=7,
    )


def test_get_analytics_dashboard_uses_defaults():
    fake_response = AnalyticsDashboardResponse(
        overview=AnalyticsOverview(),
    )

    with patch(
        "history.analytics_routes.agent_analytics_service.get_dashboard",
        return_value=fake_response,
    ) as mocked_get:
        response = client.get("/api/v1/analytics/dashboard")

    assert response.status_code == 200

    mocked_get.assert_called_once_with(
        agent_limit=100,
        recent_limit=10,
    )


def test_get_analytics_dashboard_rejects_invalid_limits():
    response = client.get(
        "/api/v1/analytics/dashboard",
        params={
            "agent_limit": 0,
            "recent_limit": 101,
        },
    )

    assert response.status_code == 422
