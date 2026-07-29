from agents.planner import AgentToolPlanner
from agents.schemas import AgentDefinition, AgentRunRequest


def make_request(objective="Test objective", **kwargs):
    data = {
        "mode": "manual",
        "agent_id": "test-agent",
        "objective": objective,
        "provider": "ollama",
        "model": "test-model",
        "temperature": 0.2,
        "max_tokens": 128,
        "retrieval_limit": 5,
        "score_threshold": 0.5,
        "document_id": None,
    }
    data.update(kwargs)
    return AgentRunRequest(**data)


def make_agent(agent_id, tools=None):
    return AgentDefinition(
        id=agent_id,
        name=agent_id,
        description="test",
        tools=tools or [],
    )


def test_plan_unknown_agent_returns_no_tools():
    planner = AgentToolPlanner()

    plan = planner.plan(
        make_request(),
        make_agent("unknown-agent"),
    )

    assert plan.tool_ids == ()
    assert plan.requires_tools is False


def test_devops_without_matching_phrase():
    planner = AgentToolPlanner()

    plan = planner.plan(
        make_request(
            objective="Write a Dockerfile",
            agent_id="devops-agent",
        ),
        make_agent("devops-agent", ["system.status"]),
    )

    assert plan.tool_ids == ()
    assert "does not require live host measurements" in plan.reason


def test_devops_matching_phrase_with_tool():
    planner = AgentToolPlanner()

    plan = planner.plan(
        make_request(
            objective="Check server health immediately",
            agent_id="devops-agent",
        ),
        make_agent("devops-agent", ["system.status"]),
    )

    assert plan.tool_ids == ("system.status",)
    assert "matched" in plan.reason


def test_knowledge_without_document_id():
    planner = AgentToolPlanner()

    plan = planner.plan(
        make_request(
            objective="Explain the knowledge base",
            agent_id="knowledge-agent",
        ),
        make_agent("knowledge-agent", ["knowledge.ask"]),
    )

    assert plan.tool_ids == ("knowledge.ask",)


def test_research_without_matches():
    planner = AgentToolPlanner()

    plan = planner.plan(
        make_request(
            objective="Summarize AI trends",
            agent_id="research-agent",
        ),
        make_agent("research-agent", ["knowledge.search"]),
    )

    assert plan.tool_ids == ("knowledge.search",)
    assert "requires indexed evidence" in plan.reason


def test_tool_step_name_default():
    planner = AgentToolPlanner()

    assert planner._tool_step_name("custom.tool") == "Execute custom.tool"


def test_tool_input_unknown_tool():
    planner = AgentToolPlanner()

    assert (
        planner._tool_input(
            "custom.tool",
            make_request(),
        )
        == {}
    )


def test_find_matches_limit():
    planner = AgentToolPlanner()

    phrases = tuple(f"word{i}" for i in range(10))
    objective = " ".join(phrases)

    matches = planner._find_matches(
        objective,
        phrases,
    )

    assert len(matches) == 5


def test_normalise():
    planner = AgentToolPlanner()

    assert planner._normalise("  HELLO    WORLD  ") == "hello world"


def test_research_with_matching_knowledge_phrase():
    planner = AgentToolPlanner()

    plan = planner.plan(
        make_request(
            objective="Search the uploaded documents",
            agent_id="research-agent",
        ),
        make_agent(
            "research-agent",
            ["knowledge.search"],
        ),
    )

    assert plan.tool_ids == ("knowledge.search",)
    assert "Research retrieval is required because" in plan.reason
    assert "uploaded document" in plan.reason
