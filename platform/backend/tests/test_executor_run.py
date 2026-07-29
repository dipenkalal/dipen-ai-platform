from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import agents.executor as executor_module
import pytest
from agents.executor import AgentExecutor
from agents.planner import ToolPlan
from agents.schemas import (
    AgentDefinition,
    AgentRunRequest,
    Workflow,
    WorkflowStep,
)
from tools.base import ToolExecutionResult


def make_request(**overrides):
    data = {
        "mode": "manual",
        "agent_id": "coding-agent",
        "objective": "Write hello world",
        "provider": "ollama",
        "model": "llama3",
        "temperature": 0.2,
        "max_tokens": 200,
        "max_steps": 3,
        "retrieval_limit": 5,
        "score_threshold": 0.4,
        "document_id": None,
    }

    data.update(overrides)
    return AgentRunRequest(**data)


def make_agent(
    agent_id="coding-agent",
    name="Coding Agent",
):
    return AgentDefinition(
        id=agent_id,
        name=name,
        description="test",
        tools=[],
    )


def make_tool_plan():
    return ToolPlan(
        tool_ids=(),
        reason="unit test",
    )


def make_tool_plan_with(*tool_ids: str) -> ToolPlan:
    return ToolPlan(
        tool_ids=tuple(tool_ids),
        reason="unit test",
    )


def make_workflow():
    return Workflow(
        reason="workflow",
        steps=[
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
            )
        ],
    )


@pytest.mark.asyncio
async def test_run_requires_agent_id():
    executor = AgentExecutor()

    request = make_request(agent_id=None)

    with pytest.raises(
        ValueError,
        match="resolved agent_id",
    ):
        await executor.run(request)


@pytest.mark.asyncio
async def test_run_without_registered_handler(
    monkeypatch,
):
    executor = AgentExecutor()

    agent = make_agent(
        "custom-agent",
        "Custom",
    )

    executor._handlers.clear()

    monkeypatch.setattr(
        "agents.executor.agent_registry.get",
        lambda _id: agent,
    )

    monkeypatch.setattr(
        "agents.executor.agent_tool_planner.plan",
        lambda **kwargs: make_tool_plan(),
    )

    monkeypatch.setattr(
        "agents.executor.agent_tool_planner.build_workflow",
        lambda **kwargs: make_workflow(),
    )

    request = make_request(
        agent_id="custom-agent",
    )

    with pytest.raises(
        ValueError,
        match="No executor",
    ):
        await executor.run(request)


@pytest.mark.asyncio
async def test_run_dispatches_to_handler(
    monkeypatch,
):
    executor = AgentExecutor()

    agent = make_agent()

    monkeypatch.setattr(
        "agents.executor.agent_registry.get",
        lambda _id: agent,
    )

    monkeypatch.setattr(
        "agents.executor.agent_tool_planner.plan",
        lambda **kwargs: make_tool_plan(),
    )

    monkeypatch.setattr(
        "agents.executor.agent_tool_planner.build_workflow",
        lambda **kwargs: make_workflow(),
    )

    async def fake_handler(
        request,
        agent,
        tool_plan,
        workflow,
        run_id,
        started_at,
        timer_started,
        steps,
    ):
        return "OK"

    executor._handlers["coding-agent"] = fake_handler

    result = await executor.run(
        make_request(),
    )

    assert result == "OK"


def test_append_planning_step():
    executor = AgentExecutor()

    steps = []

    executor._append_planning_step(
        request=make_request(),
        agent=make_agent(),
        tool_plan=make_tool_plan(),
        workflow=make_workflow(),
        steps=steps,
    )

    assert len(steps) == 1

    planning = steps[0]

    assert planning.type == "planning"

    assert planning.success is True

    assert planning.output["selected_agent"] == "coding-agent"

    assert planning.output["tool_plan"]["requires_tools"] is False


def test_validate_workflow_rejects_empty_workflow():
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Empty workflow",
        steps=[],
    )

    with pytest.raises(
        ValueError,
        match="at least one step",
    ):
        executor._validate_workflow(workflow)


def test_validate_workflow_rejects_duplicate_step_ids():
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Duplicate IDs",
        steps=[
            WorkflowStep(
                id="step-1",
                kind="generation",
                name="First",
            ),
            WorkflowStep(
                id="step-1",
                kind="generation",
                name="Second",
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="duplicate step id",
    ):
        executor._validate_workflow(workflow)


def test_validate_workflow_rejects_tool_without_tool_id():
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Missing tool ID",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Broken tool",
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="missing tool_id",
    ):
        executor._validate_workflow(workflow)


