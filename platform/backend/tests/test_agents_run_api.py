from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from agents.schemas import AgentRunResponse, AgentUsage
from app import app
from fastapi import HTTPException
from fastapi.testclient import TestClient

client = TestClient(app)


def test_run_agent_success():
    now = datetime.now(UTC)

    fake_response = AgentRunResponse(
        run_id="run-123",
        agent_id="coding-agent",
        objective="Write hello world",
        status="completed",
        answer="Hello from the mocked agent.",
        steps=[],
        sources=[],
        usage=AgentUsage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=12.5,
        ),
        started_at=now,
        completed_at=now,
    )

    with patch(
        "agents.routes.agent_service.run",
        new=AsyncMock(return_value=fake_response),
    ) as mocked_run:
        response = client.post(
            "/api/v1/agents/run",
            json={
                "mode": "manual",
                "agent_id": "coding-agent",
                "objective": "Write hello world",
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["run_id"] == "run-123"
    assert body["status"] == "completed"
    assert body["agent_id"] == "coding-agent"
    assert body["objective"] == "Write hello world"
    assert body["answer"] == "Hello from the mocked agent."
    assert body["usage"]["total_tokens"] == 15

    mocked_run.assert_awaited_once()

    submitted_request = mocked_run.await_args.args[0]

    assert submitted_request.mode == "manual"
    assert submitted_request.agent_id == "coding-agent"
    assert submitted_request.objective == "Write hello world"


def test_run_agent_validation_error():
    response = client.post(
        "/api/v1/agents/run",
        json={},
    )

    assert response.status_code == 422


def test_run_agent_manual_without_agent_id():
    response = client.post(
        "/api/v1/agents/run",
        json={
            "mode": "manual",
            "objective": "hello",
        },
    )

    assert response.status_code == 400


def test_run_agent_unknown_agent():
    with patch(
        "agents.routes.agent_service.run",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=404,
                detail="Unknown agent",
            )
        ),
    ):
        response = client.post(
            "/api/v1/agents/run",
            json={
                "mode": "manual",
                "agent_id": "does-not-exist",
                "objective": "hello",
            },
        )

    assert response.status_code == 404


def test_run_agent_internal_error():
    with patch(
        "agents.routes.agent_service.run",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=500,
                detail="Agent execution failed",
            )
        ),
    ):
        response = client.post(
            "/api/v1/agents/run",
            json={
                "mode": "manual",
                "agent_id": "coding-agent",
                "objective": "hello",
            },
        )

    assert response.status_code == 500


def test_stream_agent_success():
    async def fake_stream(_request):
        yield '{"type":"status","status":"running"}\n'
        yield '{"type":"done","status":"completed"}\n'

    with patch(
        "agents.routes.agent_service.stream",
        side_effect=fake_stream,
    ) as mocked_stream:
        response = client.post(
            "/api/v1/agents/run/stream",
            json={
                "mode": "manual",
                "agent_id": "coding-agent",
                "objective": "Write hello world",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"

    lines = response.text.strip().splitlines()

    assert lines == [
        '{"type":"status","status":"running"}',
        '{"type":"done","status":"completed"}',
    ]

    mocked_stream.assert_called_once()

    submitted_request = mocked_stream.call_args.args[0]

    assert submitted_request.mode == "manual"
    assert submitted_request.agent_id == "coding-agent"
    assert submitted_request.objective == "Write hello world"
