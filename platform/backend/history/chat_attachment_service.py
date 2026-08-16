from hashlib import sha256
from typing import Protocol

from fastapi import (
    HTTPException,
    UploadFile,
)
from pydantic import ValidationError

from history.chat_attachment_repository import (
    ChatAttachmentCountLimitError,
    ChatAttachmentRepository,
    ChatAttachmentStorageLimitError,
    chat_attachment_repository,
)
from history.chat_attachment_schemas import (
    ChatAttachmentDeleteResponse,
    ChatAttachmentListResponse,
    ChatAttachmentRecord,
    CreatePendingChatAttachmentInput,
)
from knowledge.schemas import (
    DocumentDeleteResponse,
    DocumentUploadResponse,
)
from knowledge.services.knowledge import (
    knowledge_service,
)
from knowledge.services.upload_validation import (
    PreparedUpload,
    prepare_upload,
)

CHAT_ATTACHMENT_MAX_PER_CONVERSATION = 50
CHAT_ATTACHMENT_MAX_BYTES_PER_CONVERSATION = (
    100 * 1024 * 1024
)


class KnowledgeAttachmentLifecycle(
    Protocol
):
    async def upload_document(
        self,
        upload: UploadFile | PreparedUpload,
    ) -> DocumentUploadResponse:
        ...

    async def delete_document(
        self,
        document_id: str,
    ) -> DocumentDeleteResponse:
        ...


