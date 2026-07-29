from types import SimpleNamespace

import knowledge.services.knowledge as knowledge_module
import pytest
from fastapi import HTTPException
from knowledge.schemas import SearchRequest
from knowledge.services.chunker import TextChunk
from knowledge.services.extractor import (
    UnsupportedDocumentError,
)
from knowledge.services.knowledge import KnowledgeService


class FakeUpload:
    def __init__(
        self,
        content: bytes,
        filename: str | None = "document.txt",
        content_type: str | None = "text/plain",
    ):
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self) -> bytes:
        return self._content


@pytest.fixture
def service() -> KnowledgeService:
    return KnowledgeService()


@pytest.mark.asyncio
async def test_health_returns_healthy(
    service,
    monkeypatch,
):
    async def qdrant_health():
        return True

    async def ollama_health():
        return True

    monkeypatch.setattr(
        knowledge_module.vector_store,
        "health",
        qdrant_health,
    )
    monkeypatch.setattr(
        knowledge_module.embedding_service,
        "health",
        ollama_health,
    )

    result = await service.health()

    assert result.status == "healthy"
    assert result.qdrant_online is True
    assert result.ollama_online is True
    assert result.embedding_model == knowledge_module.OLLAMA_EMBEDDING_MODEL
    assert result.collection == knowledge_module.QDRANT_COLLECTION


