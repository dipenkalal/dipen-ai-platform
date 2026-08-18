from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import socket
from typing import Any, Literal, Protocol
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field

from agents.cancellation import raise_if_current_cancellation_requested
from gateway.internet_destination_policy import (
    InternetDestinationIntent,
    InternetDestinationPolicy,
)
from gateway.internet_transport import InternetTransportLimits, PinnedHTTPSFetcher
from gateway.web_search_provider import WebSearchCandidate, WebSearchQuery

SEARXNG_PROVIDER_ID: Literal["searxng-local-v1"] = "searxng-local-v1"
SEARXNG_HOST: Literal["127.0.0.1"] = "127.0.0.1"
SEARXNG_PORT = 8888
SEARXNG_PATH = "/search"
SEARXNG_ENDPOINT = f"http://{SEARXNG_HOST}:{SEARXNG_PORT}{SEARXNG_PATH}"
_MAX_PROVIDER_RESPONSE_BYTES = 1024 * 1024


class SearXNGSearchProviderError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class SearXNGSearchRawResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    body: bytes
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    connected_address: Literal["127.0.0.1"] = SEARXNG_HOST
    status_code: int
    content_type: str | None


class SearXNGSearchDiscoveryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    discovery_id: str = Field(pattern=r"^web-search-[0-9a-f]{24}$")
    discovery_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_id: Literal["searxng-local-v1"] = SEARXNG_PROVIDER_ID
    query: str
    requested_count: int = Field(ge=1, le=10)
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    connected_address: Literal["127.0.0.1"] = SEARXNG_HOST
    candidates: tuple[WebSearchCandidate, ...]
    dropped_unsafe_candidate_count: int = Field(ge=0)
    provider_is_local_only: Literal[True] = True
    provider_credential_required: Literal[False] = False
    provider_credential_exposed_to_model: Literal[False] = False
    provider_credential_persisted: Literal[False] = False
    provider_credential_forwarded_to_result_url: Literal[False] = False
    generic_network_client_exposed: Literal[False] = False
    candidate_content_is_untrusted: Literal[True] = True
    candidate_urls_require_full_dap_retrieval: Literal[True] = True
    automatic_knowledge_mutation_performed: Literal[False] = False
    task_ledger_mutation_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False


class SearXNGSearchTransportProtocol(Protocol):
    async def search_raw(self, query: WebSearchQuery) -> SearXNGSearchRawResponse: ...


class SearXNGFixedLocalTransport:
    """HTTP transport fixed to one loopback SearXNG socket; no DNS or credentials."""

    def __init__(self, *, limits: InternetTransportLimits | None = None) -> None:
        self._limits = limits or InternetTransportLimits(
            dns_timeout_seconds=1.0,
            connect_timeout_seconds=3.0,
            read_timeout_seconds=12.0,
            total_timeout_seconds=15.0,
            max_header_bytes=32 * 1024,
            max_header_count=100,
            max_body_bytes=_MAX_PROVIDER_RESPONSE_BYTES,
            max_redirects=0,
            allowed_content_types=("application/json",),
        )
        self._response_parser = PinnedHTTPSFetcher(limits=self._limits)

    async def search_raw(self, query: WebSearchQuery) -> SearXNGSearchRawResponse:
        raise_if_current_cancellation_requested(boundary="before-searxng-search-connect")
        request = self._build_request(query)
        try:
            async with asyncio.timeout(self._limits.total_timeout_seconds):
                return await self._request(request)
        except TimeoutError as exc:
            raise SearXNGSearchProviderError(
                "searxng-total-timeout",
                "Local SearXNG search exceeded the DAP time budget.",
            ) from exc

    async def _request(self, request: bytes) -> SearXNGSearchRawResponse:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=SEARXNG_HOST,
                    port=SEARXNG_PORT,
                    family=socket.AF_INET,
                    flags=socket.AI_NUMERICHOST,
                    limit=self._limits.max_header_bytes + 4096,
                ),
                timeout=self._limits.connect_timeout_seconds,
            )
        except TimeoutError as exc:
            raise SearXNGSearchProviderError(
                "searxng-connect-timeout",
                "Connection to local SearXNG timed out.",
            ) from exc
        except OSError as exc:
            raise SearXNGSearchProviderError(
                "searxng-unavailable",
                "Local SearXNG is unavailable on the fixed DAP loopback endpoint.",
            ) from exc

        try:
            peer = writer.get_extra_info("peername")
            if not isinstance(peer, tuple) or not peer or peer[0] != SEARXNG_HOST:
                raise SearXNGSearchProviderError(
                    "searxng-peer-mismatch",
                    "Local SearXNG transport connected outside the fixed loopback endpoint.",
                )
            writer.write(request)
            await asyncio.wait_for(writer.drain(), timeout=self._limits.read_timeout_seconds)
            response = await self._response_parser._read_response(reader, "GET")
        finally:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
            except (TimeoutError, OSError):
                pass

        if response.redirect_location is not None:
            raise SearXNGSearchProviderError(
                "searxng-redirect-rejected",
                "Local SearXNG redirects are not allowed by the DAP provider boundary.",
            )
        if response.status_code != 200:
            raise SearXNGSearchProviderError(
                "searxng-http-error",
                f"Local SearXNG returned HTTP status {response.status_code}.",
            )
        if response.content_type != "application/json":
            raise SearXNGSearchProviderError(
                "searxng-content-type-rejected",
                "Local SearXNG response was not application/json.",
            )
        raise_if_current_cancellation_requested(boundary="after-searxng-search-response")
        return SearXNGSearchRawResponse(
            body=response.body,
            body_sha256=hashlib.sha256(response.body).hexdigest(),
            status_code=response.status_code,
            content_type=response.content_type,
        )

    @staticmethod
    def _build_target(query: WebSearchQuery) -> str:
        parameters = urlencode(
            {
                "q": query.query,
                "format": "json",
                "categories": "general",
                "safesearch": "2",
                "pageno": "1",
            }
        )
        return f"{SEARXNG_PATH}?{parameters}"

    @classmethod
    def _build_request(cls, query: WebSearchQuery) -> bytes:
        target = cls._build_target(query)
        lines = (
            f"GET {target} HTTP/1.1",
            f"Host: {SEARXNG_HOST}:{SEARXNG_PORT}",
            "User-Agent: DAP-InternetResearchGateway/12H-SearXNG",
            "Accept: application/json",
            "Accept-Encoding: identity",
            "Connection: close",
            "",
            "",
        )
        return "\r\n".join(lines).encode("ascii")


