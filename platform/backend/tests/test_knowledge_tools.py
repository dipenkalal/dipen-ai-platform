import pytest
import tools.knowledge_tools as knowledge_tools
from knowledge.schemas import (
    AskResponse,
    RagUsageMetrics,
    SearchResponse,
    SearchResult,
    SourceCitation,
)


@pytest.mark.asyncio
async def test_search_requires_query():
    tool = knowledge_tools.KnowledgeSearchTool()

    result = await tool.execute({"query": " "})

    assert result.success is False
    assert result.tool_id == "knowledge.search"
    assert result.error == "A search query is required."


@pytest.mark.asyncio
async def test_search_success(monkeypatch):
    captured = {}

    async def fake_search(request):
        captured["request"] = request

        return SearchResponse(
            query=request.query,
            results=[
                SearchResult(
                    score=0.91,
                    document_id="doc-1",
                    filename="manual.pdf",
                    chunk_id="chunk-1",
                    chunk_index=0,
                    text="Relevant knowledge content.",
                )
            ],
            total=1,
        )

    monkeypatch.setattr(
        knowledge_tools.knowledge_service,
        "search",
        fake_search,
    )

    tool = knowledge_tools.KnowledgeSearchTool()

    result = await tool.execute(
        {
            "query": " battery management ",
            "limit": "7",
            "score_threshold": 0.65,
            "document_id": "doc-1",
        }
    )

    request = captured["request"]

    assert request.query == "battery management"
    assert request.limit == 7
    assert request.score_threshold == 0.65
    assert request.document_id == "doc-1"

    assert result.success is True
    assert result.tool_id == "knowledge.search"
    assert result.output["query"] == "battery management"
    assert result.output["total"] == 1
    assert result.output["results"][0]["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_search_failure(monkeypatch):
    async def failing_search(request):
        raise RuntimeError("vector search failed")

    monkeypatch.setattr(
        knowledge_tools.knowledge_service,
        "search",
        failing_search,
    )

    tool = knowledge_tools.KnowledgeSearchTool()

    result = await tool.execute(
        {
            "query": "valid search query",
        }
    )

    assert result.success is False
    assert result.tool_id == "knowledge.search"
    assert result.error == "vector search failed"


@pytest.mark.asyncio
async def test_ask_requires_question():
    tool = knowledge_tools.KnowledgeAskTool()

    result = await tool.execute({"question": ""})

    assert result.success is False
    assert result.tool_id == "knowledge.ask"
    assert result.error == "A question is required."


@pytest.mark.asyncio
async def test_ask_success(monkeypatch):
    captured = {}

    async def fake_ask(request):
        captured["request"] = request

        return AskResponse(
            answer="The battery management system monitors the battery.",
            provider="ollama",
            model="qwen",
            sources=[
                SourceCitation(
                    citation_id="source-1",
                    document_id="doc-1",
                    filename="bms.pdf",
                    chunk_id="chunk-4",
                    chunk_index=3,
                    score=0.88,
                    excerpt="The BMS monitors voltage and temperature.",
                )
            ],
            usage=RagUsageMetrics(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                latency_ms=75.5,
            ),
        )

    monkeypatch.setattr(
        knowledge_tools.rag_service,
        "ask",
        fake_ask,
    )

    tool = knowledge_tools.KnowledgeAskTool()

    result = await tool.execute(
        {
            "question": " What does the BMS monitor? ",
            "model": "qwen",
            "provider": "ollama",
            "temperature": "0.4",
            "max_tokens": "700",
            "retrieval_limit": "6",
            "score_threshold": 0.55,
            "document_id": "doc-1",
        }
    )

    request = captured["request"]

    assert request.question == "What does the BMS monitor?"
    assert request.model == "qwen"
    assert request.provider == "ollama"
    assert request.temperature == 0.4
    assert request.max_tokens == 700
    assert request.retrieval_limit == 6
    assert request.score_threshold == 0.55
    assert request.document_id == "doc-1"

    assert result.success is True
    assert result.tool_id == "knowledge.ask"
    assert result.output["provider"] == "ollama"
    assert result.output["model"] == "qwen"
    assert result.output["sources"][0]["citation_id"] == "source-1"
    assert result.output["usage"]["total_tokens"] == 150


@pytest.mark.asyncio
async def test_ask_failure(monkeypatch):
    async def failing_ask(request):
        raise RuntimeError("RAG request failed")

    monkeypatch.setattr(
        knowledge_tools.rag_service,
        "ask",
        failing_ask,
    )

    tool = knowledge_tools.KnowledgeAskTool()

    result = await tool.execute(
        {
            "question": "Explain this document",
        }
    )

    assert result.success is False
    assert result.tool_id == "knowledge.ask"
    assert result.error == "RAG request failed"