def test_validate_workflow_rejects_self_dependency():
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Self dependency",
        steps=[
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
                depends_on=["generation-1"],
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="cannot depend on itself",
    ):
        executor._validate_workflow(workflow)


def test_validate_workflow_rejects_unknown_dependency():
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Unknown dependency",
        steps=[
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
                depends_on=["missing-step"],
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="unknown dependency",
    ):
        executor._validate_workflow(workflow)


def test_validate_workflow_rejects_dependency_cycle():
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Dependency cycle",
        steps=[
            WorkflowStep(
                id="step-1",
                kind="generation",
                name="First",
                depends_on=["step-2"],
            ),
            WorkflowStep(
                id="step-2",
                kind="generation",
                name="Second",
                depends_on=["step-1"],
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="dependency cycle",
    ):
        executor._validate_workflow(workflow)


def test_validate_workflow_accepts_valid_dependencies():
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Valid workflow",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Run tool",
                tool_id="system.status",
            ),
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
                depends_on=["tool-1"],
            ),
            WorkflowStep(
                id="generation-2",
                kind="generation",
                name="Generate again",
                depends_on=["tool-1"],
            ),
        ],
    )

    assert executor._validate_workflow(workflow) is None


@pytest.mark.asyncio
async def test_execute_workflow_step_dispatches_tool(
    monkeypatch,
):
    executor = AgentExecutor()

    expected = {
        "success": True,
        "output": {"cpu": 20},
    }

    mocked = AsyncMock(return_value=expected)

    monkeypatch.setattr(
        executor,
        "_execute_tool_workflow_step",
        mocked,
    )

    workflow_step = WorkflowStep(
        id="tool-1",
        kind="tool",
        name="System status",
        tool_id="system.status",
    )

    result = await executor._execute_workflow_step(
        workflow_step=workflow_step,
        previous_outputs={},
        request=make_request(),
        agent=make_agent(),
        system_prompt="System prompt",
    )

    assert result == expected
    mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_workflow_step_dispatches_generation(
    monkeypatch,
):
    executor = AgentExecutor()

    expected = {
        "success": True,
        "answer": "Generated answer",
    }

    mocked = AsyncMock(return_value=expected)

    monkeypatch.setattr(
        executor,
        "_execute_generation_workflow_step",
        mocked,
    )

    workflow_step = WorkflowStep(
        id="generation-1",
        kind="generation",
        name="Generate",
    )

    result = await executor._execute_workflow_step(
        workflow_step=workflow_step,
        previous_outputs={},
        request=make_request(),
        agent=make_agent(),
        system_prompt="System prompt",
    )

    assert result == expected
    mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_workflow_step_rejects_unsupported_kind():
    executor = AgentExecutor()

    workflow_step = WorkflowStep(
        id="condition-1",
        kind="condition",
        name="Unsupported condition",
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


@pytest.mark.asyncio
async def test_execute_tool_workflow_step_requires_tool_id():
    executor = AgentExecutor()

    workflow_step = WorkflowStep(
        id="tool-1",
        kind="tool",
        name="Broken tool",
    )

    with pytest.raises(
        ValueError,
        match="missing tool_id",
    ):
        await executor._execute_tool_workflow_step(
            workflow_step=workflow_step,
            previous_outputs={},
        )


@pytest.mark.asyncio
async def test_execute_tool_workflow_step_success(
    monkeypatch,
):
    executor = AgentExecutor()

    fake_tool = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolExecutionResult(
                tool_id="system.status",
                success=True,
                output={
                    "cpu_percent": 25,
                },
            )
        )
    )

    monkeypatch.setattr(
        "agents.executor.tool_registry.get",
        lambda tool_id: fake_tool,
    )

    workflow_step = WorkflowStep(
        id="tool-1",
        kind="tool",
        name="Collect status",
        tool_id="system.status",
        input={
            "detail": True,
        },
    )

    result = await executor._execute_tool_workflow_step(
        workflow_step=workflow_step,
        previous_outputs={},
    )

    assert result == {
        "tool_id": "system.status",
        "success": True,
        "output": {
            "cpu_percent": 25,
        },
        "error": None,
    }

    fake_tool.execute.assert_awaited_once_with(
        {
            "detail": True,
        }
    )


