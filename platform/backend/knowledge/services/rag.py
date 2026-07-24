import json
from collections.abc import AsyncIterator

from fastapi import HTTPException

from gateway.schemas import (
    ChatMessage,
    ChatRequest,
)
from gateway.service import gateway_service
from knowledge.schemas import (
    AskRequest,
    AskResponse,
    RagUsageMetrics,
    SearchRequest,
    SourceCitation,
)
from knowledge.services.knowledge import (
    knowledge_service,
)


SYSTEM_PROMPT = """
You are the document assistant inside Dipen AI Platform.

Answer the user's question using only the supplied document context.

Rules:
1. Do not use outside knowledge.
2. Every factual claim from the documents must include a citation such as [S1].
3. If multiple sources support a claim, cite them together, such as [S1][S2].
4. If the context does not contain enough information, clearly say:
   "I could not find enough information in the indexed documents."
5. Do not invent filenames, facts, citations, or quotations.
6. Keep the answer clear, accurate, and concise.
""".strip()


class RagService:
    async def retrieve_sources(
        self,
        request: AskRequest,
    ) -> list[SourceCitation]:
        search_response = await knowledge_service.search(
            SearchRequest(
                query=request.question,
                limit=request.retrieval_limit,
                score_threshold=request.score_threshold,
                document_id=request.document_id,
            )
        )

        sources: list[SourceCitation] = []

        for index, result in enumerate(
            search_response.results,
            start=1,
        ):
            excerpt = result.text.strip()

            if len(excerpt) > 1200:
                excerpt = excerpt[:1200].rstrip() + "…"

            sources.append(
                SourceCitation(
                    citation_id=f"S{index}",
                    document_id=result.document_id,
                    filename=result.filename,
                    chunk_id=result.chunk_id,
                    chunk_index=result.chunk_index,
                    score=result.score,
                    excerpt=excerpt,
                )
            )

        return sources

    def build_context(
        self,
        sources: list[SourceCitation],
    ) -> str:
        context_parts: list[str] = []

        for source in sources:
            context_parts.append(
                "\n".join(
                    [
                        f"[{source.citation_id}]",
                        f"Filename: {source.filename}",
                        f"Document ID: {source.document_id}",
                        f"Chunk index: {source.chunk_index}",
                        "Content:",
                        source.excerpt,
                    ]
                )
            )

        return "\n\n---\n\n".join(context_parts)

    def build_chat_request(
        self,
        request: AskRequest,
        sources: list[SourceCitation],
    ) -> ChatRequest:
        context = self.build_context(sources)

        user_prompt = "\n".join(
            [
                "DOCUMENT CONTEXT",
                "================",
                context,
                "",
                "USER QUESTION",
                "=============",
                request.question,
                "",
                "Answer using only the document context.",
                "Include source markers such as [S1] in the answer.",
            ]
        )

        return ChatRequest(
            provider=request.provider,
            model=request.model,
            messages=[
                ChatMessage(
                    role="system",
                    content=SYSTEM_PROMPT,
                ),
                ChatMessage(
                    role="user",
                    content=user_prompt,
                ),
            ],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
        )

    async def ask(
        self,
        request: AskRequest,
    ) -> AskResponse:
        sources = await self.retrieve_sources(request)

        if not sources:
            return AskResponse(
                answer=(
                    "I could not find enough information "
                    "in the indexed documents."
                ),
                provider=request.provider,
                model=request.model or "unknown",
                sources=[],
                usage=RagUsageMetrics(
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=0.0,
                ),
            )

        chat_request = self.build_chat_request(
            request,
            sources,
        )

        try:
            chat_response = await gateway_service.chat(
                chat_request
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"RAG generation failed: {exc}",
            ) from exc

        return AskResponse(
            answer=chat_response.message.content,
            provider=chat_response.provider,
            model=chat_response.model,
            sources=sources,
            usage=RagUsageMetrics(
                prompt_tokens=(
                    chat_response.usage.prompt_tokens
                ),
                completion_tokens=(
                    chat_response.usage.completion_tokens
                ),
                total_tokens=(
                    chat_response.usage.total_tokens
                ),
                latency_ms=(
                    chat_response.usage.latency_ms
                ),
            ),
        )

    async def stream_ask(
        self,
        request: AskRequest,
    ) -> AsyncIterator[str]:
        try:
            sources = await self.retrieve_sources(request)

            sources_event = {
                "type": "sources",
                "sources": [
                    source.model_dump()
                    for source in sources
                ],
            }

            yield json.dumps(sources_event) + "\n"

            if not sources:
                message = (
                    "I could not find enough information "
                    "in the indexed documents."
                )

                yield json.dumps(
                    {
                        "type": "content",
                        "content": message,
                    }
                ) + "\n"

                yield json.dumps(
                    {
                        "type": "done",
                        "provider": request.provider,
                        "model": request.model or "unknown",
                        "sources": [],
                        "usage": {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "latency_ms": 0.0,
                        },
                    }
                ) + "\n"

                return

            chat_request = self.build_chat_request(
                request,
                sources,
            )

            chat_request.stream = True

            async for raw_event in (
                gateway_service.stream_chat(
                    chat_request
                )
            ):
                stripped_event = raw_event.strip()

                if not stripped_event:
                    continue

                try:
                    event = json.loads(stripped_event)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "done":
                    event["sources"] = [
                        source.model_dump()
                        for source in sources
                    ]

                yield json.dumps(event) + "\n"

        except HTTPException as exc:
            yield json.dumps(
                {
                    "type": "error",
                    "error": str(exc.detail),
                    "status_code": exc.status_code,
                }
            ) + "\n"

        except Exception as exc:
            yield json.dumps(
                {
                    "type": "error",
                    "error": f"RAG request failed: {exc}",
                    "status_code": 500,
                }
            ) + "\n"


rag_service = RagService()
