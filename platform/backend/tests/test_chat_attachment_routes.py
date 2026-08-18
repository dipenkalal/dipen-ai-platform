from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from history import chat_routes
from history.chat_attachment_repository import (
    ChatAttachmentRepository,
)
from history.chat_attachment_service import (
    ChatAttachmentService,
)
from history.chat_repository import (
    ChatHistoryRepository,
)
from history.chat_service import (
    ChatHistoryService,
)
from history.database import HistoryDatabase
from knowledge.schemas import (
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentUploadResponse,
)


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.upload_count = 0
        self.deleted_document_ids: list[str] = []

    async def upload_document(
        self,
        upload,
    ) -> DocumentUploadResponse:
        content = await upload.read()

        self.upload_count += 1

        document_id = (
            f"chat-document-{self.upload_count}"
        )

        return DocumentUploadResponse(
            status="indexed",
            document=DocumentInfo(
                document_id=document_id,
                filename=(
                    upload.filename
                    or "document"
                ),
                content_type=(
                    upload.content_type
                    or "application/octet-stream"
                ),
                size_bytes=len(content),
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


def make_client(
    tmp_path: Path,
    monkeypatch,
) -> tuple[
    TestClient,
    FakeKnowledgeService,
]:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()

    chat_repository = (
        ChatHistoryRepository(
            database
        )
    )

    attachment_repository = (
        ChatAttachmentRepository(
            database
        )
    )

    knowledge = FakeKnowledgeService()

    attachment_service = (
        ChatAttachmentService(
            repository=(
                attachment_repository
            ),
            knowledge=knowledge,
        )
    )

    chat_service = ChatHistoryService(
        chat_repository,
        attachment_service=(
            attachment_service
        ),
    )

    monkeypatch.setattr(
        chat_routes,
        "chat_history_service",
        chat_service,
    )

    monkeypatch.setattr(
        chat_routes,
        "chat_attachment_service",
        attachment_service,
    )

    app = FastAPI()
    app.include_router(
        chat_routes.router
    )

    return (
        TestClient(app),
        knowledge,
    )


def create_conversation(
    client: TestClient,
    title: str,
) -> str:
    response = client.post(
        "/api/v1/chat/conversations",
        json={
            "title": title,
        },
    )

    assert response.status_code == 201

    return response.json()[
        "conversation_id"
    ]


def test_upload_list_and_delete_attachment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, knowledge = make_client(
        tmp_path,
        monkeypatch,
    )

    conversation_id = (
        create_conversation(
            client,
            "Attachment API",
        )
    )

    uploaded = client.post(
        (
            "/api/v1/chat/conversations/"
            f"{conversation_id}/attachments"
        ),
        files={
            "file": (
                "context.txt",
                b"DAP attachment context",
                "text/plain",
            ),
        },
    )

    assert uploaded.status_code == 201

    attachment = uploaded.json()

    assert (
        attachment["status"]
        == "indexed"
    )

    assert (
        attachment[
            "knowledge_document_id"
        ]
        == "chat-document-1"
    )

    attachment_id = (
        attachment["attachment_id"]
    )

    listing = client.get(

            "/api/v1/chat/conversations/"
            f"{conversation_id}/attachments"

    )

    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    deleted = client.delete(

            "/api/v1/chat/conversations/"
            f"{conversation_id}/attachments/"
            f"{attachment_id}"

    )

    assert deleted.status_code == 200
    assert deleted.json()["deleted"]

    assert (
        knowledge.deleted_document_ids
        == ["chat-document-1"]
    )

    listing = client.get(

            "/api/v1/chat/conversations/"
            f"{conversation_id}/attachments"

    )

    assert listing.json()["total"] == 0


def test_attachment_delete_rejects_other_conversation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, knowledge = make_client(
        tmp_path,
        monkeypatch,
    )

    owner_conversation = (
        create_conversation(
            client,
            "Owner conversation",
        )
    )

    other_conversation = (
        create_conversation(
            client,
            "Other conversation",
        )
    )

    uploaded = client.post(
        (
            "/api/v1/chat/conversations/"
            f"{owner_conversation}/attachments"
        ),
        files={
            "file": (
                "context.txt",
                b"context",
                "text/plain",
            ),
        },
    )

    attachment_id = uploaded.json()[
        "attachment_id"
    ]

    rejected = client.delete(

            "/api/v1/chat/conversations/"
            f"{other_conversation}/attachments/"
            f"{attachment_id}"

    )

    assert rejected.status_code == 404

    assert (
        knowledge.deleted_document_ids
        == []
    )

    owner_listing = client.get(

            "/api/v1/chat/conversations/"
            f"{owner_conversation}/attachments"

    )

    assert (
        owner_listing.json()["total"]
        == 1
    )


def test_missing_conversation_does_not_upload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, knowledge = make_client(
        tmp_path,
        monkeypatch,
    )

    response = client.post(
        (
            "/api/v1/chat/conversations/"
            "missing/attachments"
        ),
        files={
            "file": (
                "context.txt",
                b"context",
                "text/plain",
            ),
        },
    )

    assert response.status_code == 404
    assert knowledge.upload_count == 0


def test_conversation_delete_cleans_attachment_first(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, knowledge = make_client(
        tmp_path,
        monkeypatch,
    )

    conversation_id = (
        create_conversation(
            client,
            "Delete whole chat",
        )
    )

    uploaded = client.post(
        (
            "/api/v1/chat/conversations/"
            f"{conversation_id}/attachments"
        ),
        files={
            "file": (
                "context.txt",
                b"context",
                "text/plain",
            ),
        },
    )

    assert uploaded.status_code == 201

    deleted = client.delete(

            "/api/v1/chat/conversations/"
            f"{conversation_id}"

    )

    assert deleted.status_code == 200
    assert deleted.json()["deleted"]

    assert (
        knowledge.deleted_document_ids
        == ["chat-document-1"]
    )

    missing = client.get(

            "/api/v1/chat/conversations/"
            f"{conversation_id}"

    )

    assert missing.status_code == 404
