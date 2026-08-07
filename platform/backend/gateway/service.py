from collections.abc import AsyncIterator

from fastapi import HTTPException

from agents.cancellation import raise_if_current_cancellation_requested
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

        raise_if_current_cancellation_requested(
            boundary="before-model-call"
        )

        if not await self.ollama.health():
            raise HTTPException(
                status_code=503,
                detail="Ollama provider is unavailable",
            )

        try:
            response = await self.ollama.chat(request)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Ollama request failed: {exc}",
            ) from exc

        raise_if_current_cancellation_requested(
            boundary="after-model-call"
        )
        return response

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

        raise_if_current_cancellation_requested(
            boundary="before-model-stream"
        )

        if not await self.ollama.health():
            raise HTTPException(
                status_code=503,
                detail="Ollama provider is unavailable",
            )

        async for event in self.ollama.stream_chat(request):
            raise_if_current_cancellation_requested(
                boundary="between-model-stream-events"
            )
            yield event

        raise_if_current_cancellation_requested(
            boundary="after-model-stream"
        )


gateway_service = GatewayService()
