import inspect
from typing import Any

from collectors.ollama import get_ollama_status
from collectors.system import get_system_status
from tools.base import (
    BaseTool,
    ToolDefinition,
    ToolExecutionResult,
)


async def resolve_result(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value

    return value


class SystemStatusTool(BaseTool):
    definition = ToolDefinition(
        id="system.status",
        name="System Status",
        description=(
            "Collect current CPU, memory, disk, uptime, "
            "and Ollama health information."
        ),
        category="system",
        safe=True,
        requires_confirmation=False,
    )

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        del arguments

        try:
            system_status = await resolve_result(
                get_system_status()
            )

            ollama_status = await resolve_result(
                get_ollama_status()
            )

            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=True,
                output={
                    "system": system_status,
                    "ollama": ollama_status,
                },
            )

        except Exception as exc:
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                error=str(exc),
            )
