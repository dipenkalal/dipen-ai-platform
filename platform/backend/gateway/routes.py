from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from gateway.schemas import (
    ChatRequest,
    ChatResponse,
    ModelsResponse,
)
from gateway.service import gateway_service


from gateway.local_ai import local_ai_adapter
from gateway.schemas import (
    LocalAIChatRequest,
    LocalAIChatResponse,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["AI Gateway"],
)


@router.get(
    "/models",
    response_model=ModelsResponse,
)
async def list_models() -> ModelsResponse:
    models = await gateway_service.list_models()

    return ModelsResponse(models=models)


@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
) -> ChatResponse:
    request.stream = False
    return await gateway_service.chat(request)


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
)
async def stream_chat(
    request: ChatRequest,
) -> StreamingResponse:
    request.stream = True

    return StreamingResponse(
        gateway_service.stream_chat(request),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/local-ai/chat",
    response_model=LocalAIChatResponse,
)
async def local_ai_chat(
    request: LocalAIChatRequest,
) -> LocalAIChatResponse:
    return await local_ai_adapter.chat(
        request
    )
