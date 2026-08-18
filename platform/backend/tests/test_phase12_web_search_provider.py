from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from gateway.internet_destination_policy import (
    InternetDestinationPolicy,
    InternetDestinationRequest,
)
from gateway.web_search_provider import (
    BRAVE_API_HOSTNAME,
    BRAVE_API_KEY_ENV,
    BRAVE_API_PATH,
    BRAVE_PROVIDER_ID,
    BraveSearchPinnedTransport,
    BraveSearchRawResponse,
    BraveWebSearchProvider,
    WebSearchProviderError,
    WebSearchQuery,
    brave_search_configured,
)

TOKEN = "0123456789abcdef0123456789abcdef"


class FakeBraveTransport:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.body = json.dumps(payload).encode()
        self.calls: list[tuple[WebSearchQuery, str]] = []

    async def search_raw(
        self,
        query: WebSearchQuery,
        *,
        subscription_token: str,
    ) -> BraveSearchRawResponse:
        self.calls.append((query, subscription_token))
        return BraveSearchRawResponse(
            body=self.body,
            body_sha256=hashlib.sha256(self.body).hexdigest(),
            connected_address="93.184.216.34",
            status_code=200,
            content_type="application/json",
        )


def test_query_is_bounded_normalized_and_count_is_capped() -> None:
    query = WebSearchQuery(query="  cloud   devops jobs  ", count=10)

    assert query.query == "cloud devops jobs"
    assert query.count == 10

    with pytest.raises(ValueError):
        WebSearchQuery(query="word " * 51)

    with pytest.raises(ValueError):
        WebSearchQuery(query="valid query", count=11)


def test_provider_is_credential_gated_and_disabled_without_environment_key() -> None:
    assert brave_search_configured({}) is False
    assert brave_search_configured({BRAVE_API_KEY_ENV: TOKEN}) is True

    with pytest.raises(WebSearchProviderError) as exc_info:
        BraveWebSearchProvider.from_environment({})

    assert exc_info.value.code == "provider-not-configured"


def test_provider_rejects_header_unsafe_credentials() -> None:
    with pytest.raises(WebSearchProviderError) as exc_info:
        BraveWebSearchProvider(subscription_token="unsafe token value")

    assert exc_info.value.code == "provider-credential-invalid"


def test_search_url_and_request_are_fixed_to_brave_destination() -> None:
    query = WebSearchQuery(query="phase 12 research", count=4)
    url = BraveSearchPinnedTransport._build_search_url(query)
    request = BraveSearchPinnedTransport._build_request(url, TOKEN)

    assert url.startswith(f"https://{BRAVE_API_HOSTNAME}{BRAVE_API_PATH}?")
    assert "q=phase+12+research" in url
    assert "count=4" in url
    assert "safesearch=strict" in url
    assert request.startswith(f"GET {BRAVE_API_PATH}?".encode())
    assert f"Host: {BRAVE_API_HOSTNAME}\r\n".encode() in request
    assert f"X-Subscription-Token: {TOKEN}\r\n".encode() in request
    assert b"Accept-Encoding: identity\r\n" in request
    assert b"Cookie:" not in request
    assert b"Proxy-Authorization:" not in request


def test_provider_request_rejects_non_brave_target_even_with_valid_token() -> None:
    with pytest.raises(WebSearchProviderError) as exc_info:
        BraveSearchPinnedTransport._build_request(
            "https://example.com/res/v1/web/search?q=test",
            TOKEN,
        )

    assert exc_info.value.code == "provider-request-target-rejected"


