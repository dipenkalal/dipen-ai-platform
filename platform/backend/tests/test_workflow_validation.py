import pytest
from agents.executor import AgentExecutor
from agents.schemas import (
    AgentDefinition,
    AgentRunRequest,
    Workflow,
    WorkflowStep,
)


def make_executor() -> AgentExecutor:
    return AgentExecutor()


def make_request() -> AgentRunRequest:
    return AgentRunRequest(
        mode="manual",
        agent_id="test-agent",
        objective="Test objective",
        provider="ollama",
        model="test-model",
        temperature=0.3,
        max_tokens=256,
        retrieval_limit=4,
        score_threshold=0.5,
        document_id=None,
    )


def make_agent() -> AgentDefinition:
    return AgentDefinition(
        id="test-agent",
        name="Test Agent",
        description="Test",
        tools=[],
    )


def test_valid_workflow_passes_validation() -> None:
    workflow = Workflow(
        reason="test",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Tool",
                tool_id="knowledge.search",
            ),
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate",
                depends_on=["tool-1"],
            ),
        ],
    )

    make_executor()._validate_workflow(workflow)


def test_empty_workflow_is_rejected() -> None:
    workflow = Workflow(
        reason="test",
        steps=[],
    )

    with pytest.raises(
        ValueError,
        match="at least one step",
    ):
        make_executor()._validate_workflow(workflow)


def test_duplicate_step_ids_are_rejected() -> None:
    workflow = Workflow(
        reason="test",
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
        make_executor()._validate_workflow(workflow)


def test_missing_dependency_is_rejected() -> None:
    workflow = Workflow(
        reason="test",
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
        make_executor()._validate_workflow(workflow)


def test_self_dependency_is_rejected() -> None:
    workflow = Workflow(
        reason="test",
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
        make_executor()._validate_workflow(workflow)


def test_dependency_cycle_is_rejected() -> None:
    workflow = Workflow(
        reason="test",
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
        make_executor()._validate_workflow(workflow)


def test_tool_step_without_tool_id_is_rejected() -> None:
    workflow = Workflow(
        reason="test",
        steps=[
            WorkflowStep(
                id="tool-1",
                kind="tool",
                name="Tool",
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="missing tool_id",
    ):
        make_executor()._validate_workflow(workflow)


@pytest.mark.asyncio
async def test_execute_workflow_validates_before_execution() -> None:
    executor = make_executor()

    workflow = Workflow(
        reason="test",
        steps=[],
    )

    with pytest.raises(
        ValueError,
        match="at least one step",
    ):
        await executor._execute_workflow(
            workflow=workflow,
            request=make_request(),
            agent=make_agent(),
            system_prompt="",
        )
