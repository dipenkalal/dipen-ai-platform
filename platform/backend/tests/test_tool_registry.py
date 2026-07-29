import pytest
from tools.base import (
    BaseTool,
    ToolDefinition,
    ToolExecutionResult,
)
from tools.registry import ToolRegistry, tool_registry


class DummyTool(BaseTool):
    definition = ToolDefinition(
        id="dummy.tool",
        name="Dummy Tool",
        description="Tool used for registry tests",
        category="test",
    )

    async def execute(
        self,
        arguments: dict,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_id=self.definition.id,
            success=True,
            output=arguments,
        )


class SecondDummyTool(BaseTool):
    definition = ToolDefinition(
        id="dummy.second",
        name="Second Dummy Tool",
        description="Another test tool",
        category="test",
    )

    async def execute(
        self,
        arguments: dict,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_id=self.definition.id,
            success=True,
            output=arguments,
        )


def test_registry_starts_empty():
    registry = ToolRegistry()

    assert registry.list_definitions() == []


def test_register_and_get_tool():
    registry = ToolRegistry()
    tool = DummyTool()

    registry.register(tool)

    assert registry.get("dummy.tool") is tool


def test_register_duplicate_tool_raises_value_error():
    registry = ToolRegistry()
    tool = DummyTool()

    registry.register(tool)

    with pytest.raises(
        ValueError,
        match="Tool already registered: dummy.tool",
    ):
        registry.register(tool)


def test_get_unknown_tool_raises_key_error():
    registry = ToolRegistry()

    with pytest.raises(
        KeyError,
        match="Unknown tool: missing.tool",
    ):
        registry.get("missing.tool")


def test_list_definitions_returns_registered_definitions():
    registry = ToolRegistry()
    first = DummyTool()
    second = SecondDummyTool()

    registry.register(first)
    registry.register(second)

    assert registry.list_definitions() == [
        first.definition,
        second.definition,
    ]


def test_global_registry_contains_expected_tools():
    definitions = tool_registry.list_definitions()
    tool_ids = {definition.id for definition in definitions}

    assert tool_ids == {
        "system.status",
        "knowledge.search",
        "knowledge.ask",
    }


def test_global_registry_returns_registered_tool():
    tool = tool_registry.get("system.status")

    assert tool.definition.id == "system.status"


def test_global_registry_unknown_tool_raises_key_error():
    with pytest.raises(
        KeyError,
        match="Unknown tool: does.not.exist",
    ):
        tool_registry.get("does.not.exist")
