from datetime import datetime, timezone
from pathlib import Path

import pytest

from history.chat_attachment_context_service import (
    ChatAttachmentContextService,
)
from history.chat_attachment_repository import (
    ChatAttachmentRepository,
)
from history.chat_attachment_schemas import (
    ChatAttachmentContextRequest,
    ChatAttachmentRecord,
    CreatePendingChatAttachmentInput,
)
from history.database import HistoryDatabase
from knowledge.schemas import (
    SearchResponse,
    SearchResult,
)


def attachment(
    *,
    attachment_id: str,
    document_id: str,
    message_id: str = "message-a",
) -> ChatAttachmentRecord:
    now = datetime.now(timezone.utc)

    return ChatAttachmentRecord(
        attachment_id=attachment_id,
        conversation_id="conversation",
        message_id=message_id,
        knowledge_document_id=document_id,
        filename=f"{document_id}.txt",
        content_type="text/plain",
        size_bytes=100,
        chunk_count=1,
        sha256=None,
        ownership="chat_owned",
        status="indexed",
        error=None,
        created_at=now,
        updated_at=now,
    )


class FakeAttachmentRepository:
    def __init__(
        self,
        attachments: list[ChatAttachmentRecord],
    ) -> None:
        self.attachments = attachments
        self.calls: list[tuple[str, str]] = []

    def list_message_attachments(
        self,
        conversation_id: str,
        message_id: str,
    ) -> list[ChatAttachmentRecord]:
        self.calls.append(
            (
                conversation_id,
                message_id,
            )
        )

        return list(self.attachments)


class FakeKnowledgeSearch:
    def __init__(
        self,
        results: dict[
            str,
            list[SearchResult],
        ],
    ) -> None:
        self.results = results
        self.requests = []

    async def search(
        self,
        request,
    ) -> SearchResponse:
        self.requests.append(request)

        document_id = request.document_id or ""

        document_results = list(
            self.results.get(
                document_id,
                [],
            )
        )

        return SearchResponse(
            query=request.query,
            results=document_results,
            total=len(document_results),
        )


@pytest.mark.asyncio
async def test_no_bound_attachments_skips_search() -> None:
    repository = FakeAttachmentRepository([])

    knowledge = FakeKnowledgeSearch({})

    service = ChatAttachmentContextService(
        repository=repository,
        knowledge=knowledge,
    )

    result = await service.build_context(
        conversation_id="conversation",
        message_id="message-a",
        data=ChatAttachmentContextRequest(
            query="analyse this",
        ),
    )

    assert result.context == ""
    assert result.sources == []
    assert result.total == 0

    assert repository.calls == [
        (
            "conversation",
            "message-a",
        )
    ]

    assert knowledge.requests == []


@pytest.mark.asyncio
async def test_searches_only_bound_document_ids() -> None:
    repository = FakeAttachmentRepository(
        [
            attachment(
                attachment_id="attachment-a",
                document_id="document-a",
            ),
            attachment(
                attachment_id="attachment-b",
                document_id="document-b",
            ),
        ]
    )

    knowledge = FakeKnowledgeSearch(
        {
            "document-a": [
                SearchResult(
                    score=0.70,
                    document_id="document-a",
                    filename="a.txt",
                    chunk_id="chunk-a",
                    chunk_index=0,
                    text="Evidence from A",
                ),
                # Deliberately simulate a broken
                # vector-store response. The service
                # must drop this result.
                SearchResult(
                    score=0.99,
                    document_id="global-document",
                    filename="global.txt",
                    chunk_id="global-chunk",
                    chunk_index=0,
                    text="GLOBAL LEAK",
                ),
            ],
            "document-b": [
                SearchResult(
                    score=0.90,
                    document_id="document-b",
                    filename="b.txt",
                    chunk_id="chunk-b",
                    chunk_index=1,
                    text="Evidence from B",
                ),
            ],
        }
    )

    service = ChatAttachmentContextService(
        repository=repository,
        knowledge=knowledge,
    )

    result = await service.build_context(
        conversation_id="conversation",
        message_id="message-a",
        data=ChatAttachmentContextRequest(
            query="analyse the attachment",
            per_document_limit=3,
            max_sources=6,
        ),
    )

    assert [request.document_id for request in knowledge.requests] == [
        "document-a",
        "document-b",
    ]

    assert [source.document_id for source in result.sources] == [
        "document-b",
        "document-a",
    ]

    assert "Evidence from B" in (result.context)

    assert "Evidence from A" in (result.context)

    assert "GLOBAL LEAK" not in (result.context)

    assert result.total == 2


