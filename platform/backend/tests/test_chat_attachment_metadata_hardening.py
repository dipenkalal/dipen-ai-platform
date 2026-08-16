from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from history.chat_attachment_repository import (
    ChatAttachmentRepository,
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
from knowledge.services.upload_validation import (
    MAX_UPLOAD_FILENAME_LENGTH,
    PreparedUpload,
    prepare_upload,
)


class CountingUpload:
    def __init__(
        self,
        *,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._position = 0
        self.read_sizes: list[int] = []

    async def read(
        self,
        size: int = -1,
    ) -> bytes:
        self.read_sizes.append(size)

        if self._position >= len(
            self._content
        ):
            return b""

        if size < 0:
            end = len(self._content)
        else:
            end = min(
                self._position + size,
                len(self._content),
            )

        chunk = self._content[
            self._position:end
        ]
        self._position = end
        return chunk


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.upload_error: Exception | None = None
        self.delete_error: Exception | None = None

    async def upload_document(
        self,
        upload: PreparedUpload,
    ) -> DocumentUploadResponse:
        if self.upload_error is not None:
            raise self.upload_error

        return DocumentUploadResponse(
            status="indexed",
            document=DocumentInfo(
                document_id="document-1",
                filename=upload.filename,
                content_type=upload.content_type,
                size_bytes=len(upload.content),
                chunk_count=1,
                created_at=datetime.now(
                    timezone.utc
                ),
            ),
        )

    async def delete_document(
        self,
        document_id: str,
    ) -> DocumentDeleteResponse:
        if self.delete_error is not None:
            raise self.delete_error

        return DocumentDeleteResponse(
            status="deleted",
            document_id=document_id,
            deleted_chunks=1,
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
                "Metadata hardening test",
                "auto",
                "{}",
                "2026-08-16T00:00:00+00:00",
                "2026-08-16T00:00:00+00:00",
                None,
            ),
        )
        connection.commit()

    repository = ChatAttachmentRepository(
        database
    )
    knowledge = FakeKnowledgeService()
    service = ChatAttachmentService(
        repository=repository,
        knowledge=knowledge,
    )

    return repository, knowledge, service


@pytest.mark.asyncio
async def test_preflight_sanitizes_filename_and_content_type(
) -> None:
    upload = CountingUpload(
        filename="../../private/report.txt",
        content_type=(
            "Text/Plain; Charset=UTF-8"
        ),
        content=b"report",
    )

    prepared = await prepare_upload(upload)

    assert prepared.filename == "report.txt"
    assert prepared.extension == ".txt"
    assert prepared.content_type == "text/plain"


@pytest.mark.asyncio
async def test_preflight_sanitizes_windows_filename(
) -> None:
    upload = CountingUpload(
        filename="C:\\temp\\report.md",
        content_type="text/markdown",
        content=b"report",
    )

    prepared = await prepare_upload(upload)

    assert prepared.filename == "report.md"
    assert prepared.extension == ".md"


@pytest.mark.asyncio
async def test_preflight_rejects_too_long_filename_before_read(
) -> None:
    upload = CountingUpload(
        filename=(
            "a" * MAX_UPLOAD_FILENAME_LENGTH
            + ".txt"
        ),
        content_type="text/plain",
        content=b"unused",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await prepare_upload(upload)

    assert exc_info.value.status_code == 422
    assert upload.read_sizes == []


@pytest.mark.asyncio
async def test_upstream_5xx_detail_is_not_exposed_on_upload(
    tmp_path: Path,
) -> None:
    repository, knowledge, service = (
        make_service(tmp_path)
    )
    secret = (
        "/srv/private/vector-store.sock failed"
    )
    knowledge.upload_error = HTTPException(
        status_code=502,
        detail=secret,
    )
    upload = CountingUpload(
        filename="report.txt",
        content_type="text/plain",
        content=b"report",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "conversation-1",
            upload,
        )

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail
        == "Attachment ingestion failed"
    )
    assert secret not in str(
        exc_info.value.detail
    )

    records = (
        repository.list_conversation_attachments(
            "conversation-1"
        )
    )
    assert len(records) == 1
    assert records[0].status == "failed"
    assert records[0].error == secret


@pytest.mark.asyncio
async def test_unexpected_upload_error_is_not_exposed(
    tmp_path: Path,
) -> None:
    repository, knowledge, service = (
        make_service(tmp_path)
    )
    secret = "database password leaked here"
    knowledge.upload_error = RuntimeError(secret)
    upload = CountingUpload(
        filename="report.txt",
        content_type="text/plain",
        content=b"report",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "conversation-1",
            upload,
        )

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail
        == "Attachment ingestion failed"
    )
    assert secret not in str(
        exc_info.value.detail
    )

    records = (
        repository.list_conversation_attachments(
            "conversation-1"
        )
    )
    assert len(records) == 1
    assert records[0].error == secret


@pytest.mark.asyncio
async def test_upstream_5xx_detail_is_not_exposed_on_cleanup(
    tmp_path: Path,
) -> None:
    repository, knowledge, service = (
        make_service(tmp_path)
    )
    upload = CountingUpload(
        filename="report.txt",
        content_type="text/plain",
        content=b"report",
    )
    attachment = await service.upload_attachment(
        "conversation-1",
        upload,
    )

    secret = "/srv/qdrant/internal.sock denied"
    knowledge.delete_error = HTTPException(
        status_code=502,
        detail=secret,
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.delete_attachment(
            attachment.attachment_id
        )

    assert exc_info.value.status_code == 502
    assert (
        exc_info.value.detail
        == "Knowledge cleanup failed"
    )
    assert secret not in str(
        exc_info.value.detail
    )

    retained = repository.get_attachment(
        attachment.attachment_id
    )
    assert retained is not None
    assert retained.status == "deleting"
    assert retained.error == secret
