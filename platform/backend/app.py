import inspect
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_version import APP_VERSION
from career.routes import router as career_router
from collectors.system import get_system_status


app = FastAPI(
    title="Dipen Career Portal API",
    description=(
        "Career discovery, fit assessment, "
        "application tracking and owner review."
    ),
    version=APP_VERSION,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    career_router
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "Dipen Career Portal API",
        "version": APP_VERSION,
        "status": "online",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "product": "career-portal",
        "timestamp": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    value = get_system_status()

    if inspect.isawaitable(value):
        value = await value

    return {
        "version": APP_VERSION,
        "product": "career-portal",
        "timestamp": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "system": value,
    }