@pytest.mark.asyncio
async def test_adapter_returns_only_url_preflight_candidates_then_requires_full_retrieval() -> None:
    transport = FakeBraveTransport(
        {
            "web": {
                "results": [
                    {
                        "title": "Safe public result",
                        "url": "https://Example.com/article#section",
                        "description": "Search snippet only.",
                    },
                    {
                        "title": "Loopback candidate",
                        "url": "https://127.0.0.1/private",
                        "description": "Candidate only; full retrieval must reject it.",
                    },
                    {
                        "title": "Plain HTTP result",
                        "url": "http://example.org/insecure",
                        "description": "Dropped during URL preflight.",
                    },
                ]
            }
        }
    )
    provider = BraveWebSearchProvider(
        subscription_token=TOKEN,
        transport=transport,
    )

    result = await provider.search(WebSearchQuery(query="safe public evidence", count=3))

    assert transport.calls[0][1] == TOKEN
    assert result.provider_id == BRAVE_PROVIDER_ID
    assert result.query == "safe public evidence"
    assert result.requested_count == 3
    assert result.connected_address == "93.184.216.34"
    assert len(result.candidates) == 2

    public_candidate = result.candidates[0]
    assert public_candidate.rank == 1
    assert public_candidate.url == "https://example.com/article"
    assert public_candidate.snippet == "Search snippet only."

    loopback_candidate = result.candidates[1]
    assert loopback_candidate.rank == 2
    assert loopback_candidate.url == "https://127.0.0.1/private"

    for candidate in result.candidates:
        assert candidate.candidate_is_untrusted is True
        assert candidate.candidate_is_retrieval_evidence is False
        assert candidate.candidate_url_requires_dap_retrieval is True
        assert candidate.remote_instructions_are_authority is False
        assert candidate.tool_selection_allowed is False

    full_admission = InternetDestinationPolicy().evaluate(
        InternetDestinationRequest(
            url=loopback_candidate.url,
            method="GET",
            resolved_addresses=("127.0.0.1",),
        )
    )
    assert full_admission.disposition == "rejected"
    assert full_admission.admission is None
    assert "non-public-address" in {
        finding.rule_id for finding in full_admission.findings
    }

    assert result.dropped_unsafe_candidate_count == 1
    assert result.provider_credential_exposed_to_model is False
    assert result.provider_credential_persisted is False
    assert result.provider_credential_forwarded_to_result_url is False
    assert result.generic_network_client_exposed is False
    assert result.candidate_content_is_untrusted is True
    assert result.candidate_urls_require_full_dap_retrieval is True
    assert result.automatic_knowledge_mutation_performed is False
    assert result.task_ledger_mutation_performed is False
    assert result.guardian_contacted is False
    assert result.privileged_host_action_performed is False
    assert TOKEN not in result.model_dump_json()


@pytest.mark.asyncio
async def test_adapter_identity_is_deterministic_for_same_provider_response() -> None:
    payload = {
        "web": {
            "results": [
                {
                    "title": "One",
                    "url": "https://example.com/one",
                    "description": "One result",
                }
            ]
        }
    }
    transport = FakeBraveTransport(payload)
    provider = BraveWebSearchProvider(subscription_token=TOKEN, transport=transport)
    query = WebSearchQuery(query="deterministic search", count=1)

    first = await provider.search(query)
    second = await provider.search(query)

    assert first == second
    assert first.discovery_id.startswith("web-search-")
    assert first.discovery_sha256 == second.discovery_sha256


@pytest.mark.asyncio
async def test_invalid_provider_json_fails_closed_without_exposing_token() -> None:
    class InvalidTransport:
        async def search_raw(
            self,
            query: WebSearchQuery,
            *,
            subscription_token: str,
        ) -> BraveSearchRawResponse:
            del query, subscription_token
            body = b"not-json"
            return BraveSearchRawResponse(
                body=body,
                body_sha256=hashlib.sha256(body).hexdigest(),
                connected_address="93.184.216.34",
                status_code=200,
                content_type="application/json",
            )

    provider = BraveWebSearchProvider(
        subscription_token=TOKEN,
        transport=InvalidTransport(),
    )

    with pytest.raises(WebSearchProviderError) as exc_info:
        await provider.search(WebSearchQuery(query="invalid response"))

    assert exc_info.value.code == "provider-json-invalid"
    assert TOKEN not in str(exc_info.value)
