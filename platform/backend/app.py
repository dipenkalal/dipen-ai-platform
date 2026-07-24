import inspect
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from collectors.ollama import (
    get_ollama_status,
)
from collectors.system import (
    get_system_status,
)
from gateway.routes import (
    router as gateway_router,
)
from knowledge.routes import (
    router as knowledge_router,
)


app = FastAPI(
    title="DAP API",
    description=(
        "Backend service for Dipen AI Platform"
    ),
    version="0.4.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(gateway_router)
app.include_router(knowledge_router)


async def resolve_collector_result(
    value: Any,
) -> Any:
    if inspect.isawaitable(value):
        return await value

    return value


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "Dipen AI Platform API",
        "version": "0.4.0",
        "status": "online",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    system_status = (
        await resolve_collector_result(
            get_system_status()
        )
    )

    ollama_status = (
        await resolve_collector_result(
            get_ollama_status()
        )
    )

    return {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "system": system_status,
        "ollama": ollama_status,
    }
