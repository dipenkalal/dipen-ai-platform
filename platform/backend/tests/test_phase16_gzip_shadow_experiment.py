from __future__ import annotations

import asyncio
import gzip
from typing import Any

import pytest

from gateway.internet_destination_policy import (
    InternetDestinationPolicy,
    InternetDestinationRequest,
)
from gateway.internet_transport import InternetTransportError, InternetTransportLimits
from gateway.research_retrieval_gzip_experiment import (
    EXPERIMENT_TRANSPORT_ID,
    PHASE16_GZIP_EXPERIMENT_VERSION,
    _decode_gzip_bounded,
    _GzipPinnedHTTPSFetcher,
)

PUBLIC_IPV4 = "93.184.216.34"


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


def _reader(payload: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader(limit=128 * 1024)
    reader.feed_data(payload)
    reader.feed_eof()
    return reader


def _admission():
    decision = InternetDestinationPolicy().evaluate(
        InternetDestinationRequest(
            url="https://example.com/research?q=dap",
            method="GET",
            resolved_addresses=(PUBLIC_IPV4,),
        )
    )
    assert decision.disposition == "accepted"
    assert decision.admission is not None
    return decision.admission


def test_phase16f1_contract_is_frozen_and_shadow_only() -> None:
    assert PHASE16_GZIP_EXPERIMENT_VERSION == "phase16f1.1"
    assert EXPERIMENT_TRANSPORT_ID == "dap-pinned-https-http1-gzip-shadow-v1"


def test_shadow_request_advertises_only_gzip_and_identity() -> None:
    request = _GzipPinnedHTTPSFetcher._build_request(_admission())

    assert b"Accept-Encoding: gzip, identity\r\n" in request
    assert b"Accept-Encoding: identity\r\n" not in request
    assert b"Accept-Encoding: br" not in request
    assert b"Connection: close\r\n" in request
    assert b"Authorization:" not in request
    assert b"Cookie:" not in request


@pytest.mark.asyncio
async def test_valid_gzip_response_is_decoded_to_logical_body() -> None:
    logical = (b"bounded research text " * 32) + b"done"
    encoded = gzip.compress(logical)
    payload = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"Content-Encoding: gzip\r\n"
        + f"Content-Length: {len(encoded)}\r\n".encode("ascii")
        + b"\r\n"
        + encoded
    )
    writers: list[FakeWriter] = []

    async def connection_factory(**_kwargs: Any):
        writer = FakeWriter()
        writers.append(writer)
        return _reader(payload), writer

    _, response = await _GzipPinnedHTTPSFetcher(
        connection_factory=connection_factory
    ).fetch(_admission())

    assert response.body == logical
    assert writers[0].closed is True


@pytest.mark.asyncio
async def test_identity_response_path_is_unchanged() -> None:
    payload = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: 5\r\n"
        b"\r\nhello"
    )

    async def connection_factory(**_kwargs: Any):
        return _reader(payload), FakeWriter()

    _, response = await _GzipPinnedHTTPSFetcher(
        connection_factory=connection_factory
    ).fetch(_admission())

    assert response.body == b"hello"


def test_bounded_gzip_decode_rejects_decoded_overflow() -> None:
    encoded = gzip.compress(b"a" * 4096)

    with pytest.raises(InternetTransportError) as exc_info:
        _decode_gzip_bounded(encoded, 1024)

    assert exc_info.value.code == "content-body-too-large"


def test_bounded_gzip_decode_rejects_malformed_payload() -> None:
    with pytest.raises(InternetTransportError) as exc_info:
        _decode_gzip_bounded(b"not-a-gzip-stream", 4096)

    assert exc_info.value.code == "content-encoding-invalid"


@pytest.mark.asyncio
async def test_unsupported_brotli_encoding_still_fails_closed() -> None:
    payload = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Encoding: br\r\n"
        b"Content-Length: 0\r\n\r\n"
    )

    async def connection_factory(**_kwargs: Any):
        return _reader(payload), FakeWriter()

    with pytest.raises(InternetTransportError) as exc_info:
        await _GzipPinnedHTTPSFetcher(
            connection_factory=connection_factory
        ).fetch(_admission())

    assert exc_info.value.code == "content-encoding-unsupported"


@pytest.mark.asyncio
async def test_compressed_wire_length_remains_bounded() -> None:
    payload = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Encoding: gzip\r\n"
        b"Content-Length: 1025\r\n\r\n"
    )

    async def connection_factory(**_kwargs: Any):
        return _reader(payload), FakeWriter()

    with pytest.raises(InternetTransportError) as exc_info:
        await _GzipPinnedHTTPSFetcher(
            limits=InternetTransportLimits(max_body_bytes=1024),
            connection_factory=connection_factory,
        ).fetch(_admission())

    assert exc_info.value.code == "content-body-too-large"
