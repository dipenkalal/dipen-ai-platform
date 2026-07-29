from types import SimpleNamespace
from typing import Any

import pytest
from agents.executor import AgentExecutor
from agents.schemas import AgentRunRequest


@pytest.mark.asyncio
async def test_coding_agent_end_to_end_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = AgentExecutor()

    captured: dict[str, Any] = {}

    async def fake_chat(
        request: AgentRunRequest,
        system_prompt: str,
        user_content: str,
    ) -> SimpleNamespace:
        captured["request"] = request
        captured["system_prompt"] = system_prompt
        captured["user_content"] = user_content

        return SimpleNamespace(
            message=SimpleNamespace(
                content="Here is the generated Python solution.",
            ),
            provider="ollama",
            model="test-model",
            usage=SimpleNamespace(
                prompt_tokens=20,
                completion_tokens=10,
                total_tokens=30,
            ),
        )

    monkeypatch.setattr(
        executor,
        "_chat",
        fake_chat,
    )

    request = AgentRunRequest(
        mode="manual",
        agent_id="coding-agent",
        objective="Write a Python hello world program",
        provider="ollama",
        model="test-model",
        temperature=0.0,
        max_tokens=256,
        max_steps=4,
    )

    response = await executor.run(request)

    assert response.status == "completed"
    assert response.agent_id == "coding-agent"
    assert response.objective == ("Write a Python hello world program")
    assert response.answer == ("Here is the generated Python solution.")

    assert response.run_id
    assert response.started_at
    assert response.completed_at

    assert response.usage.prompt_tokens == 20
    assert response.usage.completion_tokens == 10
    assert response.usage.total_tokens == 30
    assert response.usage.latency_ms >= 0

    assert response.sources == []

    assert len(response.steps) == 3

    planning_step = response.steps[0]
    generation_step = response.steps[1]
    result_step = response.steps[2]

    assert planning_step.type == "planning"
    assert planning_step.success is True
    assert planning_step.output["selected_agent"] == ("coding-agent")

    assert generation_step.type == "generation"
    assert generation_step.success is True
    assert generation_step.output["provider"] == "ollama"
    assert generation_step.output["model"] == "test-model"

    assert result_step.type == "result"
    assert result_step.success is True
    assert result_step.output["answer"] == (
        "Here is the generated Python solution."
    )

    assert captured["request"] is request
    assert "Coding Agent" in captured["system_prompt"]
    assert captured["user_content"] == ("Write a Python hello world program")
