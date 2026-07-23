import os
from typing import Any

import httpx


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)


async def get_ollama_status() -> dict[str, Any]:
    """Check Ollama availability and return currently loaded models."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/ps")
            response.raise_for_status()

        payload = response.json()
        models = payload.get("models", [])

        loaded_models = [
            {
                "name": model.get("name"),
                "size": model.get("size"),
                "size_vram": model.get("size_vram"),
                "expires_at": model.get("expires_at"),
            }
            for model in models
        ]

        return {
            "online": True,
            "loaded_count": len(loaded_models),
            "loaded_models": loaded_models,
        }

    except (httpx.HTTPError, ValueError) as exc:
        return {
            "online": False,
            "loaded_count": 0,
            "loaded_models": [],
            "error": str(exc),
        }