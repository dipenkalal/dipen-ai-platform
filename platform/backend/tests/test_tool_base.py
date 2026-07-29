import pytest
from tools.base import (
    BaseTool,
    ToolDefinition,
    ToolExecutionResult,
)


def test_tool_definition_defaults():
    definition = ToolDefinition(
        id="demo.tool",
        name="Demo Tool",
        description="A test tool",
        category="test",
    )

    assert definition.id == "demo.tool"
    assert definition.name == "Demo Tool"
    assert definition.description == "A test tool"
    assert definition.category == "test"
    assert definition.safe is True
    assert definition.requires_confirmation is False


def test_tool_definition_custom_flags():
    definition = ToolDefinition(
        id="danger.tool",
        name="Danger Tool",
        description="Requires approval",
        category="admin",
        safe=False,
        requires_confirmation=True,
    )

    assert definition.safe is False
    assert definition.requires_confirmation is True


def test_tool_execution_result_defaults():
    result = ToolExecutionResult(
        tool_id="demo.tool",
        success=True,
    )

    assert result.tool_id == "demo.tool"
    assert result.success is True
    assert result.output is None
    assert result.error is None


def test_tool_execution_result_with_output_and_error():
    result = ToolExecutionResult(
        tool_id="demo.tool",
        success=False,
        output={"partial": True},
        error="Execution failed",
    )

    assert result.output == {"partial": True}
    assert result.error == "Execution failed"


@pytest.mark.asyncio
async def test_base_tool_execute_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await BaseTool.execute(object(), {"value": 1})


def test_base_tool_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseTool()
