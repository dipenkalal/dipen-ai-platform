import json
from types import SimpleNamespace
from typing import Any

import pytest

import agents.executor as executor_module
from agents.executor import AgentExecutor
from agents.schemas import Workflow, WorkflowStep


def make_request(
    objective: str = "Test objective",
) -> SimpleNamespace:
    return SimpleNamespace(
        objective=objective,
        provider="ollama",
        model="test-model",
        temperature=0.0,
        max_tokens=256,
    )


def make_agent() -> SimpleNamespace:
    return SimpleNamespace(
        id="test-agent",
    )


@pytest.mark.asyncio
async def test_tool_workflow_step_returns_successful_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = AgentExecutor()

    fake_result = SimpleNamespace(
        tool_id="test.tool",
        success=True,
        output={"status": "ok"},
        error=None,
    )

    class FakeTool:
        async def execute(
            self,
            tool_input: dict[str, Any],
        ) -> SimpleNamespace:
            assert tool_input == {
                "command": "status",
            }

            return fake_result

    monkeypatch.setattr(
        executor_module.tool_registry,
        "get",
        lambda tool_id: FakeTool(),
    )

    workflow = Workflow(
        reason="test tool success",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Run test tool",
                tool_id="test.tool",
                input={
                    "command": "status",
                },
            ),
        ],
    )

    outputs = await executor._execute_workflow(
        workflow=workflow,
        request=make_request(),
        agent=make_agent(),
        system_prompt="",
    )

    assert outputs == {
        "tool-1": {
            "tool_id": "test.tool",
            "success": True,
            "output": {
                "status": "ok",
            },
            "error": None,
        }
    }


@pytest.mark.asyncio
async def test_tool_failure_propagates_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = AgentExecutor()

    class FailingTool:
        async def execute(
            self,
            tool_input: dict[str, Any],
        ) -> SimpleNamespace:
            return SimpleNamespace(
                tool_id="test.fail",
                success=False,
                output=None,
                error="simulated tool failure",
            )

    monkeypatch.setattr(
        executor_module.tool_registry,
        "get",
        lambda tool_id: FailingTool(),
    )

    workflow = Workflow(
        reason="test tool failure",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Failing tool",
                tool_id="test.fail",
            ),
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="simulated tool failure",
    ):
        await executor._execute_workflow(
            workflow=workflow,
            request=make_request(),
            agent=make_agent(),
            system_prompt="",
        )


@pytest.mark.asyncio
async def test_continue_on_error_captures_failure_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = AgentExecutor()

    class FakeTool:
        def __init__(
            self,
            tool_id: str,
        ) -> None:
            self.tool_id = tool_id

        async def execute(
            self,
            tool_input: dict[str, Any],
        ) -> SimpleNamespace:
            if self.tool_id == "test.fail":
                return SimpleNamespace(
                    tool_id=self.tool_id,
                    success=False,
                    output=None,
                    error="expected failure",
                )

            return SimpleNamespace(
                tool_id=self.tool_id,
                success=True,
                output={
                    "status": "continued",
                },
                error=None,
            )

    monkeypatch.setattr(
        executor_module.tool_registry,
        "get",
        lambda tool_id: FakeTool(tool_id),
    )

    workflow = Workflow(
        reason="test continue on error",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Expected failure",
                tool_id="test.fail",
                continue_on_error=True,
            ),
            WorkflowStep(
                id="tool-2",
                kind="tool",
                name="Continue execution",
                tool_id="test.success",
                depends_on=["tool-1"],
            ),
        ],
    )

    outputs = await executor._execute_workflow(
        workflow=workflow,
        request=make_request(),
        agent=make_agent(),
        system_prompt="",
    )

    assert outputs["tool-1"] == {
        "success": False,
        "error": "expected failure",
    }

    assert outputs["tool-2"]["success"] is True
    assert outputs["tool-2"]["output"] == {
        "status": "continued",
    }


@pytest.mark.asyncio
async def test_unmet_execution_order_is_rejected() -> None:
    executor = AgentExecutor()

    workflow = Workflow(
        reason="dependency appears later",
        steps=[
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate first",
                depends_on=["tool-1"],
            ),
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Tool appears later",
                tool_id="test.tool",
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="unmet dependencies: tool-1",
    ):
        await executor._execute_workflow(
            workflow=workflow,
            request=make_request(),
            agent=make_agent(),
            system_prompt="",
        )


@pytest.mark.asyncio
async def test_generation_receives_dependency_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = AgentExecutor()
    captured: dict[str, Any] = {}

    async def fake_chat(
        request: Any,
        system_prompt: str,
        user_content: str,
    ) -> SimpleNamespace:
        captured["request"] = request
        captured["system_prompt"] = system_prompt
        captured["user_content"] = user_content

        return SimpleNamespace(
            message=SimpleNamespace(
                content="Generated answer",
            ),
            provider="ollama",
            model="test-model",
        )

    monkeypatch.setattr(
        executor,
        "_chat",
        fake_chat,
    )

    workflow_step = WorkflowStep(
        id="generation-1",
        kind="generation",
        name="Generate answer",
        depends_on=["tool-1"],
    )

    dependency_output = {
        "tool_id": "test.tool",
        "success": True,
        "output": {
            "measurement": 42,
        },
        "error": None,
    }

    result = (
        await executor._execute_generation_workflow_step(
            workflow_step=workflow_step,
            previous_outputs={
                "tool-1": dependency_output,
            },
            request=make_request(
                "Analyse the measurement"
            ),
            agent=make_agent(),
            system_prompt="Test system prompt",
        )
    )

    assert result["success"] is True
    assert result["answer"] == "Generated answer"
    assert result["agent_id"] == "test-agent"

    assert captured["system_prompt"] == (
        "Test system prompt"
    )

    user_content = captured["user_content"]

    assert "Analyse the measurement" in user_content
    assert "Workflow dependency outputs:" in user_content
    assert '"measurement": 42' in user_content

    context_text = user_content.split(
        "Workflow dependency outputs:",
        maxsplit=1,
    )[1].split(
        "Use the dependency outputs",
        maxsplit=1,
    )[0]

    parsed_context = json.loads(
        context_text.strip()
    )

    assert parsed_context == {
        "tool-1": dependency_output,
    }


@pytest.mark.asyncio
async def test_unsupported_workflow_step_kind_is_rejected() -> None:
    executor = AgentExecutor()

    workflow_step = WorkflowStep.model_construct(
        id="unsupported-1",
        kind="unsupported",
        name="Unsupported step",
        tool_id=None,
        input={},
        depends_on=[],
        continue_on_error=False,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported workflow step kind",
    ):
        await executor._execute_workflow_step(
            workflow_step=workflow_step,
            previous_outputs={},
            request=make_request(),
            agent=make_agent(),
            system_prompt="",
        )