@pytest.mark.asyncio
async def test_context_respects_character_budget() -> None:
    repository = FakeAttachmentRepository(
        [
            attachment(
                attachment_id="attachment-a",
                document_id="document-a",
            ),
        ]
    )

    knowledge = FakeKnowledgeSearch(
        {
            "document-a": [
                SearchResult(
                    score=0.9,
                    document_id="document-a",
                    filename="a.txt",
                    chunk_id="chunk-a",
                    chunk_index=0,
                    text="x" * 3000,
                ),
            ],
        }
    )

    service = ChatAttachmentContextService(
        repository=repository,
        knowledge=knowledge,
    )

    result = await service.build_context(
        conversation_id="conversation",
        message_id="message-a",
        data=ChatAttachmentContextRequest(
            query="summarise",
            max_context_chars=500,
        ),
    )

    assert result.total == 1
    assert len(result.context) <= 500
    assert len(result.sources[0].excerpt) < 1200


def test_repository_returns_only_exact_indexed_user_binding(
    tmp_path: Path,
) -> None:
    database = HistoryDatabase(tmp_path / "history.db")

    database.initialize()

    now = datetime.now(timezone.utc).isoformat()

    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_conversations (
                conversation_id,
                title,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "conversation",
                "Context test",
                now,
                now,
            ),
        )

        connection.execute(
            """
            INSERT INTO chat_messages (
                message_id,
                conversation_id,
                sequence,
                role,
                content,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                'completed', ?, ?
            )
            """,
            (
                "message-a",
                "conversation",
                1,
                "user",
                "Analyse attachment A",
                now,
                now,
            ),
        )

        connection.execute(
            """
            INSERT INTO chat_messages (
                message_id,
                conversation_id,
                sequence,
                role,
                content,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                'completed', ?, ?
            )
            """,
            (
                "message-b",
                "conversation",
                2,
                "user",
                "Analyse attachment B",
                now,
                now,
            ),
        )

        connection.commit()

    repository = ChatAttachmentRepository(database)

    def create_indexed(
        filename_stem: str,
        document_id: str,
        message_id: str | None,
    ) -> str:
        created = repository.create_pending(
            "conversation",
            CreatePendingChatAttachmentInput(
                filename=f"{filename_stem}.txt",
                content_type="text/plain",
                size_bytes=10,
            ),
        )

        assert created is not None

        generated_attachment_id = created.attachment_id

        indexed = repository.mark_indexed(
            generated_attachment_id,
            knowledge_document_id=document_id,
            chunk_count=1,
        )

        assert indexed is not None

        if message_id is not None:
            bound = repository.bind_to_message(
                generated_attachment_id,
                message_id,
            )

            assert bound is not None

        return generated_attachment_id

    attachment_a_id = create_indexed(
        "attachment-a",
        "document-a",
        "message-a",
    )

    create_indexed(
        "attachment-b",
        "document-b",
        "message-b",
    )

    create_indexed(
        "attachment-unbound",
        "document-unbound",
        None,
    )

    result = repository.list_message_attachments(
        "conversation",
        "message-a",
    )

    assert len(result) == 1

    assert result[0].attachment_id == attachment_a_id

    assert result[0].knowledge_document_id == "document-a"

    assert (
        repository.list_message_attachments(
            "conversation",
            "missing-message",
        )
        == []
    )
