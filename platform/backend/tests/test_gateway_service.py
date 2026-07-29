from collections.abc import AsyncIterator
from typing import Literal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from gateway.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ModelInfo,
    UsageMetrics,
)
from gateway.service import GatewayService
from pydantic import ValidationError


def make_request(
    *,
    provider: Literal["auto", "ollama"] = "auto",
) -> ChatRequest:
    return ChatRequest(
        provider=provider,
        model="test-model",
        messages=[
            ChatMessage(
                role="user",
                content="Hello",
            )
        ],
        temperature=0.0,
        max_tokens=128,
    )


def make_response() -> ChatResponse:
    return ChatResponse(
        provider="ollama",
        model="test-model",
        message=ChatMessage(
            role="assistant",
            content="Hello from Ollama",
        ),
        usage=UsageMetrics(
            prompt_tokens=5,
            completion_tokens=4,
            total_tokens=9,
            latency_ms=12.5,
        ),
    )


def make_models() -> list[ModelInfo]:
    return [
        ModelInfo(
            provider="ollama",
            id="test-model",
            name="Test Model",
            local=True,
            available=True,
            size_bytes=1024,
        )
    ]


@pytest.mark.asyncio
async def test_list_models_returns_provider_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()
    expected = make_models()

    list_models = AsyncMock(
        return_value=expected,
    )

    monkeypatch.setattr(
        service.ollama,
        "list_models",
        list_models,
    )

    result = await service.list_models()

    assert result == expected
    list_models.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_list_models_converts_failure_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()

    monkeypatch.setattr(
        service.ollama,
        "list_models",
        AsyncMock(side_effect=RuntimeError("Connection refused")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.list_models()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == (
        "Unable to retrieve Ollama models: Connection refused"
    )


@pytest.mark.asyncio
async def test_chat_delegates_to_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()
    request = make_request(
        provider="ollama",
    )
    response = make_response()

    health = AsyncMock(
        return_value=True,
    )
    chat = AsyncMock(
        return_value=response,
    )

    monkeypatch.setattr(
        service.ollama,
        "health",
        health,
    )
    monkeypatch.setattr(
        service.ollama,
        "chat",
        chat,
    )

    result = await service.chat(request)

    assert result is response
    health.assert_awaited_once_with()
    chat.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_chat_accepts_auto_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()
    request = make_request(
        provider="auto",
    )
    response = make_response()

    monkeypatch.setattr(
        service.ollama,
        "health",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        service.ollama,
        "chat",
        AsyncMock(return_value=response),
    )

    result = await service.chat(request)

    assert result == response


@pytest.mark.asyncio
async def test_chat_rejects_unsupported_provider() -> None:
    service = GatewayService()

    # ChatRequest restricts provider using Literal,
    # so bypass validation to exercise the service branch.
    request = make_request().model_copy(
        update={
            "provider": "openai",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.chat(request)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == ("Unsupported provider: openai")


@pytest.mark.asyncio
async def test_chat_returns_503_when_ollama_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()
    request = make_request()

    monkeypatch.setattr(
        service.ollama,
        "health",
        AsyncMock(return_value=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.chat(request)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == ("Ollama provider is unavailable")


@pytest.mark.asyncio
async def test_chat_preserves_provider_http_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()
    request = make_request()

    expected = HTTPException(
        status_code=429,
        detail="Too many requests",
    )

    monkeypatch.setattr(
        service.ollama,
        "health",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        service.ollama,
        "chat",
        AsyncMock(side_effect=expected),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.chat(request)

    assert exc_info.value is expected
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_chat_converts_provider_failure_to_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()
    request = make_request()

    monkeypatch.setattr(
        service.ollama,
        "health",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        service.ollama,
        "chat",
        AsyncMock(side_effect=RuntimeError("Generation failed")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.chat(request)

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == (
        "Ollama request failed: Generation failed"
    )


@pytest.mark.asyncio
async def test_stream_chat_yields_provider_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()
    request = make_request()

    monkeypatch.setattr(
        service.ollama,
        "health",
        AsyncMock(return_value=True),
    )

    async def fake_stream_chat(
        request: ChatRequest,
    ) -> AsyncIterator[str]:
        yield '{"type":"token","content":"Hello"}\n'
        yield '{"type":"done"}\n'

    monkeypatch.setattr(
        service.ollama,
        "stream_chat",
        fake_stream_chat,
    )

    events = [event async for event in service.stream_chat(request)]

    assert events == [
        '{"type":"token","content":"Hello"}\n',
        '{"type":"done"}\n',
    ]


@pytest.mark.asyncio
async def test_stream_chat_rejects_unsupported_provider() -> None:
    service = GatewayService()

    request = make_request().model_copy(
        update={
            "provider": "openai",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        [event async for event in service.stream_chat(request)]

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == ("Unsupported provider: openai")


@pytest.mark.asyncio
async def test_stream_chat_returns_503_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewayService()
    request = make_request()

    monkeypatch.setattr(
        service.ollama,
        "health",
        AsyncMock(return_value=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        [event async for event in service.stream_chat(request)]

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == ("Ollama provider is unavailable")


def test_chat_request_rejects_invalid_provider() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(
            provider="openai",  # type: ignore[arg-type]
            messages=[
                ChatMessage(
                    role="user",
                    content="Hello",
                )
            ],
        )
