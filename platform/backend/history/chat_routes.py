from fastapi import (
    APIRouter,
    Query,
    status,
)

from history.chat_schemas import (
    ChatConversationDeleteResponse,
    ChatConversationListResponse,
    ChatConversationRecord,
    ChatMessageRecord,
    CreateChatConversationInput,
    CreateChatMessageInput,
    UpdateChatConversationInput,
    UpdateChatMessageInput,
)
from history.chat_service import (
    chat_history_service,
)

router = APIRouter(
    prefix="/api/v1/chat/conversations",
    tags=["Chat History"],
)


@router.post(
    "",
    response_model=ChatConversationRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_conversation(
    data: CreateChatConversationInput,
) -> ChatConversationRecord:
    return (
        chat_history_service
        .create_conversation(data)
    )


@router.get(
    "",
    response_model=ChatConversationListResponse,
)
async def list_chat_conversations(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    search: str | None = None,
    include_archived: bool = False,
) -> ChatConversationListResponse:
    return (
        chat_history_service
        .list_conversations(
            limit=limit,
            offset=offset,
            search=search,
            include_archived=(
                include_archived
            ),
        )
    )


@router.get(
    "/{conversation_id}",
    response_model=ChatConversationRecord,
)
async def get_chat_conversation(
    conversation_id: str,
) -> ChatConversationRecord:
    return (
        chat_history_service
        .get_conversation(
            conversation_id
        )
    )


@router.patch(
    "/{conversation_id}",
    response_model=ChatConversationRecord,
)
async def update_chat_conversation(
    conversation_id: str,
    data: UpdateChatConversationInput,
) -> ChatConversationRecord:
    return (
        chat_history_service
        .update_conversation(
            conversation_id,
            data,
        )
    )


@router.delete(
    "/{conversation_id}",
    response_model=(
        ChatConversationDeleteResponse
    ),
)
async def delete_chat_conversation(
    conversation_id: str,
) -> ChatConversationDeleteResponse:
    return (
        chat_history_service
        .delete_conversation(
            conversation_id
        )
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=ChatMessageRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_message(
    conversation_id: str,
    data: CreateChatMessageInput,
) -> ChatMessageRecord:
    return (
        chat_history_service
        .create_message(
            conversation_id,
            data,
        )
    )


@router.patch(
    "/{conversation_id}/messages/{message_id}",
    response_model=ChatMessageRecord,
)
async def update_chat_message(
    conversation_id: str,
    message_id: str,
    data: UpdateChatMessageInput,
) -> ChatMessageRecord:
    return (
        chat_history_service
        .update_message(
            conversation_id,
            message_id,
            data,
        )
    )