@pytest.mark.asyncio
async def test_execute_tool_workflow_step_raises_tool_error(
    monkeypatch,
):
    executor = AgentExecutor()

    fake_tool = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolExecutionResult(
                tool_id="system.status",
                success=False,
                error="System tool failed",
            )
        )
    )

    monkeypatch.setattr(
        "agents.executor.tool_registry.get",
        lambda tool_id: fake_tool,
    )

    workflow_step = WorkflowStep(
        id="tool-1",
        kind="tool",
        name="Collect status",
        tool_id="system.status",
    )

    with pytest.raises(
        RuntimeError,
        match="System tool failed",
    ):
        await executor._execute_tool_workflow_step(
            workflow_step=workflow_step,
            previous_outputs={},
        )


@pytest.mark.asyncio
async def test_execute_tool_workflow_step_uses_default_error(
    monkeypatch,
):
    executor = AgentExecutor()

    fake_tool = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolExecutionResult(
                tool_id="system.status",
                success=False,
                error=None,
            )
        )
    )

    monkeypatch.setattr(
        "agents.executor.tool_registry.get",
        lambda tool_id: fake_tool,
    )

    workflow_step = WorkflowStep(
        id="tool-1",
        kind="tool",
        name="Collect status",
        tool_id="system.status",
    )

    with pytest.raises(
        RuntimeError,
        match="Tool execution failed",
    ):
        await executor._execute_tool_workflow_step(
            workflow_step=workflow_step,
            previous_outputs={},
        )


@pytest.mark.asyncio
async def test_execute_generation_without_dependencies(
    monkeypatch,
):
    executor = AgentExecutor()

    chat_response = SimpleNamespace(
        message=SimpleNamespace(
            content="Generated response",
        ),
        provider="ollama",
        model="llama3",
    )

    mocked_chat = AsyncMock(
        return_value=chat_response,
    )

    monkeypatch.setattr(
        executor,
        "_chat",
        mocked_chat,
    )

    workflow_step = WorkflowStep(
        id="generation-1",
        kind="generation",
        name="Generate",
    )

    request = make_request(
        objective="Explain Docker",
    )

    result = await executor._execute_generation_workflow_step(
        workflow_step=workflow_step,
        previous_outputs={},
        request=request,
        agent=make_agent(),
        system_prompt="Coding prompt",
    )

    assert result["success"] is True
    assert result["answer"] == "Generated response"
    assert result["provider"] == "ollama"
    assert result["model"] == "llama3"
    assert result["agent_id"] == "coding-agent"
    assert result["chat_response"] is chat_response

    mocked_chat.assert_awaited_once_with(
        request=request,
        system_prompt="Coding prompt",
        user_content="Explain Docker",
    )


@pytest.mark.asyncio
async def test_execute_generation_with_dependency_outputs(
    monkeypatch,
):
    executor = AgentExecutor()

    chat_response = SimpleNamespace(
        message=SimpleNamespace(
            content="System assessment",
        ),
        provider="ollama",
        model="llama3",
    )

    captured = {}

    async def fake_chat(
        request,
        system_prompt,
        user_content,
    ):
        captured["request"] = request
        captured["system_prompt"] = system_prompt
        captured["user_content"] = user_content
        return chat_response

    monkeypatch.setattr(
        executor,
        "_chat",
        fake_chat,
    )

    workflow_step = WorkflowStep(
        id="generation-1",
        kind="generation",
        name="Generate assessment",
        depends_on=["tool-1", "missing-output"],
    )

    previous_outputs = {
        "tool-1": {
            "success": True,
            "output": {
                "cpu_percent": 75,
            },
        },
    }

    request = make_request(
        objective="Assess system health",
    )

    result = await executor._execute_generation_workflow_step(
        workflow_step=workflow_step,
        previous_outputs=previous_outputs,
        request=request,
        agent=make_agent(
            agent_id="system-agent",
            name="System Agent",
        ),
        system_prompt="System prompt",
    )

    assert result["answer"] == "System assessment"
    assert result["agent_id"] == "system-agent"

    user_content = captured["user_content"]

    assert "User objective:" in user_content
    assert "Assess system health" in user_content
    assert "Workflow dependency outputs:" in user_content
    assert '"tool-1"' in user_content
    assert '"cpu_percent": 75' in user_content
    assert "missing-output" not in user_content
    assert "source of truth" in user_content


