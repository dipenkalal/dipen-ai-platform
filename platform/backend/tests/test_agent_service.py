import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Literal
from unittest.mock import AsyncMock

import agents.service as service_module
import pytest
from agents.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStep,
    AgentUsage,
)
from agents.service import AgentService
from fastapi import HTTPException


def make_request(
    *,
    mode: Literal["smart", "manual"] = "manual",
    agent_id: str | None = "coding-agent",
    model: str | None = "test-model",
) -> AgentRunRequest:
    return AgentRunRequest(
        mode=mode,
        agent_id=agent_id,
        objective="Test the agent service",
        provider="ollama",
        model=model,
        temperature=0.0,
        max_tokens=256,
        max_steps=4,
    )


def make_response(
    *,
    status: Literal[
        "queued",
        "running",
        "completed",
        "failed",
    ] = "completed",
    answer: str = "Agent response",
) -> AgentRunResponse:
    now = datetime.now(UTC)

    step = AgentStep(
        step_number=1,
        type="result",
        title="Execution completed",
        success=True,
        output={
            "answer": answer,
        },
        started_at=now,
        completed_at=now,
    )

    return AgentRunResponse(
        run_id="run-123",
        agent_id="coding-agent",
        objective="Test the agent service",
        status=status,
        answer=answer,
        steps=[step],
        sources=[
            {
                "title": "Test source",
            }
        ],
        usage=AgentUsage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=12.5,
        ),
        started_at=now,
        completed_at=now,
    )


def test_list_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()

    expected = [
        SimpleNamespace(
            id="coding-agent",
        )
    ]

    monkeypatch.setattr(
        service_module.agent_registry,
        "list",
        lambda: expected,
    )

    assert service.list_agents() == expected


def test_list_tools_returns_serialised_definitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()

    class FakeDefinition:
        def model_dump(self) -> dict[str, Any]:
            return {
                "id": "system.status",
                "name": "System Status",
            }

    monkeypatch.setattr(
        service_module.tool_registry,
        "list_definitions",
        lambda: [FakeDefinition()],
    )

    assert service.list_tools() == [
        {
            "id": "system.status",
            "name": "System Status",
        }
    ]


def test_resolve_smart_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()

    route = SimpleNamespace(
        agent_id="devops-agent",
        model="routed-model",
        confidence=0.95,
        reason="DevOps keywords detected",
    )

    monkeypatch.setattr(
        service_module.agent_router,
        "route",
        lambda request: route,
    )

    request = make_request(
        mode="smart",
        agent_id=None,
        model=None,
    )

    resolved, returned_route = service.resolve_request(request)

    assert returned_route is route
    assert resolved.agent_id == "devops-agent"
    assert resolved.model == "routed-model"

    # The original request must remain unchanged.
    assert request.agent_id is None
    assert request.model is None


def test_resolve_manual_request_uses_recommended_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()

    agent = SimpleNamespace(
        recommended_model="recommended-model",
    )

    monkeypatch.setattr(
        service_module.agent_registry,
        "get",
        lambda agent_id: agent,
    )

    request = make_request(
        mode="manual",
        model=None,
    )

    resolved, route = service.resolve_request(request)

    assert route is None
    assert resolved.agent_id == "coding-agent"
    assert resolved.model == "recommended-model"


def test_resolve_manual_request_requires_agent_id() -> None:
    service = AgentService()

    request = make_request(
        mode="manual",
        agent_id=None,
    )

    with pytest.raises(
        ValueError,
        match="agent_id is required in manual mode",
    ):
        service.resolve_request(request)


@pytest.mark.asyncio
async def test_run_returns_response_and_saves_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()
    request = make_request()
    response = make_response()

    executor_run = AsyncMock(
        return_value=response,
    )

    saved: dict[str, Any] = {}

    def fake_save(
        *,
        request: AgentRunRequest,
        response: AgentRunResponse,
        error: str | None,
    ) -> None:
        saved["request"] = request
        saved["response"] = response
        saved["error"] = error

    monkeypatch.setattr(
        service_module.agent_executor,
        "run",
        executor_run,
    )

    monkeypatch.setattr(
        service_module.agent_run_history_service,
        "save",
        fake_save,
    )

    result = await service.run(request)

    assert result is response

    executor_run.assert_awaited_once()

    assert executor_run.await_args is not None

    resolved_request = executor_run.await_args.args[0]

    assert resolved_request.agent_id == "coding-agent"
    assert saved["request"] is resolved_request
    assert saved["response"] is response
    assert saved["error"] is None


