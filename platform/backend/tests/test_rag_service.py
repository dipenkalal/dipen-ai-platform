import json
from types import SimpleNamespace
from typing import Any, cast

import knowledge.services.rag as rag_module
import pytest
from fastapi import HTTPException
from knowledge.schemas import AskRequest, SourceCitation
from knowledge.services.rag import (
    SYSTEM_PROMPT,
    RagService,
)


@pytest.fixture
def service() -> RagService:
    return RagService()


def make_request(**overrides: Any) -> AskRequest:
    values: dict[str, Any] = {
        "question": "What does the document say?",
        "provider": "ollama",
        "model": "llama3.2",
        "retrieval_limit": 5,
        "score_threshold": 0.25,
        "document_id": None,
        "temperature": 0.2,
        "max_tokens": 300,
    }

    values.update(overrides)

    return AskRequest(
        question=cast(str, values["question"]),
        provider=cast(str, values["provider"]),
        model=cast(str | None, values["model"]),
        retrieval_limit=cast(int, values["retrieval_limit"]),
        score_threshold=cast(float | None, values["score_threshold"]),
        document_id=cast(str | None, values["document_id"]),
        temperature=cast(float, values["temperature"]),
        max_tokens=cast(int, values["max_tokens"]),
    )


def make_source(
    citation_id: str = "S1",
    document_id: str = "doc-1",
    filename: str = "notes.txt",
    chunk_id: str = "chunk-1",
    chunk_index: int = 0,
    score: float = 0.95,
    excerpt: str = "Relevant document content.",
) -> SourceCitation:
    return SourceCitation(
        citation_id=citation_id,
        document_id=document_id,
        filename=filename,
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        score=score,
        excerpt=excerpt,
    )


@pytest.mark.asyncio
async def test_retrieve_sources_maps_search_results(
    service,
    monkeypatch,
):
    captured_request = {}

    async def fake_search(request):
        captured_request["request"] = request

        return SimpleNamespace(
            results=[
                SimpleNamespace(
                    document_id="doc-1",
                    filename="manual.pdf",
                    chunk_id="chunk-10",
                    chunk_index=4,
                    score=0.912345,
                    text="  Battery information from the manual.  ",
                ),
                SimpleNamespace(
                    document_id="doc-2",
                    filename="report.txt",
                    chunk_id="chunk-20",
                    chunk_index=7,
                    score=0.812345,
                    text="Second source text.",
                ),
            ]
        )

    monkeypatch.setattr(
        rag_module.knowledge_service,
        "search",
        fake_search,
    )

    request = make_request(
        question="Explain the battery",
        retrieval_limit=4,
        score_threshold=0.4,
        document_id="doc-filter",
    )

    sources = await service.retrieve_sources(request)

    search_request = captured_request["request"]

    assert search_request.query == "Explain the battery"
    assert search_request.limit == 4
    assert search_request.score_threshold == 0.4
    assert search_request.document_id == "doc-filter"

    assert len(sources) == 2

    assert sources[0].citation_id == "S1"
    assert sources[0].document_id == "doc-1"
    assert sources[0].filename == "manual.pdf"
    assert sources[0].chunk_id == "chunk-10"
    assert sources[0].chunk_index == 4
    assert sources[0].score == 0.912345
    assert sources[0].excerpt == "Battery information from the manual."

    assert sources[1].citation_id == "S2"
    assert sources[1].document_id == "doc-2"
    assert sources[1].filename == "report.txt"


@pytest.mark.asyncio
async def test_retrieve_sources_truncates_long_excerpt(
    service,
    monkeypatch,
):
    long_text = "x" * 1300

    async def fake_search(request):
        return SimpleNamespace(
            results=[
                SimpleNamespace(
                    document_id="doc-1",
                    filename="large.txt",
                    chunk_id="chunk-1",
                    chunk_index=0,
                    score=0.9,
                    text=long_text,
                )
            ]
        )

    monkeypatch.setattr(
        rag_module.knowledge_service,
        "search",
        fake_search,
    )

    sources = await service.retrieve_sources(make_request())

    assert len(sources) == 1
    assert sources[0].excerpt.endswith("…")
    assert len(sources[0].excerpt) == 1201
    assert sources[0].excerpt == ("x" * 1200) + "…"


@pytest.mark.asyncio
async def test_retrieve_sources_returns_empty_list(
    service,
    monkeypatch,
):
    async def fake_search(request):
        return SimpleNamespace(results=[])

    monkeypatch.setattr(
        rag_module.knowledge_service,
        "search",
        fake_search,
    )

    sources = await service.retrieve_sources(make_request())

    assert sources == []


