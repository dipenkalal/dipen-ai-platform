from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi import HTTPException

from history.chat_attachment_repository import (
    ChatAttachmentRepository,
)
from history.chat_attachment_schemas import (
    CreatePendingChatAttachmentInput,
)
from history.chat_attachment_service import (
    ChatAttachmentService,
)
from history.database import HistoryDatabase
from knowledge.schemas import (
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentUploadResponse,
)


class FakeUpload:
    def __init__(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> None:
        self.filename = filename
        self.content_type = content_type

        self._content = content
        self._position = 0

    async def read(
        self,
    ) -> bytes:
        if self._position != 0:
            return b""

        self._position = len(
            self._content
        )

        return self._content

    async def seek(
        self,
        offset: int,
    ) -> None:
        self._position = offset


class FakeKnowledgeService:
    def __init__(
        self,
    ) -> None:
        self.upload_error: (
            Exception | None
        ) = None

        self.delete_error: (
            Exception | None
        ) = None

        self.uploaded_content: (
            bytes | None
        ) = None

        self.deleted_document_ids: (
            list[str]
        ) = []

    async def upload_document(
        self,
        upload,
    ) -> DocumentUploadResponse:
        if self.upload_error is not None:
            raise self.upload_error

        self.uploaded_content = (
            await upload.read()
        )

        return DocumentUploadResponse(
            status="indexed",
            document=DocumentInfo(
                document_id="document-1",
                filename=(
                    upload.filename
                    or "document"
                ),
                content_type=(
                    upload.content_type
                    or "application/octet-stream"
                ),
                size_bytes=len(
                    self.uploaded_content
                ),
                chunk_count=3,
                created_at=datetime.now(
                    timezone.utc
                ),
            ),
        )

    async def delete_document(
        self,
        document_id: str,
    ) -> DocumentDeleteResponse:
        self.deleted_document_ids.append(
            document_id
        )

        if self.delete_error is not None:
            raise self.delete_error

        return DocumentDeleteResponse(
            status="deleted",
            document_id=document_id,
            deleted_chunks=3,
        )


def make_service(
    tmp_path: Path,
) -> tuple[
    ChatAttachmentRepository,
    FakeKnowledgeService,
    ChatAttachmentService,
]:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()

    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_conversations (
                conversation_id,
                title,
                preferred_role_id,
                settings_json,
                created_at,
                updated_at,
                archived_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "conversation-1",
                "Attachment service test",
                "auto",
                "{}",
                "2026-08-09T12:00:00+00:00",
                "2026-08-09T12:00:00+00:00",
                None,
            ),
        )

        connection.commit()

    repository = (
        ChatAttachmentRepository(
            database
        )
    )

    knowledge = (
        FakeKnowledgeService()
    )

    service = ChatAttachmentService(
        repository=repository,
        knowledge=knowledge,
    )

    return (
        repository,
        knowledge,
        service,
    )


