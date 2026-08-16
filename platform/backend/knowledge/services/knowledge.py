from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from knowledge.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    KNOWLEDGE_UPLOAD_DIRECTORY,
    OLLAMA_EMBEDDING_MODEL,
    QDRANT_COLLECTION,
)
from knowledge.schemas import (
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadResponse,
    KnowledgeHealthResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from knowledge.services.chunker import (
    chunk_text,
)
from knowledge.services.embeddings import (
    embedding_service,
)
from knowledge.services.extractor import (
    EmptyDocumentError,
    UnsupportedDocumentError,
    extract_document_text,
)
from knowledge.services.upload_validation import (
    PreparedUpload,
    prepare_upload,
)
from knowledge.services.vector_store import (
    vector_store,
)


class KnowledgeService:
    async def health(
        self,
    ) -> KnowledgeHealthResponse:
        qdrant_online = (
            await vector_store.health()
        )

        ollama_online = (
            await embedding_service.health()
        )

        status = (
            "healthy"
            if qdrant_online and ollama_online
            else "degraded"
        )

        return KnowledgeHealthResponse(
            status=status,
            qdrant_online=qdrant_online,
            ollama_online=ollama_online,
            embedding_model=OLLAMA_EMBEDDING_MODEL,
            collection=QDRANT_COLLECTION,
        )

    async def upload_document(
        self,
        upload: UploadFile | PreparedUpload,
    ) -> DocumentUploadResponse:
        prepared = await prepare_upload(
            upload
        )

        return await self.upload_prepared_document(
            prepared
        )

    async def upload_prepared_document(
        self,
        prepared: PreparedUpload,
    ) -> DocumentUploadResponse:
        original_filename = prepared.filename
        extension = prepared.extension
        content_type = prepared.content_type
        content = prepared.content

        document_id = str(uuid4())
        created_at = datetime.now(
            timezone.utc
        )

        safe_filename = (
            f"{document_id}{extension}"
        )

        stored_path = (
            KNOWLEDGE_UPLOAD_DIRECTORY
            / safe_filename
        )

        stored_path.write_bytes(content)

        try:
            text = extract_document_text(
                stored_path
            )

            chunks = chunk_text(
                text=text,
                chunk_size=DEFAULT_CHUNK_SIZE,
                overlap=DEFAULT_CHUNK_OVERLAP,
            )

            if not chunks:
                raise EmptyDocumentError(
                    "The document produced no text chunks"
                )

            chunk_contents = [
                chunk.text
                for chunk in chunks
            ]

            embeddings: list[
                list[float]
            ] = []

            batch_size = 16

            for start in range(
                0,
                len(chunk_contents),
                batch_size,
            ):
                batch = chunk_contents[
                    start:start + batch_size
                ]

                batch_embeddings = (
                    await embedding_service
                    .embed_texts(batch)
                )

                embeddings.extend(
                    batch_embeddings
                )

            await vector_store.add_document_chunks(
                document_id=document_id,
                filename=original_filename,
                content_type=content_type,
                size_bytes=len(content),
                created_at=created_at,
                chunks=chunk_contents,
                embeddings=embeddings,
            )

        except UnsupportedDocumentError as exc:
            stored_path.unlink(
                missing_ok=True
            )

            raise HTTPException(
                status_code=415,
                detail=str(exc),
            ) from exc

        except EmptyDocumentError as exc:
            stored_path.unlink(
                missing_ok=True
            )

            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except Exception as exc:
            stored_path.unlink(
                missing_ok=True
            )

            raise HTTPException(
                status_code=502,
                detail=(
                    "Document ingestion failed: "
                    f"{exc}"
                ),
            ) from exc

        document = DocumentInfo(
            document_id=document_id,
            filename=original_filename,
            content_type=content_type,
            size_bytes=len(content),
            chunk_count=len(chunks),
            created_at=created_at,
        )

        return DocumentUploadResponse(
            status="indexed",
            document=document,
        )

    async def list_documents(
        self,
    ) -> DocumentListResponse:
        points = (
            await vector_store
            .list_document_points()
        )

        documents: dict[
            str,
            DocumentInfo,
        ] = {}

        chunk_counts: dict[str, int] = {}

        for point in points:
            payload = point.payload or {}
            document_id = payload.get(
                "document_id"
            )

            if not isinstance(
                document_id,
                str,
            ):
                continue

            chunk_counts[document_id] = (
                chunk_counts.get(
                    document_id,
                    0,
                )
                + 1
            )

            if document_id not in documents:
                created_at_raw = payload.get(
                    "created_at"
                )

                created_at = (
                    datetime.fromisoformat(
                        created_at_raw
                    )
                    if isinstance(
                        created_at_raw,
                        str,
                    )
                    else datetime.now(
                        timezone.utc
                    )
                )

                documents[document_id] = (
                    DocumentInfo(
                        document_id=document_id,
                        filename=str(
                            payload.get(
                                "filename",
                                "unknown",
                            )
                        ),
                        content_type=str(
                            payload.get(
                                "content_type",
                                "application/octet-stream",
                            )
                        ),
                        size_bytes=int(
                            payload.get(
                                "size_bytes",
                                0,
                            )
                        ),
                        chunk_count=0,
                        created_at=created_at,
                    )
                )

        result: list[DocumentInfo] = []

        for document_id, document in (
            documents.items()
        ):
            result.append(
                document.model_copy(
                    update={
                        "chunk_count":
                            chunk_counts.get(
                                document_id,
                                0,
                            )
                    }
                )
            )

        result.sort(
            key=lambda item: item.created_at,
            reverse=True,
        )

        return DocumentListResponse(
            documents=result,
            total=len(result),
        )

    async def search(
        self,
        request: SearchRequest,
    ) -> SearchResponse:
        try:
            query_vector = (
                await embedding_service
                .embed_query(request.query)
            )

            points = await vector_store.search(
                query_vector=query_vector,
                limit=request.limit,
                score_threshold=(
                    request.score_threshold
                ),
                document_id=(
                    request.document_id
                ),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Knowledge search failed: "
                    f"{exc}"
                ),
            ) from exc

        results: list[SearchResult] = []

        for point in points:
            payload = point.payload or {}

            results.append(
                SearchResult(
                    score=round(
                        float(point.score),
                        6,
                    ),
                    document_id=str(
                        payload.get(
                            "document_id",
                            "",
                        )
                    ),
                    filename=str(
                        payload.get(
                            "filename",
                            "unknown",
                        )
                    ),
                    chunk_id=str(
                        payload.get(
                            "chunk_id",
                            point.id,
                        )
                    ),
                    chunk_index=int(
                        payload.get(
                            "chunk_index",
                            0,
                        )
                    ),
                    text=str(
                        payload.get(
                            "text",
                            "",
                        )
                    ),
                )
            )

        return SearchResponse(
            query=request.query,
            results=results,
            total=len(results),
        )

    async def delete_document(
        self,
        document_id: str,
    ) -> DocumentDeleteResponse:
        deleted_chunks = (
            await vector_store
            .delete_document(document_id)
        )

        if deleted_chunks == 0:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        for path in (
            KNOWLEDGE_UPLOAD_DIRECTORY.glob(
                f"{document_id}.*"
            )
        ):
            path.unlink(
                missing_ok=True
            )

        return DocumentDeleteResponse(
            status="deleted",
            document_id=document_id,
            deleted_chunks=deleted_chunks,
        )


knowledge_service = KnowledgeService()
