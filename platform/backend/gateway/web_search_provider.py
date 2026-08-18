from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import socket
import ssl
from collections.abc import Mapping
from typing import Any, Literal, Protocol
from urllib.parse import urlencode, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agents.cancellation import raise_if_current_cancellation_requested
from gateway.internet_destination_policy import (
    InternetDestinationIntent,
    InternetDestinationPolicy,
    InternetDestinationRequest,
)
from gateway.internet_transport import (
    InternetTransportError,
    InternetTransportLimits,
    PinnedHTTPSFetcher,
    SystemInternetDNSResolver,
)

BRAVE_PROVIDER_ID: Literal["brave-web-search-v1"] = "brave-web-search-v1"
BRAVE_API_HOSTNAME = "api.search.brave.com"
BRAVE_API_PATH = "/res/v1/web/search"
BRAVE_API_KEY_ENV = "DAP_BRAVE_SEARCH_API_KEY"
_MAX_PROVIDER_RESPONSE_BYTES = 1024 * 1024


class WebSearchProviderError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WebSearchQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1, max_length=400)
    count: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("search query must not be empty")
        if len(normalized.split()) > 50:
            raise ValueError("search query must contain at most 50 words")
        return normalized


class WebSearchCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=1000)
    url: str = Field(min_length=1, max_length=8192)
    snippet: str = Field(default="", max_length=5000)
    candidate_is_untrusted: Literal[True] = True
    candidate_is_retrieval_evidence: Literal[False] = False
    candidate_url_requires_dap_retrieval: Literal[True] = True
    remote_instructions_are_authority: Literal[False] = False
    tool_selection_allowed: Literal[False] = False


class WebSearchDiscoveryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    discovery_id: str = Field(pattern=r"^web-search-[0-9a-f]{24}$")
    discovery_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_id: Literal["brave-web-search-v1"] = BRAVE_PROVIDER_ID
    query: str
    requested_count: int
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    connected_address: str
    candidates: tuple[WebSearchCandidate, ...]
    dropped_unsafe_candidate_count: int = Field(ge=0)
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


class BraveSearchRawResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    body: bytes
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    connected_address: str
    status_code: int
    content_type: str | None


class BraveSearchTransportProtocol(Protocol):
    async def search_raw(
        self,
        query: WebSearchQuery,
        *,
        subscription_token: str,
    ) -> BraveSearchRawResponse: ...


