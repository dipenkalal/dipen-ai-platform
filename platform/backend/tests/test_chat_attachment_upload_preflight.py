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
from knowledge.services import upload_validation
from knowledge.services.upload_validation import (
    PreparedUpload,
    prepare_upload,
)


class CountingUpload:
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
            end = len(
                self._content
            )
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
    def __init__(
        self,
    ) -> None:
        self.upload_count = 0
        self.uploaded_content: bytes | None = None
        self.deleted_document_ids: list[str] = []

    async def upload_document(
        self,
        upload: PreparedUpload,
    ) -> DocumentUploadResponse:
        self.upload_count += 1
        self.uploaded_content = await upload.read()

        return DocumentUploadResponse(
            status="indexed",
            document=DocumentInfo(
                document_id="document-1",
                filename=upload.filename,
                content_type=upload.content_type,
                size_bytes=len(
                    self.uploaded_content
                ),
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
        self.deleted_document_ids.append(
            document_id
        )

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
                "Bounded upload test",
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
async def test_missing_conversation_is_rejected_before_read(
    tmp_path: Path,
) -> None:
    _, knowledge, service = make_service(
        tmp_path
    )
    upload = CountingUpload(
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

    assert exc_info.value.status_code == 404
    assert upload.read_sizes == []
    assert knowledge.upload_count == 0


@pytest.mark.asyncio
async def test_empty_upload_is_rejected_before_metadata(
    tmp_path: Path,
) -> None:
    repository, knowledge, service = (
        make_service(tmp_path)
    )
    upload = CountingUpload(
        filename="empty.txt",
        content_type="text/plain",
        content=b"",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "conversation-1",
            upload,
        )

    assert exc_info.value.status_code == 400
    assert upload.read_sizes == [
        upload_validation.MAX_FILE_SIZE_BYTES
        + 1
    ]
    assert knowledge.upload_count == 0
    assert (
        repository.list_conversation_attachments(
            "conversation-1"
        )
        == []
    )


@pytest.mark.asyncio
async def test_oversized_upload_is_bounded_before_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        upload_validation,
        "MAX_FILE_SIZE_BYTES",
        8,
    )
    repository, knowledge, service = (
        make_service(tmp_path)
    )
    upload = CountingUpload(
        filename="oversized.txt",
        content_type="text/plain",
        content=b"123456789",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await service.upload_attachment(
            "conversation-1",
            upload,
        )

    assert exc_info.value.status_code == 413
    assert upload.read_sizes == [9]
    assert knowledge.upload_count == 0
    assert (
        repository.list_conversation_attachments(
            "conversation-1"
        )
        == []
    )


@pytest.mark.asyncio
async def test_exact_limit_is_allowed_and_source_is_read_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        upload_validation,
        "MAX_FILE_SIZE_BYTES",
        8,
    )
    _, knowledge, service = make_service(
        tmp_path
    )
    content = b"12345678"
    upload = CountingUpload(
        filename="limit.txt",
        content_type="text/plain",
        content=content,
    )

    attachment = await service.upload_attachment(
        "conversation-1",
        upload,
    )

    assert attachment.status == "indexed"
    assert attachment.size_bytes == 8
    assert upload.read_sizes == [9]
    assert knowledge.upload_count == 1
    assert knowledge.uploaded_content == content


@pytest.mark.asyncio
async def test_direct_preflight_rejects_extension_before_read(
) -> None:
    upload = CountingUpload(
        filename="malware.exe",
        content_type="application/octet-stream",
        content=b"not-used",
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        await prepare_upload(upload)

    assert exc_info.value.status_code == 415
    assert upload.read_sizes == []
