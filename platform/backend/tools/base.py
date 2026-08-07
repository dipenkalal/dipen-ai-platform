from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from agents.cancellation import raise_if_current_cancellation_requested


class ToolDefinition(BaseModel):
    id: str
    name: str
    description: str
    category: str
    safe: bool = True
    requires_confirmation: bool = False


class ToolExecutionResult(BaseModel):
    tool_id: str
    success: bool
    output: Any = None
    error: str | None = None


class BaseTool(ABC):
    definition: ToolDefinition

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        raise NotImplementedError


class CancellationAwareTool(BaseTool):
    def __init__(self, tool: BaseTool) -> None:
        self.tool = tool
        self.definition = tool.definition

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        raise_if_current_cancellation_requested(
            boundary="before-tool-call"
        )
        result = await self.tool.execute(arguments)
        raise_if_current_cancellation_requested(
            boundary="after-tool-call"
        )
        return result
