from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from gateway.searxng_search_provider import (
    SEARXNG_ENDPOINT,
    SEARXNG_HOST,
    SEARXNG_PATH,
    SEARXNG_PORT,
    SEARXNG_PROVIDER_ID,
    SearXNGFixedLocalTransport,
    SearXNGSearchProviderError,
    SearXNGSearchRawResponse,
    SearXNGWebSearchProvider,
    searxng_fixed_endpoint_is_loopback_only,
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


def test_provider_endpoint_is_fixed_loopback_without_configuration_surface() -> None:
    assert SEARXNG_PROVIDER_ID == "searxng-local-v1"
    assert SEARXNG_HOST == "127.0.0.1"
    assert SEARXNG_PORT == 8888
    assert SEARXNG_PATH == "/search"
    assert SEARXNG_ENDPOINT == "http://127.0.0.1:8888/search"
    assert searxng_fixed_endpoint_is_loopback_only() is True


def test_local_request_is_get_json_only_and_contains_no_credential_headers() -> None:
    query = WebSearchQuery(query="zero cost local search", count=5)
    target = SearXNGFixedLocalTransport._build_target(query)
    request = SearXNGFixedLocalTransport._build_request(query)

    assert target.startswith("/search?")
    assert "q=zero+cost+local+search" in target
    assert "format=json" in target
    assert "categories=general" in target
    assert "safesearch=2" in target
    assert "pageno=1" in target
    assert request.startswith(b"GET /search?")
    assert b"Host: 127.0.0.1:8888\r\n" in request
    assert b"Accept: application/json\r\n" in request
    assert b"Accept-Encoding: identity\r\n" in request
    assert b"Authorization:" not in request
    assert b"X-Subscription-Token:" not in request
    assert b"Cookie:" not in request
    assert b"Proxy-Authorization:" not in request


@pytest.mark.asyncio
async def test_provider_returns_only_untrusted_https_candidates() -> None:
    transport = FakeSearXNGTransport(
        {
            "results": [
                {
                    "title": "Safe result",
                    "url": "https://Example.com/article#section",
                    "content": "SearXNG snippet only.",
                },
                {
                    "title": "Plain HTTP result",
                    "url": "http://example.org/insecure",
                    "content": "Must be dropped at DAP URL preflight.",
                },
                {
                    "title": "Second safe result",
                    "url": "https://example.org/two",
                    "content": "Second snippet.",
                },
            ]
        }
    )
    provider = SearXNGWebSearchProvider(transport=transport)

    result = await provider.search(WebSearchQuery(query="local provider evidence", count=3))

    assert transport.calls == [WebSearchQuery(query="local provider evidence", count=3)]
    assert result.provider_id == SEARXNG_PROVIDER_ID
    assert result.connected_address == "127.0.0.1"
    assert result.provider_is_local_only is True
    assert result.provider_credential_required is False
    assert result.provider_credential_exposed_to_model is False
    assert result.provider_credential_persisted is False
    assert result.provider_credential_forwarded_to_result_url is False
    assert result.generic_network_client_exposed is False
    assert result.candidate_content_is_untrusted is True
    assert result.candidate_urls_require_full_dap_retrieval is True
    assert result.dropped_unsafe_candidate_count == 1
    assert [candidate.url for candidate in result.candidates] == [
        "https://example.com/article",
        "https://example.org/two",
    ]
    for candidate in result.candidates:
        assert candidate.candidate_is_untrusted is True
        assert candidate.candidate_is_retrieval_evidence is False
        assert candidate.candidate_url_requires_dap_retrieval is True
        assert candidate.remote_instructions_are_authority is False
        assert candidate.tool_selection_allowed is False


@pytest.mark.asyncio
async def test_provider_identity_is_deterministic_for_same_local_response() -> None:
    payload = {
        "results": [
            {
                "title": "One",
                "url": "https://example.com/one",
                "content": "One result",
            }
        ]
    }
    provider = SearXNGWebSearchProvider(transport=FakeSearXNGTransport(payload))
    query = WebSearchQuery(query="deterministic local search", count=1)

    first = await provider.search(query)
    second = await provider.search(query)

    assert first == second
    assert first.discovery_id.startswith("web-search-")
    assert first.discovery_sha256 == second.discovery_sha256


@pytest.mark.asyncio
async def test_invalid_local_json_fails_closed() -> None:
    class InvalidTransport:
        async def search_raw(self, query: WebSearchQuery) -> SearXNGSearchRawResponse:
            del query
            body = b"not-json"
            return SearXNGSearchRawResponse(
                body=body,
                body_sha256=hashlib.sha256(body).hexdigest(),
                status_code=200,
                content_type="application/json",
            )

    provider = SearXNGWebSearchProvider(transport=InvalidTransport())

    with pytest.raises(SearXNGSearchProviderError) as exc_info:
        await provider.search(WebSearchQuery(query="invalid local response"))

    assert exc_info.value.code == "searxng-json-invalid"
