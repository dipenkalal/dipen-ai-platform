import httpx
import pytest
from gateway.providers.ollama import OllamaProvider
from gateway.schemas import ChatMessage, ChatRequest


class FakeAsyncClient:
    def __init__(
        self,
        *,
        get_response: object | None = None,
        post_response: object | None = None,
        get_error: Exception | None = None,
        post_error: Exception | None = None,
        **_: object,
    ) -> None:
        self.get_response = get_response
        self.post_response = post_response
        self.get_error = get_error
        self.post_error = post_error

        self.get_calls: list[tuple[str, dict[str, object]]] = []
        self.post_calls: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None

    async def get(
        self,
        url: str,
        **kwargs: object,
    ) -> object:
        self.get_calls.append((url, kwargs))

        if self.get_error is not None:
            raise self.get_error

        return self.get_response

    async def post(
        self,
        url: str,
        **kwargs: object,
    ) -> object:
        self.post_calls.append((url, kwargs))

        if self.post_error is not None:
            raise self.post_error

        return self.post_response


class FakeResponse:
    def __init__(
        self,
        *,
        payload: object,
        is_success: bool = True,
        status_error: Exception | None = None,
    ) -> None:
        self._payload = payload
        self.is_success = is_success
        self.status_error = status_error
        self.raise_for_status_calls = 0

    def raise_for_status(self) -> None:
        self.raise_for_status_calls += 1

        if self.status_error is not None:
            raise self.status_error

    def json(self) -> object:
        return self._payload


def make_request(
    *,
    model: str | None = "test-model",
    max_tokens: int | None = 256,
) -> ChatRequest:
    return ChatRequest(
        provider="ollama",
        model=model,
        messages=[
            ChatMessage(
                role="user",
                content="Explain containers.",
            )
        ],
        temperature=0.3,
        max_tokens=max_tokens,
    )


@pytest.mark.asyncio
async def test_health_returns_true_for_successful_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    response = FakeResponse(
        payload={},
        is_success=True,
    )
    client = FakeAsyncClient(
        get_response=response,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )

    result = await provider.health()

    assert result is True
    assert client.get_calls == [
        (
            f"{provider.base_url}/api/tags",
            {},
        )
    ]


@pytest.mark.asyncio
async def test_health_returns_false_for_unsuccessful_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    response = FakeResponse(
        payload={},
        is_success=False,
    )
    client = FakeAsyncClient(
        get_response=response,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )

    assert await provider.health() is False


@pytest.mark.asyncio
async def test_health_returns_false_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    client = FakeAsyncClient(
        get_error=httpx.ConnectError("Connection refused"),
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )

    assert await provider.health() is False


@pytest.mark.asyncio
async def test_list_models_maps_ollama_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()

    response = FakeResponse(
        payload={
            "models": [
                {
                    "name": "qwen3:1.7b",
                    "size": 1_234,
                },
                {
                    "name": "llama3:latest",
                    "size": 5_678,
                },
            ]
        }
    )
    client = FakeAsyncClient(
        get_response=response,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )

    models = await provider.list_models()

    assert len(models) == 2

    assert models[0].provider == "ollama"
    assert models[0].id == "qwen3:1.7b"
    assert models[0].name == "qwen3:1.7b"
    assert models[0].local is True
    assert models[0].available is True
    assert models[0].size_bytes == 1_234

    assert models[1].id == "llama3:latest"
    assert models[1].size_bytes == 5_678

    assert response.raise_for_status_calls == 1


@pytest.mark.asyncio
async def test_list_models_skips_non_dictionary_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()

    response = FakeResponse(
        payload={
            "models": [
                "invalid",
                None,
                123,
                {
                    "name": "valid-model",
                    "size": 999,
                },
            ]
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            get_response=response,
        ),
    )

    models = await provider.list_models()

    assert len(models) == 1
    assert models[0].id == "valid-model"


@pytest.mark.asyncio
async def test_list_models_uses_unknown_for_missing_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()

    response = FakeResponse(
        payload={
            "models": [
                {
                    "size": 123,
                }
            ]
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            get_response=response,
        ),
    )

    models = await provider.list_models()

    assert models[0].id == "unknown"
    assert models[0].name == "unknown"


