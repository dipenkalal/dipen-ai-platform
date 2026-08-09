from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agents.executor import (
    AgentExecutor,
    gateway_service,
    tool_registry,
)
from agents.registry import agent_registry
from agents.schemas import AgentRunRequest
from agents.service import (
    AgentService,
    agent_router,
)
from gateway.schemas import ChatRequest


def test_supplemental_context_is_bounded() -> None:
    with pytest.raises(ValidationError):
        AgentRunRequest(
            objective="review this",
            supplemental_context=("x" * 12001),
        )


def test_smart_router_never_receives_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, AgentRunRequest] = {}

    def fake_route(
        request: AgentRunRequest,
    ) -> SimpleNamespace:
        observed["request"] = request

        return SimpleNamespace(
            agent_id="coding-agent",
            model="qwen3:1.7b",
            confidence=0.91,
            reason="test route",
            matched_terms=[],
            candidate_scores={
                "coding-agent": 1,
            },
            routing_latency_ms=1.0,
        )

    monkeypatch.setattr(
        agent_router,
        "route",
        fake_route,
    )

    request = AgentRunRequest(
        mode="smart",
        objective="analyse the attached file",
        supplemental_context=("PRIVATE ATTACHMENT CONTEXT"),
    )

    resolved, route = AgentService().resolve_request(request)

    routed_request = observed["request"]

    assert route is not None
    assert routed_request.objective == request.objective
    assert routed_request.supplemental_context is None
    assert resolved.supplemental_context == "PRIVATE ATTACHMENT CONTEXT"


@pytest.mark.asyncio
async def test_generation_receives_context_as_untrusted_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = AgentExecutor()

    captured: dict[str, object] = {}

    async def fake_chat(
        request: ChatRequest,
    ) -> object:
        captured["request"] = request
        return object()

    monkeypatch.setattr(
        gateway_service,
        "chat",
        fake_chat,
    )

    request = AgentRunRequest(
        mode="manual",
        agent_id="coding-agent",
        objective="review this file",
        supplemental_context=("ATTACHMENT FACT 123"),
        model="qwen3:1.7b",
    )

    await executor._chat(
        request=request,
        system_prompt="SYSTEM PROMPT",
        user_content="USER OBJECTIVE",
    )

    chat_request = captured["request"]

    assert isinstance(
        chat_request,
        ChatRequest,
    )

    normalized_system_prompt = " ".join(
        chat_request.messages[0].content.lower().split()
    )

    assert "untrusted reference material" in normalized_system_prompt

    assert "USER OBJECTIVE" in chat_request.messages[1].content

    assert "ATTACHMENT FACT 123" in chat_request.messages[1].content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "agent_id",
        "dispatch_name",
    ),
    [
        (
            "knowledge-agent",
            "_dispatch_knowledge_agent",
        ),
        (
            "research-agent",
            "_dispatch_research_agent",
        ),
    ],
)
async def test_scoped_context_bypasses_global_knowledge(
    monkeypatch: pytest.MonkeyPatch,
    agent_id: str,
    dispatch_name: str,
) -> None:
    executor = AgentExecutor()
    sentinel = object()

    async def fake_prompt_agent(
        **kwargs: object,
    ) -> object:
        prompt_request = kwargs["request"]

        assert isinstance(
            prompt_request,
            AgentRunRequest,
        )

        assert prompt_request.supplemental_context == "message-scoped context"

        return sentinel

    def fail_tool_lookup(
        _tool_id: str,
    ) -> object:
        raise AssertionError(
            "Global Knowledge lookup must not run for scoped attachment context."
        )

    monkeypatch.setattr(
        executor,
        "_run_prompt_agent",
        fake_prompt_agent,
    )

    monkeypatch.setattr(
        tool_registry,
        "get",
        fail_tool_lookup,
    )

    request = AgentRunRequest(
        mode="manual",
        agent_id=agent_id,
        objective="analyse attached evidence",
        supplemental_context=("message-scoped context"),
        model="qwen3:1.7b",
    )

    agent = agent_registry.get(agent_id)

    dispatch = getattr(
        executor,
        dispatch_name,
    )

    result = await dispatch(
        request=request,
        agent=agent,
        run_id="test-run",
        started_at=datetime.now(timezone.utc),
        timer_started=0.0,
        steps=[],
    )

    assert result is sentinel


def test_history_request_redacts_supplemental_context() -> None:
    request = AgentRunRequest(
        mode="manual",
        agent_id="coding-agent",
        objective="analyse attached evidence",
        supplemental_context=("SENSITIVE MESSAGE-SCOPED EXCERPT"),
    )

    history_request = AgentService._request_for_history(request)

    assert request.supplemental_context == "SENSITIVE MESSAGE-SCOPED EXCERPT"

    assert history_request.supplemental_context is None

    assert history_request.objective == request.objective

    assert "SENSITIVE MESSAGE-SCOPED EXCERPT" not in str(
        history_request.model_dump(mode="json")
    )
