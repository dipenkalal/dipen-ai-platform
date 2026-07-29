from typing import Any

import collectors.ollama as ollama_collector
import httpx
import pytest


class FakeResponse:
    def __init__(
        self,
        *,
        payload: Any = None,
        status_error: Exception | None = None,
        json_error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.status_error = status_error
        self.json_error = json_error
        self.raise_for_status_calls = 0

    def raise_for_status(self) -> None:
        self.raise_for_status_calls += 1

        if self.status_error is not None:
            raise self.status_error

    def json(self) -> Any:
        if self.json_error is not None:
            raise self.json_error

        return self.payload


class FakeAsyncClient:
    def __init__(
        self,
        *,
        response: FakeResponse | None = None,
        get_error: Exception | None = None,
        **_: object,
    ) -> None:
        self.response = response
        self.get_error = get_error
        self.get_calls: list[str] = []

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None

    async def get(self, url: str) -> FakeResponse:
        self.get_calls.append(url)

        if self.get_error is not None:
            raise self.get_error

        assert self.response is not None
        return self.response


@pytest.mark.asyncio
async def test_get_ollama_status_returns_loaded_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(
        payload={
            "models": [
                {
                    "name": "qwen3:1.7b",
                    "size": 1_234,
                    "size_vram": 1_000,
                    "expires_at": "2026-07-28T12:00:00Z",
                    "ignored": "value",
                },
                {
                    "name": "llama3:latest",
                    "size": 5_678,
                    "size_vram": 4_500,
                    "expires_at": "2026-07-28T13:00:00Z",
                },
            ]
        }
    )
    client = FakeAsyncClient(response=response)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )
    monkeypatch.setattr(
        ollama_collector,
        "OLLAMA_BASE_URL",
        "http://ollama.test:11434",
    )

    result = await ollama_collector.get_ollama_status()

    assert result == {
        "online": True,
        "loaded_count": 2,
        "loaded_models": [
            {
                "name": "qwen3:1.7b",
                "size": 1_234,
                "size_vram": 1_000,
                "expires_at": "2026-07-28T12:00:00Z",
            },
            {
                "name": "llama3:latest",
                "size": 5_678,
                "size_vram": 4_500,
                "expires_at": "2026-07-28T13:00:00Z",
            },
        ],
    }

    assert client.get_calls == ["http://ollama.test:11434/api/ps"]
    assert response.raise_for_status_calls == 1


@pytest.mark.asyncio
async def test_get_ollama_status_returns_empty_loaded_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(
        payload={
            "models": [],
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            response=response,
        ),
    )

    result = await ollama_collector.get_ollama_status()

    assert result == {
        "online": True,
        "loaded_count": 0,
        "loaded_models": [],
    }


@pytest.mark.asyncio
async def test_get_ollama_status_uses_empty_list_when_models_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(payload={})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            response=response,
        ),
    )

    result = await ollama_collector.get_ollama_status()

    assert result == {
        "online": True,
        "loaded_count": 0,
        "loaded_models": [],
    }


@pytest.mark.asyncio
async def test_get_ollama_status_preserves_missing_model_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(
        payload={
            "models": [
                {},
                {
                    "name": "partial-model",
                },
            ]
        }
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            response=response,
        ),
    )

    result = await ollama_collector.get_ollama_status()

    assert result["loaded_count"] == 2
    assert result["loaded_models"] == [
        {
            "name": None,
            "size": None,
            "size_vram": None,
            "expires_at": None,
        },
        {
            "name": "partial-model",
            "size": None,
            "size_vram": None,
            "expires_at": None,
        },
    ]


@pytest.mark.asyncio
async def test_get_ollama_status_returns_offline_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = httpx.ConnectError("Connection refused")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            get_error=error,
        ),
    )

    result = await ollama_collector.get_ollama_status()

    assert result == {
        "online": False,
        "loaded_count": 0,
        "loaded_models": [],
        "error": "Connection refused",
    }


@pytest.mark.asyncio
async def test_get_ollama_status_returns_offline_on_status_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request(
        "GET",
        f"{ollama_collector.OLLAMA_BASE_URL}/api/ps",
    )
    http_response = httpx.Response(
        status_code=500,
        request=request,
    )
    error = httpx.HTTPStatusError(
        "Server error",
        request=request,
        response=http_response,
    )

    response = FakeResponse(
        payload={},
        status_error=error,
    )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            response=response,
        ),
    )

    result = await ollama_collector.get_ollama_status()

    assert result["online"] is False
    assert result["loaded_count"] == 0
    assert result["loaded_models"] == []
    assert "Server error" in result["error"]


@pytest.mark.asyncio
async def test_get_ollama_status_returns_offline_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(json_error=ValueError("Invalid JSON"))

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            response=response,
        ),
    )

    result = await ollama_collector.get_ollama_status()

    assert result == {
        "online": False,
        "loaded_count": 0,
        "loaded_models": [],
        "error": "Invalid JSON",
    }
