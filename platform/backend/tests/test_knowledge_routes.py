from datetime import datetime

import knowledge.routes as routes
import pytest
from knowledge.schemas import (
    AskResponse,
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadResponse,
    KnowledgeHealthResponse,
    RagUsageMetrics,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SourceCitation,
)


@pytest.mark.asyncio
async def test_health_route(monkeypatch):
    response = KnowledgeHealthResponse(
        status="ok",
        qdrant_online=True,
        ollama_online=True,
        embedding_model="nomic-embed-text",
        collection="docs",
    )

    async def fake_health():
        return response

    monkeypatch.setattr(routes.knowledge_service, "health", fake_health)

    result = await routes.knowledge_health()

    assert result == response


@pytest.mark.asyncio
async def test_upload_document_route(monkeypatch):
    response = DocumentUploadResponse(
        status="uploaded",
        document=DocumentInfo(
            document_id="doc1",
            filename="test.pdf",
            content_type="application/pdf",
            size_bytes=100,
            chunk_count=5,
            created_at=datetime.now(),
        ),
    )

    async def fake_upload(file):
        assert file == "fake-file"
        return response

    monkeypatch.setattr(
        routes.knowledge_service,
        "upload_document",
        fake_upload,
    )

    result = await routes.upload_document("fake-file")

    assert result == response


@pytest.mark.asyncio
async def test_list_documents_route(monkeypatch):
    response = DocumentListResponse(
        documents=[],
        total=0,
    )

    async def fake_list():
        return response

    monkeypatch.setattr(
        routes.knowledge_service,
        "list_documents",
        fake_list,
    )

    result = await routes.list_documents()

    assert result == response


@pytest.mark.asyncio
async def test_delete_document_route(monkeypatch):
    response = DocumentDeleteResponse(
        status="deleted",
        document_id="doc1",
        deleted_chunks=12,
    )

    async def fake_delete(document_id):
        assert document_id == "doc1"
        return response

    monkeypatch.setattr(
        routes.knowledge_service,
        "delete_document",
        fake_delete,
    )

    result = await routes.delete_document("doc1")

    assert result == response


@pytest.mark.asyncio
async def test_search_route(monkeypatch):
    response = SearchResponse(
        query="battery",
        results=[
            SearchResult(
                score=0.9,
                document_id="doc1",
                filename="manual.pdf",
                chunk_id="chunk1",
                chunk_index=0,
                text="Battery management",
            )
        ],
        total=1,
    )

    async def fake_search(request):
        assert isinstance(request, SearchRequest)
        return response

    monkeypatch.setattr(
        routes.knowledge_service,
        "search",
        fake_search,
    )

    result = await routes.search_knowledge(SearchRequest(query="battery"))

    assert result == response


@pytest.mark.asyncio
async def test_ask_route(monkeypatch):
    response = AskResponse(
        answer="Battery is monitored.",
        provider="ollama",
        model="qwen",
        sources=[
            SourceCitation(
                citation_id="1",
                document_id="doc1",
                filename="manual.pdf",
                chunk_id="chunk1",
                chunk_index=0,
                score=0.9,
                excerpt="Battery management...",
            )
        ],
        usage=RagUsageMetrics(
            latency_ms=25,
            total_tokens=100,
            prompt_tokens=60,
            completion_tokens=40,
        ),
    )

    async def fake_ask(request):
        return response

    monkeypatch.setattr(routes.rag_service, "ask", fake_ask)

    result = await routes.ask_knowledge(
        routes.AskRequest(question="What is BMS?")
    )

    assert result == response


@pytest.mark.asyncio
async def test_stream_route():
    response = await routes.stream_knowledge_answer(
        routes.AskRequest(question="hello")
    )

    assert response.media_type == "application/x-ndjson"
    assert response.headers["Cache-Control"] == "no-cache, no-transform"
    assert response.headers["X-Accel-Buffering"] == "no"
