from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

import pytest

from gateway.research_query_fallback import (
    MAX_SEARCH_QUERY_ATTEMPTS,
    SEARCH_QUERY_FALLBACK_POLICY_ID,
    build_research_query_attempts,
    build_research_query_fallback_plan,
)
from gateway.research_source_quality import (
    SOURCE_URL_DUPLICATE_POLICY_ID,
    canonical_source_url_duplicate_key,
    select_source_diverse_candidates,
)
from gateway.web_search_discovery import WebSearchRetrievalPipeline
from gateway.web_search_provider import WebSearchCandidate, WebSearchQuery
from tools.base import ToolExecutionResult


def _candidate(rank: int, url: str) -> WebSearchCandidate:
    return WebSearchCandidate(
        rank=rank,
        title=f"Candidate {rank}",
        url=url,
        snippet="provider metadata only",
    )


def _discovery(query: str, candidates: tuple[WebSearchCandidate, ...]) -> Any:
    digest = hashlib.sha256(
        (query + "|" + "|".join(candidate.url for candidate in candidates)).encode()
    ).hexdigest()
    return SimpleNamespace(
        provider_id="searxng-local-v1",
        discovery_id=f"web-search-{digest[:24]}",
        discovery_sha256=digest,
        query=query,
        candidates=candidates,
        provider_result_count=len(candidates),
        considered_result_count=len(candidates),
        invalid_candidate_count=0,
        policy_rejected_candidate_count=0,
        accepted_candidate_count=len(candidates),
        provider_zero_results=not candidates,
        admissible_candidate_zero_after_filtering=False,
    )


class FallbackProvider:
    def __init__(self) -> None:
        self.calls: list[WebSearchQuery] = []

    async def search(self, query: WebSearchQuery) -> Any:
        self.calls.append(query)
        if len(self.calls) == 1:
            return _discovery(query.query, ())
        return _discovery(
            query.query,
            (_candidate(1, "https://example.com/source"),),
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
                "sources": [],
            },
        )


def test_query_fallback_plan_is_deterministic_owner_query_only_and_bounded() -> None:
    query = WebSearchQuery(query="IANA example domains RFC 2606", count=5)

    plan = build_research_query_fallback_plan(query)
    attempts = build_research_query_attempts(query)

    assert plan.policy_id == SEARCH_QUERY_FALLBACK_POLICY_ID
    assert plan.maximum_attempt_count == MAX_SEARCH_QUERY_ATTEMPTS == 3
    assert plan.queries == (
        "IANA example domains RFC 2606",
        "IANA example domains RFC",
        "example domains RFC 2606",
    )
    assert tuple(item.query for item in attempts) == plan.queries
    assert all(item.count == 5 for item in attempts)
    original_tokens = set(query.query.split())
    assert all(set(value.split()) <= original_tokens for value in plan.queries)
    assert plan.model_generated_expansion_allowed is False
    assert plan.provider_switching_allowed is False
    assert plan.added_query_terms_allowed is False


@pytest.mark.asyncio
async def test_pipeline_falls_back_only_after_zero_candidate_attempt() -> None:
    provider = FallbackProvider()
    retrieval = FakeRetrievalTool()
    pipeline = WebSearchRetrievalPipeline(
        provider=provider,
        retrieval_tool=retrieval,
        enable_bounded_query_fallback=True,
    )

    result = await pipeline.run(
        objective="Find one admissible public source.",
        query=WebSearchQuery(query="IANA example domains RFC 2606", count=5),
    )

    assert [call.query for call in provider.calls] == [
        "IANA example domains RFC 2606",
        "IANA example domains RFC",
    ]
    assert result.original_query == "IANA example domains RFC 2606"
    assert result.query == "IANA example domains RFC"
    assert result.search_attempt_count == 2
    assert result.search_queries_attempted == (
        "IANA example domains RFC 2606",
        "IANA example domains RFC",
    )
    assert result.search_fallback_policy_id == SEARCH_QUERY_FALLBACK_POLICY_ID
    assert result.fallback_used is True
    assert [item.outcome for item in result.search_attempts] == [
        "no-candidate",
        "selected",
    ]
    assert result.selected_urls == ("https://example.com/source",)
    assert retrieval.calls == [
        {
            "objective": "Find one admissible public source.",
            "urls": ["https://example.com/source"],
        }
    ]
    assert result.provider_search_duration_ms is not None
    assert result.retrieval_duration_ms is not None
    assert result.total_pipeline_duration_ms is not None
    assert result.provider_snippets_exposed_to_model is False
    assert result.provider_titles_exposed_to_model is False


def test_tracking_and_fragment_variants_are_canonical_duplicates_only_for_selection() -> None:
    first = "https://example.com/page?a=1&utm_source=feed#section"
    second = "https://example.com/page?utm_medium=email&a=1"

    assert canonical_source_url_duplicate_key(first) == (
        canonical_source_url_duplicate_key(second)
    )

    result = select_source_diverse_candidates(
        (
            _candidate(1, first),
            _candidate(2, second),
            _candidate(3, "https://example.org/other"),
        ),
        limit=3,
    )

    assert result.duplicate_normalization_policy_id == SOURCE_URL_DUPLICATE_POLICY_ID
    assert result.skipped_exact_duplicate_count == 0
    assert result.skipped_canonical_duplicate_count == 1
    assert result.selected_urls == (
        first,
        "https://example.org/other",
    )
    assert result.selected_urls[0] == first