@pytest.mark.asyncio
async def test_list_models_returns_empty_when_models_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()

    response = FakeResponse(payload={})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            get_response=response,
        ),
    )

    assert await provider.list_models() == []


@pytest.mark.asyncio
async def test_chat_returns_mapped_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeResponse(
        payload={
            "model": "test-model",
            "message": {
                "role": "assistant",
                "content": "  Containers package applications.  ",
            },
            "prompt_eval_count": 10,
            "eval_count": 7,
            "done_reason": "stop",
        }
    )
    client = FakeAsyncClient(
        post_response=response,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )

    perf_counter = iter(
        [
            100.0,
            100.125,
        ]
    )

    monkeypatch.setattr(
        "gateway.providers.ollama.time.perf_counter",
        lambda: next(perf_counter),
    )

    result = await provider.chat(request)

    assert result.provider == "ollama"
    assert result.model == "test-model"
    assert result.message.role == "assistant"
    assert result.message.content == "Containers package applications."

    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 7
    assert result.usage.total_tokens == 17
    assert result.usage.latency_ms == 125.0

    assert response.raise_for_status_calls == 1

    assert client.post_calls == [
        (
            f"{provider.base_url}/api/chat",
            {
                "json": {
                    "model": "test-model",
                    "messages": [
                        {
                            "role": "user",
                            "content": ("Explain containers."),
                        }
                    ],
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 256,
                    },
                }
            },
        )
    ]


@pytest.mark.asyncio
async def test_chat_uses_default_model_when_request_model_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    provider.default_model = "default-model"

    request = make_request(
        model=None,
    )

    response = FakeResponse(
        payload={
            "message": {
                "content": "Default response",
            },
            "prompt_eval_count": 1,
            "eval_count": 2,
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            post_response=response,
        ),
    )

    result = await provider.chat(request)

    assert result.model == "default-model"


@pytest.mark.asyncio
async def test_chat_handles_non_dictionary_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeResponse(
        payload={
            "model": "test-model",
            "message": "not-a-dictionary",
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            post_response=response,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="returned an empty response",
    ):
        await provider.chat(request)


@pytest.mark.asyncio
async def test_chat_raises_reasoning_token_budget_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeResponse(
        payload={
            "model": "reasoning-model",
            "message": {
                "content": "",
                "thinking": "Internal reasoning",
            },
            "done_reason": "length",
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            post_response=response,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="exhausted its token budget",
    ):
        await provider.chat(request)


@pytest.mark.asyncio
async def test_chat_raises_normal_token_limit_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeResponse(
        payload={
            "model": "limited-model",
            "message": {
                "content": "   ",
            },
            "done_reason": "length",
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            post_response=response,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="reached its token limit",
    ):
        await provider.chat(request)


@pytest.mark.asyncio
async def test_chat_raises_thinking_without_answer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeResponse(
        payload={
            "model": "thinking-model",
            "message": {
                "content": "",
                "thinking": "Reasoning only",
            },
            "done_reason": "stop",
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            post_response=response,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="returned reasoning output",
    ):
        await provider.chat(request)


@pytest.mark.asyncio
async def test_chat_raises_generic_empty_response_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeResponse(
        payload={
            "model": "empty-model",
            "message": {
                "content": "",
            },
            "done_reason": "stop",
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            post_response=response,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="returned an empty response",
    ):
        await provider.chat(request)


@pytest.mark.asyncio
async def test_chat_sets_total_tokens_none_when_count_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()
    request = make_request()

    response = FakeResponse(
        payload={
            "model": "test-model",
            "message": {
                "content": "Hello",
            },
            "prompt_eval_count": 10,
            "eval_count": None,
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            post_response=response,
        ),
    )

    result = await provider.chat(request)

    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens is None
    assert result.usage.total_tokens is None


@pytest.mark.asyncio
async def test_chat_propagates_http_status_error(
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
    )
    expected = httpx.HTTPStatusError(
        "Server error",
        request=http_request,
        response=http_response,
    )

    response = FakeResponse(
        payload={},
        status_error=expected,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            post_response=response,
        ),
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await provider.chat(request)

    assert exc_info.value is expected
