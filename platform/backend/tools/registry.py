from typing import Any

from agents.cancellation import raise_if_current_cancellation_requested
from tools.base import (
    BaseTool,
    ToolDefinition,
    ToolExecutionResult,
)
from tools.knowledge_tools import (
    KnowledgeAskTool,
    KnowledgeSearchTool,
)
from tools.system_tools import SystemStatusTool


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


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(
        self,
        tool: BaseTool,
    ) -> None:
        tool_id = tool.definition.id

        if tool_id in self._tools:
            raise ValueError(
                f"Tool already registered: {tool_id}"
            )

        self._tools[tool_id] = CancellationAwareTool(tool)

    def get(
        self,
        tool_id: str,
    ) -> BaseTool:
        tool = self._tools.get(tool_id)

        if tool is None:
            raise KeyError(
                f"Unknown tool: {tool_id}"
            )

        return tool

    def list_definitions(
        self,
    ) -> list[ToolDefinition]:
        return [
            tool.definition
            for tool in self._tools.values()
        ]


tool_registry = ToolRegistry()

tool_registry.register(SystemStatusTool())
tool_registry.register(KnowledgeSearchTool())
tool_registry.register(KnowledgeAskTool())
