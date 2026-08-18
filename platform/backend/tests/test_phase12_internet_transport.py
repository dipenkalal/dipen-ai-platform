from __future__ import annotations

import asyncio
import hashlib
import socket
from types import SimpleNamespace
from typing import Any

import pytest

from gateway.internet_destination_policy import (
    InternetDestinationIntent,
    InternetDestinationPolicy,
    InternetDestinationRequest,
)
from gateway.internet_transport import (
    BoundedInternetRetriever,
    InternetDNSResolution,
    InternetTransportError,
    InternetTransportLimits,
    PinnedHTTPSFetcher,
    SystemInternetDNSResolver,
)

PUBLIC_IPV4 = "93.184.216.34"
PUBLIC_IPV6 = "2606:4700:4700::1111"


class FakeWriter:
    def __init__(self) -> None:
        self.written = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


def _reader(payload: bytes, *, limit: int = 128 * 1024) -> asyncio.StreamReader:
    reader = asyncio.StreamReader(limit=limit)
    reader.feed_data(payload)
    reader.feed_eof()
    return reader


def _admission(
    *,
    url: str = "https://example.com/research?q=dap",
    addresses: tuple[str, ...] = (PUBLIC_IPV4,),
    method: str = "GET",
):
    decision = InternetDestinationPolicy().evaluate(
        InternetDestinationRequest(
            url=url,
            method=method,
            resolved_addresses=addresses,
        )
    )
    assert decision.disposition == "accepted"
    assert decision.admission is not None
    return decision.admission


@pytest.mark.asyncio
async def test_literal_dns_resolution_performs_no_hostname_lookup() -> None:
    policy = InternetDestinationPolicy()
    preflight = policy.preflight(
        InternetDestinationIntent(url=f"https://{PUBLIC_IPV4}/")
    )
    assert preflight.admission is not None

    result = await SystemInternetDNSResolver().resolve(preflight.admission)

    assert result.hostname == PUBLIC_IPV4
    assert result.addresses == (PUBLIC_IPV4,)


@pytest.mark.asyncio
async def test_pinned_fetch_connects_to_numeric_admitted_ip_with_hostname_sni() -> None:
    calls: list[dict[str, Any]] = []
    writers: list[FakeWriter] = []
    payload = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"Content-Length: 5\r\n"
        b"ETag: test-etag\r\n"
        b"\r\nhello"
    )

    async def connection_factory(**kwargs: Any):
        calls.append(kwargs)
        writer = FakeWriter()
        writers.append(writer)
        return _reader(payload), writer

    fetcher = PinnedHTTPSFetcher(connection_factory=connection_factory)
    connected_address, response = await fetcher.fetch(_admission())

    assert connected_address == PUBLIC_IPV4
    assert response.status_code == 200
    assert response.content_type == "text/plain"
    assert response.body == b"hello"
    assert response.etag == "test-etag"
    assert calls[0]["host"] == PUBLIC_IPV4
    assert calls[0]["port"] == 443
    assert calls[0]["flags"] == socket.AI_NUMERICHOST
    assert calls[0]["server_hostname"] == "example.com"
    assert calls[0]["family"] == socket.AF_INET
    assert writers[0].closed is True

    request = bytes(writers[0].written)
    assert request.startswith(b"GET /research?q=dap HTTP/1.1\r\n")
    assert b"Host: example.com\r\n" in request
    assert b"Accept-Encoding: identity\r\n" in request
    assert b"Connection: close\r\n" in request
    assert b"Authorization:" not in request
    assert b"Proxy-Authorization:" not in request
    assert b"Cookie:" not in request


@pytest.mark.asyncio
async def test_ipv6_pinned_fetch_uses_numeric_ipv6_family_and_hostname_sni() -> None:
    calls: list[dict[str, Any]] = []

    async def connection_factory(**kwargs: Any):
        calls.append(kwargs)
        return _reader(
            b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n"
        ), FakeWriter()

    admission = _admission(addresses=(PUBLIC_IPV6,))
    connected_address, response = await PinnedHTTPSFetcher(
        connection_factory=connection_factory
    ).fetch(admission)

    assert connected_address == PUBLIC_IPV6
    assert response.status_code == 204
    assert calls[0]["host"] == PUBLIC_IPV6
    assert calls[0]["family"] == socket.AF_INET6
    assert calls[0]["flags"] == socket.AI_NUMERICHOST
    assert calls[0]["server_hostname"] == "example.com"


@pytest.mark.asyncio
async def test_chunked_identity_body_is_decoded_within_ceiling() -> None:
    payload = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"\r\n"
        b"5\r\nhello\r\n"
        b"6\r\n world\r\n"
        b"0\r\n\r\n"
    )

    async def connection_factory(**_kwargs: Any):
        return _reader(payload), FakeWriter()

    _, response = await PinnedHTTPSFetcher(
        connection_factory=connection_factory
    ).fetch(_admission())

    assert response.body == b"hello world"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/octet-stream\r\n"
            b"Content-Length: 0\r\n\r\n",
            "content-type-unsupported",
        ),
        (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Encoding: gzip\r\n"
            b"Content-Length: 0\r\n\r\n",
            "content-encoding-unsupported",
        ),
        (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Content-Length: 5\r\n\r\n",
            "response-framing-ambiguous",
        ),
    ],
)
async def test_unsupported_or_ambiguous_response_framing_fails_closed(
    payload: bytes,
    expected_code: str,
) -> None:
    async def connection_factory(**_kwargs: Any):
        return _reader(payload), FakeWriter()

    with pytest.raises(InternetTransportError) as exc_info:
        await PinnedHTTPSFetcher(connection_factory=connection_factory).fetch(_admission())

    assert exc_info.value.code == expected_code


