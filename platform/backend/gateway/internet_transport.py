from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import socket
import ssl
from collections.abc import Awaitable, Callable
from typing import Literal, Protocol
from urllib.parse import urljoin, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agents.cancellation import raise_if_current_cancellation_requested
from gateway.internet_destination_policy import (
    InternetDestinationAdmission,
    InternetDestinationIntent,
    InternetDestinationPolicy,
    InternetDestinationPreflightAdmission,
    InternetDestinationRequest,
)

TRANSPORT_ID = "dap-pinned-https-http1-v1"
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_NO_BODY_STATUS_CODES = frozenset({204, 304})
_HEADER_NAME_RE = re.compile(rb"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_ALLOWED_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/json",
    "application/pdf",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
)


class InternetTransportError(RuntimeError):
    """Fail-closed bounded transport error with a stable machine-readable code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class InternetTransportLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    dns_timeout_seconds: float = Field(default=4.0, ge=0.5, le=30.0)
    connect_timeout_seconds: float = Field(default=5.0, ge=0.5, le=30.0)
    read_timeout_seconds: float = Field(default=10.0, ge=0.5, le=60.0)
    total_timeout_seconds: float = Field(default=25.0, ge=2.0, le=120.0)
    max_header_bytes: int = Field(default=32 * 1024, ge=4096, le=128 * 1024)
    max_header_count: int = Field(default=100, ge=1, le=200)
    max_body_bytes: int = Field(default=4 * 1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    max_redirects: int = Field(default=3, ge=0, le=3)
    allowed_content_types: tuple[str, ...] = _ALLOWED_CONTENT_TYPES

    @model_validator(mode="after")
    def validate_time_budget(self) -> InternetTransportLimits:
        minimum = max(self.dns_timeout_seconds, self.connect_timeout_seconds)
        if self.total_timeout_seconds < minimum:
            raise ValueError("total timeout must cover DNS and connect timeout ceilings")
        return self


class InternetDNSResolution(BaseModel):
    model_config = ConfigDict(frozen=True)

    resolver_id: Literal["system-getaddrinfo-v1"] = "system-getaddrinfo-v1"
    hostname: str
    port: Literal[443] = 443
    addresses: tuple[str, ...] = Field(min_length=1, max_length=16)


class InternetRetrievalHop(BaseModel):
    model_config = ConfigDict(frozen=True)

    redirect_depth: int
    canonical_url: str
    destination_admission_id: str
    destination_admission_sha256: str
    approved_addresses: tuple[str, ...]
    connected_address: str
    status_code: int
    redirect_location: str | None = None


class InternetRetrievalResult(BaseModel):
    """Bounded raw retrieval result. 12E will normalize content before model use."""

    model_config = ConfigDict(frozen=True)

    transport_id: Literal["dap-pinned-https-http1-v1"] = TRANSPORT_ID
    requested_url: str
    final_url: str
    method: Literal["GET", "HEAD"]
    status_code: int
    reason: str
    content_type: str | None
    content_length: int | None
    body: bytes
    body_sha256: str
    byte_count: int
    etag: str | None = None
    last_modified: str | None = None
    hops: tuple[InternetRetrievalHop, ...]
    automatic_knowledge_mutation_performed: Literal[False] = False
    task_ledger_mutation_performed: Literal[False] = False
    agent_tool_registration_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False


class _ConnectionWriter(Protocol):
    def write(self, data: bytes) -> None: ...

    async def drain(self) -> None: ...

    def close(self) -> None: ...

    async def wait_closed(self) -> None: ...


ConnectionFactory = Callable[..., Awaitable[tuple[asyncio.StreamReader, _ConnectionWriter]]]


class SystemInternetDNSResolver:
    """Resolve only a URL that already passed the 12C pre-DNS admission."""

    def __init__(self, *, limits: InternetTransportLimits | None = None) -> None:
        self._limits = limits or InternetTransportLimits()

    async def resolve(
        self,
        preflight: InternetDestinationPreflightAdmission,
    ) -> InternetDNSResolution:
        raise_if_current_cancellation_requested(boundary="before-internet-dns")

        try:
            literal = ipaddress.ip_address(preflight.hostname)
        except ValueError:
            literal = None

        if literal is not None:
            return InternetDNSResolution(
                hostname=preflight.hostname,
                addresses=(literal.compressed,),
            )

        loop = asyncio.get_running_loop()
        try:
            records = await asyncio.wait_for(
                loop.getaddrinfo(
                    preflight.hostname,
                    443,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                    proto=socket.IPPROTO_TCP,
                ),
                timeout=self._limits.dns_timeout_seconds,
            )
        except TimeoutError as exc:
            raise InternetTransportError("dns-timeout", "Public DNS resolution timed out.") from exc
        except OSError as exc:
            raise InternetTransportError("dns-failed", "Public DNS resolution failed.") from exc

        addresses: list[str] = []
        for family, socktype, proto, _canonname, sockaddr in records:
            if family not in {socket.AF_INET, socket.AF_INET6}:
                continue
            if socktype != socket.SOCK_STREAM or proto not in {0, socket.IPPROTO_TCP}:
                continue
            raw_address = str(sockaddr[0])
            try:
                normalized = ipaddress.ip_address(raw_address).compressed
            except ValueError as exc:
                raise InternetTransportError(
                    "dns-invalid-address",
                    "Resolver returned an address that cannot be normalized.",
                ) from exc
            if normalized not in addresses:
                addresses.append(normalized)
            if len(addresses) > 16:
                raise InternetTransportError(
                    "dns-too-many-addresses",
                    "Resolver returned more addresses than the Phase 12 ceiling.",
                )

        if not addresses:
            raise InternetTransportError("dns-empty", "Resolver returned no usable IP addresses.")

        raise_if_current_cancellation_requested(boundary="after-internet-dns")
        return InternetDNSResolution(
            hostname=preflight.hostname,
            addresses=tuple(addresses),
        )


class _ParsedHTTPResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status_code: int
    reason: str
    content_type: str | None
    content_length: int | None
    body: bytes
    redirect_location: str | None
    etag: str | None
    last_modified: str | None


class PinnedHTTPSFetcher:
    """HTTP/1.1 over TLS to an exact 12C-approved numeric destination."""

    def __init__(
        self,
        *,
        limits: InternetTransportLimits | None = None,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._limits = limits or InternetTransportLimits()
        self._connection_factory = connection_factory or asyncio.open_connection

    async def fetch(
        self,
        admission: InternetDestinationAdmission,
    ) -> tuple[str, _ParsedHTTPResponse]:
        raise_if_current_cancellation_requested(boundary="before-internet-connect")

        last_error: Exception | None = None
        for address in admission.approved_addresses:
            try:
                response = await self._fetch_from_address(admission, address)
                return address, response
            except InternetTransportError as exc:
                last_error = exc
                if exc.code.startswith("response-") or exc.code.startswith("content-"):
                    raise
            except (OSError, ssl.SSLError, TimeoutError) as exc:
                last_error = exc

        if isinstance(last_error, InternetTransportError):
            raise last_error
        raise InternetTransportError(
            "connect-failed",
            "Unable to establish a validated TLS connection to any admitted address.",
        ) from last_error

    async def _fetch_from_address(
        self,
        admission: InternetDestinationAdmission,
        address: str,
    ) -> _ParsedHTTPResponse:
        if address not in admission.approved_addresses:
            raise InternetTransportError(
                "address-not-admitted",
                "Transport attempted to use an address outside the destination admission.",
            )

        parsed_address = ipaddress.ip_address(address)
        family = socket.AF_INET6 if parsed_address.version == 6 else socket.AF_INET
        tls_context = ssl.create_default_context()
        tls_context.minimum_version = ssl.TLSVersion.TLSv1_2
        tls_context.set_alpn_protocols(["http/1.1"])
        if hasattr(ssl, "OP_NO_COMPRESSION"):
            tls_context.options |= ssl.OP_NO_COMPRESSION

        try:
            reader, writer = await asyncio.wait_for(
                self._connection_factory(
                    host=parsed_address.compressed,
                    port=443,
                    family=family,
                    flags=socket.AI_NUMERICHOST,
                    ssl=tls_context,
                    server_hostname=admission.hostname,
                    limit=self._limits.max_header_bytes + 4096,
                ),
                timeout=self._limits.connect_timeout_seconds,
            )
        except TimeoutError as exc:
            raise InternetTransportError("connect-timeout", "TLS connection timed out.") from exc
        except (OSError, ssl.SSLError) as exc:
            raise InternetTransportError(
                "connect-failed",
                "TLS connection to the admitted public address failed.",
            ) from exc

        try:
            request_bytes = self._build_request(admission)
            writer.write(request_bytes)
            await asyncio.wait_for(writer.drain(), timeout=self._limits.read_timeout_seconds)
            raise_if_current_cancellation_requested(boundary="after-internet-request-write")
            return await self._read_response(reader, admission.method)
        finally:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
            except (TimeoutError, OSError, ssl.SSLError):
                pass

    @staticmethod
    def _build_request(admission: InternetDestinationAdmission) -> bytes:
        parsed = urlsplit(admission.canonical_url)
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        try:
            target_bytes = target.encode("ascii")
        except UnicodeEncodeError as exc:
            raise InternetTransportError(
                "request-target-non-ascii",
                "Canonical request target must be ASCII/percent-encoded.",
            ) from exc
        if b"\r" in target_bytes or b"\n" in target_bytes or b" " in target_bytes:
            raise InternetTransportError(
                "request-target-invalid",
                "Canonical request target contains unsafe request-line bytes.",
            )

        host_header = (
            f"[{admission.hostname}]" if ":" in admission.hostname else admission.hostname
        )
        lines = (
            f"{admission.method} {target} HTTP/1.1",
            f"Host: {host_header}",
            "User-Agent: DAP-InternetResearchGateway/12D",
            "Accept: text/html,text/plain,application/json,application/pdf,application/xhtml+xml,application/xml,text/xml;q=0.9",
            "Accept-Encoding: identity",
            "Connection: close",
            "",
            "",
        )
        return "\r\n".join(lines).encode("ascii")

    async def _read_response(
        self,
        reader: asyncio.StreamReader,
        method: Literal["GET", "HEAD"],
    ) -> _ParsedHTTPResponse:
        try:
            raw_headers = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"),
                timeout=self._limits.read_timeout_seconds,
            )
        except asyncio.LimitOverrunError as exc:
            raise InternetTransportError(
                "response-headers-too-large",
                "Response headers exceeded the Phase 12 byte ceiling.",
            ) from exc
        except asyncio.IncompleteReadError as exc:
            raise InternetTransportError(
                "response-headers-incomplete",
                "Connection closed before response headers completed.",
            ) from exc
        except TimeoutError as exc:
            raise InternetTransportError(
                "response-header-timeout",
                "Timed out waiting for response headers.",
            ) from exc

        if len(raw_headers) > self._limits.max_header_bytes:
            raise InternetTransportError(
                "response-headers-too-large",
                "Response headers exceeded the Phase 12 byte ceiling.",
            )

        status_code, reason, headers = self._parse_headers(raw_headers)
        content_type = self._content_type(headers)
        content_length = self._content_length(headers)
        transfer_encoding = self._single_header(headers, "transfer-encoding")
        content_encoding = self._single_header(headers, "content-encoding")
        location = self._single_header(headers, "location")

        if content_encoding and content_encoding.lower() != "identity":
            raise InternetTransportError(
                "content-encoding-unsupported",
                "Compressed response encodings are disabled in the initial transport.",
            )
        if transfer_encoding and transfer_encoding.lower() != "chunked":
            raise InternetTransportError(
                "response-transfer-encoding-unsupported",
                "Only identity or chunked HTTP transfer framing is supported.",
            )
        if transfer_encoding and content_length is not None:
            raise InternetTransportError(
                "response-framing-ambiguous",
                "Response contains both Transfer-Encoding and Content-Length.",
            )

        is_redirect = status_code in _REDIRECT_STATUS_CODES
        if is_redirect:
            if location is None or not location.strip():
                raise InternetTransportError(
                    "response-redirect-location-missing",
                    "Redirect response did not provide a usable Location header.",
                )
            return _ParsedHTTPResponse(
                status_code=status_code,
                reason=reason,
                content_type=content_type,
                content_length=content_length,
                body=b"",
                redirect_location=location.strip(),
                etag=self._single_header(headers, "etag"),
                last_modified=self._single_header(headers, "last-modified"),
            )

        if (
            method != "HEAD"
            and status_code not in _NO_BODY_STATUS_CODES
            and content_type not in self._limits.allowed_content_types
        ):
            raise InternetTransportError(
                "content-type-unsupported",
                "Response Content-Type is outside the Phase 12 research allowlist.",
            )

        if method == "HEAD" or status_code in _NO_BODY_STATUS_CODES:
            body = b""
        elif transfer_encoding and transfer_encoding.lower() == "chunked":
            body = await self._read_chunked_body(reader)
        elif content_length is not None:
            if content_length > self._limits.max_body_bytes:
                raise InternetTransportError(
                    "content-body-too-large",
                    "Response Content-Length exceeds the Phase 12 body ceiling.",
                )
            body = await self._read_exact(reader, content_length)
        else:
            body = await self._read_to_eof(reader)

        raise_if_current_cancellation_requested(boundary="after-internet-response-read")
        return _ParsedHTTPResponse(
            status_code=status_code,
            reason=reason,
            content_type=content_type,
            content_length=content_length,
            body=body,
            redirect_location=None,
            etag=self._single_header(headers, "etag"),
            last_modified=self._single_header(headers, "last-modified"),
        )

    def _parse_headers(
        self,
        raw_headers: bytes,
    ) -> tuple[int, str, dict[str, list[str]]]:
        lines = raw_headers[:-4].split(b"\r\n")
        if not lines:
            raise InternetTransportError("response-status-missing", "HTTP status line is missing.")
        try:
            status_line = lines[0].decode("ascii")
        except UnicodeDecodeError as exc:
            raise InternetTransportError(
                "response-status-invalid",
                "HTTP status line must be ASCII.",
            ) from exc
        parts = status_line.split(" ", 2)
        if len(parts) < 2 or parts[0] not in {"HTTP/1.0", "HTTP/1.1"}:
            raise InternetTransportError(
                "response-status-invalid",
                "Only HTTP/1.0 and HTTP/1.1 responses are supported.",
            )
        try:
            status_code = int(parts[1])
        except ValueError as exc:
            raise InternetTransportError(
                "response-status-invalid",
                "HTTP status code is not numeric.",
            ) from exc
        if not 100 <= status_code <= 599:
            raise InternetTransportError(
                "response-status-invalid",
                "HTTP status code is outside the valid range.",
            )
        reason = parts[2] if len(parts) == 3 else ""

        header_lines = lines[1:]
        if len(header_lines) > self._limits.max_header_count:
            raise InternetTransportError(
                "response-header-count-exceeded",
                "Response contains too many headers.",
            )

        headers: dict[str, list[str]] = {}
        for line in header_lines:
            if not line:
                continue
            if line[:1] in {b" ", b"\t"} or b":" not in line:
                raise InternetTransportError(
                    "response-header-invalid",
                    "Obsolete folding or malformed response headers are prohibited.",
                )
            raw_name, raw_value = line.split(b":", 1)
            if _HEADER_NAME_RE.fullmatch(raw_name) is None:
                raise InternetTransportError(
                    "response-header-invalid",
                    "Response contains an invalid header name.",
                )
            name = raw_name.decode("ascii").lower()
            value = raw_value.decode("latin-1").strip()
            headers.setdefault(name, []).append(value)
        return status_code, reason, headers

    @staticmethod
    def _single_header(headers: dict[str, list[str]], name: str) -> str | None:
        values = headers.get(name, [])
        if not values:
            return None
        if len(values) != 1:
            raise InternetTransportError(
                "response-header-duplicate",
                f"Response contains multiple {name} headers.",
            )
        return values[0]

    def _content_type(self, headers: dict[str, list[str]]) -> str | None:
        value = self._single_header(headers, "content-type")
        if value is None:
            return None
        media_type = value.split(";", 1)[0].strip().lower()
        return media_type or None

    def _content_length(self, headers: dict[str, list[str]]) -> int | None:
        values = headers.get("content-length", [])
        if not values:
            return None
        normalized = {value.strip() for value in values}
        if len(normalized) != 1:
            raise InternetTransportError(
                "response-content-length-conflict",
                "Response contains conflicting Content-Length values.",
            )
        value = next(iter(normalized))
        try:
            parsed = int(value, 10)
        except ValueError as exc:
            raise InternetTransportError(
                "response-content-length-invalid",
                "Response Content-Length is not a non-negative integer.",
            ) from exc
        if parsed < 0:
            raise InternetTransportError(
                "response-content-length-invalid",
                "Response Content-Length is not a non-negative integer.",
            )
        return parsed

    async def _read_exact(self, reader: asyncio.StreamReader, size: int) -> bytes:
        try:
            return await asyncio.wait_for(
                reader.readexactly(size),
                timeout=self._limits.read_timeout_seconds,
            )
        except asyncio.IncompleteReadError as exc:
            raise InternetTransportError(
                "content-body-incomplete",
                "Connection closed before Content-Length bytes were received.",
            ) from exc
        except TimeoutError as exc:
            raise InternetTransportError("content-read-timeout", "Response body timed out.") from exc

    async def _read_to_eof(self, reader: asyncio.StreamReader) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = await asyncio.wait_for(
                    reader.read(min(64 * 1024, self._limits.max_body_bytes - total + 1)),
                    timeout=self._limits.read_timeout_seconds,
                )
            except TimeoutError as exc:
                raise InternetTransportError(
                    "content-read-timeout",
                    "Response body timed out.",
                ) from exc
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > self._limits.max_body_bytes:
                raise InternetTransportError(
                    "content-body-too-large",
                    "Response body exceeds the Phase 12 byte ceiling.",
                )
            chunks.append(chunk)
            raise_if_current_cancellation_requested(boundary="between-internet-body-chunks")

    async def _read_chunked_body(self, reader: asyncio.StreamReader) -> bytes:
        chunks: list[bytes] = []
        total = 0
        trailer_bytes = 0
        while True:
            line = await self._read_line(reader)
            size_token = line.rstrip(b"\r\n").split(b";", 1)[0].strip()
            try:
                size = int(size_token, 16)
            except ValueError as exc:
                raise InternetTransportError(
                    "content-chunk-size-invalid",
                    "Chunked response contains an invalid chunk size.",
                ) from exc
            if size < 0:
                raise InternetTransportError(
                    "content-chunk-size-invalid",
                    "Chunked response contains an invalid chunk size.",
                )
            if size == 0:
                while True:
                    trailer = await self._read_line(reader)
                    trailer_bytes += len(trailer)
                    if trailer_bytes > self._limits.max_header_bytes:
                        raise InternetTransportError(
                            "content-trailers-too-large",
                            "Chunked response trailers exceed the header ceiling.",
                        )
                    if trailer == b"\r\n":
                        return b"".join(chunks)
                    if trailer[:1] in {b" ", b"\t"} or b":" not in trailer:
                        raise InternetTransportError(
                            "content-trailer-invalid",
                            "Chunked response contains a malformed trailer header.",
                        )
            if total + size > self._limits.max_body_bytes:
                raise InternetTransportError(
                    "content-body-too-large",
                    "Chunked response body exceeds the Phase 12 byte ceiling.",
                )
            chunk = await self._read_exact(reader, size)
            terminator = await self._read_exact(reader, 2)
            if terminator != b"\r\n":
                raise InternetTransportError(
                    "content-chunk-framing-invalid",
                    "Chunked response is missing a CRLF chunk terminator.",
                )
            total += size
            chunks.append(chunk)
            raise_if_current_cancellation_requested(boundary="between-internet-body-chunks")

    async def _read_line(self, reader: asyncio.StreamReader) -> bytes:
        try:
            line = await asyncio.wait_for(
                reader.readline(),
                timeout=self._limits.read_timeout_seconds,
            )
        except (ValueError, asyncio.LimitOverrunError) as exc:
            raise InternetTransportError(
                "response-line-too-large",
                "Response line exceeds the Phase 12 parsing ceiling.",
            ) from exc
        except TimeoutError as exc:
            raise InternetTransportError("content-read-timeout", "Response body timed out.") from exc
        if not line.endswith(b"\r\n"):
            raise InternetTransportError(
                "response-line-incomplete",
                "Response line ended without CRLF framing.",
            )
        if len(line) > self._limits.max_header_bytes:
            raise InternetTransportError(
                "response-line-too-large",
                "Response line exceeds the Phase 12 parsing ceiling.",
            )
        return line


class BoundedInternetRetriever:
    """Preflight → DNS → admission → pinned fetch, with re-admitted redirects."""

    def __init__(
        self,
        *,
        policy: InternetDestinationPolicy | None = None,
        resolver: SystemInternetDNSResolver | None = None,
        fetcher: PinnedHTTPSFetcher | None = None,
        limits: InternetTransportLimits | None = None,
    ) -> None:
        self._limits = limits or InternetTransportLimits()
        self._policy = policy or InternetDestinationPolicy()
        self._resolver = resolver or SystemInternetDNSResolver(limits=self._limits)
        self._fetcher = fetcher or PinnedHTTPSFetcher(limits=self._limits)

    async def retrieve(
        self,
        url: str,
        *,
        method: Literal["GET", "HEAD"] = "GET",
    ) -> InternetRetrievalResult:
        try:
            async with asyncio.timeout(self._limits.total_timeout_seconds):
                return await self._retrieve_within_budget(url=url, method=method)
        except TimeoutError as exc:
            raise InternetTransportError(
                "retrieval-total-timeout",
                "Internet retrieval exceeded the total Phase 12 time budget.",
            ) from exc

    async def _retrieve_within_budget(
        self,
        *,
        url: str,
        method: Literal["GET", "HEAD"],
    ) -> InternetRetrievalResult:
        requested_url = url.strip()
        current_url = requested_url
        hops: list[InternetRetrievalHop] = []

        for redirect_depth in range(self._limits.max_redirects + 1):
            raise_if_current_cancellation_requested(boundary="before-internet-preflight")
            preflight = self._policy.preflight(
                InternetDestinationIntent(
                    url=current_url,
                    method=method,
                    redirect_depth=redirect_depth,
                )
            )
            if preflight.disposition != "accepted" or preflight.admission is None:
                raise InternetTransportError(
                    "destination-preflight-rejected",
                    "Destination failed Phase 12 pre-DNS admission.",
                )

            resolution = await self._resolver.resolve(preflight.admission)
            decision = self._policy.evaluate(
                InternetDestinationRequest(
                    url=preflight.admission.canonical_url,
                    method=preflight.admission.method,
                    redirect_depth=preflight.admission.redirect_depth,
                    resolved_addresses=resolution.addresses,
                )
            )
            if decision.disposition != "accepted" or decision.admission is None:
                raise InternetTransportError(
                    "destination-addresses-rejected",
                    "Resolved destination failed Phase 12 public-address admission.",
                )

            connected_address, response = await self._fetcher.fetch(decision.admission)
            hop = InternetRetrievalHop(
                redirect_depth=redirect_depth,
                canonical_url=decision.admission.canonical_url,
                destination_admission_id=decision.admission.admission_id,
                destination_admission_sha256=decision.admission.admission_sha256,
                approved_addresses=decision.admission.approved_addresses,
                connected_address=connected_address,
                status_code=response.status_code,
                redirect_location=response.redirect_location,
            )
            hops.append(hop)

            if response.status_code in _REDIRECT_STATUS_CODES:
                if redirect_depth >= self._limits.max_redirects:
                    raise InternetTransportError(
                        "redirect-limit-exceeded",
                        "Redirect chain exceeded the Phase 12 ceiling.",
                    )
                assert response.redirect_location is not None
                current_url = urljoin(
                    decision.admission.canonical_url,
                    response.redirect_location,
                )
                continue

            body_sha256 = hashlib.sha256(response.body).hexdigest()
            return InternetRetrievalResult(
                requested_url=requested_url,
                final_url=decision.admission.canonical_url,
                method=decision.admission.method,
                status_code=response.status_code,
                reason=response.reason,
                content_type=response.content_type,
                content_length=response.content_length,
                body=response.body,
                body_sha256=body_sha256,
                byte_count=len(response.body),
                etag=response.etag,
                last_modified=response.last_modified,
                hops=tuple(hops),
            )

        raise InternetTransportError(
            "redirect-limit-exceeded",
            "Redirect chain exceeded the Phase 12 ceiling.",
        )