class ChatAttachmentService:
    def __init__(
        self,
        repository: ChatAttachmentRepository,
        knowledge: KnowledgeAttachmentLifecycle,
    ) -> None:
        self.repository = repository
        self.knowledge = knowledge

    def list_attachments(
        self,
        conversation_id: str,
    ) -> ChatAttachmentListResponse:
        if not self.repository.conversation_exists(
            conversation_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat conversation "
                    f"'{conversation_id}' "
                    "was not found."
                ),
            )

        attachments = (
            self.repository
            .list_conversation_attachments(
                conversation_id
            )
        )

        return ChatAttachmentListResponse(
            attachments=attachments,
            total=len(attachments),
        )

    async def delete_conversation_attachment(
        self,
        conversation_id: str,
        attachment_id: str,
    ) -> ChatAttachmentDeleteResponse:
        attachment = (
            self.repository.get_attachment(
                attachment_id
            )
        )

        if (
            attachment is None
            or attachment.conversation_id
            != conversation_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat attachment "
                    f"'{attachment_id}' "
                    "was not found in "
                    "conversation "
                    f"'{conversation_id}'."
                ),
            )

        if attachment.message_id is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Chat attachment "
                    f"'{attachment_id}' "
                    "is already bound to a message "
                    "and cannot be removed independently. "
                    "Delete the conversation to remove "
                    "bound attachment evidence."
                ),
            )

        return await self.delete_attachment(
            attachment_id
        )

    async def upload_attachment(
        self,
        conversation_id: str,
        upload: UploadFile,
    ) -> ChatAttachmentRecord:
        usage = (
            self.repository
            .conversation_attachment_usage(
                conversation_id
            )
        )

        if usage is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat conversation "
                    f"'{conversation_id}' "
                    "was not found."
                ),
            )

        attachment_count, _ = usage

        if (
            attachment_count
            >= CHAT_ATTACHMENT_MAX_PER_CONVERSATION
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Chat conversation attachment "
                    "limit reached. Remove an "
                    "unbound attachment or delete "
                    "the conversation before "
                    "uploading another file."
                ),
            )

        prepared = await prepare_upload(
            upload,
            validate_extension=False,
        )

        filename = prepared.filename
        content_type = prepared.content_type
        content = prepared.content

        digest = sha256(
            content
        ).hexdigest()

        try:
            pending_input = (
                CreatePendingChatAttachmentInput(
                    filename=filename,
                    content_type=content_type,
                    size_bytes=len(content),
                    sha256=digest,
                )
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Invalid attachment metadata"
                ),
            ) from exc

        try:
            attachment = (
                self.repository.create_pending(
                    conversation_id,
                    pending_input,
                    max_attachments=(
                        CHAT_ATTACHMENT_MAX_PER_CONVERSATION
                    ),
                    max_total_bytes=(
                        CHAT_ATTACHMENT_MAX_BYTES_PER_CONVERSATION
                    ),
                )
            )
        except ChatAttachmentCountLimitError as exc:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Chat conversation attachment "
                    "limit reached. Remove an "
                    "unbound attachment or delete "
                    "the conversation before "
                    "uploading another file."
                ),
            ) from exc
        except ChatAttachmentStorageLimitError as exc:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Chat conversation attachment "
                    "storage limit would be exceeded. "
                    "Remove an unbound attachment or "
                    "delete the conversation before "
                    "uploading another file."
                ),
            ) from exc

        if attachment is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat conversation "
                    f"'{conversation_id}' "
                    "was not found."
                ),
            )

        try:
            uploaded = (
                await self.knowledge
                .upload_document(prepared)
            )
        except HTTPException as exc:
            self.repository.mark_failed(
                attachment.attachment_id,
                self._exception_message(
                    exc
                ),
            )

            raise
        except Exception as exc:
            self.repository.mark_failed(
                attachment.attachment_id,
                self._exception_message(
                    exc
                ),
            )

            raise HTTPException(
                status_code=502,
                detail=(
                    "Attachment ingestion "
                    f"failed: {exc}"
                ),
            ) from exc

        document = uploaded.document

        try:
            indexed = (
                self.repository.mark_indexed(
                    attachment.attachment_id,
                    knowledge_document_id=(
                        document.document_id
                    ),
                    chunk_count=(
                        document.chunk_count
                    ),
                )
            )
        except Exception as exc:
            await self._compensate_after_indexing(
                attachment_id=(
                    attachment.attachment_id
                ),
                knowledge_document_id=(
                    document.document_id
                ),
                cause=exc,
            )

            raise AssertionError(
                "unreachable"
            ) from exc

        if indexed is None:
            await self._compensate_after_indexing(
                attachment_id=(
                    attachment.attachment_id
                ),
                knowledge_document_id=(
                    document.document_id
                ),
                cause=RuntimeError(
                    "Attachment metadata "
                    "could not transition "
                    "from pending to indexed"
                ),
            )

            raise AssertionError(
                "unreachable"
            )

        return indexed

    async def delete_attachment(
        self,
        attachment_id: str,
    ) -> ChatAttachmentDeleteResponse:
        attachment = (
            self.repository.get_attachment(
                attachment_id
            )
        )

        if attachment is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Chat attachment "
                    f"'{attachment_id}' "
                    "was not found."
                ),
            )

        document_id = (
            attachment.knowledge_document_id
        )

        if document_id is None:
            deleted = (
                self.repository.delete_metadata(
                    attachment_id
                )
            )

            if not deleted:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Chat attachment "
                        f"'{attachment_id}' "
                        "was not found."
                    ),
                )

            return ChatAttachmentDeleteResponse(
                deleted=True,
                attachment_id=attachment_id,
                knowledge_document_id=None,
                cleanup_result="not_required",
            )

        deleting = (
            self.repository.mark_deleting(
                attachment_id
            )
        )

        if deleting is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Chat attachment "
                    f"'{attachment_id}' "
                    "is not in a deletable state."
                ),
            )

        cleanup_result = "deleted"

        try:
            await self.knowledge.delete_document(
                document_id
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                cleanup_result = (
                    "already_missing"
                )
            else:
                self.repository.record_delete_error(
                    attachment_id,
                    self._exception_message(
                        exc
                    ),
                )
                raise
        except Exception as exc:
            self.repository.record_delete_error(
                attachment_id,
                self._exception_message(
                    exc
                ),
            )

            raise HTTPException(
                status_code=502,
                detail=(
                    "Knowledge cleanup "
                    f"failed: {exc}"
                ),
            ) from exc

        self.repository.delete_metadata(
            attachment_id
        )

        return ChatAttachmentDeleteResponse(
            deleted=True,
            attachment_id=attachment_id,
            knowledge_document_id=(
                document_id
            ),
            cleanup_result=cleanup_result,
        )

    async def cleanup_conversation_attachments(
        self,
        conversation_id: str,
    ) -> None:
        targets = (
            self.repository
            .list_cleanup_targets(
                conversation_id
            )
        )

        for attachment in targets:
            await self.delete_attachment(
                attachment.attachment_id
            )

    async def _compensate_after_indexing(
        self,
        *,
        attachment_id: str,
        knowledge_document_id: str,
        cause: Exception,
    ) -> None:
        compensation_error: (
            Exception | None
        ) = None

        try:
            await self.knowledge.delete_document(
                knowledge_document_id
            )
        except HTTPException as exc:
            if exc.status_code != 404:
                compensation_error = exc
        except Exception as exc:  # noqa: BLE001
            # Compensation is the final recovery boundary.
            # Preserve unexpected cleanup failures so the
            # attachment cannot appear successfully cleaned.
            compensation_error = exc

        error_message = (
            "Attachment metadata "
            "finalization failed: "
            f"{cause}"
        )

        if compensation_error is not None:
            error_message += (
                "; Knowledge cleanup "
                "also failed: "
                f"{compensation_error}"
            )

        if compensation_error is not None:
            cleanup_record = (
                self.repository
                .mark_cleanup_required(
                    attachment_id,
                    knowledge_document_id=(
                        knowledge_document_id
                    ),
                    error=error_message,
                )
            )

            if cleanup_record is None:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "Attachment cleanup "
                        "ownership could not "
                        "be persisted."
                    ),
                ) from compensation_error

            raise HTTPException(
                status_code=502,
                detail=(
                    "Attachment metadata "
                    "finalization failed and "
                    "Knowledge cleanup could "
                    "not be completed."
                ),
            ) from compensation_error

        self.repository.mark_failed(
            attachment_id,
            error_message,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Attachment metadata "
                "finalization failed. "
                "The indexed Knowledge "
                "document was cleaned up."
            ),
        ) from cause

    @staticmethod
    def _exception_message(
        exc: Exception,
    ) -> str:
        if isinstance(
            exc,
            HTTPException,
        ):
            return str(
                exc.detail
            )

        return str(exc)


chat_attachment_service = (
    ChatAttachmentService(
        repository=(
            chat_attachment_repository
        ),
        knowledge=knowledge_service,
    )
)
