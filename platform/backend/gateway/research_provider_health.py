from __future__ import annotations

import asyncio
import socket
import time
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gateway.searxng_search_provider import (
    SEARXNG_HOST,
    SEARXNG_PORT,
    SEARXNG_PROVIDER_ID,
    searxng_fixed_endpoint_is_loopback_only,
)


class ResearchProviderHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_id: Literal["searxng-local-v1"] = SEARXNG_PROVIDER_ID
    endpoint: Literal["http://127.0.0.1:8888/"] = "http://127.0.0.1:8888/"
    healthy: bool
    status_code: int | None = Field(default=None, ge=100, le=599)
    latency_ms: float = Field(ge=0)
    error_code: str | None = None
    checked_at: datetime
    provider_is_local_only: Literal[True] = True
    loopback_contract_valid: Literal[True] = True
    network_authority_granted: Literal[False] = False
    mutation_authority_granted: Literal[False] = False
    service_control_authority_granted: Literal[False] = False
    credentials_used: Literal[False] = False


async def check_searxng_health(
    *,
    connect_timeout_seconds: float = 2.0,
    read_timeout_seconds: float = 3.0,
) -> ResearchProviderHealth:
    if not searxng_fixed_endpoint_is_loopback_only():
        raise RuntimeError("SearXNG fixed endpoint no longer satisfies loopback contract")

    started = time.perf_counter()
    status_code: int | None = None
    error_code: str | None = None
    writer: asyncio.StreamWriter | None = None

    try:
        reader, connected_writer = await asyncio.wait_for(
            asyncio.open_connection(
                host=SEARXNG_HOST,
                port=SEARXNG_PORT,
                family=socket.AF_INET,
                flags=socket.AI_NUMERICHOST,
            ),
            timeout=connect_timeout_seconds,
        )
        writer = connected_writer
        peer = connected_writer.get_extra_info("peername")
        if not isinstance(peer, tuple) or not peer or peer[0] != SEARXNG_HOST:
            error_code = "searxng-health-peer-mismatch"
        else:
            request = (
                "GET / HTTP/1.1\r\n"
                f"Host: {SEARXNG_HOST}:{SEARXNG_PORT}\r\n"
                "User-Agent: DAP-ResearchOperations/14E\r\n"
                "Accept: text/html\r\n"
                "Accept-Encoding: identity\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            connected_writer.write(request)
            await asyncio.wait_for(
                connected_writer.drain(),
                timeout=read_timeout_seconds,
            )
            status_line = await asyncio.wait_for(
                reader.readline(),
                timeout=read_timeout_seconds,
            )
            parts = status_line.decode("ascii", errors="replace").strip().split(" ", 2)
            if len(parts) < 2 or parts[0] not in {"HTTP/1.0", "HTTP/1.1"}:
                error_code = "searxng-health-response-invalid"
            else:
                try:
                    status_code = int(parts[1])
                except ValueError:
                    error_code = "searxng-health-response-invalid"
                else:
                    if status_code != 200:
                        error_code = "searxng-health-http-error"
    except TimeoutError:
        error_code = "searxng-health-timeout"
    except OSError:
        error_code = "searxng-health-unavailable"
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except (TimeoutError, OSError):
                pass

    latency_ms = round(max(0.0, (time.perf_counter() - started) * 1000.0), 3)
    return ResearchProviderHealth(
        healthy=status_code == 200 and error_code is None,
        status_code=status_code,
        latency_ms=latency_ms,
        error_code=error_code,
        checked_at=datetime.now(timezone.utc),
    )
