import httpx
import knowledge.services.embeddings as embeddings_module
import pytest
from knowledge.services.embeddings import EmbeddingService


class FakeResponse:
    def __init__(
        self,
        *,
        is_success=True,
        json_data=None,
        status_error=None,
    ):
        self.is_success = is_success
        self._json_data = json_data
        self._status_error = status_error
        self.raise_for_status_called = False

    def raise_for_status(self):
        self.raise_for_status_called = True

        if self._status_error is not None:
            raise self._status_error

    def json(self):
        return self._json_data


class FakeAsyncClient:
    def __init__(
        self,
        *,
        timeout,
        get_response=None,
        post_response=None,
        get_error=None,
    ):
        self.timeout = timeout
        self.get_response = get_response
        self.post_response = post_response
        self.get_error = get_error
        self.get_calls = []
        self.post_calls = []
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        self.exited = True

    async def get(self, url):
        self.get_calls.append(url)

        if self.get_error is not None:
            raise self.get_error

        return self.get_response

    async def post(
        self,
        url,
        json,
    ):
        self.post_calls.append(
            {
                "url": url,
                "json": json,
            }
        )

        return self.post_response


def test_embedding_service_initialization(monkeypatch):
    monkeypatch.setattr(
        embeddings_module,
        "OLLAMA_BASE_URL",
        "http://ollama.test",
    )
    monkeypatch.setattr(
        embeddings_module,
        "OLLAMA_EMBEDDING_MODEL",
        "test-embedding-model",
    )

    service = EmbeddingService()

    assert service.base_url == "http://ollama.test"
    assert service.model == "test-embedding-model"
    assert isinstance(service.timeout, httpx.Timeout)

    assert service.timeout.connect == 15.0
    assert service.timeout.read == 600.0
    assert service.timeout.write == 120.0
    assert service.timeout.pool == 15.0


@pytest.mark.asyncio
async def test_health_returns_true_for_successful_response(
    monkeypatch,
):
    response = FakeResponse(
        is_success=True,
    )

    client = FakeAsyncClient(
        timeout=15.0,
        get_response=response,
    )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        lambda timeout: client,
    )

    service = EmbeddingService()
    service.base_url = "http://ollama.test"

    result = await service.health()

    assert result is True
    assert client.entered is True
    assert client.exited is True
    assert client.timeout == 15.0
    assert client.get_calls == ["http://ollama.test/api/tags"]


@pytest.mark.asyncio
async def test_health_returns_false_for_unsuccessful_response(
    monkeypatch,
):
    response = FakeResponse(
        is_success=False,
    )

    client = FakeAsyncClient(
        timeout=15.0,
        get_response=response,
    )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        lambda timeout: client,
    )

    service = EmbeddingService()

    result = await service.health()

    assert result is False


@pytest.mark.asyncio
async def test_health_returns_false_on_http_error(
    monkeypatch,
):
    request = httpx.Request(
        "GET",
        "http://ollama.test/api/tags",
    )

    error = httpx.ConnectError(
        "Connection failed",
        request=request,
    )

    client = FakeAsyncClient(
        timeout=15.0,
        get_error=error,
    )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        lambda timeout: client,
    )

    service = EmbeddingService()

    result = await service.health()

    assert result is False
    assert client.exited is True


@pytest.mark.asyncio
async def test_embed_texts_returns_empty_for_empty_input(
    monkeypatch,
):
    async_client_called = False

    def fake_async_client(timeout):
        nonlocal async_client_called
        async_client_called = True
        raise AssertionError("AsyncClient should not be created")

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        fake_async_client,
    )

    service = EmbeddingService()

    result = await service.embed_texts([])

    assert result == []
    assert async_client_called is False


@pytest.mark.asyncio
async def test_embed_texts_posts_payload_and_returns_embeddings(
    monkeypatch,
):
    response = FakeResponse(
        json_data={
            "embeddings": [
                [0.1, 0.2],
                [0.3, 0.4],
            ]
        }
    )

    client = FakeAsyncClient(
        timeout=None,
        post_response=response,
    )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        lambda timeout: client,
    )

    service = EmbeddingService()
    service.base_url = "http://ollama.test"
    service.model = "embed-model"

    result = await service.embed_texts(
        [
            "first text",
            "second text",
        ]
    )

    assert result == [
        [0.1, 0.2],
        [0.3, 0.4],
    ]

    assert client.timeout is None
    assert client.entered is True
    assert client.exited is True
    assert response.raise_for_status_called is True

    assert client.post_calls == [
        {
            "url": "http://ollama.test/api/embed",
            "json": {
                "model": "embed-model",
                "input": [
                    "first text",
                    "second text",
                ],
                "truncate": True,
            },
        }
    ]


