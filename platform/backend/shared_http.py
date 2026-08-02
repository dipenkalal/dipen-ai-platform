from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx


_shared_http_client: httpx.AsyncClient | None = None


def get_shared_http_client() -> httpx.AsyncClient:
    global _shared_http_client

    if (
        _shared_http_client is None
        or _shared_http_client.is_closed
    ):
        _shared_http_client = httpx.AsyncClient(
            timeout=4.0,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )

    return _shared_http_client


@asynccontextmanager
async def shared_http_client() -> AsyncIterator[httpx.AsyncClient]:
    yield get_shared_http_client()


async def close_shared_http_client() -> None:
    global _shared_http_client

    client = _shared_http_client
    _shared_http_client = None

    if client is not None and not client.is_closed:
        await client.aclose()
