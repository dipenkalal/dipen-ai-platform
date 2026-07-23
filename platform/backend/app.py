from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collectors.ollama import get_ollama_status
from collectors.system import get_system_status


app = FastAPI(
    title="DAP API",
    description="Backend service for Dipen AI Platform",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "Dipen AI Platform API",
        "version": "0.2.0",
        "status": "online",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@app.get("/api/status")
async def status() -> dict:
    system = get_system_status()
    ollama = await get_ollama_status()

    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "system": system,
        "ollama": ollama,
    }