@pytest.mark.asyncio
async def test_declared_body_above_ceiling_is_rejected_before_body_read() -> None:
    payload = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: 1025\r\n\r\n"
    )

    async def connection_factory(**_kwargs: Any):
        return _reader(payload), FakeWriter()

    limits = InternetTransportLimits(max_body_bytes=1024)
    with pytest.raises(InternetTransportError) as exc_info:
        await PinnedHTTPSFetcher(
            limits=limits,
            connection_factory=connection_factory,
        ).fetch(_admission())

    assert exc_info.value.code == "content-body-too-large"


@pytest.mark.asyncio
async def test_transport_returns_redirect_metadata_without_following_it() -> None:
    payload = (
        b"HTTP/1.1 302 Found\r\n"
        b"Location: /next\r\n"
        b"Content-Type: text/html\r\n"
        b"Content-Length: 999999\r\n\r\n"
    )

    async def connection_factory(**_kwargs: Any):
        return _reader(payload), FakeWriter()

    _, response = await PinnedHTTPSFetcher(
        connection_factory=connection_factory
    ).fetch(_admission())

    assert response.status_code == 302
    assert response.redirect_location == "/next"
    assert response.body == b""


class FakeResolver:
    def __init__(self, mapping: dict[str, tuple[str, ...]]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    async def resolve(
        self,
        preflight: Any,
    ) -> InternetDNSResolution:
        self.calls.append(preflight.hostname)
        return InternetDNSResolution(
            hostname=preflight.hostname,
            addresses=self.mapping[preflight.hostname],
        )


class FakeFetcher:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = list(responses)
        self.calls: list[Any] = []

    async def fetch(self, admission: Any):
        self.calls.append(admission)
        response = self.responses.pop(0)
        return admission.approved_addresses[0], response


def _fake_response(
    *,
    status_code: int,
    body: bytes = b"",
    content_type: str | None = "text/plain",
    redirect_location: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=status_code,
        reason="OK" if status_code == 200 else "Found",
        content_type=content_type,
        content_length=len(body),
        body=body,
        redirect_location=redirect_location,
        etag=None,
        last_modified=None,
    )


@pytest.mark.asyncio
async def test_retriever_revalidates_each_redirect_before_second_dns_resolution() -> None:
    resolver = FakeResolver(
        {
            "example.com": (PUBLIC_IPV4,),
            "www.example.com": (PUBLIC_IPV6,),
        }
    )
    fetcher = FakeFetcher(
        [
            _fake_response(status_code=302, redirect_location="https://www.example.com/final"),
            _fake_response(status_code=200, body=b"final"),
        ]
    )
    retriever = BoundedInternetRetriever(
        resolver=resolver,  # type: ignore[arg-type]
        fetcher=fetcher,  # type: ignore[arg-type]
    )

    result = await retriever.retrieve("https://example.com/start")

    assert resolver.calls == ["example.com", "www.example.com"]
    assert len(fetcher.calls) == 2
    assert result.final_url == "https://www.example.com/final"
    assert result.body == b"final"
    assert result.body_sha256 == hashlib.sha256(b"final").hexdigest()
    assert len(result.hops) == 2
    assert result.hops[0].redirect_location == "https://www.example.com/final"
    assert result.hops[1].redirect_location is None
    assert result.agent_tool_registration_performed is False
    assert result.guardian_contacted is False


@pytest.mark.asyncio
async def test_unsafe_redirect_is_rejected_before_resolver_is_called_again() -> None:
    resolver = FakeResolver({"example.com": (PUBLIC_IPV4,)})
    fetcher = FakeFetcher(
        [_fake_response(status_code=302, redirect_location="https://localhost/private")]
    )
    retriever = BoundedInternetRetriever(
        resolver=resolver,  # type: ignore[arg-type]
        fetcher=fetcher,  # type: ignore[arg-type]
    )

    with pytest.raises(InternetTransportError) as exc_info:
        await retriever.retrieve("https://example.com/start")

    assert exc_info.value.code == "destination-preflight-rejected"
    assert resolver.calls == ["example.com"]
    assert len(fetcher.calls) == 1


@pytest.mark.asyncio
async def test_mixed_public_private_dns_is_rejected_before_fetch() -> None:
    resolver = FakeResolver({"example.com": (PUBLIC_IPV4, "127.0.0.1")})
    fetcher = FakeFetcher([_fake_response(status_code=200, body=b"must-not-run")])
    retriever = BoundedInternetRetriever(
        resolver=resolver,  # type: ignore[arg-type]
        fetcher=fetcher,  # type: ignore[arg-type]
    )

    with pytest.raises(InternetTransportError) as exc_info:
        await retriever.retrieve("https://example.com/")

    assert exc_info.value.code == "destination-addresses-rejected"
    assert fetcher.calls == []


def test_limits_reject_total_budget_below_connect_or_dns_ceiling() -> None:
    with pytest.raises(ValueError, match="total timeout"):
        InternetTransportLimits(
            dns_timeout_seconds=10,
            connect_timeout_seconds=5,
            total_timeout_seconds=4,
        )
