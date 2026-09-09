import asyncio
from datetime import (
    datetime,
    timezone,
)

from agents.schemas import (
    AgentRunResponse,
    AgentUsage,
)
from gateway import openai_facade


class FakeAgentService:
    def __init__(self) -> None:
        self.requests = []

    async def run(
        self,
        request,
    ) -> AgentRunResponse:
        self.requests.append(
            request
        )

        now = datetime.now(
            timezone.utc
        )

        return AgentRunResponse(
            run_id="run-test",
            agent_id="devops-agent",
            objective=request.objective,
            status="completed",
            answer=(
                "Grounded DAP answer "
                "with AWS citation."
            ),
            steps=[],
            sources=[
                {
                    "url": (
                        "https://docs.aws.amazon.com/"
                    )
                }
            ],
            usage=AgentUsage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                latency_ms=1.0,
            ),
            started_at=now,
            completed_at=now,
        )


def test_models_exposes_only_dap_auto() -> None:
    async def run() -> None:
        result = (
            await openai_facade.openai_models()
        )

        assert result["object"] == "list"
        assert len(result["data"]) == 1
        assert (
            result["data"][0]["id"]
            == "dap-auto"
        )

    asyncio.run(run())


def test_chat_maps_openai_to_smart_dap(
    monkeypatch,
) -> None:
    fake = FakeAgentService()

    monkeypatch.setattr(
        openai_facade,
        "agent_service",
        fake,
    )

    request = (
        openai_facade
        .OpenAIChatCompletionRequest(
            model="dap-auto",
            messages=[
                openai_facade.OpenAIMessage(
                    role="system",
                    content=(
                        "Client system prompt"
                    ),
                ),
                openai_facade.OpenAIMessage(
                    role="user",
                    content=(
                        "Explain AWS VPC."
                    ),
                ),
            ],
            temperature=0.3,
            max_tokens=500,
        )
    )

    async def run() -> None:
        result = await (
            openai_facade
            .openai_chat_completions(
                request
            )
        )

        assert result[
            "object"
        ] == "chat.completion"

        assert result[
            "model"
        ] == "dap-auto"

        assert result[
            "choices"
        ][0]["message"]["content"].startswith(
            "Grounded DAP answer"
        )

    asyncio.run(run())

    assert len(fake.requests) == 1

    dap_request = fake.requests[0]

    assert dap_request.mode == "smart"
    assert dap_request.provider == "ollama"

    assert (
        "Explain AWS VPC."
        in dap_request.objective
    )

    assert (
        "Client system prompt"
        not in dap_request.objective
    )


def test_recent_context_is_preserved(
    monkeypatch,
) -> None:
    fake = FakeAgentService()

    monkeypatch.setattr(
        openai_facade,
        "agent_service",
        fake,
    )

    request = (
        openai_facade
        .OpenAIChatCompletionRequest(
            messages=[
                openai_facade.OpenAIMessage(
                    role="user",
                    content=(
                        "Explain AWS NAT Gateway."
                    ),
                ),
                openai_facade.OpenAIMessage(
                    role="assistant",
                    content=(
                        "A NAT Gateway..."
                    ),
                ),
                openai_facade.OpenAIMessage(
                    role="user",
                    content=(
                        "What about high availability?"
                    ),
                ),
            ],
        )
    )

    async def run() -> None:
        await (
            openai_facade
            .openai_chat_completions(
                request
            )
        )

    asyncio.run(run())

    objective = (
        fake.requests[0].objective
    )

    assert "AWS NAT Gateway" in objective
    assert (
        "What about high availability?"
        in objective
    )


def test_content_parts_are_supported() -> None:
    message = (
        openai_facade.OpenAIMessage(
            role="user",
            content=[
                {
                    "type": "text",
                    "text": "Hello",
                },
                {
                    "type": "text",
                    "text": "DAP",
                },
            ],
        )
    )

    assert (
        openai_facade._content_text(
            message.content
        )
        == "Hello\nDAP"
    )


def test_streaming_returns_openai_sse(
    monkeypatch,
) -> None:
    fake = FakeAgentService()

    monkeypatch.setattr(
        openai_facade,
        "agent_service",
        fake,
    )

    request = (
        openai_facade
        .OpenAIChatCompletionRequest(
            model="dap-auto",
            messages=[
                openai_facade.OpenAIMessage(
                    role="user",
                    content="Hello",
                )
            ],
            stream=True,
        )
    )

    async def run() -> None:
        response = await (
            openai_facade
            .openai_chat_completions(
                request
            )
        )

        assert (
            response.media_type
            == "text/event-stream"
        )

        pieces = []

        async for piece in (
            response.body_iterator
        ):
            if isinstance(
                piece,
                bytes,
            ):
                piece = piece.decode(
                    "utf-8"
                )

            pieces.append(
                str(piece)
            )

        body = "".join(
            pieces
        )

        assert (
            "chat.completion.chunk"
            in body
        )

        assert (
            "Grounded DAP answer"
            in body
        )

        assert (
            "data: [DONE]"
            in body
        )

    asyncio.run(run())

    assert len(fake.requests) == 1