@pytest.mark.asyncio
async def test_embed_texts_uses_service_timeout(
    monkeypatch,
):
    response = FakeResponse(
        json_data={
            "embeddings": [
                [0.5, 0.6],
            ]
        }
    )

    captured = {}

    def fake_async_client(timeout):
        captured["timeout"] = timeout

        return FakeAsyncClient(
            timeout=timeout,
            post_response=response,
        )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        fake_async_client,
    )

    service = EmbeddingService()

    result = await service.embed_texts(["hello"])

    assert result == [[0.5, 0.6]]
    assert captured["timeout"] is service.timeout


@pytest.mark.asyncio
async def test_embed_texts_raises_when_embeddings_missing(
    monkeypatch,
):
    response = FakeResponse(json_data={})

    client = FakeAsyncClient(
        timeout=None,
        post_response=response,
    )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        lambda timeout: client,
    )

    service = EmbeddingService()

    with pytest.raises(
        RuntimeError,
        match="Ollama returned no embeddings",
    ):
        await service.embed_texts(["hello"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "embeddings",
    [
        None,
        "not-a-list",
        {"value": [0.1]},
        123,
    ],
)
async def test_embed_texts_rejects_non_list_embeddings(
    monkeypatch,
    embeddings,
):
    response = FakeResponse(
        json_data={
            "embeddings": embeddings,
        }
    )

    client = FakeAsyncClient(
        timeout=None,
        post_response=response,
    )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        lambda timeout: client,
    )

    service = EmbeddingService()

    with pytest.raises(
        RuntimeError,
        match="Ollama returned no embeddings",
    ):
        await service.embed_texts(["hello"])


@pytest.mark.asyncio
async def test_embed_texts_raises_for_embedding_count_mismatch(
    monkeypatch,
):
    response = FakeResponse(
        json_data={
            "embeddings": [
                [0.1, 0.2],
            ]
        }
    )

    client = FakeAsyncClient(
        timeout=None,
        post_response=response,
    )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        lambda timeout: client,
    )

    service = EmbeddingService()

    with pytest.raises(
        RuntimeError,
        match="Embedding count did not match input count",
    ):
        await service.embed_texts(
            [
                "first",
                "second",
            ]
        )


@pytest.mark.asyncio
async def test_embed_texts_propagates_http_status_error(
    monkeypatch,
):
    request = httpx.Request(
        "POST",
        "http://ollama.test/api/embed",
    )

    status_error = httpx.HTTPStatusError(
        "Server error",
        request=request,
        response=httpx.Response(
            500,
            request=request,
        ),
    )

    response = FakeResponse(
        json_data=None,
        status_error=status_error,
    )

    client = FakeAsyncClient(
        timeout=None,
        post_response=response,
    )

    monkeypatch.setattr(
        embeddings_module.httpx,
        "AsyncClient",
        lambda timeout: client,
    )

    service = EmbeddingService()

    with pytest.raises(httpx.HTTPStatusError):
        await service.embed_texts(["hello"])

    assert response.raise_for_status_called is True
    assert client.exited is True


@pytest.mark.asyncio
async def test_embed_query_returns_first_embedding(
    monkeypatch,
):
    service = EmbeddingService()

    calls = []

    async def fake_embed_texts(texts):
        calls.append(texts)

        return [
            [0.1, 0.2, 0.3],
        ]

    monkeypatch.setattr(
        service,
        "embed_texts",
        fake_embed_texts,
    )

    result = await service.embed_query("What is AI?")

    assert result == [0.1, 0.2, 0.3]
    assert calls == [["What is AI?"]]


@pytest.mark.asyncio
async def test_embed_query_raises_when_no_embedding_generated(
    monkeypatch,
):
    service = EmbeddingService()

    async def fake_embed_texts(texts):
        return []

    monkeypatch.setattr(
        service,
        "embed_texts",
        fake_embed_texts,
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to generate query embedding",
    ):
        await service.embed_query("hello")


def test_global_embedding_service_exists():
    assert isinstance(
        embeddings_module.embedding_service,
        EmbeddingService,
    )