@pytest.mark.asyncio
async def test_execute_workflow_runs_steps_in_order(
    monkeypatch,
):
    executor = AgentExecutor()

    calls = []

    async def fake_execute_step(
        workflow_step,
        previous_outputs,
        request,
        agent,
        system_prompt,
    ):
        calls.append(
            (
                workflow_step.id,
                dict(previous_outputs),
            )
        )

        return {
            "success": True,
            "step_id": workflow_step.id,
        }

    monkeypatch.setattr(
        executor,
        "_execute_workflow_step",
        fake_execute_step,
    )

    workflow = Workflow(
        reason="Ordered workflow",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Tool",
                tool_id="system.status",
            ),
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
                depends_on=["tool-1"],
            ),
        ],
    )

    result = await executor._execute_workflow(
        workflow=workflow,
        request=make_request(),
        agent=make_agent(),
        system_prompt="Prompt",
    )

    assert result == {
        "tool-1": {
            "success": True,
            "step_id": "tool-1",
        },
        "generation-1": {
            "success": True,
            "step_id": "generation-1",
        },
    }

    assert calls[0] == (
        "tool-1",
        {},
    )

    assert "tool-1" in calls[1][1]


@pytest.mark.asyncio
async def test_execute_workflow_rejects_unmet_ordered_dependency():
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Wrong execution order",
        steps=[
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
                depends_on=["tool-1"],
            ),
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Tool",
                tool_id="system.status",
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="unmet dependencies",
    ):
        await executor._execute_workflow(
            workflow=workflow,
            request=make_request(),
            agent=make_agent(),
            system_prompt="Prompt",
        )


@pytest.mark.asyncio
async def test_execute_workflow_reraises_step_failure(
    monkeypatch,
):
    executor = AgentExecutor()

    async def failing_step(**kwargs):
        raise RuntimeError("Execution exploded")

    monkeypatch.setattr(
        executor,
        "_execute_workflow_step",
        failing_step,
    )

    workflow = Workflow(
        reason="Failure workflow",
        steps=[
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
                continue_on_error=False,
            ),
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="Execution exploded",
    ):
        await executor._execute_workflow(
            workflow=workflow,
            request=make_request(),
            agent=make_agent(),
            system_prompt="Prompt",
        )


@pytest.mark.asyncio
async def test_execute_workflow_continues_after_allowed_failure(
    monkeypatch,
):
    executor = AgentExecutor()

    async def failing_step(**kwargs):
        raise RuntimeError("Optional step failed")

    monkeypatch.setattr(
        executor,
        "_execute_workflow_step",
        failing_step,
    )

    workflow = Workflow(
        reason="Continue on error",
        steps=[
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Optional generation",
                continue_on_error=True,
            ),
        ],
    )

    result = await executor._execute_workflow(
        workflow=workflow,
        request=make_request(),
        agent=make_agent(),
        system_prompt="Prompt",
    )

    assert result == {
        "generation-1": {
            "success": False,
            "error": "Optional step failed",
        }
    }


@pytest.mark.asyncio
async def test_dispatch_system_agent(
    monkeypatch,
):
    executor = AgentExecutor()

    expected_response = object()
    mocked_runner = AsyncMock(
        return_value=expected_response,
    )

    monkeypatch.setattr(
        executor,
        "_run_workflow_agent",
        mocked_runner,
    )

    request = make_request(
        agent_id="system-agent",
    )
    agent = make_agent(
        agent_id="system-agent",
        name="System Agent",
    )
    workflow = make_workflow()
    steps = []
    started_at = datetime.now(UTC)

    result = await executor._dispatch_system_agent(
        request=request,
        agent=agent,
        tool_plan=make_tool_plan_with(
            "system.status",
        ),
        workflow=workflow,
        run_id="run-system",
        started_at=started_at,
        timer_started=1.0,
        steps=steps,
    )

    assert result is expected_response

    mocked_runner.assert_awaited_once_with(
        request=request,
        agent=agent,
        workflow=workflow,
        system_prompt=executor_module.SYSTEM_AGENT_PROMPT,
        generation_title="Generate system assessment",
        result_title="System assessment completed",
        run_id="run-system",
        started_at=started_at,
        timer_started=1.0,
        steps=steps,
    )


