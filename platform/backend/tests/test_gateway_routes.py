from collections.abc import AsyncIterator
from typing import Any

import gateway.routes as routes
import pytest
from fastapi.responses import StreamingResponse
from gateway.schemas import ChatMessage, ChatRequest


@pytest.mark.asyncio
async def test_list_models_returns_models_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_models() -> list[Any]:
        return []

    monkeypatch.setattr(
        routes.gateway_service,
        "list_models",
        fake_list_models,
    )

    response = await routes.list_models()

    assert response.models == []


@pytest.mark.asyncio
async def test_chat_forces_stream_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    expected = object()

    async def fake_chat(request: ChatRequest) -> object:
        captured["request"] = request
        return expected

    monkeypatch.setattr(
        routes.gateway_service,
        "chat",
        fake_chat,
    )

    request = ChatRequest(
        provider="ollama",
        model="qwen3",
        stream=True,
        messages=[
            ChatMessage(
                role="user",
                content="Hi",
            )
        ],
    )

    result = await routes.chat(request)

    assert result is expected
    assert request.stream is False
    assert captured["request"] is request


@pytest.mark.asyncio
async def test_stream_chat_returns_streaming_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_generator() -> AsyncIterator[str]:
        yield '{"type":"content","content":"Hello"}\n'

    def fake_stream_chat(
        request: ChatRequest,
    ) -> AsyncIterator[str]:
        captured["request"] = request
        return fake_generator()

    monkeypatch.setattr(
        routes.gateway_service,
        "stream_chat",
        fake_stream_chat,
    )

    request = ChatRequest(
        provider="ollama",
        model="qwen3",
        stream=False,
        messages=[
            ChatMessage(
                role="user",
                content="Hello",
            )
        ],
    )

    response = await routes.stream_chat(request)

    assert isinstance(response, StreamingResponse)
    assert request.stream is True
    assert captured["request"] is request
    assert response.media_type == "application/x-ndjson"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
