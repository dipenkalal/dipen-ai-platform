from collections.abc import AsyncIterator

from fastapi import HTTPException

from gateway.providers.ollama import OllamaProvider
from gateway.schemas import (
    ChatRequest,
    ChatResponse,
    ModelInfo,
)


class GatewayService:
    def __init__(self) -> None:
        self.ollama = OllamaProvider()

    async def list_models(self) -> list[ModelInfo]:
        try:
            return await self.ollama.list_models()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Unable to retrieve Ollama models: "
                    f"{exc}"
                ),
            ) from exc

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        if request.provider not in {"auto", "ollama"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported provider: "
                    f"{request.provider}"
                ),
            )

        if not await self.ollama.health():
            raise HTTPException(
                status_code=503,
                detail="Ollama provider is unavailable",
            )

        try:
            return await self.ollama.chat(request)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Ollama request failed: {exc}",
            ) from exc

    async def stream_chat(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[str]:
        if request.provider not in {"auto", "ollama"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported provider: "
                    f"{request.provider}"
                ),
            )

        if not await self.ollama.health():
            raise HTTPException(
                status_code=503,
                detail="Ollama provider is unavailable",
            )

        async for event in self.ollama.stream_chat(request):
            yield event


gateway_service = GatewayService()
