import inspect
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import (
    FastAPI,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from agents.routes import (
    router as agents_router,
)
from agents.truth_routes import (
    router as agent_truth_router,
)
from collectors.ollama import (
    get_ollama_status,
)
from collectors.system import (
    get_system_status,
)
from company.routes import (
    router as company_router,
)
from executive_office.routes import (
    router as executive_office_router,
)
from gateway.routes import (
    router as gateway_router,
)
from history.analytics_routes import (
    router as analytics_router,
)
from history.orchestration_routes import (
    router as orchestration_history_router,
)
from history.routes import (
    router as history_router,
)
from knowledge.routes import (
    router as knowledge_router,
)
from monitoring.routes import (
    router as monitoring_router,
)
from shared_http import (
    close_shared_http_client,
)

APP_VERSION = "0.12.0"


@asynccontextmanager
async def backend_lifespan(_: FastAPI):
    try:
        yield
    finally:
        await close_shared_http_client()


app = FastAPI(
    title="DAP API",
    description=("Backend service for Dipen AI Platform"),
    version=APP_VERSION,
    lifespan=backend_lifespan,
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
app.include_router(agents_router)
app.include_router(agent_truth_router)
app.include_router(company_router)
app.include_router(executive_office_router)
app.include_router(history_router)
app.include_router(orchestration_history_router)
app.include_router(analytics_router)
app.include_router(monitoring_router)


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
        "version": APP_VERSION,
        "status": "online",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    system_status = await resolve_collector_result(get_system_status())

    ollama_status = await resolve_collector_result(get_ollama_status())

    return {
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": system_status,
        "ollama": ollama_status,
    }