@pytest.mark.asyncio
async def test_run_saves_failed_answer_as_history_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()
    request = make_request()

    response = make_response(
        status="failed",
        answer="Execution failed",
    )

    monkeypatch.setattr(
        service_module.agent_executor,
        "run",
        AsyncMock(return_value=response),
    )

    saved: dict[str, Any] = {}

    def fake_save(
        *,
        request: AgentRunRequest,
        response: AgentRunResponse,
        error: str | None,
    ) -> None:
        saved["error"] = error

    monkeypatch.setattr(
        service_module.agent_run_history_service,
        "save",
        fake_save,
    )

    result = await service.run(request)

    assert result.status == "failed"
    assert saved["error"] == "Execution failed"


@pytest.mark.asyncio
async def test_run_converts_key_error_to_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()

    monkeypatch.setattr(
        service_module.agent_registry,
        "get",
        lambda agent_id: (_ for _ in ()).throw(KeyError("Unknown agent")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.run(make_request())

    assert exc_info.value.status_code == 404
    assert "Unknown agent" in exc_info.value.detail


@pytest.mark.asyncio
async def test_run_converts_value_error_to_400() -> None:
    service = AgentService()

    request = make_request(
        agent_id=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.run(request)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == ("agent_id is required in manual mode")


@pytest.mark.asyncio
async def test_run_preserves_http_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()

    expected = HTTPException(
        status_code=409,
        detail="Execution conflict",
    )

    monkeypatch.setattr(
        service,
        "resolve_request",
        lambda request: (_ for _ in ()).throw(expected),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.run(make_request())

    assert exc_info.value is expected
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_run_converts_unexpected_error_to_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()

    monkeypatch.setattr(
        service_module.agent_executor,
        "run",
        AsyncMock(side_effect=RuntimeError("Gateway unavailable")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.run(make_request())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == (
        "Agent execution failed: Gateway unavailable"
    )


@pytest.mark.asyncio
async def test_stream_smart_request_emits_all_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()
    response = make_response()

    route = SimpleNamespace(
        agent_id="coding-agent",
        model="test-model",
        confidence=0.91,
        reason="Coding request detected",
    )

    monkeypatch.setattr(
        service_module.agent_router,
        "route",
        lambda request: route,
    )

    executor_run = AsyncMock(
        return_value=response,
    )

    monkeypatch.setattr(
        service_module.agent_executor,
        "run",
        executor_run,
    )

    saved: dict[str, Any] = {}

    def fake_save(
        *,
        request: AgentRunRequest,
        response: AgentRunResponse,
        error: str | None,
    ) -> None:
        saved["request"] = request
        saved["response"] = response
        saved["error"] = error

    monkeypatch.setattr(
        service_module.agent_run_history_service,
        "save",
        fake_save,
    )

    request = make_request(
        mode="smart",
        agent_id=None,
        model=None,
    )

    events = [json.loads(chunk) async for chunk in service.stream(request)]

    assert [event["type"] for event in events] == [
        "routing",
        "status",
        "step",
        "answer",
        "done",
    ]

    routing_event = events[0]

    assert routing_event["agent_id"] == "coding-agent"
    assert routing_event["model"] == "test-model"
    assert routing_event["confidence"] == 0.91

    status_event = events[1]

    assert status_event["status"] == "running"
    assert status_event["agent_id"] == "coding-agent"

    step_event = events[2]

    assert step_event["step"]["type"] == "result"
    assert step_event["step"]["success"] is True

    answer_event = events[3]

    assert answer_event["content"] == "Agent response"
    assert answer_event["sources"] == [
        {
            "title": "Test source",
        }
    ]

    done_event = events[4]

    assert done_event["run"]["run_id"] == "run-123"
    assert done_event["run"]["status"] == "completed"

    executor_run.assert_awaited_once()

    assert saved["response"] is response
    assert saved["error"] is None


@pytest.mark.asyncio
async def test_stream_emits_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AgentService()

    monkeypatch.setattr(
        service_module.agent_executor,
        "run",
        AsyncMock(side_effect=RuntimeError("Model unavailable")),
    )

    events = [
        json.loads(chunk) async for chunk in service.stream(make_request())
    ]

    # The running status is emitted before execution fails.
    assert events[0]["type"] == "status"
    assert events[0]["status"] == "running"

    error_event = events[-1]

    assert error_event["type"] == "error"
    assert error_event["error"] == (
        "Agent execution failed: Model unavailable"
    )
    assert error_event["message"] == (
        "Agent execution failed: Model unavailable"
    )