def test_build_context_returns_empty_string_for_no_sources(
    service,
):
    result = service.build_context([])

    assert result == ""


def test_build_context_formats_single_source(
    service,
):
    source = make_source(
        citation_id="S1",
        document_id="doc-123",
        filename="guide.pdf",
        chunk_index=3,
        excerpt="This is the source content.",
    )

    context = service.build_context([source])

    assert context == "\n".join(
        [
            "[S1]",
            "Filename: guide.pdf",
            "Document ID: doc-123",
            "Chunk index: 3",
            "Content:",
            "This is the source content.",
        ]
    )


def test_build_context_joins_multiple_sources(
    service,
):
    first = make_source(
        citation_id="S1",
        filename="first.txt",
        excerpt="First source.",
    )
    second = make_source(
        citation_id="S2",
        document_id="doc-2",
        filename="second.txt",
        chunk_id="chunk-2",
        chunk_index=1,
        excerpt="Second source.",
    )

    context = service.build_context(
        [
            first,
            second,
        ]
    )

    assert "[S1]" in context
    assert "[S2]" in context
    assert "First source." in context
    assert "Second source." in context
    assert "\n\n---\n\n" in context


def test_build_chat_request_maps_configuration(
    service,
):
    request = make_request(
        question="What is regenerative braking?",
        provider="ollama",
        model="qwen2.5",
        temperature=0.35,
        max_tokens=450,
    )

    sources = [
        make_source(
            citation_id="S1",
            filename="ev-guide.pdf",
            excerpt="Regenerative braking recovers energy.",
        )
    ]

    chat_request = service.build_chat_request(
        request,
        sources,
    )

    assert chat_request.provider == "ollama"
    assert chat_request.model == "qwen2.5"
    assert chat_request.temperature == 0.35
    assert chat_request.max_tokens == 450
    assert chat_request.stream is False

    assert len(chat_request.messages) == 2

    system_message = chat_request.messages[0]
    user_message = chat_request.messages[1]

    assert system_message.role == "system"
    assert system_message.content == SYSTEM_PROMPT

    assert user_message.role == "user"
    assert "DOCUMENT CONTEXT" in user_message.content
    assert "[S1]" in user_message.content
    assert "Filename: ev-guide.pdf" in user_message.content
    assert "Regenerative braking recovers energy." in user_message.content
    assert "USER QUESTION" in user_message.content
    assert "What is regenerative braking?" in user_message.content
    assert "Include source markers such as [S1]" in user_message.content


@pytest.mark.asyncio
async def test_ask_returns_fallback_when_no_sources(
    service,
    monkeypatch,
):
    async def fake_retrieve_sources(request):
        return []

    monkeypatch.setattr(
        service,
        "retrieve_sources",
        fake_retrieve_sources,
    )

    request = make_request(
        provider="ollama",
        model=None,
    )

    response = await service.ask(request)

    assert (
        response.answer == "I could not find enough information "
        "in the indexed documents."
    )
    assert response.provider == "ollama"
    assert response.model == "unknown"
    assert response.sources == []

    assert response.usage.prompt_tokens == 0
    assert response.usage.completion_tokens == 0
    assert response.usage.total_tokens == 0
    assert response.usage.latency_ms == 0.0


@pytest.mark.asyncio
async def test_ask_returns_gateway_response(
    service,
    monkeypatch,
):
    sources = [
        make_source(
            citation_id="S1",
            excerpt="Relevant knowledge.",
        )
    ]

    async def fake_retrieve_sources(request):
        return sources

    captured = {}

    async def fake_chat(chat_request):
        captured["chat_request"] = chat_request

        return SimpleNamespace(
            message=SimpleNamespace(
                content="The answer is supported by [S1]."
            ),
            provider="ollama",
            model="qwen2.5",
            usage=SimpleNamespace(
                prompt_tokens=120,
                completion_tokens=30,
                total_tokens=150,
                latency_ms=245.7,
            ),
        )

    monkeypatch.setattr(
        service,
        "retrieve_sources",
        fake_retrieve_sources,
    )
    monkeypatch.setattr(
        rag_module.gateway_service,
        "chat",
        fake_chat,
    )

    request = make_request(
        provider="ollama",
        model="qwen2.5",
    )

    response = await service.ask(request)

    assert response.answer == "The answer is supported by [S1]."
    assert response.provider == "ollama"
    assert response.model == "qwen2.5"
    assert response.sources == sources

    assert response.usage.prompt_tokens == 120
    assert response.usage.completion_tokens == 30
    assert response.usage.total_tokens == 150
    assert response.usage.latency_ms == 245.7

    chat_request = captured["chat_request"]

    assert chat_request.stream is False
    assert chat_request.provider == "ollama"
    assert chat_request.model == "qwen2.5"


