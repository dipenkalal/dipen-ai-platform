import pytest
from agents.router import agent_router
from agents.schemas import AgentRunRequest


@pytest.mark.parametrize(
    ("objective", "expected_agent"),
    [
        (
            "Check CPU memory and disk resource usage",
            "system-agent",
        ),
        (
            "Answer this question from the uploaded PDF",
            "knowledge-agent",
        ),
        (
            "Research and compare the available evidence",
            "research-agent",
        ),
        (
            "Deploy this Docker application to Kubernetes",
            "devops-agent",
        ),
        (
            "Debug this Python FastAPI error",
            "coding-agent",
        ),
        (
            "Write a README and technical user guide",
            "documentation-agent",
        ),
    ],
)
def test_smart_router_selects_expected_agent(
    objective: str,
    expected_agent: str,
):
    request = AgentRunRequest(
        mode="smart",
        objective=objective,
    )

    route = agent_router.route(request)

    assert route.agent_id == expected_agent
    assert route.model is not None
    assert 0.0 <= route.confidence <= 1.0
    assert route.reason


def test_smart_router_defaults_to_coding_agent():
    request = AgentRunRequest(
        mode="smart",
        objective="Please help me complete this task",
    )

    route = agent_router.route(request)

    assert route.agent_id == "coding-agent"
    assert route.confidence == 0.50
    assert "No specialised routing keywords" in route.reason


def test_smart_router_defaults_to_knowledge_agent_with_document():
    request = AgentRunRequest(
        mode="smart",
        objective="Please help me understand this",
        document_id="document-123",
    )

    route = agent_router.route(request)

    assert route.agent_id == "knowledge-agent"
    assert route.confidence == 0.50
    assert "document was supplied" in route.reason


def test_smart_router_preserves_requested_model():
    request = AgentRunRequest(
        mode="smart",
        objective="Debug this Python function",
        model="custom-model",
    )

    route = agent_router.route(request)

    assert route.agent_id == "coding-agent"
    assert route.model == "custom-model"


def test_smart_router_uses_priority_to_resolve_equal_scores():
    request = AgentRunRequest(
        mode="smart",
        objective="Check cpu and python",
    )

    route = agent_router.route(request)

    assert route.agent_id == "system-agent"
