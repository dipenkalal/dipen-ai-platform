from typing import Any

import httpx

from knowledge.config import (
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
)


class EmbeddingService:
    def __init__(self) -> None:
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_EMBEDDING_MODEL

        self.timeout = httpx.Timeout(
            connect=15.0,
            read=600.0,
            write=120.0,
            pool=15.0,
        )

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
            ) as client:
                response = await client.get(
                    f"{self.base_url}/api/tags"
                )

                return response.is_success
        except httpx.HTTPError:
            return False

    async def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self.model,
            "input": texts,
            "truncate": True,
        }

        async with httpx.AsyncClient(
            timeout=self.timeout,
        ) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json=payload,
            )

            response.raise_for_status()

        result: dict[str, Any] = response.json()
        embeddings = result.get("embeddings")

        if not isinstance(embeddings, list):
            raise RuntimeError(
                "Ollama returned no embeddings"
            )

        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Embedding count did not match input count"
            )

        return embeddings

    async def embed_query(
        self,
        query: str,
    ) -> list[float]:
        embeddings = await self.embed_texts(
            [query]
        )

        if not embeddings:
            raise RuntimeError(
                "Unable to generate query embedding"
            )

        return embeddings[0]


embedding_service = EmbeddingService()