@pytest.mark.asyncio
async def test_dispatch_devops_agent(
    monkeypatch,
):
    executor = AgentExecutor()

    expected_response = object()
    mocked_runner = AsyncMock(
        return_value=expected_response,
    )

    monkeypatch.setattr(
        executor,
        "_run_workflow_agent",
        mocked_runner,
    )

    request = make_request(
        agent_id="devops-agent",
    )
    agent = make_agent(
        agent_id="devops-agent",
        name="DevOps Agent",
    )
    workflow = make_workflow()
    steps = []
    started_at = datetime.now(UTC)

    result = await executor._dispatch_devops_agent(
        request=request,
        agent=agent,
        tool_plan=make_tool_plan(),
        workflow=workflow,
        run_id="run-devops",
        started_at=started_at,
        timer_started=2.0,
        steps=steps,
    )

    assert result is expected_response

    mocked_runner.assert_awaited_once_with(
        request=request,
        agent=agent,
        workflow=workflow,
        system_prompt=executor_module.DEVOPS_AGENT_PROMPT,
        generation_title="Generate DevOps response",
        result_title="DevOps response completed",
        run_id="run-devops",
        started_at=started_at,
        timer_started=2.0,
        steps=steps,
    )


@pytest.mark.asyncio
async def test_dispatch_knowledge_agent_requires_knowledge_ask():
    executor = AgentExecutor()

    with pytest.raises(
        ValueError,
        match="Knowledge Agent requires knowledge.ask",
    ):
        await executor._dispatch_knowledge_agent(
            request=make_request(
                agent_id="knowledge-agent",
            ),
            agent=make_agent(
                agent_id="knowledge-agent",
                name="Knowledge Agent",
            ),
            tool_plan=make_tool_plan(),
            workflow=make_workflow(),
            run_id="run-knowledge",
            started_at=datetime.now(UTC),
            timer_started=1.0,
            steps=[],
        )


@pytest.mark.asyncio
async def test_dispatch_knowledge_agent(
    monkeypatch,
):
    executor = AgentExecutor()

    expected_response = object()
    mocked_runner = AsyncMock(
        return_value=expected_response,
    )

    monkeypatch.setattr(
        executor,
        "_run_workflow_agent",
        mocked_runner,
    )

    request = make_request(
        agent_id="knowledge-agent",
    )
    agent = make_agent(
        agent_id="knowledge-agent",
        name="Knowledge Agent",
    )
    workflow = Workflow(
        reason="Knowledge workflow",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Ask knowledge",
                tool_id="knowledge.ask",
            ),
        ],
    )
    steps = []
    started_at = datetime.now(UTC)

    result = await executor._dispatch_knowledge_agent(
        request=request,
        agent=agent,
        tool_plan=make_tool_plan_with(
            "knowledge.ask",
        ),
        workflow=workflow,
        run_id="run-knowledge",
        started_at=started_at,
        timer_started=3.0,
        steps=steps,
    )

    assert result is expected_response

    mocked_runner.assert_awaited_once_with(
        request=request,
        agent=agent,
        workflow=workflow,
        system_prompt="",
        generation_title="Generate knowledge answer",
        result_title="Knowledge answer completed",
        run_id="run-knowledge",
        started_at=started_at,
        timer_started=3.0,
        steps=steps,
    )


@pytest.mark.asyncio
async def test_dispatch_research_agent_requires_search():
    executor = AgentExecutor()

    with pytest.raises(
        ValueError,
        match="Research Agent requires knowledge.search",
    ):
        await executor._dispatch_research_agent(
            request=make_request(
                agent_id="research-agent",
            ),
            agent=make_agent(
                agent_id="research-agent",
                name="Research Agent",
            ),
            tool_plan=make_tool_plan(),
            workflow=make_workflow(),
            run_id="run-research",
            started_at=datetime.now(UTC),
            timer_started=1.0,
            steps=[],
        )


@pytest.mark.asyncio
async def test_dispatch_research_agent(
    monkeypatch,
):
    executor = AgentExecutor()

    expected_response = object()
    mocked_runner = AsyncMock(
        return_value=expected_response,
    )

    monkeypatch.setattr(
        executor,
        "_run_workflow_agent",
        mocked_runner,
    )

    request = make_request(
        agent_id="research-agent",
    )
    agent = make_agent(
        agent_id="research-agent",
        name="Research Agent",
    )
    workflow = make_workflow()
    steps = []
    started_at = datetime.now(UTC)

    result = await executor._dispatch_research_agent(
        request=request,
        agent=agent,
        tool_plan=make_tool_plan_with(
            "knowledge.search",
        ),
        workflow=workflow,
        run_id="run-research",
        started_at=started_at,
        timer_started=4.0,
        steps=steps,
    )

    assert result is expected_response

    mocked_runner.assert_awaited_once_with(
        request=request,
        agent=agent,
        workflow=workflow,
        system_prompt=executor_module.RESEARCH_AGENT_PROMPT,
        generation_title="Synthesise research findings",
        result_title="Research summary completed",
        run_id="run-research",
        started_at=started_at,
        timer_started=4.0,
        steps=steps,
    )


