from fastapi import HTTPException

from history.chat_repository import (
    ChatHistoryRepository,
    chat_history_repository,
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


class ChatHistoryService:
    def __init__(
        self,
        repository: ChatHistoryRepository,
    ) -> None:
        self.repository = repository

    def create_conversation(
        self,
        data: CreateChatConversationInput,
    ) -> ChatConversationRecord:
        return (
            self.repository
            .create_conversation(data)
        )

    def get_conversation(
        self,
        conversation_id: str,
    ) -> ChatConversationRecord:
        record = (
            self.repository
            .get_conversation(
                conversation_id
            )
        )

        if record is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat conversation "
                    f"'{conversation_id}' "
                    "was not found."
                ),
            )

        return record

    def list_conversations(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None,
        include_archived: bool,
    ) -> ChatConversationListResponse:
        conversations, total = (
            self.repository
            .list_conversations(
                limit=limit,
                offset=offset,
                search=search,
                include_archived=(
                    include_archived
                ),
            )
        )

        return ChatConversationListResponse(
            conversations=conversations,
            total=total,
            limit=limit,
            offset=offset,
        )

    def update_conversation(
        self,
        conversation_id: str,
        data: UpdateChatConversationInput,
    ) -> ChatConversationRecord:
        record = (
            self.repository
            .update_conversation(
                conversation_id,
                data,
            )
        )

        if record is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat conversation "
                    f"'{conversation_id}' "
                    "was not found."
                ),
            )

        return record

    def delete_conversation(
        self,
        conversation_id: str,
    ) -> ChatConversationDeleteResponse:
        deleted = (
            self.repository
            .delete_conversation(
                conversation_id
            )
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat conversation "
                    f"'{conversation_id}' "
                    "was not found."
                ),
            )

        return ChatConversationDeleteResponse(
            deleted=True,
            conversation_id=(
                conversation_id
            ),
        )

    def create_message(
        self,
        conversation_id: str,
        data: CreateChatMessageInput,
    ) -> ChatMessageRecord:
        message = (
            self.repository
            .create_message(
                conversation_id,
                data,
            )
        )

        if message is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat conversation "
                    f"'{conversation_id}' "
                    "was not found."
                ),
            )

        return message

    def update_message(
        self,
        conversation_id: str,
        message_id: str,
        data: UpdateChatMessageInput,
    ) -> ChatMessageRecord:
        message = (
            self.repository
            .update_message(
                conversation_id,
                message_id,
                data,
            )
        )

        if message is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat message "
                    f"'{message_id}' "
                    "was not found in "
                    "conversation "
                    f"'{conversation_id}'."
                ),
            )

        return message


chat_history_service = (
    ChatHistoryService(
        chat_history_repository
    )
)