class SearXNGWebSearchProvider:
    """Convert local SearXNG results into untrusted candidate URLs only."""

    def __init__(
        self,
        *,
        transport: SearXNGSearchTransportProtocol | None = None,
        destination_policy: InternetDestinationPolicy | None = None,
    ) -> None:
        self._transport = transport or SearXNGFixedLocalTransport()
        self._destination_policy = destination_policy or InternetDestinationPolicy()

    async def search(self, query: WebSearchQuery) -> SearXNGSearchDiscoveryResult:
        raw = await self._transport.search_raw(query)
        try:
            payload = json.loads(raw.body)
        except json.JSONDecodeError as exc:
            raise SearXNGSearchProviderError(
                "searxng-json-invalid",
                "Local SearXNG returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise SearXNGSearchProviderError(
                "searxng-json-invalid",
                "Local SearXNG response root must be an object.",
            )
        provider_results = payload.get("results", [])
        if not isinstance(provider_results, list):
            raise SearXNGSearchProviderError(
                "searxng-json-invalid",
                "Local SearXNG results must be a list.",
            )

        candidates: list[WebSearchCandidate] = []
        dropped = 0
        for rank, item in enumerate(provider_results[: query.count], start=1):
            candidate = self._candidate_from_item(rank, item)
            if candidate is None:
                dropped += 1
                continue
            candidates.append(candidate)

        discovery_payload = {
            "provider_id": SEARXNG_PROVIDER_ID,
            "query": query.query,
            "requested_count": query.count,
            "raw_response_sha256": raw.body_sha256,
            "connected_address": raw.connected_address,
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "dropped_unsafe_candidate_count": dropped,
        }
        canonical = json.dumps(discovery_payload, sort_keys=True, separators=(",", ":"))
        discovery_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return SearXNGSearchDiscoveryResult(
            discovery_id=f"web-search-{discovery_sha256[:24]}",
            discovery_sha256=discovery_sha256,
            query=query.query,
            requested_count=query.count,
            raw_response_sha256=raw.body_sha256,
            candidates=tuple(candidates),
            dropped_unsafe_candidate_count=dropped,
        )

    def _candidate_from_item(self, rank: int, item: Any) -> WebSearchCandidate | None:
        if not isinstance(item, dict):
            return None
        title = item.get("title")
        url = item.get("url")
        content = item.get("content", "")
        if not isinstance(title, str) or not title.strip() or not isinstance(url, str):
            return None
        preflight = self._destination_policy.preflight(
            InternetDestinationIntent(url=url, method="GET")
        )
        if preflight.disposition != "accepted" or preflight.admission is None:
            return None
        snippet = content.strip() if isinstance(content, str) else ""
        return WebSearchCandidate(
            rank=rank,
            title=title.strip()[:1000],
            url=preflight.admission.canonical_url,
            snippet=snippet[:5000],
        )


def searxng_fixed_endpoint_is_loopback_only() -> bool:
    address = ipaddress.ip_address(SEARXNG_HOST)
    return address.is_loopback and SEARXNG_HOST == "127.0.0.1" and SEARXNG_PORT == 8888