@pytest.mark.asyncio
async def test_ask_propagates_gateway_http_exception(
    service,
    monkeypatch,
):
    sources = [make_source()]

    async def fake_retrieve_sources(request):
        return sources

    async def fake_chat(chat_request):
        raise HTTPException(
            status_code=503,
            detail="Gateway unavailable",
        )

    monkeypatch.setattr(
        service,
        "retrieve_sources",
        fake_retrieve_sources,
    )
    monkeypatch.setattr(
        rag_module.gateway_service,
        "chat",
        fake_chat,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.ask(make_request())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Gateway unavailable"


@pytest.mark.asyncio
async def test_ask_converts_unexpected_error_to_http_502(
    service,
    monkeypatch,
):
    sources = [make_source()]

    async def fake_retrieve_sources(request):
        return sources

    async def fake_chat(chat_request):
        raise RuntimeError("generation crashed")

    monkeypatch.setattr(
        service,
        "retrieve_sources",
        fake_retrieve_sources,
    )
    monkeypatch.setattr(
        rag_module.gateway_service,
        "chat",
        fake_chat,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.ask(make_request())

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "RAG generation failed: generation crashed"


@pytest.mark.asyncio
async def test_stream_ask_without_sources(
    service,
    monkeypatch,
):
    async def fake_retrieve_sources(request):
        return []

    monkeypatch.setattr(
        service,
        "retrieve_sources",
        fake_retrieve_sources,
    )

    events = []

    async for event in service.stream_ask(make_request(model=None)):
        events.append(json.loads(event))

    assert len(events) == 3

    assert events[0]["type"] == "sources"
    assert events[0]["sources"] == []

    assert events[1]["type"] == "content"
    assert (
        events[1]["content"]
        == "I could not find enough information in the indexed documents."
    )

    assert events[2]["type"] == "done"
    assert events[2]["provider"] == "ollama"
    assert events[2]["model"] == "unknown"
    assert events[2]["sources"] == []
    assert events[2]["usage"]["total_tokens"] == 0


@pytest.mark.asyncio
async def test_stream_ask_success(
    service,
    monkeypatch,
):
    sources = [
        make_source(
            citation_id="S1",
            excerpt="Important information.",
        )
    ]

    async def fake_retrieve_sources(request):
        return sources

    captured = {}

    async def fake_stream_chat(chat_request):
        captured["request"] = chat_request

        yield json.dumps(
            {
                "type": "content",
                "content": "Hello ",
            }
        )

        yield ""

        yield "not-json"

        yield json.dumps(
            {
                "type": "content",
                "content": "World",
            }
        )

        yield json.dumps(
            {
                "type": "done",
                "provider": "ollama",
                "model": "llama3.2",
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 5,
                    "total_tokens": 25,
                    "latency_ms": 11.5,
                },
            }
        )

    monkeypatch.setattr(
        service,
        "retrieve_sources",
        fake_retrieve_sources,
    )

    monkeypatch.setattr(
        rag_module.gateway_service,
        "stream_chat",
        fake_stream_chat,
    )

    events = []

    async for event in service.stream_ask(make_request()):
        events.append(json.loads(event))

    assert len(events) == 4

    assert events[0]["type"] == "sources"
    assert events[0]["sources"][0]["citation_id"] == "S1"

    assert events[1]["content"] == "Hello "
    assert events[2]["content"] == "World"

    assert events[3]["type"] == "done"
    assert events[3]["sources"][0]["citation_id"] == "S1"

    chat_request = captured["request"]
    assert chat_request.stream is True


@pytest.mark.asyncio
async def test_stream_ask_http_exception(
    service,
    monkeypatch,
):
    async def fake_retrieve_sources(request):
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    monkeypatch.setattr(
        service,
        "retrieve_sources",
        fake_retrieve_sources,
    )

    events = []

    async for event in service.stream_ask(make_request()):
        events.append(json.loads(event))

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["status_code"] == 404
    assert events[0]["error"] == "Document not found"


@pytest.mark.asyncio
async def test_stream_ask_unexpected_exception(
    service,
    monkeypatch,
):
    async def fake_retrieve_sources(request):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        service,
        "retrieve_sources",
        fake_retrieve_sources,
    )

    events = []

    async for event in service.stream_ask(make_request()):
        events.append(json.loads(event))

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["status_code"] == 500
    assert events[0]["error"] == "RAG request failed: boom"
