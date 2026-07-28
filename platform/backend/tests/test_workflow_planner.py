from agents.planner import AgentToolPlanner
from agents.schemas import (
    AgentDefinition,
    AgentRunRequest,
)


def make_request(
    objective: str = "Complete the task",
    **overrides,
) -> AgentRunRequest:
    data = {
        "mode": "manual",
        "agent_id": "test-agent",
        "objective": objective,
        "provider": "ollama",
        "model": "test-model",
        "temperature": 0.3,
        "max_tokens": 512,
        "retrieval_limit": 4,
        "score_threshold": 0.55,
        "document_id": None,
    }

    data.update(overrides)

    return AgentRunRequest(**data)


def make_agent(
    agent_id: str = "coding-agent",
    name: str = "Coding Agent",
    tools: list[str] | None = None,
) -> AgentDefinition:
    return AgentDefinition(
        id=agent_id,
        name=name,
        description="Test agent",
        tools=tools or [],
    )


def test_no_tool_workflow_contains_generation_step() -> None:
    planner = AgentToolPlanner()

    request = make_request(
        objective="Write a Python function",
        agent_id="coding-agent",
    )

    agent = make_agent(
        agent_id="coding-agent",
        name="Coding Agent",
    )

    workflow = planner.build_workflow(
        request=request,
        agent=agent,
    )

    assert len(workflow.steps) == 1

    step = workflow.steps[0]

    assert step.id == "generation-1"
    assert step.kind == "generation"
    assert step.name == "Generate final response"
    assert step.depends_on == []

    assert workflow.requires_tools is False
    assert workflow.tool_ids == ()


def test_system_agent_builds_tool_then_generation() -> None:
    planner = AgentToolPlanner()

    request = make_request(
        objective="Check the system status",
        agent_id="system-agent",
    )

    agent = make_agent(
        agent_id="system-agent",
        name="System Agent",
        tools=["system.status"],
    )

    workflow = planner.build_workflow(
        request=request,
        agent=agent,
    )

    assert [step.id for step in workflow.steps] == [
        "tool-1",
        "generation-1",
    ]

    tool_step = workflow.steps[0]
    generation_step = workflow.steps[1]

    assert tool_step.kind == "tool"
    assert tool_step.name == "Collect system status"
    assert tool_step.tool_id == "system.status"
    assert tool_step.input == {}
    assert tool_step.depends_on == []

    assert generation_step.kind == "generation"
    assert generation_step.depends_on == [
        "tool-1",
    ]

    assert workflow.requires_tools is True
    assert workflow.tool_ids == ("system.status",)


def test_research_workflow_maps_search_input() -> None:
    planner = AgentToolPlanner()

    request = make_request(
        objective="Analyse the indexed documents",
        agent_id="research-agent",
        document_id="document-123",
        retrieval_limit=7,
        score_threshold=0.65,
    )

    agent = make_agent(
        agent_id="research-agent",
        name="Research Agent",
        tools=["knowledge.search"],
    )

    workflow = planner.build_workflow(
        request=request,
        agent=agent,
    )

    assert [step.id for step in workflow.steps] == [
        "tool-1",
        "generation-1",
    ]

    tool_step = workflow.steps[0]

    assert tool_step.tool_id == "knowledge.search"
    assert tool_step.name == "Search indexed knowledge"
    assert tool_step.input == {
        "query": "Analyse the indexed documents",
        "document_id": "document-123",
        "limit": 7,
        "score_threshold": 0.65,
    }

    assert workflow.steps[1].depends_on == [
        "tool-1",
    ]


def test_knowledge_ask_is_terminal_workflow() -> None:
    planner = AgentToolPlanner()

    request = make_request(
        objective="Answer from the uploaded document",
        agent_id="knowledge-agent",
        document_id="document-456",
        retrieval_limit=6,
        score_threshold=0.5,
    )

    agent = make_agent(
        agent_id="knowledge-agent",
        name="Knowledge Agent",
        tools=["knowledge.ask"],
    )

    workflow = planner.build_workflow(
        request=request,
        agent=agent,
    )

    assert len(workflow.steps) == 1

    step = workflow.steps[0]

    assert step.id == "tool-1"
    assert step.kind == "tool"
    assert step.tool_id == "knowledge.ask"
    assert step.name == "Ask indexed knowledge"

    assert step.input == {
        "question": "Answer from the uploaded document",
        "model": "test-model",
        "provider": "ollama",
        "temperature": 0.3,
        "max_tokens": 512,
        "retrieval_limit": 6,
        "score_threshold": 0.5,
        "document_id": "document-456",
    }

    assert all(
        workflow_step.kind != "generation" for workflow_step in workflow.steps
    )


def test_unavailable_tool_is_not_added_to_workflow() -> None:
    planner = AgentToolPlanner()

    request = make_request(
        objective="Check server health",
        agent_id="devops-agent",
    )

    agent = make_agent(
        agent_id="devops-agent",
        name="DevOps Agent",
        tools=[],
    )

    workflow = planner.build_workflow(
        request=request,
        agent=agent,
    )

    assert len(workflow.steps) == 1
    assert workflow.steps[0].kind == "generation"
    assert workflow.requires_tools is False
    assert workflow.tool_ids == ()


def test_workflow_metadata_is_populated() -> None:
    planner = AgentToolPlanner()

    request = make_request(
        objective="Check system status",
        agent_id="system-agent",
    )

    agent = make_agent(
        agent_id="system-agent",
        name="System Agent",
        tools=["system.status"],
    )

    workflow = planner.build_workflow(
        request=request,
        agent=agent,
    )

    assert workflow.metadata == {
        "version": "0.12",
        "planner": "deterministic",
        "agent_id": "system-agent",
        "tool_ids": [
            "system.status",
        ],
    }


def test_planner_is_deterministic_for_same_input() -> None:
    planner = AgentToolPlanner()

    request = make_request(
        objective="Analyse the indexed documents",
        agent_id="research-agent",
        document_id="document-789",
    )

    agent = make_agent(
        agent_id="research-agent",
        name="Research Agent",
        tools=["knowledge.search"],
    )

    first = planner.build_workflow(
        request=request,
        agent=agent,
    )

    second = planner.build_workflow(
        request=request,
        agent=agent,
    )

    assert first.model_dump() == second.model_dump()