class BraveSearchPinnedTransport:
    """Destination-pinned Brave transport with one destination-scoped secret header."""

    def __init__(
        self,
        *,
        policy: InternetDestinationPolicy | None = None,
        resolver: SystemInternetDNSResolver | None = None,
        limits: InternetTransportLimits | None = None,
    ) -> None:
        self._limits = limits or InternetTransportLimits(
            dns_timeout_seconds=4.0,
            connect_timeout_seconds=5.0,
            read_timeout_seconds=10.0,
            total_timeout_seconds=20.0,
            max_header_bytes=32 * 1024,
            max_header_count=100,
            max_body_bytes=_MAX_PROVIDER_RESPONSE_BYTES,
            max_redirects=0,
            allowed_content_types=("application/json",),
        )
        self._policy = policy or InternetDestinationPolicy()
        self._resolver = resolver or SystemInternetDNSResolver(limits=self._limits)
        self._response_parser = PinnedHTTPSFetcher(limits=self._limits)

    async def search_raw(
        self,
        query: WebSearchQuery,
        *,
        subscription_token: str,
    ) -> BraveSearchRawResponse:
        token = self._validate_subscription_token(subscription_token)
        url = self._build_search_url(query)
        try:
            async with asyncio.timeout(self._limits.total_timeout_seconds):
                preflight = self._policy.preflight(
                    InternetDestinationIntent(url=url, method="GET")
                )
                if preflight.disposition != "accepted" or preflight.admission is None:
                    raise WebSearchProviderError(
                        "provider-destination-rejected",
                        "Fixed Brave provider destination failed DAP preflight.",
                    )
                if preflight.admission.hostname != BRAVE_API_HOSTNAME:
                    raise WebSearchProviderError(
                        "provider-host-mismatch",
                        "Search provider hostname does not match the fixed Brave endpoint.",
                    )
                resolution = await self._resolver.resolve(preflight.admission)
                decision = self._policy.evaluate(
                    InternetDestinationRequest(
                        url=preflight.admission.canonical_url,
                        method="GET",
                        redirect_depth=0,
                        resolved_addresses=resolution.addresses,
                    )
                )
                if decision.disposition != "accepted" or decision.admission is None:
                    raise WebSearchProviderError(
                        "provider-addresses-rejected",
                        "Brave provider resolved addresses failed DAP public-address admission.",
                    )
                return await self._fetch_admitted(decision.admission, token)
        except TimeoutError as exc:
            raise WebSearchProviderError(
                "provider-total-timeout",
                "Brave search exceeded the DAP provider time budget.",
            ) from exc

    async def _fetch_admitted(self, admission: Any, token: str) -> BraveSearchRawResponse:
        last_error: Exception | None = None
        for raw_address in admission.approved_addresses:
            raise_if_current_cancellation_requested(boundary="before-web-search-connect")
            try:
                return await self._fetch_address(admission, raw_address, token)
            except (OSError, ssl.SSLError, TimeoutError, InternetTransportError) as exc:
                last_error = exc
        raise WebSearchProviderError(
            "provider-connect-failed",
            "Unable to reach the admitted Brave provider address set.",
        ) from last_error

    async def _fetch_address(
        self,
        admission: Any,
        raw_address: str,
        token: str,
    ) -> BraveSearchRawResponse:
        if admission.hostname != BRAVE_API_HOSTNAME:
            raise WebSearchProviderError(
                "provider-host-mismatch",
                "Provider credential may only be sent to the fixed Brave hostname.",
            )
        if raw_address not in admission.approved_addresses:
            raise WebSearchProviderError(
                "provider-address-not-admitted",
                "Provider transport attempted an address outside DAP admission.",
            )

        address = ipaddress.ip_address(raw_address)
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        tls_context = ssl.create_default_context()
        tls_context.minimum_version = ssl.TLSVersion.TLSv1_2
        tls_context.set_alpn_protocols(["http/1.1"])
        if hasattr(ssl, "OP_NO_COMPRESSION"):
            tls_context.options |= ssl.OP_NO_COMPRESSION

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=address.compressed,
                    port=443,
                    family=family,
                    flags=socket.AI_NUMERICHOST,
                    ssl=tls_context,
                    server_hostname=BRAVE_API_HOSTNAME,
                    limit=self._limits.max_header_bytes + 4096,
                ),
                timeout=self._limits.connect_timeout_seconds,
            )
        except TimeoutError as exc:
            raise WebSearchProviderError(
                "provider-connect-timeout",
                "TLS connection to Brave Search timed out.",
            ) from exc
        except (OSError, ssl.SSLError) as exc:
            raise WebSearchProviderError(
                "provider-connect-failed",
                "TLS connection to an admitted Brave Search address failed.",
            ) from exc

        try:
            request = self._build_request(admission.canonical_url, token)
            writer.write(request)
            await asyncio.wait_for(writer.drain(), timeout=self._limits.read_timeout_seconds)
            response = await self._response_parser._read_response(reader, "GET")
        finally:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
            except (TimeoutError, OSError, ssl.SSLError):
                pass

        if response.redirect_location is not None:
            raise WebSearchProviderError(
                "provider-redirect-rejected",
                "Provider redirects are rejected so the subscription token is never forwarded.",
            )
        if response.status_code != 200:
            raise WebSearchProviderError(
                "provider-http-error",
                f"Brave Search returned HTTP status {response.status_code}.",
            )
        if response.content_type != "application/json":
            raise WebSearchProviderError(
                "provider-content-type-rejected",
                "Brave Search response was not application/json.",
            )
        raise_if_current_cancellation_requested(boundary="after-web-search-response")
        return BraveSearchRawResponse(
            body=response.body,
            body_sha256=hashlib.sha256(response.body).hexdigest(),
            connected_address=address.compressed,
            status_code=response.status_code,
            content_type=response.content_type,
        )

    @staticmethod
    def _build_search_url(query: WebSearchQuery) -> str:
        parameters = urlencode(
            {
                "q": query.query,
                "count": query.count,
                "safesearch": "strict",
            }
        )
        return f"https://{BRAVE_API_HOSTNAME}{BRAVE_API_PATH}?{parameters}"

    @staticmethod
    def _build_request(canonical_url: str, token: str) -> bytes:
        parsed = urlsplit(canonical_url)
        if parsed.hostname != BRAVE_API_HOSTNAME or parsed.path != BRAVE_API_PATH:
            raise WebSearchProviderError(
                "provider-request-target-rejected",
                "Provider request target must remain the fixed Brave web-search endpoint.",
            )
        target = parsed.path
        if parsed.query:
            target = f"{target}?{parsed.query}"
        lines = (
            f"GET {target} HTTP/1.1",
            f"Host: {BRAVE_API_HOSTNAME}",
            "User-Agent: DAP-InternetResearchGateway/12H",
            "Accept: application/json",
            "Accept-Encoding: identity",
            f"X-Subscription-Token: {token}",
            "Connection: close",
            "",
            "",
        )
        return "\r\n".join(lines).encode("ascii")

    @staticmethod
    def _validate_subscription_token(value: str) -> str:
        if not isinstance(value, str) or not 16 <= len(value) <= 512:
            raise WebSearchProviderError(
                "provider-credential-invalid",
                "Brave Search subscription token is missing or malformed.",
            )
        try:
            encoded = value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise WebSearchProviderError(
                "provider-credential-invalid",
                "Brave Search subscription token must be ASCII.",
            ) from exc
        if any(byte <= 0x20 or byte >= 0x7F for byte in encoded):
            raise WebSearchProviderError(
                "provider-credential-invalid",
                "Brave Search subscription token contains unsafe header bytes.",
            )
        return value


