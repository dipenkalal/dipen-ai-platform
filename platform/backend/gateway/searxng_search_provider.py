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
MAX_SEARXNG_PROVIDER_RESULT_SCAN = 20
MAX_SEARXNG_ENGINE_TELEMETRY_ITEMS = 16
_MAX_PROVIDER_RESPONSE_BYTES = 1024 * 1024

SearXNGEngineFailureClass = Literal[
    "too-many-requests",
    "captcha",
    "access-denied",
    "timeout",
    "http-error",
    "http-protocol-error",
    "network-error",
    "proxy-error",
    "ssl-error",
    "parsing-error",
    "server-api-error",
    "unexpected-crash",
    "other",
]


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


class SearXNGEngineFailure(BaseModel):
    """DAP-normalized SearXNG engine failure metadata with raw text discarded."""

    model_config = ConfigDict(frozen=True)

    engine_name: str = Field(min_length=1, max_length=120)
    failure_class: SearXNGEngineFailureClass
    suspended: bool = False
    raw_error_text_recorded: Literal[False] = False


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
    provider_result_count: int = Field(ge=0)
    considered_result_count: int = Field(ge=0, le=MAX_SEARXNG_PROVIDER_RESULT_SCAN)
    invalid_candidate_count: int = Field(ge=0)
    policy_rejected_candidate_count: int = Field(ge=0)
    accepted_candidate_count: int = Field(ge=0, le=10)
    dropped_unsafe_candidate_count: int = Field(ge=0)
    provider_zero_results: bool
    admissible_candidate_zero_after_filtering: bool
    contributing_engines: tuple[str, ...] = Field(
        default=(), max_length=MAX_SEARXNG_ENGINE_TELEMETRY_ITEMS
    )
    unresponsive_engines: tuple[SearXNGEngineFailure, ...] = Field(
        default=(), max_length=MAX_SEARXNG_ENGINE_TELEMETRY_ITEMS
    )
    provider_engine_error_text_recorded: Literal[False] = False
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


CandidateDisposition = Literal["accepted", "invalid", "policy-rejected"]


def _safe_engine_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized or any(ord(char) < 32 for char in normalized):
        return None
    return normalized[:120]


def _normalize_engine_failure(message: Any) -> tuple[SearXNGEngineFailureClass, bool]:
    if not isinstance(message, str):
        return "other", False
    normalized = " ".join(message.casefold().split())
    suspended = normalized.startswith("suspended:")
    if "too many requests" in normalized:
        return "too-many-requests", suspended
    if "captcha" in normalized:
        return "captcha", suspended
    if "access denied" in normalized:
        return "access-denied", suspended
    if "timeout" in normalized:
        return "timeout", suspended
    if "ssl error" in normalized:
        return "ssl-error", suspended
    if "proxy error" in normalized:
        return "proxy-error", suspended
    if "http protocol error" in normalized:
        return "http-protocol-error", suspended
    if "http connection error" in normalized or "network error" in normalized:
        return "network-error", suspended
    if "http error" in normalized:
        return "http-error", suspended
    if "parsing error" in normalized:
        return "parsing-error", suspended
    if "server api error" in normalized:
        return "server-api-error", suspended
    if "unexpected crash" in normalized:
        return "unexpected-crash", suspended
    return "other", suspended


def _extract_contributing_engines(provider_results: list[Any]) -> tuple[str, ...]:
    names: set[str] = set()
    for item in provider_results[:MAX_SEARXNG_PROVIDER_RESULT_SCAN]:
        if not isinstance(item, dict):
            continue
        raw_engines = item.get("engines")
        if isinstance(raw_engines, list):
            for value in raw_engines:
                name = _safe_engine_name(value)
                if name is not None:
                    names.add(name)
        raw_engine = item.get("engine")
        name = _safe_engine_name(raw_engine)
        if name is not None:
            names.add(name)
        if len(names) >= MAX_SEARXNG_ENGINE_TELEMETRY_ITEMS:
            break
    return tuple(sorted(names)[:MAX_SEARXNG_ENGINE_TELEMETRY_ITEMS])


