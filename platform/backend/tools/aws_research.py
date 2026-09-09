from typing import Any

from gateway.aws_knowledge import (
    AWSKnowledgeError,
    AWSKnowledgeLiteClient,
)
from tools.base import (
    BaseTool,
    ToolDefinition,
    ToolExecutionResult,
)


class AWSResearchTool(BaseTool):
    definition = ToolDefinition(
        id="aws.research",
        name="AWS Research",
        description=(
            "Retrieve bounded read-only evidence from "
            "official AWS Knowledge documentation."
        ),
        category="research",
        safe=True,
        requires_confirmation=False,
    )

    def __init__(
        self,
        client: AWSKnowledgeLiteClient | None = None,
    ) -> None:
        self.client = (
            client or AWSKnowledgeLiteClient()
        )

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        question = arguments.get("question")

        if not isinstance(question, str):
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                error=(
                    "aws.research requires a string "
                    "'question' argument"
                ),
            )

        question = " ".join(question.split())

        if not question:
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                error=(
                    "aws.research question must not be empty"
                ),
            )

        try:
            output = await self.client.research(
                question
            )
        except (
            AWSKnowledgeError,
            ValueError,
        ) as exc:
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                error=str(exc),
            )

        return ToolExecutionResult(
            tool_id=self.definition.id,
            success=True,
            output=output,
        )
