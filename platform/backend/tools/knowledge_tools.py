from typing import Any

from knowledge.schemas import (
    AskRequest,
    SearchRequest,
)
from knowledge.services.knowledge import (
    knowledge_service,
)
from knowledge.services.rag import rag_service
from tools.base import (
    BaseTool,
    ToolDefinition,
    ToolExecutionResult,
)


class KnowledgeSearchTool(BaseTool):
    definition = ToolDefinition(
        id="knowledge.search",
        name="Knowledge Search",
        description=(
            "Search indexed documents using semantic "
            "vector retrieval."
        ),
        category="knowledge",
        safe=True,
        requires_confirmation=False,
    )

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        query = str(
            arguments.get("query", "")
        ).strip()

        if len(query) < 2:
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                error="A search query is required.",
            )

        try:
            response = await knowledge_service.search(
                SearchRequest(
                    query=query,
                    limit=int(
                        arguments.get("limit", 5)
                    ),
                    score_threshold=arguments.get(
                        "score_threshold",
                        0.40,
                    ),
                    document_id=arguments.get(
                        "document_id"
                    ),
                )
            )

            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=True,
                output=response.model_dump(
                    mode="json"
                ),
            )

        except Exception as exc:
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                error=str(exc),
            )


class KnowledgeAskTool(BaseTool):
    definition = ToolDefinition(
        id="knowledge.ask",
        name="Ask Knowledge",
        description=(
            "Answer a question using only information "
            "retrieved from indexed documents."
        ),
        category="knowledge",
        safe=True,
        requires_confirmation=False,
    )

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        question = str(
            arguments.get("question", "")
        ).strip()

        if len(question) < 2:
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                error="A question is required.",
            )

        try:
            response = await rag_service.ask(
                AskRequest(
                    question=question,
                    model=arguments.get("model"),
                    provider=arguments.get(
                        "provider",
                        "auto",
                    ),
                    temperature=float(
                        arguments.get(
                            "temperature",
                            0.2,
                        )
                    ),
                    max_tokens=int(
                        arguments.get(
                            "max_tokens",
                            600,
                        )
                    ),
                    retrieval_limit=int(
                        arguments.get(
                            "retrieval_limit",
                            5,
                        )
                    ),
                    score_threshold=arguments.get(
                        "score_threshold",
                        0.40,
                    ),
                    document_id=arguments.get(
                        "document_id"
                    ),
                )
            )

            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=True,
                output=response.model_dump(
                    mode="json"
                ),
            )

        except Exception as exc:
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                error=str(exc),
            )
