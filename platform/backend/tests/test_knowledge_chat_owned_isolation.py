from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from history.database import HistoryDatabase
from knowledge.schemas import SearchRequest
from knowledge.services import knowledge as knowledge_module
from knowledge.services.knowledge import KnowledgeService
from knowledge.services.vector_store import VectorStore


class FakeEmbeddingService:
    async def embed_query(
        self,
        query: str,
    ) -> list[float]:
        del query
        return [0.1, 0.2]


class FakeVectorStore:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        **kwargs,
    ) -> list[object]:
        self.calls.append(kwargs)
        return []


class FakeQdrantClient:
    def __init__(self) -> None:
        self.query_filter = None

    async def query_points(
        self,
        **kwargs,
    ) -> SimpleNamespace:
        self.query_filter = kwargs["query_filter"]
        return SimpleNamespace(points=[])


def seed_chat_owned_document(
    database: HistoryDatabase,
    document_id: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()

    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_conversations (
                conversation_id,
                title,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "conversation-a",
                "Isolation test",
                now,
                now,
            ),
        )

        connection.execute(
            """
            INSERT INTO chat_attachments (
                attachment_id,
                conversation_id,
                knowledge_document_id,
                filename,
                content_type,
                size_bytes,
                chunk_count,
                ownership,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                'chat_owned', 'indexed', ?, ?
            )
            """,
            (
                "attachment-a",
                "conversation-a",
                document_id,
                "private.txt",
                "text/plain",
                10,
                1,
                now,
                now,
            ),
        )

        connection.commit()


@pytest.mark.asyncio
async def test_global_search_excludes_chat_owned_document_ids(
    tmp_path,
    monkeypatch,
) -> None:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )
    database.initialize()

    seed_chat_owned_document(
        database,
        "chat-document-a",
    )

    fake_vector_store = FakeVectorStore()

    monkeypatch.setattr(
        knowledge_module,
        "history_database",
        database,
    )
    monkeypatch.setattr(
        knowledge_module,
        "embedding_service",
        FakeEmbeddingService(),
    )
    monkeypatch.setattr(
        knowledge_module,
        "vector_store",
        fake_vector_store,
    )

    service = KnowledgeService()

    await service.search(
        SearchRequest(
            query="private canary",
        )
    )

    assert fake_vector_store.calls[0][
        "excluded_document_ids"
    ] == {
        "chat-document-a",
    }


@pytest.mark.asyncio
async def test_document_scoped_search_keeps_attachment_path_available(
    tmp_path,
    monkeypatch,
) -> None:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )
    database.initialize()

    seed_chat_owned_document(
        database,
        "chat-document-a",
    )

    fake_vector_store = FakeVectorStore()

    monkeypatch.setattr(
        knowledge_module,
        "history_database",
        database,
    )
    monkeypatch.setattr(
        knowledge_module,
        "embedding_service",
        FakeEmbeddingService(),
    )
    monkeypatch.setattr(
        knowledge_module,
        "vector_store",
        fake_vector_store,
    )

    service = KnowledgeService()

    await service.search(
        SearchRequest(
            query="private canary",
            document_id="chat-document-a",
        )
    )

    assert fake_vector_store.calls[0][
        "document_id"
    ] == "chat-document-a"

    assert fake_vector_store.calls[0][
        "excluded_document_ids"
    ] == set()


@pytest.mark.asyncio
async def test_vector_store_builds_must_not_document_filter() -> None:
    store = VectorStore()
    fake_client = FakeQdrantClient()
    store.client = fake_client

    await store.search(
        query_vector=[0.1, 0.2],
        limit=5,
        score_threshold=None,
        document_id=None,
        excluded_document_ids={
            "chat-document-b",
            "chat-document-a",
        },
    )

    query_filter = fake_client.query_filter

    assert query_filter is not None
    assert query_filter.must is None
    assert query_filter.must_not is not None

    excluded = {
        condition.match.value
        for condition in query_filter.must_not
    }

    assert excluded == {
        "chat-document-a",
        "chat-document-b",
    }
