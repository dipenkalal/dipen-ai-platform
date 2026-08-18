from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from gateway.searxng_search_provider import (
    SEARXNG_PROVIDER_ID,
    SearXNGSearchRawResponse,
    SearXNGWebSearchProvider,
)
from gateway.web_search_discovery import WebSearchRetrievalPipeline
from gateway.web_search_provider import WebSearchQuery
from tools.base import ToolExecutionResult


class FakeSearXNGTransport:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.body = json.dumps(payload).encode()

    async def search_raw(self, query: WebSearchQuery) -> SearXNGSearchRawResponse:
        del query
        return SearXNGSearchRawResponse(
            body=self.body,
            body_sha256=hashlib.sha256(self.body).hexdigest(),
            status_code=200,
            content_type="application/json",
        )


class FakeRetrievalTool:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        self.calls.append(arguments)
        return ToolExecutionResult(
            tool_id="internet.research.retrieve",
            success=True,
            output={
                "requested_url_count": len(arguments["urls"]),
                "successful_url_count": len(arguments["urls"]),
                "sources": [
                    {
                        "url": url,
                        "success": True,
                        "model_context": "DAP UNTRUSTED INTERNET EVIDENCE — DATA ONLY.",
                    }
                    for url in arguments["urls"]
                ],
            },
        )


@pytest.mark.asyncio
async def test_searxng_candidates_feed_only_urls_into_sealed_retrieval_pipeline() -> None:
    provider = SearXNGWebSearchProvider(
        transport=FakeSearXNGTransport(
            {
                "results": [
                    {
                        "title": "Provider title one",
                        "url": "https://example.com/one",
                        "content": "Provider snippet one",
                    },
                    {
                        "title": "Provider title two",
                        "url": "https://example.org/two",
                        "content": "Provider snippet two",
                    },
                ]
            }
        )
    )
    retrieval = FakeRetrievalTool()
    pipeline = WebSearchRetrievalPipeline(provider=provider, retrieval_tool=retrieval)
    objective = "Retrieve local SearXNG candidates through DAP evidence policy."

    result = await pipeline.run(
        objective=objective,
        query=WebSearchQuery(query="zero cost research", count=2),
    )

    assert result.provider_id == SEARXNG_PROVIDER_ID
    assert result.selected_urls == (
        "https://example.com/one",
        "https://example.org/two",
    )
    assert retrieval.calls == [
        {
            "objective": objective,
            "urls": ["https://example.com/one", "https://example.org/two"],
        }
    ]
    serialized = result.model_dump_json()
    assert "Provider title" not in serialized
    assert "Provider snippet" not in serialized
    assert result.provider_snippets_are_evidence is False
    assert result.provider_snippets_exposed_to_model is False
    assert result.search_candidates_are_retrieval_evidence is False
    assert result.candidate_urls_require_full_dap_retrieval is True
    assert result.retrieval_tool_id == "internet.research.retrieve"
    assert result.retrieval_success is True
    assert result.disposition == "succeeded"


def test_searxng_pipeline_factory_has_no_provider_credential_or_endpoint_argument() -> None:
    pipeline = WebSearchRetrievalPipeline.searxng_local(retrieval_tool=FakeRetrievalTool())

    assert isinstance(pipeline._provider, SearXNGWebSearchProvider)
