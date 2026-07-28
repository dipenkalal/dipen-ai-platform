from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


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