@pytest.mark.asyncio
async def test_successful_upload_indexes_attachment(
    tmp_path: Path,
) -> None:
    (
        repository,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    content = (
        b"DAP attachment lifecycle test."
    )

    upload = FakeUpload(
        filename="example.txt",
        content_type="text/plain",
        content=content,
    )

    attachment = (
        await service.upload_attachment(
            "conversation-1",
            upload,
        )
    )

    assert (
        knowledge.uploaded_content
        == content
    )

    assert (
        attachment.status
        == "indexed"
    )

    assert (
        attachment.knowledge_document_id
        == "document-1"
    )

    assert attachment.chunk_count == 3

    assert (
        attachment.sha256
        == sha256(
            content
        ).hexdigest()
    )

    assert (
        attachment.size_bytes
        == len(content)
    )

    loaded = (
        repository.get_attachment(
            attachment.attachment_id
        )
    )

    assert loaded is not None
    assert loaded.status == "indexed"


@pytest.mark.asyncio
async def test_missing_conversation_does_not_upload(
    tmp_path: Path,
) -> None:
    (
        _,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    upload = FakeUpload(
        filename="example.txt",
        content_type="text/plain",
        content=b"example",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "missing-conversation",
            upload,
        )

    assert (
        exc_info.value.status_code
        == 404
    )

    assert (
        knowledge.uploaded_content
        is None
    )


@pytest.mark.asyncio
async def test_knowledge_failure_marks_attachment_failed(
    tmp_path: Path,
) -> None:
    (
        repository,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    knowledge.upload_error = (
        HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type"
            ),
        )
    )

    upload = FakeUpload(
        filename="example.exe",
        content_type=(
            "application/octet-stream"
        ),
        content=b"not-supported",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "conversation-1",
            upload,
        )

    assert (
        exc_info.value.status_code
        == 415
    )

    records = (
        repository
        .list_conversation_attachments(
            "conversation-1"
        )
    )

    assert len(records) == 1

    attachment = records[0]

    assert (
        attachment.status
        == "failed"
    )

    assert (
        attachment.knowledge_document_id
        is None
    )

    assert (
        attachment.error
        == "Unsupported file type"
    )


@pytest.mark.asyncio
async def test_metadata_finalize_failure_compensates_knowledge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repository,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    monkeypatch.setattr(
        repository,
        "mark_indexed",
        lambda *args, **kwargs: None,
    )

    upload = FakeUpload(
        filename="example.txt",
        content_type="text/plain",
        content=b"example",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "conversation-1",
            upload,
        )

    assert (
        exc_info.value.status_code
        == 500
    )

    assert (
        knowledge.deleted_document_ids
        == [
            "document-1",
        ]
    )

    records = (
        repository
        .list_conversation_attachments(
            "conversation-1"
        )
    )

    assert len(records) == 1

    assert (
        records[0].status
        == "failed"
    )

    assert (
        records[0].knowledge_document_id
        is None
    )


@pytest.mark.asyncio
async def test_compensation_accepts_already_missing_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repository,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    monkeypatch.setattr(
        repository,
        "mark_indexed",
        lambda *args, **kwargs: None,
    )

    knowledge.delete_error = (
        HTTPException(
            status_code=404,
            detail="Document not found",
        )
    )

    upload = FakeUpload(
        filename="example.txt",
        content_type="text/plain",
        content=b"example",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "conversation-1",
            upload,
        )

    assert (
        exc_info.value.status_code
        == 500
    )

    assert (
        knowledge.deleted_document_ids
        == [
            "document-1",
        ]
    )


@pytest.mark.asyncio
async def test_compensation_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        repository,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    monkeypatch.setattr(
        repository,
        "mark_indexed",
        lambda *args, **kwargs: None,
    )

    knowledge.delete_error = (
        HTTPException(
            status_code=502,
            detail="Qdrant unavailable",
        )
    )

    upload = FakeUpload(
        filename="example.txt",
        content_type="text/plain",
        content=b"example",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "conversation-1",
            upload,
        )

    assert (
        exc_info.value.status_code
        == 502
    )

    records = (
        repository
        .list_conversation_attachments(
            "conversation-1"
        )
    )

    assert len(records) == 1

    assert (
        records[0].status
        == "deleting"
    )

    assert (
        records[0].knowledge_document_id
        == "document-1"
    )

    assert (
        "cleanup also failed"
        in (
            records[0].error
            or ""
        )
    )


@pytest.mark.asyncio
async def test_delete_pending_attachment_needs_no_knowledge_cleanup(
    tmp_path: Path,
) -> None:
    (
        repository,
        knowledge,
        _,
    ) = make_service(
        tmp_path
    )

    attachment = (
        repository.create_pending(
            "conversation-1",
            CreatePendingChatAttachmentInput(
                filename="pending.txt",
                content_type="text/plain",
                size_bytes=7,
                sha256="a" * 64,
            ),
        )
    )

    assert attachment is not None

    service = ChatAttachmentService(
        repository=repository,
        knowledge=knowledge,
    )

    result = await service.delete_attachment(
        attachment.attachment_id
    )

    assert result.deleted
    assert (
        result.cleanup_result
        == "not_required"
    )

    assert (
        knowledge.deleted_document_ids
        == []
    )

    assert (
        repository.get_attachment(
            attachment.attachment_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_delete_indexed_attachment_cleans_knowledge_first(
    tmp_path: Path,
) -> None:
    (
        repository,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    upload = FakeUpload(
        filename="example.txt",
        content_type="text/plain",
        content=b"example",
    )

    attachment = (
        await service.upload_attachment(
            "conversation-1",
            upload,
        )
    )

    result = (
        await service.delete_attachment(
            attachment.attachment_id
        )
    )

    assert (
        result.cleanup_result
        == "deleted"
    )

    assert (
        knowledge.deleted_document_ids
        == ["document-1"]
    )

    assert (
        repository.get_attachment(
            attachment.attachment_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_delete_tolerates_missing_knowledge_document(
    tmp_path: Path,
) -> None:
    (
        repository,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    upload = FakeUpload(
        filename="example.txt",
        content_type="text/plain",
        content=b"example",
    )

    attachment = (
        await service.upload_attachment(
            "conversation-1",
            upload,
        )
    )

    knowledge.delete_error = (
        HTTPException(
            status_code=404,
            detail="Document not found",
        )
    )

    result = (
        await service.delete_attachment(
            attachment.attachment_id
        )
    )

    assert (
        result.cleanup_result
        == "already_missing"
    )

    assert (
        repository.get_attachment(
            attachment.attachment_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_delete_failure_retains_retryable_cleanup_target(
    tmp_path: Path,
) -> None:
    (
        repository,
        knowledge,
        service,
    ) = make_service(
        tmp_path
    )

    upload = FakeUpload(
        filename="example.txt",
        content_type="text/plain",
        content=b"example",
    )

    attachment = (
        await service.upload_attachment(
            "conversation-1",
            upload,
        )
    )

    knowledge.delete_error = (
        HTTPException(
            status_code=502,
            detail="Qdrant unavailable",
        )
    )

    with pytest.raises(
        HTTPException
    ):
        await service.delete_attachment(
            attachment.attachment_id
        )

    retained = (
        repository.get_attachment(
            attachment.attachment_id
        )
    )

    assert retained is not None
    assert retained.status == "deleting"

    assert (
        retained.knowledge_document_id
        == "document-1"
    )

    assert (
        retained.error
        == "Qdrant unavailable"
    )

    knowledge.delete_error = None

    result = (
        await service.delete_attachment(
            attachment.attachment_id
        )
    )

    assert result.deleted

    assert (
        repository.get_attachment(
            attachment.attachment_id
        )
        is None
    )