@pytest.mark.asyncio
async def test_dispatch_prompt_agent_requires_configured_prompt(
    monkeypatch,
):
    executor = AgentExecutor()

    monkeypatch.setattr(
        executor_module,
        "GENERIC_AGENT_PROMPTS",
        {},
    )

    with pytest.raises(
        ValueError,
        match="No prompt is configured for custom-agent",
    ):
        await executor._dispatch_prompt_agent(
            request=make_request(
                agent_id="custom-agent",
            ),
            agent=make_agent(
                agent_id="custom-agent",
                name="Custom Agent",
            ),
            tool_plan=make_tool_plan(),
            workflow=make_workflow(),
            run_id="run-custom",
            started_at=datetime.now(UTC),
            timer_started=1.0,
            steps=[],
        )


@pytest.mark.asyncio
async def test_dispatch_prompt_agent(
    monkeypatch,
):
    executor = AgentExecutor()

    expected_response = object()
    mocked_runner = AsyncMock(
        return_value=expected_response,
    )

    monkeypatch.setattr(
        executor,
        "_run_workflow_agent",
        mocked_runner,
    )

    monkeypatch.setattr(
        executor_module,
        "GENERIC_AGENT_PROMPTS",
        {
            "coding-agent": "Coding system prompt",
        },
    )

    request = make_request(
        agent_id="coding-agent",
    )
    agent = make_agent(
        agent_id="coding-agent",
        name="Coding Agent",
    )
    workflow = make_workflow()
    steps = []
    started_at = datetime.now(UTC)

    result = await executor._dispatch_prompt_agent(
        request=request,
        agent=agent,
        tool_plan=make_tool_plan(),
        workflow=workflow,
        run_id="run-coding",
        started_at=started_at,
        timer_started=5.0,
        steps=steps,
    )

    assert result is expected_response

    mocked_runner.assert_awaited_once_with(
        request=request,
        agent=agent,
        workflow=workflow,
        system_prompt="Coding system prompt",
        generation_title="Generate Coding Agent response",
        result_title="Coding Agent response completed",
        run_id="run-coding",
        started_at=started_at,
        timer_started=5.0,
        steps=steps,
    )


@pytest.mark.asyncio
async def test_run_workflow_agent_generation_success(
    monkeypatch,
):
    executor = AgentExecutor()

    chat_response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
    )

    monkeypatch.setattr(
        executor,
        "_execute_workflow",
        AsyncMock(
            return_value={
                "generation-1": {
                    "success": True,
                    "answer": "Generated answer",
                    "provider": "ollama",
                    "model": "llama3",
                    "chat_response": chat_response,
                }
            }
        ),
    )

    request = make_request()
    agent = make_agent()
    workflow = make_workflow()
    steps = []
    started_at = datetime.now(UTC)

    result = await executor._run_workflow_agent(
        request=request,
        agent=agent,
        workflow=workflow,
        system_prompt="Coding prompt",
        generation_title="Generate coding answer",
        result_title="Coding answer completed",
        run_id="run-generation",
        started_at=started_at,
        timer_started=1.0,
        steps=steps,
    )

    assert result.status == "completed"
    assert result.answer == "Generated answer"
    assert result.run_id == "run-generation"
    assert result.agent_id == "coding-agent"
    assert result.sources == []

    assert len(result.steps) == 2

    generation_step = result.steps[0]
    result_step = result.steps[1]

    assert generation_step.type == "generation"
    assert generation_step.title == "Generate coding answer"
    assert generation_step.success is True
    assert generation_step.output == {
        "provider": "ollama",
        "model": "llama3",
    }

    assert result_step.type == "result"
    assert result_step.title == "Coding answer completed"
    assert result_step.output == {
        "answer": "Generated answer",
    }

    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 20
    assert result.usage.total_tokens == 30


