from fastapi import (
    APIRouter,
    File,
    UploadFile,
)
from fastapi.responses import StreamingResponse

from knowledge.schemas import (
    AskRequest,
    AskResponse,
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    KnowledgeHealthResponse,
    SearchRequest,
    SearchResponse,
)
from knowledge.services.knowledge import (
    knowledge_service,
)
from knowledge.services.rag import (
    rag_service,
)


router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["Knowledge Engine"],
)


@router.get(
    "/health",
    response_model=KnowledgeHealthResponse,
)
async def knowledge_health(
) -> KnowledgeHealthResponse:
    return await knowledge_service.health()


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=201,
)
async def upload_document(
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    return await knowledge_service.upload_document(
        file
    )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
) -> DocumentListResponse:
    return await knowledge_service.list_documents()


@router.delete(
    "/documents/{document_id}",
    response_model=DocumentDeleteResponse,
)
async def delete_document(
    document_id: str,
) -> DocumentDeleteResponse:
    return await knowledge_service.delete_document(
        document_id
    )


@router.post(
    "/search",
    response_model=SearchResponse,
)
async def search_knowledge(
    request: SearchRequest,
) -> SearchResponse:
    return await knowledge_service.search(
        request
    )


@router.post(
    "/ask",
    response_model=AskResponse,
)
async def ask_knowledge(
    request: AskRequest,
) -> AskResponse:
    return await rag_service.ask(request)


@router.post(
    "/ask/stream",
    response_class=StreamingResponse,
)
async def stream_knowledge_answer(
    request: AskRequest,
) -> StreamingResponse:
    return StreamingResponse(
        rag_service.stream_ask(request),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
