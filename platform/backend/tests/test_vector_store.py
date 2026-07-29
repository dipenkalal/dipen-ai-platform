from datetime import UTC, datetime
from types import SimpleNamespace

import knowledge.services.vector_store as vector_store_module
import pytest
from knowledge.services.vector_store import VectorStore


class FakeClient:
    def __init__(self):
        self.calls = []
        self.collection_exists_result = False
        self.get_collections_error = None
        self.collection_vector_size = 3
        self.query_points_result = SimpleNamespace(points=[])
        self.scroll_results = []

    async def get_collections(self):
        self.calls.append(("get_collections", {}))

        if self.get_collections_error:
            raise self.get_collections_error

        return SimpleNamespace(collections=[])

    async def collection_exists(self, collection_name):
        self.calls.append(
            (
                "collection_exists",
                {"collection_name": collection_name},
            )
        )
        return self.collection_exists_result

    async def get_collection(self, collection_name):
        self.calls.append(
            (
                "get_collection",
                {"collection_name": collection_name},
            )
        )

        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors=SimpleNamespace(
                        size=self.collection_vector_size,
                    )
                )
            )
        )

    async def create_collection(self, **kwargs):
        self.calls.append(("create_collection", kwargs))

    async def upsert(self, **kwargs):
        self.calls.append(("upsert", kwargs))

    async def query_points(self, **kwargs):
        self.calls.append(("query_points", kwargs))
        return self.query_points_result

    async def scroll(self, **kwargs):
        self.calls.append(("scroll", kwargs))

        if self.scroll_results:
            return self.scroll_results.pop(0)

        return [], None

    async def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture
def store(fake_client):
    instance = VectorStore.__new__(VectorStore)
    instance.client = fake_client
    instance.collection_name = "test-collection"
    return instance


@pytest.mark.asyncio
async def test_health_returns_true(store, fake_client):
    result = await store.health()

    assert result is True
    assert fake_client.calls == [("get_collections", {})]


@pytest.mark.asyncio
async def test_health_returns_false_on_exception(
    store,
    fake_client,
):
    fake_client.get_collections_error = RuntimeError("Qdrant unavailable")

    result = await store.health()

    assert result is False


@pytest.mark.asyncio
async def test_ensure_collection_returns_when_existing_size_matches(
    store,
    fake_client,
):
    fake_client.collection_exists_result = True
    fake_client.collection_vector_size = 3

    await store.ensure_collection(vector_size=3)

    call_names = [name for name, _ in fake_client.calls]

    assert call_names == [
        "collection_exists",
        "get_collection",
    ]


@pytest.mark.asyncio
async def test_ensure_collection_rejects_size_mismatch(
    store,
    fake_client,
):
    fake_client.collection_exists_result = True
    fake_client.collection_vector_size = 384

    with pytest.raises(
        RuntimeError,
        match="vector size 384",
    ):
        await store.ensure_collection(vector_size=768)


@pytest.mark.asyncio
async def test_ensure_collection_creates_missing_collection(
    store,
    fake_client,
):
    fake_client.collection_exists_result = False

    await store.ensure_collection(vector_size=768)

    create_call = next(
        kwargs
        for name, kwargs in fake_client.calls
        if name == "create_collection"
    )

    assert create_call["collection_name"] == "test-collection"
    assert create_call["vectors_config"].size == 768

    distance = create_call["vectors_config"].distance
    assert distance == vector_store_module.Distance.COSINE


@pytest.mark.asyncio
async def test_add_document_chunks_rejects_count_mismatch(
    store,
):
    with pytest.raises(
        ValueError,
        match="counts must match",
    ):
        await store.add_document_chunks(
            document_id="doc-1",
            filename="test.txt",
            content_type="text/plain",
            size_bytes=10,
            created_at=datetime.now(UTC),
            chunks=["one", "two"],
            embeddings=[[0.1, 0.2]],
        )


@pytest.mark.asyncio
async def test_add_document_chunks_rejects_empty_embeddings(
    store,
):
    with pytest.raises(
        ValueError,
        match="At least one embedding",
    ):
        await store.add_document_chunks(
            document_id="doc-1",
            filename="test.txt",
            content_type="text/plain",
            size_bytes=10,
            created_at=datetime.now(UTC),
            chunks=[],
            embeddings=[],
        )


@pytest.mark.asyncio
async def test_add_document_chunks_builds_and_upserts_points(
    store,
    fake_client,
    monkeypatch,
):
    generated_ids = iter(
        [
            "chunk-id-1",
            "chunk-id-2",
        ]
    )

    monkeypatch.setattr(
        vector_store_module,
        "uuid4",
        lambda: next(generated_ids),
    )

    ensured_sizes = []

    async def ensure_collection(vector_size):
        ensured_sizes.append(vector_size)

    monkeypatch.setattr(
        store,
        "ensure_collection",
        ensure_collection,
    )

    created_at = datetime(
        2026,
        7,
        28,
        12,
        30,
        tzinfo=UTC,
    )

    await store.add_document_chunks(
        document_id="doc-123",
        filename="notes.txt",
        content_type="text/plain",
        size_bytes=42,
        created_at=created_at,
        chunks=[
            "first chunk",
            "second chunk",
        ],
        embeddings=[
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ],
    )

    assert ensured_sizes == [3]

    upsert_call = next(
        kwargs for name, kwargs in fake_client.calls if name == "upsert"
    )

    assert upsert_call["collection_name"] == "test-collection"
    assert upsert_call["wait"] is True
    assert len(upsert_call["points"]) == 2

    first = upsert_call["points"][0]
    second = upsert_call["points"][1]

    assert str(first.id) == "chunk-id-1"
    assert first.vector == [0.1, 0.2, 0.3]
    assert first.payload == {
        "document_id": "doc-123",
        "filename": "notes.txt",
        "content_type": "text/plain",
        "size_bytes": 42,
        "created_at": created_at.isoformat(),
        "chunk_id": "chunk-id-1",
        "chunk_index": 0,
        "text": "first chunk",
    }

    assert str(second.id) == "chunk-id-2"
    assert second.payload["chunk_index"] == 1
    assert second.payload["text"] == "second chunk"


