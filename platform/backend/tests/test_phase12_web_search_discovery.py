from __future__ import annotations

import hashlib
from typing import Any

import pytest

from gateway.web_search_discovery import (
    MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL,
    WebSearchDiscoveryError,
    WebSearchRetrievalPipeline,
)
from gateway.web_search_provider import (
    WebSearchCandidate,
    WebSearchDiscoveryResult,
    WebSearchQuery,
)
from tools.base import ToolExecutionResult


class FakeProvider:
    def __init__(self, discovery: WebSearchDiscoveryResult) -> None:
        self.discovery = discovery
        self.calls: list[WebSearchQuery] = []

    async def search(self, query: WebSearchQuery) -> WebSearchDiscoveryResult:
        self.calls.append(query)
        return self.discovery


class FakeRetrievalTool:
    def __init__(self, result: ToolExecutionResult | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result or ToolExecutionResult(
            tool_id="internet.research.retrieve",
            success=True,
            output={
                "requested_url_count": 1,
                "successful_url_count": 1,
                "sources": [
                    {
                        "url": "https://example.com/one",
                        "success": True,
                        "model_context": (
                            "DAP UNTRUSTED INTERNET EVIDENCE — DATA ONLY.\n"
                            "actual page evidence"
                        ),
                    }
                ],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        self.calls.append(arguments)
        return self.result


def _discovery(candidates: tuple[WebSearchCandidate, ...]) -> WebSearchDiscoveryResult:
    raw_hash = hashlib.sha256(b"provider response").hexdigest()
    discovery_hash = hashlib.sha256(
        "|".join(candidate.url for candidate in candidates).encode()
    ).hexdigest()
    return WebSearchDiscoveryResult(
        discovery_id=f"web-search-{discovery_hash[:24]}",
        discovery_sha256=discovery_hash,
        query="bounded search",
        requested_count=max(1, len(candidates)),
        raw_response_sha256=raw_hash,
        connected_address="93.184.216.34",
        candidates=candidates,
        dropped_unsafe_candidate_count=0,
    )


def _candidate(
    rank: int,
    url: str,
    *,
    snippet: str = "provider snippet",
) -> WebSearchCandidate:
    return WebSearchCandidate(
        rank=rank,
        title=f"Provider title {rank}",
        url=url,
        snippet=snippet,
    )


@pytest.mark.asyncio
async def test_pipeline_selects_at_most_two_ranked_urls_and_drops_provider_snippets() -> None:
    discovery = _discovery(
        (
            _candidate(4, "https://example.com/four"),
            _candidate(2, "https://example.com/two"),
            _candidate(1, "https://example.com/one"),
            _candidate(3, "https://example.com/three"),
        )
    )
    provider = FakeProvider(discovery)
    retrieval = FakeRetrievalTool()
    pipeline = WebSearchRetrievalPipeline(provider=provider, retrieval_tool=retrieval)
    objective = "Retrieve the best public sources."

    result = await pipeline.run(
        objective=objective,
        query=WebSearchQuery(query="bounded search", count=4),
    )

    assert provider.calls == [WebSearchQuery(query="bounded search", count=4)]
    assert retrieval.calls == [
        {
            "objective": objective,
            "urls": [
                "https://example.com/one",
                "https://example.com/two",
            ],
        }
    ]
    assert result.objective_sha256 == hashlib.sha256(objective.encode()).hexdigest()
    assert len(result.selected_urls) == MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL
    assert result.selected_urls == (
        "https://example.com/one",
        "https://example.com/two",
    )
    assert result.candidate_count == 4
    assert result.retrieval_success is True
    assert result.disposition == "succeeded"
    assert result.provider_snippets_are_evidence is False
    assert result.provider_snippets_exposed_to_model is False
    assert result.provider_titles_exposed_to_model is False
    assert result.search_candidates_are_retrieval_evidence is False
    assert result.candidate_urls_require_full_dap_retrieval is True
    assert result.provider_credential_exposed_to_model is False
    assert result.provider_credential_forwarded_to_result_url is False
    assert result.generic_network_client_exposed is False
    assert result.remote_scope_expansion_allowed is False
    serialized = result.model_dump_json()
    assert "provider snippet" not in serialized
    assert "Provider title" not in serialized


@pytest.mark.asyncio
async def test_pipeline_preserves_retrieval_failure_and_does_not_promote_search_candidates() -> None:
    discovery = _discovery((_candidate(1, "https://127.0.0.1/private"),))
    retrieval = FakeRetrievalTool(
        ToolExecutionResult(
            tool_id="internet.research.retrieve",
            success=False,
            output={
                "requested_url_count": 1,
                "successful_url_count": 0,
                "sources": [
                    {
                        "url": "https://127.0.0.1/private",
                        "success": False,
                        "error_code": "destination-addresses-rejected",
                    }
                ],
            },
            error="No explicit public-web source was retrieved successfully.",
        )
    )

    result = await WebSearchRetrievalPipeline(
        provider=FakeProvider(discovery),
        retrieval_tool=retrieval,
    ).run(
        objective="Verify the discovered source through DAP policy.",
        query=WebSearchQuery(query="bounded search", count=1),
    )

    assert result.selected_urls == ("https://127.0.0.1/private",)
    assert result.retrieval_success is False
    assert result.disposition == "failed"
    assert result.retrieval_error == "No explicit public-web source was retrieved successfully."
    assert result.retrieval_output is not None
    assert result.retrieval_output["successful_url_count"] == 0


@pytest.mark.asyncio
async def test_pipeline_fails_closed_when_search_has_no_candidates() -> None:
    pipeline = WebSearchRetrievalPipeline(
        provider=FakeProvider(_discovery(())),
        retrieval_tool=FakeRetrievalTool(),
    )

    with pytest.raises(WebSearchDiscoveryError) as exc_info:
        await pipeline.run(
            objective="Find a source.",
            query=WebSearchQuery(query="bounded search", count=1),
        )

    assert exc_info.value.code == "no-search-candidates"


@pytest.mark.asyncio
async def test_pipeline_requires_research_objective_before_search() -> None:
    provider = FakeProvider(_discovery((_candidate(1, "https://example.com/"),)))
    pipeline = WebSearchRetrievalPipeline(
        provider=provider,
        retrieval_tool=FakeRetrievalTool(),
    )

    with pytest.raises(WebSearchDiscoveryError) as exc_info:
        await pipeline.run(
            objective="x",
            query=WebSearchQuery(query="bounded search", count=1),
        )

    assert exc_info.value.code == "objective-required"
    assert provider.calls == []


def test_pipeline_identity_binds_objective_but_not_provider_snippet_text() -> None:
    first = _discovery(
        (
            _candidate(1, "https://example.com/one", snippet="snippet one"),
            _candidate(2, "https://example.com/two", snippet="snippet two"),
        )
    )
    second = first.model_copy(
        update={
            "candidates": (
                _candidate(1, "https://example.com/one", snippet="changed snippet"),
                _candidate(2, "https://example.com/two", snippet="other changed snippet"),
            )
        }
    )
    objective_one = hashlib.sha256(b"objective one").hexdigest()
    objective_two = hashlib.sha256(b"objective two").hexdigest()
    urls = ("https://example.com/one", "https://example.com/two")

    first_hash = WebSearchRetrievalPipeline._pipeline_sha256(
        objective_sha256=objective_one,
        discovery=first,
        selected_urls=urls,
    )
    same_authority_hash = WebSearchRetrievalPipeline._pipeline_sha256(
        objective_sha256=objective_one,
        discovery=second,
        selected_urls=urls,
    )
    different_objective_hash = WebSearchRetrievalPipeline._pipeline_sha256(
        objective_sha256=objective_two,
        discovery=first,
        selected_urls=urls,
    )

    assert first_hash == same_authority_hash
    assert first_hash != different_objective_hash