def _extract_unresponsive_engines(value: Any) -> tuple[SearXNGEngineFailure, ...]:
    if not isinstance(value, list):
        return ()
    failures: list[SearXNGEngineFailure] = []
    seen: set[tuple[str, str, bool]] = set()
    for item in value[:MAX_SEARXNG_ENGINE_TELEMETRY_ITEMS]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        engine_name = _safe_engine_name(item[0])
        if engine_name is None:
            continue
        failure_class, suspended = _normalize_engine_failure(item[1])
        key = (engine_name, failure_class, suspended)
        if key in seen:
            continue
        seen.add(key)
        failures.append(
            SearXNGEngineFailure(
                engine_name=engine_name,
                failure_class=failure_class,
                suspended=suspended,
            )
        )
    return tuple(failures)


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

        contributing_engines = _extract_contributing_engines(provider_results)
        unresponsive_engines = _extract_unresponsive_engines(
            payload.get("unresponsive_engines")
        )

        candidates: list[WebSearchCandidate] = []
        considered = 0
        invalid = 0
        policy_rejected = 0
        bounded_results = provider_results[:MAX_SEARXNG_PROVIDER_RESULT_SCAN]
        for rank, item in enumerate(bounded_results, start=1):
            if len(candidates) >= query.count:
                break
            considered += 1
            candidate, disposition = self._candidate_from_item_with_disposition(rank, item)
            if disposition == "invalid":
                invalid += 1
                continue
            if disposition == "policy-rejected":
                policy_rejected += 1
                continue
            if candidate is not None:
                candidates.append(candidate)

        dropped = invalid + policy_rejected
        provider_result_count = len(provider_results)
        provider_zero_results = provider_result_count == 0
        admissible_candidate_zero_after_filtering = (
            provider_result_count > 0 and not candidates
        )

        discovery_payload = {
            "provider_id": SEARXNG_PROVIDER_ID,
            "query": query.query,
            "requested_count": query.count,
            "raw_response_sha256": raw.body_sha256,
            "connected_address": raw.connected_address,
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "provider_result_count": provider_result_count,
            "considered_result_count": considered,
            "invalid_candidate_count": invalid,
            "policy_rejected_candidate_count": policy_rejected,
            "accepted_candidate_count": len(candidates),
            "dropped_unsafe_candidate_count": dropped,
            "provider_zero_results": provider_zero_results,
            "admissible_candidate_zero_after_filtering": (
                admissible_candidate_zero_after_filtering
            ),
            "contributing_engines": list(contributing_engines),
            "unresponsive_engines": [
                item.model_dump(mode="json") for item in unresponsive_engines
            ],
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
            provider_result_count=provider_result_count,
            considered_result_count=considered,
            invalid_candidate_count=invalid,
            policy_rejected_candidate_count=policy_rejected,
            accepted_candidate_count=len(candidates),
            dropped_unsafe_candidate_count=dropped,
            provider_zero_results=provider_zero_results,
            admissible_candidate_zero_after_filtering=(
                admissible_candidate_zero_after_filtering
            ),
            contributing_engines=contributing_engines,
            unresponsive_engines=unresponsive_engines,
        )

    def _candidate_from_item(self, rank: int, item: Any) -> WebSearchCandidate | None:
        candidate, _ = self._candidate_from_item_with_disposition(rank, item)
        return candidate

    def _candidate_from_item_with_disposition(
        self,
        rank: int,
        item: Any,
    ) -> tuple[WebSearchCandidate | None, CandidateDisposition]:
        if not isinstance(item, dict):
            return None, "invalid"
        title = item.get("title")
        url = item.get("url")
        content = item.get("content", "")
        if not isinstance(title, str) or not title.strip() or not isinstance(url, str):
            return None, "invalid"
        preflight = self._destination_policy.preflight(
            InternetDestinationIntent(url=url, method="GET")
        )
        if preflight.disposition != "accepted" or preflight.admission is None:
            return None, "policy-rejected"
        snippet = content.strip() if isinstance(content, str) else ""
        return (
            WebSearchCandidate(
                rank=rank,
                title=title.strip()[:1000],
                url=preflight.admission.canonical_url,
                snippet=snippet[:5000],
            ),
            "accepted",
        )


def searxng_fixed_endpoint_is_loopback_only() -> bool:
    address = ipaddress.ip_address(SEARXNG_HOST)
    return address.is_loopback and SEARXNG_HOST == "127.0.0.1" and SEARXNG_PORT == 8888
