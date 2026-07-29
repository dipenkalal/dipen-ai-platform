from datetime import UTC, datetime
from time import perf_counter
from types import SimpleNamespace

import pytest
from agents.executor import AgentExecutor


def make_request():
    return SimpleNamespace(
        agent_id="coding-agent",
        objective="Test objective",
    )


def test_completed_response_populates_usage():
    executor = AgentExecutor()

    started = datetime.now(UTC)

    usage = SimpleNamespace(
        prompt_tokens=12,
        completion_tokens=8,
        total_tokens=20,
    )

    chat = SimpleNamespace(usage=usage)

    response = executor._completed_response(
        request=make_request(),
        run_id="run-1",
        answer="done",
        steps=[],
        sources=[],
        chat_response=chat,
        started_at=started,
        completed_at=started,
        timer_started=perf_counter(),
    )

    assert response.status == "completed"
    assert response.answer == "done"
    assert response.usage.total_tokens == 20


def test_failed_response():
    executor = AgentExecutor()

    now = datetime.now(UTC)

    response = executor._failed_response(
        request=make_request(),
        run_id="run-1",
        answer="failed",
        steps=[],
        started_at=now,
        completed_at=now,
        timer_started=perf_counter(),
    )

    assert response.status == "failed"
    assert response.answer == "failed"


def test_required_agent_id():
    executor = AgentExecutor()

    request = SimpleNamespace(agent_id="coding-agent")

    assert executor._required_agent_id(request) == "coding-agent"


def test_required_agent_id_missing():
    executor = AgentExecutor()

    request = SimpleNamespace(agent_id=None)

    with pytest.raises(ValueError):
        executor._required_agent_id(request)


def test_as_dict_returns_input_dict():
    executor = AgentExecutor()

    data = {"hello": "world"}

    assert executor._as_dict(data) == data


def test_as_dict_model_dump():
    executor = AgentExecutor()

    class FakeModel:
        def model_dump(self):
            return {"x": 123}

    assert executor._as_dict(FakeModel()) == {"x": 123}


def test_as_list_of_dicts():
    executor = AgentExecutor()

    class FakeModel:
        def model_dump(self):
            return {"value": 5}

    result = executor._as_list_of_dicts(
        [
            {"a": 1},
            FakeModel(),
        ]
    )

    assert result == [
        {"a": 1},
        {"value": 5},
    ]