@pytest.mark.asyncio
async def test_run_workflow_agent_tool_and_generation_success(
    monkeypatch,
):
    executor = AgentExecutor()

    chat_response = SimpleNamespace(
        usage=None,
    )

    workflow = Workflow(
        reason="Tool and generation",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Collect system status",
                tool_id="system.status",
                input={
                    "detail": True,
                },
            ),
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
                depends_on=["tool-1"],
            ),
        ],
    )

    monkeypatch.setattr(
        executor,
        "_execute_workflow",
        AsyncMock(
            return_value={
                "tool-1": {
                    "tool_id": "system.status",
                    "success": True,
                    "output": {
                        "cpu": 35,
                    },
                    "error": None,
                },
                "generation-1": {
                    "success": True,
                    "answer": "System is healthy",
                    "provider": "ollama",
                    "model": "llama3",
                    "chat_response": chat_response,
                },
            }
        ),
    )

    result = await executor._run_workflow_agent(
        request=make_request(
            agent_id="system-agent",
        ),
        agent=make_agent(
            agent_id="system-agent",
            name="System Agent",
        ),
        workflow=workflow,
        system_prompt="System prompt",
        generation_title="Generate system assessment",
        result_title="System assessment completed",
        run_id="run-system",
        started_at=datetime.now(UTC),
        timer_started=1.0,
        steps=[],
    )

    assert result.status == "completed"
    assert result.answer == "System is healthy"
    assert len(result.steps) == 3

    tool_step = result.steps[0]

    assert tool_step.type == "tool"
    assert tool_step.tool_id == "system.status"
    assert tool_step.input == {
        "detail": True,
    }
    assert tool_step.output == {
        "cpu": 35,
    }


