import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from agents.registry import agent_registry
from agents.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStep,
    AgentUsage,
)
from gateway.schemas import (
    ChatMessage,
    ChatRequest,
)
from gateway.service import gateway_service
from tools.registry import tool_registry


SYSTEM_AGENT_PROMPT = """
You are the System Agent inside Dipen AI Platform.

You receive live system and Ollama status data.

Your job:
1. Summarize CPU, memory, disk, uptime, and Ollama health.
2. Clearly identify warnings or unhealthy conditions.
3. Do not invent measurements.
4. Do not suggest destructive commands.
5. Keep the response practical and concise.
""".strip()


class AgentExecutor:
    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        started_at = datetime.now(
            timezone.utc
        )
        timer_started = perf_counter()
        run_id = str(uuid4())
        steps: list[AgentStep] = []

        agent = agent_registry.get(
            request.agent_id
        )

        if request.max_steps < 1:
            raise ValueError(
                "At least one agent step is required."
            )

        planning_started = datetime.now(
            timezone.utc
        )

        steps.append(
            AgentStep(
                step_number=1,
                type="planning",
                title=(
                    f"Selected {agent.name}"
                ),
                success=True,
                input={
                    "objective": request.objective,
                    "available_tools": agent.tools,
                    "max_steps": request.max_steps,
                },
                output={
                    "selected_agent": agent.id,
                },
                started_at=planning_started,
                completed_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        if request.agent_id == "knowledge-agent":
            return await self._run_knowledge_agent(
                request=request,
                run_id=run_id,
                started_at=started_at,
                timer_started=timer_started,
                steps=steps,
            )

        if request.agent_id == "system-agent":
            return await self._run_system_agent(
                request=request,
                run_id=run_id,
                started_at=started_at,
                timer_started=timer_started,
                steps=steps,
            )

        raise ValueError(
            f"No executor is configured for "
            f"{request.agent_id}"
        )

    async def _run_knowledge_agent(
        self,
        request: AgentRunRequest,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        tool = tool_registry.get(
            "knowledge.ask"
        )

        tool_started = datetime.now(
            timezone.utc
        )

        arguments = {
            "question": request.objective,
            "model": request.model,
            "provider": request.provider,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "retrieval_limit": (
                request.retrieval_limit
            ),
            "score_threshold": (
                request.score_threshold
            ),
            "document_id": (
                request.document_id
            ),
        }

        result = await tool.execute(
            arguments
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="tool",
                title="Ask indexed knowledge",
                tool_id=tool.definition.id,
                success=result.success,
                input=arguments,
                output=result.output,
                error=result.error,
                started_at=tool_started,
                completed_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        completed_at = datetime.now(
            timezone.utc
        )

        if not result.success:
            return AgentRunResponse(
                run_id=run_id,
                agent_id=request.agent_id,
                objective=request.objective,
                status="failed",
                answer=(
                    result.error
                    or "Knowledge tool failed."
                ),
                steps=steps,
                sources=[],
                usage=AgentUsage(
                    latency_ms=round(
                        (
                            perf_counter()
                            - timer_started
                        )
                        * 1000,
                        2,
                    )
                ),
                started_at=started_at,
                completed_at=completed_at,
            )

        output = result.output or {}
        usage_data = output.get(
            "usage",
            {},
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="result",
                title="Knowledge answer completed",
                success=True,
                output={
                    "answer": output.get(
                        "answer",
                        "",
                    ),
                    "source_count": len(
                        output.get(
                            "sources",
                            [],
                        )
                    ),
                },
                started_at=completed_at,
                completed_at=completed_at,
            )
        )

        return AgentRunResponse(
            run_id=run_id,
            agent_id=request.agent_id,
            objective=request.objective,
            status="completed",
            answer=output.get(
                "answer",
                "",
            ),
            steps=steps,
            sources=output.get(
                "sources",
                [],
            ),
            usage=AgentUsage(
                prompt_tokens=usage_data.get(
                    "prompt_tokens"
                ),
                completion_tokens=usage_data.get(
                    "completion_tokens"
                ),
                total_tokens=usage_data.get(
                    "total_tokens"
                ),
                latency_ms=round(
                    (
                        perf_counter()
                        - timer_started
                    )
                    * 1000,
                    2,
                ),
            ),
            started_at=started_at,
            completed_at=completed_at,
        )

    async def _run_system_agent(
        self,
        request: AgentRunRequest,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        tool = tool_registry.get(
            "system.status"
        )

        tool_started = datetime.now(
            timezone.utc
        )

        result = await tool.execute({})

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="tool",
                title="Collect system status",
                tool_id=tool.definition.id,
                success=result.success,
                input={},
                output=result.output,
                error=result.error,
                started_at=tool_started,
                completed_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        if not result.success:
            completed_at = datetime.now(
                timezone.utc
            )

            return AgentRunResponse(
                run_id=run_id,
                agent_id=request.agent_id,
                objective=request.objective,
                status="failed",
                answer=(
                    result.error
                    or "System status tool failed."
                ),
                steps=steps,
                sources=[],
                usage=AgentUsage(
                    latency_ms=round(
                        (
                            perf_counter()
                            - timer_started
                        )
                        * 1000,
                        2,
                    )
                ),
                started_at=started_at,
                completed_at=completed_at,
            )

        generation_started = datetime.now(
            timezone.utc
        )

        chat_response = await gateway_service.chat(
            ChatRequest(
                provider=request.provider,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
                messages=[
                    ChatMessage(
                        role="system",
                        content=SYSTEM_AGENT_PROMPT,
                    ),
                    ChatMessage(
                        role="user",
                        content="\n".join(
                            [
                                (
                                    "User objective:"
                                ),
                                request.objective,
                                "",
                                (
                                    "Current system data:"
                                ),
                                json.dumps(
                                    result.output,
                                    indent=2,
                                    default=str,
                                ),
                            ]
                        ),
                    ),
                ],
            )
        )

        generation_completed = datetime.now(
            timezone.utc
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="generation",
                title="Generate system assessment",
                success=True,
                input={
                    "provider": (
                        request.provider
                    ),
                    "model": request.model,
                },
                output={
                    "provider": (
                        chat_response.provider
                    ),
                    "model": chat_response.model,
                },
                started_at=generation_started,
                completed_at=(
                    generation_completed
                ),
            )
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="result",
                title="System assessment completed",
                success=True,
                output={
                    "answer": (
                        chat_response
                        .message
                        .content
                    )
                },
                started_at=(
                    generation_completed
                ),
                completed_at=(
                    generation_completed
                ),
            )
        )

        return AgentRunResponse(
            run_id=run_id,
            agent_id=request.agent_id,
            objective=request.objective,
            status="completed",
            answer=(
                chat_response.message.content
            ),
            steps=steps,
            sources=[],
            usage=AgentUsage(
                prompt_tokens=(
                    chat_response
                    .usage
                    .prompt_tokens
                ),
                completion_tokens=(
                    chat_response
                    .usage
                    .completion_tokens
                ),
                total_tokens=(
                    chat_response
                    .usage
                    .total_tokens
                ),
                latency_ms=round(
                    (
                        perf_counter()
                        - timer_started
                    )
                    * 1000,
                    2,
                ),
            ),
            started_at=started_at,
            completed_at=(
                generation_completed
            ),
        )

    async def stream(
        self,
        request: AgentRunRequest,
    ) -> AsyncIterator[str]:
        yield json.dumps(
            {
                "type": "status",
                "status": "running",
                "agent_id": request.agent_id,
                "message": (
                    "Agent execution started."
                ),
            }
        ) + "\n"

        try:
            response = await self.run(
                request
            )

            for step in response.steps:
                yield json.dumps(
                    {
                        "type": "step",
                        "step": step.model_dump(
                            mode="json"
                        ),
                    }
                ) + "\n"

            yield json.dumps(
                {
                    "type": "answer",
                    "content": response.answer,
                    "sources": (
                        response.sources
                    ),
                }
            ) + "\n"

            yield json.dumps(
                {
                    "type": "done",
                    "run": response.model_dump(
                        mode="json"
                    ),
                }
            ) + "\n"

        except Exception as exc:
            yield json.dumps(
                {
                    "type": "error",
                    "message": str(exc),
                }
            ) + "\n"


agent_executor = AgentExecutor()
