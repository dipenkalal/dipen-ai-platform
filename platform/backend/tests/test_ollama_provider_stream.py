import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from gateway.providers.ollama import OllamaProvider
from gateway.schemas import ChatMessage, ChatRequest


class FakeStreamResponse:
    def __init__(
        self,
        *,
        lines: list[str] | None = None,
        status_error: Exception | None = None,
    ) -> None:
        self.lines = lines or []
        self.status_error = status_error
        self.raise_for_status_calls = 0

    async def __aenter__(self) -> FakeStreamResponse:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None

    def raise_for_status(self) -> None:
        self.raise_for_status_calls += 1

        if self.status_error is not None:
            raise self.status_error

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self.lines:
            yield line


class FakeAsyncClient:
    def __init__(
        self,
        *,
        stream_response: FakeStreamResponse | None = None,
        stream_error: Exception | None = None,
        **_: object,
    ) -> None:
        self.stream_response = stream_response
        self.stream_error = stream_error

        self.stream_calls: list[tuple[str, str, dict[str, Any]]] = []

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None

    def stream(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> FakeStreamResponse:
        self.stream_calls.append(
            (
                method,
                url,
                kwargs,
            )
        )

        if self.stream_error is not None:
            raise self.stream_error

        assert self.stream_response is not None
        return self.stream_response


def make_request(
    *,
    model: str | None = "test-model",
    max_tokens: int | None = 128,
) -> ChatRequest:
    return ChatRequest(
        provider="ollama",
        model=model,
        messages=[
            ChatMessage(
                role="user",
                content="Explain Docker.",
            )
        ],
        temperature=0.2,
        max_tokens=max_tokens,
        stream=True,
    )


async def collect_events(
    provider: OllamaProvider,
    request: ChatRequest,
) -> list[dict[str, Any]]:
    raw_events = [event async for event in provider.stream_chat(request)]

    return [json.loads(event) for event in raw_events]


@pytest.mark.asyncio
async def test_stream_chat_yields_content_and_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeStreamResponse(
        lines=[
            "",
            json.dumps(
                {
                    "message": {
                        "content": "Docker ",
                    },
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "message": {
                        "content": "runs containers.",
                    },
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "model": "test-model",
                    "message": {
                        "content": "",
                    },
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 8,
                    "eval_count": 4,
                }
            ),
        ]
    )
    client = FakeAsyncClient(
        stream_response=response,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )

    perf_counter = iter(
        [
            10.0,
            10.250,
        ]
    )
    monkeypatch.setattr(
        "gateway.providers.ollama.time.perf_counter",
        lambda: next(perf_counter),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events == [
        {
            "type": "content",
            "content": "Docker ",
        },
        {
            "type": "content",
            "content": "runs containers.",
        },
        {
            "type": "done",
            "provider": "ollama",
            "model": "test-model",
            "done_reason": "stop",
            "usage": {
                "prompt_tokens": 8,
                "completion_tokens": 4,
                "total_tokens": 12,
                "latency_ms": 250.0,
            },
        },
    ]

    assert response.raise_for_status_calls == 1

    assert client.stream_calls == [
        (
            "POST",
            f"{provider.base_url}/api/chat",
            {
                "json": {
                    "model": "test-model",
                    "messages": [
                        {
                            "role": "user",
                            "content": "Explain Docker.",
                        }
                    ],
                    "stream": True,
                    "think": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 128,
                    },
                }
            },
        )
    ]


@pytest.mark.asyncio
async def test_stream_chat_skips_blank_and_invalid_json_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeStreamResponse(
        lines=[
            "",
            "not-json",
            "{broken-json",
            json.dumps(
                {
                    "message": {
                        "content": "Valid",
                    },
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "message": {},
                    "done": True,
                }
            ),
        ]
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events[0] == {
        "type": "content",
        "content": "Valid",
    }
    assert events[1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_chat_ignores_non_dictionary_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeStreamResponse(
        lines=[
            json.dumps(
                {
                    "message": "invalid-message",
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "model": "test-model",
                    "message": {
                        "content": "Answer",
                    },
                    "done": True,
                }
            ),
        ]
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events[0] == {
        "type": "content",
        "content": "Answer",
    }
    assert events[1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_chat_tracks_thinking_without_emitting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeStreamResponse(
        lines=[
            json.dumps(
                {
                    "message": {
                        "thinking": "Internal reasoning",
                    },
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "model": "thinking-model",
                    "message": {},
                    "done": True,
                    "done_reason": "stop",
                }
            ),
        ]
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "returned reasoning output" in events[0]["error"]


@pytest.mark.asyncio
async def test_stream_chat_returns_reasoning_budget_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeStreamResponse(
        lines=[
            json.dumps(
                {
                    "message": {
                        "thinking": "Reasoning",
                    },
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "model": "reasoning-model",
                    "message": {},
                    "done": True,
                    "done_reason": "length",
                }
            ),
        ]
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "exhausted its token budget" in events[0]["error"]


@pytest.mark.asyncio
async def test_stream_chat_returns_normal_token_limit_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeStreamResponse(
        lines=[
            json.dumps(
                {
                    "model": "limited-model",
                    "message": {},
                    "done": True,
                    "done_reason": "length",
                }
            ),
        ]
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "reached its token limit" in events[0]["error"]


@pytest.mark.asyncio
async def test_stream_chat_returns_generic_empty_response_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeStreamResponse(
        lines=[
            json.dumps(
                {
                    "model": "empty-model",
                    "message": {},
                    "done": True,
                    "done_reason": "stop",
                }
            ),
        ]
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert len(events) == 1
    assert events[0] == {
        "type": "error",
        "error": ("Model 'empty-model' returned an empty response."),
    }


@pytest.mark.asyncio
async def test_stream_chat_uses_default_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    provider.default_model = "default-model"

    request = make_request(
        model=None,
    )

    response = FakeStreamResponse(
        lines=[
            json.dumps(
                {
                    "message": {
                        "content": "Hello",
                    },
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "message": {},
                    "done": True,
                }
            ),
        ]
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events[-1]["model"] == "default-model"


@pytest.mark.asyncio
async def test_stream_chat_sets_total_tokens_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeStreamResponse(
        lines=[
            json.dumps(
                {
                    "message": {
                        "content": "Hello",
                    },
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "message": {},
                    "done": True,
                    "prompt_eval_count": 5,
                    "eval_count": None,
                }
            ),
        ]
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events[-1]["usage"]["total_tokens"] is None


@pytest.mark.asyncio
async def test_stream_chat_formats_http_status_error_with_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    http_request = httpx.Request(
        "POST",
        f"{provider.base_url}/api/chat",
    )
    http_response = httpx.Response(
        status_code=500,
        request=http_request,
        text="Internal Ollama failure",
    )
    status_error = httpx.HTTPStatusError(
        "Server error",
        request=http_request,
        response=http_response,
    )

    response = FakeStreamResponse(
        status_error=status_error,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events == [
        {
            "type": "error",
            "error": ("Ollama returned HTTP 500: Internal Ollama failure"),
        }
    ]


@pytest.mark.asyncio
async def test_stream_chat_formats_http_status_error_without_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    http_request = httpx.Request(
        "POST",
        f"{provider.base_url}/api/chat",
    )
    http_response = httpx.Response(
        status_code=404,
        request=http_request,
        text="",
    )
    status_error = httpx.HTTPStatusError(
        "Not found",
        request=http_request,
        response=http_response,
    )

    response = FakeStreamResponse(
        status_error=status_error,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events == [
        {
            "type": "error",
            "error": "Ollama returned HTTP 404",
        }
    ]


@pytest.mark.asyncio
async def test_stream_chat_handles_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_error=httpx.ConnectError("Connection refused"),
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events == [
        {
            "type": "error",
            "error": ("Ollama connection failed: Connection refused"),
        }
    ]


@pytest.mark.asyncio
async def test_stream_chat_handles_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_error=RuntimeError("Unexpected failure"),
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events == [
        {
            "type": "error",
            "error": ("Ollama generation failed: Unexpected failure"),
        }
    ]


@pytest.mark.asyncio
async def test_stream_chat_truncates_long_http_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    long_body = "x" * 700

    http_request = httpx.Request(
        "POST",
        f"{provider.base_url}/api/chat",
    )
    http_response = httpx.Response(
        status_code=500,
        request=http_request,
        text=long_body,
    )
    status_error = httpx.HTTPStatusError(
        "Server error",
        request=http_request,
        response=http_response,
    )

    response = FakeStreamResponse(
        status_error=status_error,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    error = events[0]["error"]

    assert error.startswith("Ollama returned HTTP 500: ")
    assert error.endswith("x" * 500)
    assert len(error.split(": ", 1)[1]) == 500


@pytest.mark.asyncio
async def test_stream_chat_handles_failure_reading_http_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    http_request = httpx.Request(
        "POST",
        f"{provider.base_url}/api/chat",
    )

    class BrokenTextResponse:
        status_code = 503

        @property
        def text(self) -> str:
            raise RuntimeError("Unable to read response body")

    status_error = httpx.HTTPStatusError(
        "Service unavailable",
        request=http_request,
        response=BrokenTextResponse(),  # type: ignore[arg-type]
    )

    response = FakeStreamResponse(
        status_error=status_error,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            stream_response=response,
        ),
    )

    events = await collect_events(
        provider,
        request,
    )

    assert events == [
        {
            "type": "error",
            "error": "Ollama returned HTTP 503",
        }
    ]