@pytest.mark.asyncio
async def test_search_without_document_filter(
    store,
    fake_client,
):
    expected_points = [
        SimpleNamespace(id="point-1"),
        SimpleNamespace(id="point-2"),
    ]

    fake_client.query_points_result = SimpleNamespace(points=expected_points)

    result = await store.search(
        query_vector=[0.1, 0.2],
        limit=5,
        score_threshold=0.7,
        document_id=None,
    )

    assert result == expected_points

    query_call = next(
        kwargs for name, kwargs in fake_client.calls if name == "query_points"
    )

    assert query_call == {
        "collection_name": "test-collection",
        "query": [0.1, 0.2],
        "query_filter": None,
        "limit": 5,
        "score_threshold": 0.7,
        "with_payload": True,
    }


@pytest.mark.asyncio
async def test_search_with_document_filter(
    store,
    fake_client,
):
    await store.search(
        query_vector=[1.0],
        limit=3,
        score_threshold=None,
        document_id="doc-99",
    )

    query_call = next(
        kwargs for name, kwargs in fake_client.calls if name == "query_points"
    )

    query_filter = query_call["query_filter"]

    assert query_filter is not None
    assert len(query_filter.must) == 1

    condition = query_filter.must[0]

    assert condition.key == "document_id"
    assert condition.match.value == "doc-99"


@pytest.mark.asyncio
async def test_list_document_points_returns_empty_when_collection_missing(
    store,
    fake_client,
):
    fake_client.collection_exists_result = False

    result = await store.list_document_points()

    assert result == []

    call_names = [name for name, _ in fake_client.calls]

    assert call_names == ["collection_exists"]


@pytest.mark.asyncio
async def test_list_document_points_scrolls_all_pages(
    store,
    fake_client,
):
    fake_client.collection_exists_result = True

    first_page = [
        SimpleNamespace(id="point-1"),
        SimpleNamespace(id="point-2"),
    ]
    second_page = [
        SimpleNamespace(id="point-3"),
    ]

    fake_client.scroll_results = [
        (first_page, "next-page"),
        (second_page, None),
    ]

    result = await store.list_document_points()

    assert result == [
        *first_page,
        *second_page,
    ]

    scroll_calls = [
        kwargs for name, kwargs in fake_client.calls if name == "scroll"
    ]

    assert len(scroll_calls) == 2

    assert scroll_calls[0] == {
        "collection_name": "test-collection",
        "limit": 256,
        "offset": None,
        "with_payload": True,
        "with_vectors": False,
    }

    assert scroll_calls[1]["offset"] == "next-page"


@pytest.mark.asyncio
async def test_delete_document_returns_zero_when_collection_missing(
    store,
    fake_client,
):
    fake_client.collection_exists_result = False

    result = await store.delete_document("doc-1")

    assert result == 0

    call_names = [name for name, _ in fake_client.calls]

    assert call_names == ["collection_exists"]


@pytest.mark.asyncio
async def test_delete_document_returns_zero_when_no_points_match(
    store,
    fake_client,
):
    fake_client.collection_exists_result = True
    fake_client.scroll_results = [
        ([], None),
    ]

    result = await store.delete_document("doc-1")

    assert result == 0

    call_names = [name for name, _ in fake_client.calls]

    assert "delete" not in call_names


@pytest.mark.asyncio
async def test_delete_document_deletes_matching_points(
    store,
    fake_client,
):
    fake_client.collection_exists_result = True
    fake_client.scroll_results = [
        (
            [
                SimpleNamespace(id="point-1"),
                SimpleNamespace(id="point-2"),
                SimpleNamespace(id="point-3"),
            ],
            None,
        )
    ]

    result = await store.delete_document("doc-55")

    assert result == 3

    scroll_call = next(
        kwargs for name, kwargs in fake_client.calls if name == "scroll"
    )

    scroll_filter = scroll_call["scroll_filter"]

    assert scroll_filter.must[0].key == "document_id"
    assert scroll_filter.must[0].match.value == "doc-55"

    delete_call = next(
        kwargs for name, kwargs in fake_client.calls if name == "delete"
    )

    assert delete_call["collection_name"] == "test-collection"
    assert delete_call["wait"] is True

    points_selector = delete_call["points_selector"]

    assert points_selector.must[0].key == "document_id"
    assert points_selector.must[0].match.value == "doc-55"
