from datetime import UTC, datetime
from unittest.mock import patch

from app import app
from fastapi.testclient import TestClient
from history.schemas import (
    AgentRunClearResponse,
    AgentRunDeleteResponse,
    AgentRunListResponse,
    AgentRunRecord,
    AgentRunSummary,
)

client = TestClient(app)


def make_record(run_id: str = "run-123") -> AgentRunRecord:
    now = datetime.now(UTC)

    return AgentRunRecord(
        run_id=run_id,
        agent_id="coding-agent",
        objective="Write hello world",
        status="completed",
        answer="Hello world",
        error=None,
        model="test-model",
        steps=[],
        sources=[],
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )


def make_summary(
    run_id: str = "run-123",
) -> AgentRunSummary:
    now = datetime.now(UTC)

    return AgentRunSummary(
        run_id=run_id,
        agent_id="coding-agent",
        objective="Write hello world",
        model="test-model",
        provider="ollama",
        status="completed",
        answer_preview="Hello world",
        error=None,
        step_count=0,
        source_count=0,
        total_tokens=15,
        latency_ms=12.5,
        started_at=now,
        completed_at=now,
        created_at=now,
    )


def test_list_agent_runs():
    summary = make_summary()

    fake_response = AgentRunListResponse(
        runs=[summary],
        total=1,
        limit=25,
        offset=5,
    )

    with patch(
        "history.routes.agent_run_history_service.list",
        return_value=fake_response,
    ) as mocked_list:
        response = client.get(
            "/api/v1/agent-runs",
            params={
                "limit": 25,
                "offset": 5,
                "agent_id": "coding-agent",
                "status": "completed",
                "model": "test-model",
                "search": "hello",
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["limit"] == 25
    assert body["offset"] == 5
    assert body["runs"][0]["run_id"] == "run-123"

    mocked_list.assert_called_once_with(
        limit=25,
        offset=5,
        agent_id="coding-agent",
        status="completed",
        model="test-model",
        search="hello",
    )


def test_list_agent_runs_uses_defaults():
    fake_response = AgentRunListResponse(
        runs=[],
        total=0,
        limit=100,
        offset=0,
    )

    with patch(
        "history.routes.agent_run_history_service.list",
        return_value=fake_response,
    ) as mocked_list:
        response = client.get("/api/v1/agent-runs")

    assert response.status_code == 200

    mocked_list.assert_called_once_with(
        limit=100,
        offset=0,
        agent_id=None,
        status=None,
        model=None,
        search=None,
    )


def test_list_agent_runs_rejects_invalid_limit():
    response = client.get(
        "/api/v1/agent-runs",
        params={"limit": 0},
    )

    assert response.status_code == 422


def test_list_agent_runs_rejects_negative_offset():
    response = client.get(
        "/api/v1/agent-runs",
        params={"offset": -1},
    )

    assert response.status_code == 422


def test_get_agent_run():
    record = make_record()

    with patch(
        "history.routes.agent_run_history_service.get",
        return_value=record,
    ) as mocked_get:
        response = client.get("/api/v1/agent-runs/run-123")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run-123"

    mocked_get.assert_called_once_with("run-123")


def test_delete_agent_run():
    fake_response = AgentRunDeleteResponse(
        run_id="run-123",
        deleted=True,
    )

    with patch(
        "history.routes.agent_run_history_service.delete",
        return_value=fake_response,
    ) as mocked_delete:
        response = client.delete("/api/v1/agent-runs/run-123")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run-123"
    assert response.json()["deleted"] is True

    mocked_delete.assert_called_once_with("run-123")


def test_clear_agent_runs():
    fake_response = AgentRunClearResponse(
        deleted_count=3,
    )

    with patch(
        "history.routes.agent_run_history_service.clear",
        return_value=fake_response,
    ) as mocked_clear:
        response = client.delete("/api/v1/agent-runs")

    assert response.status_code == 200
    assert response.json()["deleted_count"] == 3

    mocked_clear.assert_called_once_with()