@pytest.mark.asyncio
async def test_health_returns_degraded(
    service,
    monkeypatch,
):
    async def qdrant_health():
        return True

    async def ollama_health():
        return False

    monkeypatch.setattr(
        knowledge_module.vector_store,
        "health",
        qdrant_health,
    )
    monkeypatch.setattr(
        knowledge_module.embedding_service,
        "health",
        ollama_health,
    )

    result = await service.health()

    assert result.status == "degraded"
    assert result.qdrant_online is True
    assert result.ollama_online is False


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_extension(
    service,
):
    upload = FakeUpload(
        content=b"content",
        filename="malware.exe",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload)

    assert exc_info.value.status_code == 415
    assert "Unsupported file type" in exc_info.value.detail


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(
    service,
):
    upload = FakeUpload(
        content=b"",
        filename="empty.txt",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "The uploaded file is empty"


@pytest.mark.asyncio
async def test_upload_rejects_file_over_size_limit(
    service,
    monkeypatch,
):
    monkeypatch.setattr(
        knowledge_module,
        "MAX_FILE_SIZE_BYTES",
        3,
    )

    upload = FakeUpload(
        content=b"four",
        filename="large.txt",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload)

    assert exc_info.value.status_code == 413
    assert "3 byte limit" in exc_info.value.detail


@pytest.mark.asyncio
async def test_upload_document_success_with_embedding_batches(
    service,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        knowledge_module,
        "KNOWLEDGE_UPLOAD_DIRECTORY",
        tmp_path,
    )
    monkeypatch.setattr(
        knowledge_module,
        "uuid4",
        lambda: "document-123",
    )
    monkeypatch.setattr(
        knowledge_module,
        "extract_document_text",
        lambda path: "extracted text",
    )

    chunks = [
        TextChunk(
            index=index,
            text=f"chunk-{index}",
        )
        for index in range(17)
    ]

    monkeypatch.setattr(
        knowledge_module,
        "chunk_text",
        lambda **kwargs: chunks,
    )

    embedded_batches = []

    async def embed_texts(texts):
        embedded_batches.append(list(texts))
        return [[float(index)] for index, _ in enumerate(texts)]

    added = {}

    async def add_document_chunks(**kwargs):
        added.update(kwargs)

    monkeypatch.setattr(
        knowledge_module.embedding_service,
        "embed_texts",
        embed_texts,
    )
    monkeypatch.setattr(
        knowledge_module.vector_store,
        "add_document_chunks",
        add_document_chunks,
    )

    upload = FakeUpload(
        content=b"document contents",
        filename="notes.txt",
        content_type=None,
    )

    result = await service.upload_document(upload)

    assert result.status == "indexed"
    assert result.document.document_id == "document-123"
    assert result.document.filename == "notes.txt"
    assert result.document.content_type == "application/octet-stream"
    assert result.document.size_bytes == len(b"document contents")
    assert result.document.chunk_count == 17

    assert len(embedded_batches) == 2
    assert len(embedded_batches[0]) == 16
    assert len(embedded_batches[1]) == 1

    assert added["document_id"] == "document-123"
    assert added["filename"] == "notes.txt"
    assert len(added["chunks"]) == 17
    assert len(added["embeddings"]) == 17

    stored_file = tmp_path / "document-123.txt"
    assert stored_file.read_bytes() == b"document contents"


@pytest.mark.asyncio
async def test_upload_uses_default_filename_when_missing(
    service,
):
    upload = FakeUpload(
        content=b"content",
        filename=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload)

    # "document" has no allowed extension.
    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_removes_file_for_unsupported_document(
    service,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        knowledge_module,
        "KNOWLEDGE_UPLOAD_DIRECTORY",
        tmp_path,
    )
    monkeypatch.setattr(
        knowledge_module,
        "uuid4",
        lambda: "unsupported-doc",
    )

    def raise_unsupported(path):
        raise UnsupportedDocumentError("Cannot extract this document")

    monkeypatch.setattr(
        knowledge_module,
        "extract_document_text",
        raise_unsupported,
    )

    upload = FakeUpload(
        content=b"content",
        filename="document.txt",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload)

    assert exc_info.value.status_code == 415
    assert exc_info.value.detail == "Cannot extract this document"
    assert not (tmp_path / "unsupported-doc.txt").exists()


@pytest.mark.asyncio
async def test_upload_removes_file_for_empty_document(
    service,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        knowledge_module,
        "KNOWLEDGE_UPLOAD_DIRECTORY",
        tmp_path,
    )
    monkeypatch.setattr(
        knowledge_module,
        "uuid4",
        lambda: "empty-doc",
    )
    monkeypatch.setattr(
        knowledge_module,
        "extract_document_text",
        lambda path: "text",
    )
    monkeypatch.setattr(
        knowledge_module,
        "chunk_text",
        lambda **kwargs: [],
    )

    upload = FakeUpload(
        content=b"content",
        filename="document.txt",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload)

    assert exc_info.value.status_code == 422
    assert "no text chunks" in exc_info.value.detail
    assert not (tmp_path / "empty-doc.txt").exists()


@pytest.mark.asyncio
async def test_upload_removes_file_for_unexpected_error(
    service,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        knowledge_module,
        "KNOWLEDGE_UPLOAD_DIRECTORY",
        tmp_path,
    )
    monkeypatch.setattr(
        knowledge_module,
        "uuid4",
        lambda: "failed-doc",
    )
    monkeypatch.setattr(
        knowledge_module,
        "extract_document_text",
        lambda path: "text",
    )
    monkeypatch.setattr(
        knowledge_module,
        "chunk_text",
        lambda **kwargs: [
            TextChunk(
                index=0,
                text="chunk",
            )
        ],
    )

    async def fail_embedding(texts):
        raise RuntimeError("embedding offline")

    monkeypatch.setattr(
        knowledge_module.embedding_service,
        "embed_texts",
        fail_embedding,
    )

    upload = FakeUpload(
        content=b"content",
        filename="document.txt",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_document(upload)

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail == "Document ingestion failed: embedding offline"
    )
    assert not (tmp_path / "failed-doc.txt").exists()


@pytest.mark.asyncio
async def test_list_documents_groups_chunks_and_sorts(
    service,
    monkeypatch,
):
    newer = "2026-07-20T12:00:00+00:00"
    older = "2026-07-10T12:00:00+00:00"

    points = [
        SimpleNamespace(
            payload={
                "document_id": "older-document",
                "filename": "older.txt",
                "content_type": "text/plain",
                "size_bytes": 100,
                "created_at": older,
            }
        ),
        SimpleNamespace(
            payload={
                "document_id": "newer-document",
                "filename": "newer.txt",
                "content_type": "text/plain",
                "size_bytes": 200,
                "created_at": newer,
            }
        ),
        SimpleNamespace(
            payload={
                "document_id": "older-document",
            }
        ),
        SimpleNamespace(
            payload={
                "document_id": 123,
            }
        ),
        SimpleNamespace(
            payload=None,
        ),
    ]

    async def list_document_points():
        return points

    monkeypatch.setattr(
        knowledge_module.vector_store,
        "list_document_points",
        list_document_points,
    )

    result = await service.list_documents()

    assert result.total == 2
    assert result.documents[0].document_id == "newer-document"
    assert result.documents[0].chunk_count == 1
    assert result.documents[1].document_id == "older-document"
    assert result.documents[1].chunk_count == 2


@pytest.mark.asyncio
async def test_list_documents_uses_payload_defaults(
    service,
    monkeypatch,
):
    async def list_document_points():
        return [
            SimpleNamespace(
                payload={
                    "document_id": "document-1",
                    "created_at": None,
                }
            )
        ]

    monkeypatch.setattr(
        knowledge_module.vector_store,
        "list_document_points",
        list_document_points,
    )

    result = await service.list_documents()
    document = result.documents[0]

    assert document.filename == "unknown"
    assert document.content_type == "application/octet-stream"
    assert document.size_bytes == 0
    assert document.chunk_count == 1
    assert document.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_search_returns_mapped_results(
    service,
    monkeypatch,
):
    async def embed_query(query):
        assert query == "electric vehicles"
        return [0.1, 0.2]

    async def search(**kwargs):
        assert kwargs["query_vector"] == [0.1, 0.2]
        assert kwargs["limit"] == 3
        assert kwargs["document_id"] == "doc-1"

        return [
            SimpleNamespace(
                id="point-1",
                score=0.987654321,
                payload={
                    "document_id": "doc-1",
                    "filename": "ev.txt",
                    "chunk_id": "chunk-1",
                    "chunk_index": 2,
                    "text": "EV battery content",
                },
            ),
            SimpleNamespace(
                id="point-2",
                score=0.5,
                payload=None,
            ),
        ]

    monkeypatch.setattr(
        knowledge_module.embedding_service,
        "embed_query",
        embed_query,
    )
    monkeypatch.setattr(
        knowledge_module.vector_store,
        "search",
        search,
    )

    request = SearchRequest(
        query="electric vehicles",
        limit=3,
        score_threshold=0.2,
        document_id="doc-1",
    )

    result = await service.search(request)

    assert result.query == "electric vehicles"
    assert result.total == 2

    first = result.results[0]
    assert first.score == 0.987654
    assert first.document_id == "doc-1"
    assert first.filename == "ev.txt"
    assert first.chunk_id == "chunk-1"
    assert first.chunk_index == 2
    assert first.text == "EV battery content"

    second = result.results[1]
    assert second.document_id == ""
    assert second.filename == "unknown"
    assert second.chunk_id == "point-2"
    assert second.chunk_index == 0
    assert second.text == ""


@pytest.mark.asyncio
async def test_search_converts_dependency_error_to_http_502(
    service,
    monkeypatch,
):
    async def fail_query(query):
        raise RuntimeError("Ollama unavailable")

    monkeypatch.setattr(
        knowledge_module.embedding_service,
        "embed_query",
        fail_query,
    )

    request = SearchRequest(
        query="test query",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.search(request)

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail == "Knowledge search failed: Ollama unavailable"
    )


@pytest.mark.asyncio
async def test_delete_document_returns_404_when_not_found(
    service,
    monkeypatch,
):
    async def delete_document(document_id):
        return 0

    monkeypatch.setattr(
        knowledge_module.vector_store,
        "delete_document",
        delete_document,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_document("missing-document")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Document not found"


@pytest.mark.asyncio
async def test_delete_document_removes_matching_files(
    service,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        knowledge_module,
        "KNOWLEDGE_UPLOAD_DIRECTORY",
        tmp_path,
    )

    matching_txt = tmp_path / "document-1.txt"
    matching_pdf = tmp_path / "document-1.pdf"
    unrelated = tmp_path / "document-2.txt"

    matching_txt.write_text("text")
    matching_pdf.write_bytes(b"pdf")
    unrelated.write_text("keep")

    async def delete_document(document_id):
        assert document_id == "document-1"
        return 3

    monkeypatch.setattr(
        knowledge_module.vector_store,
        "delete_document",
        delete_document,
    )

    result = await service.delete_document("document-1")

    assert result.status == "deleted"
    assert result.document_id == "document-1"
    assert result.deleted_chunks == 3

    assert not matching_txt.exists()
    assert not matching_pdf.exists()
    assert unrelated.exists()
