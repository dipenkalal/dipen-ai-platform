# Save this file as:
# platform/backend/knowledge/services/vector_store.py

from datetime import datetime
from typing import Any
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from knowledge.config import (
    QDRANT_COLLECTION,
    QDRANT_URL,
)


class VectorStore:
    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=QDRANT_URL, timeout=60)
        self.collection_name = QDRANT_COLLECTION

    async def health(self) -> bool:
        try:
            await self.client.get_collections()
            return True
        except Exception:
            return False

    async def ensure_collection(self, vector_size: int) -> None:
        exists = await self.client.collection_exists(self.collection_name)

        if exists:
            collection = await self.client.get_collection(self.collection_name)
            vectors = collection.config.params.vectors
            current_size = getattr(vectors, "size", None)

            if current_size is None:
                raise RuntimeError(
                    "Expected a single-vector Qdrant collection configuration"
                )

            if current_size != vector_size:
                raise RuntimeError(
                    "Existing Qdrant collection uses "
                    f"vector size {current_size}, but "
                    f"the embedding model returned {vector_size}."
                )
            return

        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    async def add_document_chunks(
        self,
        document_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        created_at: datetime,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts must match")

        if not embeddings:
            raise ValueError("At least one embedding is required")

        await self.ensure_collection(len(embeddings[0]))

        points: list[PointStruct] = []

        for chunk_index, (chunk_text, embedding) in enumerate(
            zip(chunks, embeddings, strict=True)
        ):
            chunk_id = str(uuid4())

            points.append(
                PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload={
                        "document_id": document_id,
                        "filename": filename,
                        "content_type": content_type,
                        "size_bytes": size_bytes,
                        "created_at": created_at.isoformat(),
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                    },
                )
            )

        await self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    async def search(
        self,
        query_vector: list[float],
        limit: int,
        score_threshold: float | None,
        document_id: str | None,
    ) -> list[Any]:
        query_filter = None

        if document_id:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            )

        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return list(result.points)

    async def list_document_points(self) -> list[Any]:
        exists = await self.client.collection_exists(self.collection_name)

        if not exists:
            return []

        records: list[Any] = []
        offset = None

        while True:
            points, next_offset = await self.client.scroll(
                collection_name=self.collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            records.extend(points)

            if next_offset is None:
                break

            offset = next_offset

        return records

    async def delete_document(self, document_id: str) -> int:
        exists = await self.client.collection_exists(self.collection_name)

        if not exists:
            return 0

        matching, _ = await self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )

        deleted_count = len(matching)

        if deleted_count == 0:
            return 0

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
            wait=True,
        )

        return deleted_count


vector_store = VectorStore()
