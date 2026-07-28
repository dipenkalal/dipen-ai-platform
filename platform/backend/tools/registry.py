from tools.base import (
    BaseTool,
    ToolDefinition,
)
from tools.knowledge_tools import (
    KnowledgeAskTool,
    KnowledgeSearchTool,
)
from tools.system_tools import SystemStatusTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(
        self,
        tool: BaseTool,
    ) -> None:
        tool_id = tool.definition.id

        if tool_id in self._tools:
            raise ValueError(f"Tool already registered: {tool_id}")

        self._tools[tool_id] = tool

    def get(
        self,
        tool_id: str,
    ) -> BaseTool:
        tool = self._tools.get(tool_id)

        if tool is None:
            raise KeyError(f"Unknown tool: {tool_id}")

        return tool

    def list_definitions(
        self,
    ) -> list[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]


tool_registry = ToolRegistry()

tool_registry.register(SystemStatusTool())
tool_registry.register(KnowledgeSearchTool())
tool_registry.register(KnowledgeAskTool())