class BraveWebSearchProvider:
    """Parse Brave discovery output into untrusted URL candidates only."""

    def __init__(
        self,
        *,
        subscription_token: str,
        transport: BraveSearchTransportProtocol | None = None,
        destination_policy: InternetDestinationPolicy | None = None,
    ) -> None:
        self._subscription_token = BraveSearchPinnedTransport._validate_subscription_token(
            subscription_token
        )
        self._transport = transport or BraveSearchPinnedTransport()
        self._destination_policy = destination_policy or InternetDestinationPolicy()

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        transport: BraveSearchTransportProtocol | None = None,
    ) -> BraveWebSearchProvider:
        environment = os.environ if environ is None else environ
        token = environment.get(BRAVE_API_KEY_ENV, "")
        if not token:
            raise WebSearchProviderError(
                "provider-not-configured",
                f"Brave Search is disabled until {BRAVE_API_KEY_ENV} is configured.",
            )
        return cls(subscription_token=token, transport=transport)

    async def search(self, query: WebSearchQuery) -> WebSearchDiscoveryResult:
        raw = await self._transport.search_raw(
            query,
            subscription_token=self._subscription_token,
        )
        try:
            payload = json.loads(raw.body)
        except json.JSONDecodeError as exc:
            raise WebSearchProviderError(
                "provider-json-invalid",
                "Brave Search returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise WebSearchProviderError(
                "provider-json-invalid",
                "Brave Search response root must be an object.",
            )
        web = payload.get("web")
        provider_results = web.get("results", []) if isinstance(web, dict) else []
        if not isinstance(provider_results, list):
            raise WebSearchProviderError(
                "provider-json-invalid",
                "Brave Search web results must be a list.",
            )

        candidates: list[WebSearchCandidate] = []
        dropped = 0
        for rank, item in enumerate(provider_results[: query.count], start=1):
            if not isinstance(item, dict):
                dropped += 1
                continue
            title = item.get("title")
            url = item.get("url")
            description = item.get("description", "")
            if not isinstance(title, str) or not title.strip() or not isinstance(url, str):
                dropped += 1
                continue
            preflight = self._destination_policy.preflight(
                InternetDestinationIntent(url=url, method="GET")
            )
            if preflight.disposition != "accepted" or preflight.admission is None:
                dropped += 1
                continue
            snippet = description.strip() if isinstance(description, str) else ""
            candidates.append(
                WebSearchCandidate(
                    rank=rank,
                    title=title.strip()[:1000],
                    url=preflight.admission.canonical_url,
                    snippet=snippet[:5000],
                )
            )

        discovery_payload = {
            "provider_id": BRAVE_PROVIDER_ID,
            "query": query.query,
            "requested_count": query.count,
            "raw_response_sha256": raw.body_sha256,
            "connected_address": raw.connected_address,
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "dropped_unsafe_candidate_count": dropped,
        }
        canonical = json.dumps(discovery_payload, sort_keys=True, separators=(",", ":"))
        discovery_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return WebSearchDiscoveryResult(
            discovery_id=f"web-search-{discovery_sha256[:24]}",
            discovery_sha256=discovery_sha256,
            query=query.query,
            requested_count=query.count,
            raw_response_sha256=raw.body_sha256,
            connected_address=raw.connected_address,
            candidates=tuple(candidates),
            dropped_unsafe_candidate_count=dropped,
        )


def brave_search_configured(environ: Mapping[str, str] | None = None) -> bool:
    environment = os.environ if environ is None else environ
    return bool(environment.get(BRAVE_API_KEY_ENV, ""))
