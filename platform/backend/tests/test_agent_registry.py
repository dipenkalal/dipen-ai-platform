import pytest
from agents.registry import AgentRegistry, agent_registry
from agents.schemas import AgentDefinition


def make_agent(
    agent_id: str = "test-agent",
    *,
    enabled: bool = True,
) -> AgentDefinition:
    return AgentDefinition(
        id=agent_id,
        name="Test Agent",
        description="Agent used for registry tests",
        category="general",
        icon="test-icon",
        accent="blue",
        tools=[],
        capabilities=["Testing"],
        recommended_model="test-model",
        safe=True,
        enabled=enabled,
    )


def test_registry_starts_empty():
    registry = AgentRegistry()

    assert registry.list() == []


def test_register_and_get_agent():
    registry = AgentRegistry()
    agent = make_agent()

    registry.register(agent)

    assert registry.get("test-agent") is agent


def test_register_duplicate_agent_raises_value_error():
    registry = AgentRegistry()
    agent = make_agent()

    registry.register(agent)

    with pytest.raises(
        ValueError,
        match="Agent already registered: test-agent",
    ):
        registry.register(agent)


def test_get_unknown_agent_raises_key_error():
    registry = AgentRegistry()

    with pytest.raises(
        KeyError,
        match="Unknown agent: missing-agent",
    ):
        registry.get("missing-agent")


def test_get_disabled_agent_raises_value_error():
    registry = AgentRegistry()
    agent = make_agent(
        agent_id="disabled-agent",
        enabled=False,
    )

    registry.register(agent)

    with pytest.raises(
        ValueError,
        match="Agent is disabled: disabled-agent",
    ):
        registry.get("disabled-agent")


def test_list_returns_all_registered_agents():
    registry = AgentRegistry()
    first = make_agent("first-agent")
    second = make_agent("second-agent")

    registry.register(first)
    registry.register(second)

    assert registry.list() == [first, second]


def test_global_registry_contains_expected_agents():
    agents = agent_registry.list()
    agent_ids = {agent.id for agent in agents}

    assert agent_ids == {
        "system-agent",
        "knowledge-agent",
        "research-agent",
        "devops-agent",
        "coding-agent",
        "documentation-agent",
        "sql-agent",
    }


def test_global_enabled_agent_can_be_retrieved():
    agent = agent_registry.get("system-agent")

    assert agent.id == "system-agent"
    assert agent.enabled is True


def test_global_disabled_agent_cannot_be_retrieved():
    with pytest.raises(
        ValueError,
        match="Agent is disabled: sql-agent",
    ):
        agent_registry.get("sql-agent")