@pytest.mark.asyncio
async def test_run_workflow_agent_terminal_knowledge_success(
    monkeypatch,
):
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Terminal knowledge workflow",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Ask indexed knowledge",
                tool_id="knowledge.ask",
                input={
                    "question": "What is Docker?",
                },
            ),
        ],
    )

    monkeypatch.setattr(
        executor,
        "_execute_workflow",
        AsyncMock(
            return_value={
                "tool-1": {
                    "tool_id": "knowledge.ask",
                    "success": True,
                    "output": {
                        "answer": "Docker runs containers.",
                        "sources": [
                            {
                                "document_id": "doc-1",
                                "title": "Docker Guide",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 12,
                            "completion_tokens": 8,
                            "total_tokens": 20,
                        },
                    },
                    "error": None,
                }
            }
        ),
    )

    result = await executor._run_workflow_agent(
        request=make_request(
            agent_id="knowledge-agent",
        ),
        agent=make_agent(
            agent_id="knowledge-agent",
            name="Knowledge Agent",
        ),
        workflow=workflow,
        system_prompt="",
        generation_title="Generate knowledge answer",
        result_title="Knowledge answer completed",
        run_id="run-knowledge",
        started_at=datetime.now(UTC),
        timer_started=1.0,
        steps=[],
    )

    assert result.status == "completed"
    assert result.answer == "Docker runs containers."

    assert result.sources == [
        {
            "document_id": "doc-1",
            "title": "Docker Guide",
        }
    ]

    assert result.usage.prompt_tokens == 12
    assert result.usage.completion_tokens == 8
    assert result.usage.total_tokens == 20

    assert len(result.steps) == 2
    assert result.steps[0].type == "tool"
    assert result.steps[1].type == "result"

    assert result.steps[1].output == {
        "answer": "Docker runs containers.",
        "source_count": 1,
    }


@pytest.mark.asyncio
async def test_run_workflow_agent_requires_generation_or_terminal_result(
    monkeypatch,
):
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Non-terminal tool workflow",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="System status",
                tool_id="system.status",
            ),
        ],
    )

    monkeypatch.setattr(
        executor,
        "_execute_workflow",
        AsyncMock(
            return_value={
                "tool-1": {
                    "tool_id": "system.status",
                    "success": True,
                    "output": {
                        "cpu": 25,
                    },
                    "error": None,
                }
            }
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=("Workflow completed without a generation or terminal result"),
    ):
        await executor._run_workflow_agent(
            request=make_request(
                agent_id="system-agent",
            ),
            agent=make_agent(
                agent_id="system-agent",
                name="System Agent",
            ),
            workflow=workflow,
            system_prompt="System prompt",
            generation_title="Generate",
            result_title="Completed",
            run_id="run-no-result",
            started_at=datetime.now(UTC),
            timer_started=1.0,
            steps=[],
        )


@pytest.mark.asyncio
async def test_run_workflow_agent_rejects_empty_terminal_answer(
    monkeypatch,
):
    executor = AgentExecutor()

    workflow = Workflow(
        reason="Empty terminal answer",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Ask knowledge",
                tool_id="knowledge.ask",
            ),
        ],
    )

    monkeypatch.setattr(
        executor,
        "_execute_workflow",
        AsyncMock(
            return_value={
                "tool-1": {
                    "tool_id": "knowledge.ask",
                    "success": True,
                    "output": {
                        "answer": "   ",
                    },
                    "error": None,
                }
            }
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Terminal workflow returned no answer",
    ):
        await executor._run_workflow_agent(
            request=make_request(
                agent_id="knowledge-agent",
            ),
            agent=make_agent(
                agent_id="knowledge-agent",
                name="Knowledge Agent",
            ),
            workflow=workflow,
            system_prompt="",
            generation_title="Generate",
            result_title="Completed",
            run_id="run-empty-terminal",
            started_at=datetime.now(UTC),
            timer_started=1.0,
            steps=[],
        )


@pytest.mark.asyncio
async def test_run_workflow_agent_rejects_empty_generation_answer(
    monkeypatch,
):
    executor = AgentExecutor()

    monkeypatch.setattr(
        executor,
        "_execute_workflow",
        AsyncMock(
            return_value={
                "generation-1": {
                    "success": True,
                    "answer": "   ",
                    "provider": "ollama",
                    "model": "llama3",
                    "chat_response": object(),
                }
            }
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Workflow generation returned no answer",
    ):
        await executor._run_workflow_agent(
            request=make_request(),
            agent=make_agent(),
            workflow=make_workflow(),
            system_prompt="Prompt",
            generation_title="Generate",
            result_title="Completed",
            run_id="run-empty-generation",
            started_at=datetime.now(UTC),
            timer_started=1.0,
            steps=[],
        )


@pytest.mark.asyncio
async def test_run_workflow_agent_requires_chat_metadata(
    monkeypatch,
):
    executor = AgentExecutor()

    monkeypatch.setattr(
        executor,
        "_execute_workflow",
        AsyncMock(
            return_value={
                "generation-1": {
                    "success": True,
                    "answer": "Valid answer",
                    "provider": "ollama",
                    "model": "llama3",
                    "chat_response": None,
                }
            }
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="chat response metadata",
    ):
        await executor._run_workflow_agent(
            request=make_request(),
            agent=make_agent(),
            workflow=make_workflow(),
            system_prompt="Prompt",
            generation_title="Generate",
            result_title="Completed",
            run_id="run-no-chat",
            started_at=datetime.now(UTC),
            timer_started=1.0,
            steps=[],
        )


@pytest.mark.asyncio
async def test_chat_builds_gateway_request(
    monkeypatch,
):
    executor = AgentExecutor()

    expected_response = object()

    mocked_chat = AsyncMock(
        return_value=expected_response,
    )

    monkeypatch.setattr(
        executor_module.gateway_service,
        "chat",
        mocked_chat,
    )

    request = make_request(
        provider="ollama",
        model="test-model",
        temperature=0.6,
        max_tokens=450,
    )

    result = await executor._chat(
        request=request,
        system_prompt="You are a coding assistant.",
        user_content="Write a Python function.",
    )

    assert result is expected_response

    mocked_chat.assert_awaited_once()

    gateway_request = mocked_chat.await_args.args[0]

    assert gateway_request.provider == "ollama"
    assert gateway_request.model == "test-model"
    assert gateway_request.temperature == 0.6
    assert gateway_request.max_tokens == 450
    assert gateway_request.stream is False

    assert len(gateway_request.messages) == 2

    assert gateway_request.messages[0].role == "system"
    assert gateway_request.messages[0].content == "You are a coding assistant."

    assert gateway_request.messages[1].role == "user"
    assert gateway_request.messages[1].content == "Write a Python function."


@pytest.mark.asyncio
async def test_run_rejects_non_positive_max_steps_after_validation_bypass():
    executor = AgentExecutor()

    request = AgentRunRequest.model_construct(
        mode="manual",
        agent_id="coding-agent",
        objective="Write hello world",
        provider="ollama",
        model="llama3",
        temperature=0.2,
        max_tokens=200,
        max_steps=0,
        retrieval_limit=5,
        score_threshold=0.4,
        document_id=None,
    )

    with pytest.raises(
        ValueError,
        match="At least one agent step is required",
    ):
        await executor.run(request)
