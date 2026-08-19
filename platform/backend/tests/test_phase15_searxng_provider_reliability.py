from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from gateway.searxng_search_provider import (
    MAX_SEARXNG_PROVIDER_RESULT_SCAN,
    SearXNGSearchRawResponse,
    SearXNGWebSearchProvider,
)
from gateway.web_search_discovery import (
    WebSearchDiscoveryError,
    WebSearchRetrievalPipeline,
)
from gateway.web_search_provider import WebSearchQuery


class FakeSearXNGTransport:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.body = json.dumps(payload).encode()
        self.calls: list[WebSearchQuery] = []

    async def search_raw(self, query: WebSearchQuery) -> SearXNGSearchRawResponse:
        self.calls.append(query)
        return SearXNGSearchRawResponse(
            body=self.body,
            body_sha256=hashlib.sha256(self.body).hexdigest(),
            status_code=200,
            content_type="application/json",
        )


class RetrievalMustNotRun:
    async def execute(self, arguments: dict[str, Any]) -> None:
        raise AssertionError(f"retrieval must not run without candidates: {arguments}")


@pytest.mark.asyncio
async def test_provider_scans_past_rejected_top_results_until_requested_candidates() -> None:
    transport = FakeSearXNGTransport(
        {
            "results": [
                {
                    "title": "Rejected HTTP one",
                    "url": "http://example.com/one",
                    "content": "not admissible",
                },
                "malformed-item",
                {
                    "title": "Rejected HTTP two",
                    "url": "http://example.org/two",
                    "content": "not admissible",
                },
                {
                    "title": "Safe one",
                    "url": "https://example.com/safe-one",
                    "content": "candidate",
                },
                {
                    "title": "Safe two",
                    "url": "https://example.org/safe-two",
                    "content": "candidate",
                },
                {
                    "title": "Safe three not needed",
                    "url": "https://iana.org/safe-three",
                    "content": "candidate",
                },
            ]
        }
    )
    provider = SearXNGWebSearchProvider(transport=transport)
    query = WebSearchQuery(query="bounded scan reliability", count=2)

    result = await provider.search(query)

    assert transport.calls == [query]
    assert result.provider_result_count == 6
    assert result.considered_result_count == 5
    assert result.invalid_candidate_count == 1
    assert result.policy_rejected_candidate_count == 2
    assert result.accepted_candidate_count == 2
    assert result.dropped_unsafe_candidate_count == 3
    assert result.provider_zero_results is False
    assert result.admissible_candidate_zero_after_filtering is False
    assert [candidate.url for candidate in result.candidates] == [
        "https://example.com/safe-one",
        "https://example.org/safe-two",
    ]


@pytest.mark.asyncio
async def test_provider_result_scan_is_hard_bounded_to_twenty_items() -> None:
    results: list[dict[str, str]] = [
        {
            "title": f"Rejected {index}",
            "url": f"http://example.com/{index}",
            "content": "not admissible",
        }
        for index in range(MAX_SEARXNG_PROVIDER_RESULT_SCAN)
    ]
    results.append(
        {
            "title": "Safe but outside bounded scan",
            "url": "https://example.org/outside-window",
            "content": "must not be considered",
        }
    )
    provider = SearXNGWebSearchProvider(
        transport=FakeSearXNGTransport({"results": results})
    )

    result = await provider.search(WebSearchQuery(query="bounded window", count=1))

    assert result.provider_result_count == MAX_SEARXNG_PROVIDER_RESULT_SCAN + 1
    assert result.considered_result_count == MAX_SEARXNG_PROVIDER_RESULT_SCAN
    assert result.policy_rejected_candidate_count == MAX_SEARXNG_PROVIDER_RESULT_SCAN
    assert result.accepted_candidate_count == 0
    assert result.candidates == ()
    assert result.provider_zero_results is False
    assert result.admissible_candidate_zero_after_filtering is True


@pytest.mark.asyncio
async def test_pipeline_distinguishes_provider_zero_results_in_diagnostics() -> None:
    provider = SearXNGWebSearchProvider(
        transport=FakeSearXNGTransport({"results": []})
    )
    pipeline = WebSearchRetrievalPipeline(
        provider=provider,
        retrieval_tool=RetrievalMustNotRun(),
    )

    with pytest.raises(WebSearchDiscoveryError) as exc_info:
        await pipeline.run(
            objective="Find a public source for the owner request.",
            query=WebSearchQuery(query="provider zero diagnostic", count=3),
        )

    assert exc_info.value.code == "no-search-candidates"
    assert exc_info.value.diagnostics == {
        "provider_result_count": 0,
        "considered_result_count": 0,
        "invalid_candidate_count": 0,
        "policy_rejected_candidate_count": 0,
        "accepted_candidate_count": 0,
        "provider_zero_results": True,
        "admissible_candidate_zero_after_filtering": False,
    }
    assert "zero raw results" in exc_info.value.detail


@pytest.mark.asyncio
async def test_pipeline_distinguishes_filtering_zero_results_in_diagnostics() -> None:
    provider = SearXNGWebSearchProvider(
        transport=FakeSearXNGTransport(
            {
                "results": [
                    {
                        "title": "Rejected local-policy result",
                        "url": "http://example.com/not-https",
                        "content": "not admissible",
                    }
                ]
            }
        )
    )
    pipeline = WebSearchRetrievalPipeline(
        provider=provider,
        retrieval_tool=RetrievalMustNotRun(),
    )

    with pytest.raises(WebSearchDiscoveryError) as exc_info:
        await pipeline.run(
            objective="Find a public source for the owner request.",
            query=WebSearchQuery(query="filtering zero diagnostic", count=1),
        )

    assert exc_info.value.code == "no-search-candidates"
    assert exc_info.value.diagnostics["provider_result_count"] == 1
    assert exc_info.value.diagnostics["considered_result_count"] == 1
    assert exc_info.value.diagnostics["policy_rejected_candidate_count"] == 1
    assert exc_info.value.diagnostics["provider_zero_results"] is False
    assert exc_info.value.diagnostics["admissible_candidate_zero_after_filtering"] is True
    assert "none survived DAP candidate validation" in exc_info.value.detail
