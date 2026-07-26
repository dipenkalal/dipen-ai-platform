import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from agents.planner import (
    ToolPlan,
    agent_tool_planner,
)
from agents.registry import agent_registry
from agents.schemas import (
    AgentDefinition,
    AgentRunRequest,
    AgentRunResponse,
    AgentStep,
    AgentUsage,
    Workflow,
    WorkflowStep,
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

Your responsibilities:
1. Summarize CPU, memory, disk, uptime, and Ollama health.
2. Clearly identify warnings or unhealthy conditions.
3. Use only measurements provided in the tool output.
4. Never invent system measurements.
5. Do not suggest destructive commands.
6. Keep the response practical and concise.
""".strip()


DEVOPS_AGENT_PROMPT = """
You are the DevOps Agent inside Dipen AI Platform.

You receive a user objective and may receive live server
status data when the tool planner determines it is needed.

Your responsibilities:
1. Complete the user's DevOps objective directly.
2. When live system data is provided, use it to identify
   risks, warnings, bottlenecks, or failures.
3. When live system data is not provided, do not invent
   measurements, logs, containers, services, or test results.
4. For configuration or script requests, provide complete,
   practical, secure, and maintainable output.
5. Recommend safe and reversible troubleshooting steps.
6. Never claim that a command was executed.
7. Clearly separate observations from recommendations when
   operational evidence is available.
""".strip()


RESEARCH_AGENT_PROMPT = """
You are the Research Agent inside Dipen AI Platform.

You receive a research objective and retrieved excerpts
from the indexed DAP knowledge base.

Your responsibilities:
1. Analyse only the provided retrieved information.
2. Compare relevant evidence where possible.
3. Clearly state when evidence is missing or insufficient.
4. Do not invent sources, authors, quotations, or findings.
5. Produce a structured research summary.
6. Refer to available source metadata when useful.
""".strip()


CODING_AGENT_PROMPT = """
You are the Coding Agent inside Dipen AI Platform.

Your responsibilities:
1. Understand the requested software objective.
2. Produce correct, maintainable, and secure guidance.
3. Explain important architecture and implementation choices.
4. Include complete code when the user asks for a full file.
5. Avoid destructive commands unless clearly required.
6. Never claim that code was executed or tested unless
   execution evidence is provided.
7. Mention assumptions and limitations clearly.
""".strip()


DOCUMENTATION_AGENT_PROMPT = """
You are the Documentation Agent inside Dipen AI Platform.

Your responsibilities:
1. Convert the user's objective into clear documentation.
2. Use concise headings and logical organisation.
3. Produce practical runbooks, guides, release notes,
   procedures, or implementation plans.
4. Preserve technical accuracy.
5. Clearly identify prerequisites, commands, validation,
   expected results, and rollback steps when relevant.
6. Do not invent completed actions or test results.
""".strip()


GENERIC_AGENT_PROMPTS: dict[str, str] = {
    "coding-agent": CODING_AGENT_PROMPT,
    "documentation-agent": DOCUMENTATION_AGENT_PROMPT,
}


ExecutorHandler = Callable[
    [
        AgentRunRequest,
        AgentDefinition,
        ToolPlan,
        str,
        datetime,
        float,
        list[AgentStep],
    ],
    Awaitable[AgentRunResponse],
]


class AgentExecutor:
    def __init__(self) -> None:
        self._handlers: dict[str, ExecutorHandler] = {
            "system-agent": self._dispatch_system_agent,
            "knowledge-agent": self._dispatch_knowledge_agent,
            "research-agent": self._dispatch_research_agent,
            "devops-agent": self._dispatch_devops_agent,
            "coding-agent": self._dispatch_prompt_agent,
            "documentation-agent": self._dispatch_prompt_agent,
        }

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        started_at = datetime.now(timezone.utc)
        timer_started = perf_counter()
        run_id = str(uuid4())
        steps: list[AgentStep] = []

        if not request.agent_id:
            raise ValueError(
                "A resolved agent_id is required for execution."
            )

        agent = agent_registry.get(request.agent_id)

        if request.max_steps < 1:
            raise ValueError(
                "At least one agent step is required."
            )

        tool_plan = agent_tool_planner.plan(
            request=request,
            agent=agent,
        )

        workflow = agent_tool_planner.build_workflow(
            request=request,
            agent=agent,
        )

        self._append_planning_step(
            request=request,
            agent=agent,
            tool_plan=tool_plan,
            workflow=workflow,
            steps=steps,
        )

        handler = self._handlers.get(agent.id)

        if handler is None:
            raise ValueError(
                "No executor is configured for "
                f"{agent.id}"
            )

        return await handler(
            request,
            agent,
            tool_plan,
            run_id,
            started_at,
            timer_started,
            steps,
        )

    async def _dispatch_system_agent(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
        tool_plan: ToolPlan,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        return await self._run_status_capable_agent(
            request=request,
            agent=agent,
            tool_plan=tool_plan,
            system_prompt=SYSTEM_AGENT_PROMPT,
            generation_title="Generate system assessment",
            result_title="System assessment completed",
            run_id=run_id,
            started_at=started_at,
            timer_started=timer_started,
            steps=steps,
        )

    async def _dispatch_devops_agent(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
        tool_plan: ToolPlan,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        return await self._run_status_capable_agent(
            request=request,
            agent=agent,
            tool_plan=tool_plan,
            system_prompt=DEVOPS_AGENT_PROMPT,
            generation_title="Generate DevOps response",
            result_title="DevOps response completed",
            run_id=run_id,
            started_at=started_at,
            timer_started=timer_started,
            steps=steps,
        )

    async def _dispatch_knowledge_agent(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
        tool_plan: ToolPlan,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        del agent

        if "knowledge.ask" not in tool_plan.tool_ids:
            raise ValueError(
                "Knowledge Agent requires knowledge.ask "
                "in its tool plan."
            )

        return await self._run_knowledge_agent(
            request=request,
            run_id=run_id,
            started_at=started_at,
            timer_started=timer_started,
            steps=steps,
        )

    async def _dispatch_research_agent(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
        tool_plan: ToolPlan,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        del agent

        if "knowledge.search" not in tool_plan.tool_ids:
            raise ValueError(
                "Research Agent requires knowledge.search "
                "in its tool plan."
            )

        return await self._run_research_agent(
            request=request,
            run_id=run_id,
            started_at=started_at,
            timer_started=timer_started,
            steps=steps,
        )

    async def _dispatch_prompt_agent(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
        tool_plan: ToolPlan,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        del tool_plan

        system_prompt = GENERIC_AGENT_PROMPTS.get(
            agent.id
        )

        if system_prompt is None:
            raise ValueError(
                "No prompt is configured for "
                f"{agent.id}"
            )

        return await self._run_prompt_agent(
            request=request,
            agent=agent,
            system_prompt=system_prompt,
            run_id=run_id,
            started_at=started_at,
            timer_started=timer_started,
            steps=steps,
        )

    def _append_planning_step(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
        tool_plan: ToolPlan,
        workflow: Workflow,
        steps: list[AgentStep],
    ) -> None:
        planning_started = datetime.now(
            timezone.utc
        )

        steps.append(
            AgentStep(
                step_number=1,
                type="planning",
                title=f"Planned {agent.name} execution",
                success=True,
                input={
                    "objective": request.objective,
                    "available_tools": agent.tools,
                    "capabilities": agent.capabilities,
                    "max_steps": request.max_steps,
                },
                output={
                    "selected_agent": agent.id,
                    "category": agent.category,
                    "recommended_model": (
                        agent.recommended_model
                    ),
                    "tool_plan": {
                        "requires_tools": (
                            tool_plan.requires_tools
                        ),
                        "selected_tools": list(
                            tool_plan.tool_ids
                        ),
                        "reason": tool_plan.reason,
                    },
                    "workflow": {
                        "reason": workflow.reason,
                        "steps": [
                            {
                                "id": workflow_step.id,
                                "kind": workflow_step.kind,
                                "name": workflow_step.name,
                                "tool_id": workflow_step.tool_id,
                                "depends_on": (
                                    workflow_step.depends_on
                                ),
                            }
                            for workflow_step
                            in workflow.steps
                        ],
                    },
                },
                started_at=planning_started,
                completed_at=datetime.now(
                    timezone.utc
                ),
            )
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

        result = await tool.execute(arguments)

        tool_completed = datetime.now(
            timezone.utc
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
                completed_at=tool_completed,
            )
        )

        if not result.success:
            return self._failed_response(
                request=request,
                run_id=run_id,
                answer=(
                    result.error
                    or "Knowledge tool failed."
                ),
                steps=steps,
                started_at=started_at,
                completed_at=tool_completed,
                timer_started=timer_started,
            )

        output = self._as_dict(
            result.output
        )

        usage_data = self._as_dict(
            output.get("usage")
        )

        sources = self._as_list_of_dicts(
            output.get("sources")
        )

        answer = str(
            output.get("answer", "")
        )

        result_completed = datetime.now(
            timezone.utc
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="result",
                title="Knowledge answer completed",
                success=True,
                output={
                    "answer": answer,
                    "source_count": len(
                        sources
                    ),
                },
                started_at=result_completed,
                completed_at=result_completed,
            )
        )

        return AgentRunResponse(
            run_id=run_id,
            agent_id=self._required_agent_id(
                request
            ),
            objective=request.objective,
            status="completed",
            answer=answer,
            steps=steps,
            sources=sources,
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
                latency_ms=self._latency_ms(
                    timer_started
                ),
            ),
            started_at=started_at,
            completed_at=result_completed,
        )

    async def _run_research_agent(
        self,
        request: AgentRunRequest,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        tool = tool_registry.get(
            "knowledge.search"
        )

        tool_started = datetime.now(
            timezone.utc
        )

        arguments = {
            "query": request.objective,
            "limit": request.retrieval_limit,
            "score_threshold": (
                request.score_threshold
            ),
            "document_id": (
                request.document_id
            ),
        }

        result = await tool.execute(arguments)

        tool_completed = datetime.now(
            timezone.utc
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="tool",
                title="Search indexed research material",
                tool_id=tool.definition.id,
                success=result.success,
                input=arguments,
                output=result.output,
                error=result.error,
                started_at=tool_started,
                completed_at=tool_completed,
            )
        )

        if not result.success:
            return self._failed_response(
                request=request,
                run_id=run_id,
                answer=(
                    result.error
                    or "Knowledge search failed."
                ),
                steps=steps,
                started_at=started_at,
                completed_at=tool_completed,
                timer_started=timer_started,
            )

        search_output = self._as_dict(
            result.output
        )

        sources = self._extract_sources(
            search_output
        )

        generation_started = datetime.now(
            timezone.utc
        )

        chat_response = await self._chat(
            request=request,
            system_prompt=RESEARCH_AGENT_PROMPT,
            user_content="\n".join(
                [
                    "Research objective:",
                    request.objective,
                    "",
                    "Retrieved knowledge:",
                    json.dumps(
                        search_output,
                        indent=2,
                        default=str,
                    ),
                ]
            ),
        )

        generation_completed = datetime.now(
            timezone.utc
        )

        answer = chat_response.message.content

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="generation",
                title="Synthesise research findings",
                success=True,
                input={
                    "provider": request.provider,
                    "model": request.model,
                    "retrieved_sources": len(
                        sources
                    ),
                },
                output={
                    "provider": (
                        chat_response.provider
                    ),
                    "model": chat_response.model,
                },
                started_at=generation_started,
                completed_at=generation_completed,
            )
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="result",
                title="Research summary completed",
                success=True,
                output={
                    "answer": answer,
                    "source_count": len(
                        sources
                    ),
                },
                started_at=generation_completed,
                completed_at=generation_completed,
            )
        )

        return self._completed_response(
            request=request,
            run_id=run_id,
            answer=answer,
            steps=steps,
            sources=sources,
            chat_response=chat_response,
            started_at=started_at,
            completed_at=generation_completed,
            timer_started=timer_started,
        )

    async def _run_status_capable_agent(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
        tool_plan: ToolPlan,
        system_prompt: str,
        generation_title: str,
        result_title: str,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        tool_output: Any = None

        if "system.status" in tool_plan.tool_ids:
            tool = tool_registry.get(
                "system.status"
            )

            tool_started = datetime.now(
                timezone.utc
            )

            result = await tool.execute({})

            tool_completed = datetime.now(
                timezone.utc
            )

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
                    completed_at=tool_completed,
                )
            )

            if not result.success:
                return self._failed_response(
                    request=request,
                    run_id=run_id,
                    answer=(
                        result.error
                        or "System status tool failed."
                    ),
                    steps=steps,
                    started_at=started_at,
                    completed_at=tool_completed,
                    timer_started=timer_started,
                )

            tool_output = result.output

        generation_started = datetime.now(
            timezone.utc
        )

        chat_response = await self._chat(
            request=request,
            system_prompt=system_prompt,
            user_content=self._build_status_user_content(
                request=request,
                tool_plan=tool_plan,
                tool_output=tool_output,
            ),
        )

        generation_completed = datetime.now(
            timezone.utc
        )

        answer = chat_response.message.content

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="generation",
                title=generation_title,
                success=True,
                input={
                    "provider": request.provider,
                    "model": request.model,
                    "agent": agent.id,
                    "planned_tools": list(
                        tool_plan.tool_ids
                    ),
                },
                output={
                    "provider": (
                        chat_response.provider
                    ),
                    "model": chat_response.model,
                },
                started_at=generation_started,
                completed_at=generation_completed,
            )
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="result",
                title=result_title,
                success=True,
                output={
                    "answer": answer,
                },
                started_at=generation_completed,
                completed_at=generation_completed,
            )
        )

        return self._completed_response(
            request=request,
            run_id=run_id,
            answer=answer,
            steps=steps,
            sources=[],
            chat_response=chat_response,
            started_at=started_at,
            completed_at=generation_completed,
            timer_started=timer_started,
        )

    def _build_status_user_content(
        self,
        request: AgentRunRequest,
        tool_plan: ToolPlan,
        tool_output: Any,
    ) -> str:
        sections = [
            "User objective:",
            request.objective,
            "",
            "Tool planning decision:",
            tool_plan.reason,
        ]

        if tool_output is not None:
            sections.extend(
                [
                    "",
                    "Current system data:",
                    json.dumps(
                        tool_output,
                        indent=2,
                        default=str,
                    ),
                ]
            )
        else:
            sections.extend(
                [
                    "",
                    (
                        "No live system data was collected. "
                        "Complete the objective without "
                        "inventing measurements or claiming "
                        "that commands were executed."
                    ),
                ]
            )

        return "\n".join(sections)

    async def _run_prompt_agent(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
        system_prompt: str,
        run_id: str,
        started_at: datetime,
        timer_started: float,
        steps: list[AgentStep],
    ) -> AgentRunResponse:
        generation_started = datetime.now(
            timezone.utc
        )

        chat_response = await self._chat(
            request=request,
            system_prompt=system_prompt,
            user_content=request.objective,
        )

        generation_completed = datetime.now(
            timezone.utc
        )

        answer = chat_response.message.content

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="generation",
                title=f"Generate {agent.name} response",
                success=True,
                input={
                    "provider": request.provider,
                    "model": request.model,
                    "agent": agent.id,
                },
                output={
                    "provider": (
                        chat_response.provider
                    ),
                    "model": chat_response.model,
                },
                started_at=generation_started,
                completed_at=generation_completed,
            )
        )

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                type="result",
                title=f"{agent.name} response completed",
                success=True,
                output={
                    "answer": answer,
                },
                started_at=generation_completed,
                completed_at=generation_completed,
            )
        )

        return self._completed_response(
            request=request,
            run_id=run_id,
            answer=answer,
            steps=steps,
            sources=[],
            chat_response=chat_response,
            started_at=started_at,
            completed_at=generation_completed,
            timer_started=timer_started,
        )

    async def _chat(
        self,
        request: AgentRunRequest,
        system_prompt: str,
        user_content: str,
    ) -> Any:
        return await gateway_service.chat(
            ChatRequest(
                provider=request.provider,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
                messages=[
                    ChatMessage(
                        role="system",
                        content=system_prompt,
                    ),
                    ChatMessage(
                        role="user",
                        content=user_content,
                    ),
                ],
            )
        )

    def _completed_response(
        self,
        request: AgentRunRequest,
        run_id: str,
        answer: str,
        steps: list[AgentStep],
        sources: list[dict[str, Any]],
        chat_response: Any,
        started_at: datetime,
        completed_at: datetime,
        timer_started: float,
    ) -> AgentRunResponse:
        usage = getattr(
            chat_response,
            "usage",
            None,
        )

        return AgentRunResponse(
            run_id=run_id,
            agent_id=self._required_agent_id(
                request
            ),
            objective=request.objective,
            status="completed",
            answer=answer,
            steps=steps,
            sources=sources,
            usage=AgentUsage(
                prompt_tokens=getattr(
                    usage,
                    "prompt_tokens",
                    None,
                ),
                completion_tokens=getattr(
                    usage,
                    "completion_tokens",
                    None,
                ),
                total_tokens=getattr(
                    usage,
                    "total_tokens",
                    None,
                ),
                latency_ms=self._latency_ms(
                    timer_started
                ),
            ),
            started_at=started_at,
            completed_at=completed_at,
        )

    def _failed_response(
        self,
        request: AgentRunRequest,
        run_id: str,
        answer: str,
        steps: list[AgentStep],
        started_at: datetime,
        completed_at: datetime,
        timer_started: float,
    ) -> AgentRunResponse:
        return AgentRunResponse(
            run_id=run_id,
            agent_id=self._required_agent_id(
                request
            ),
            objective=request.objective,
            status="failed",
            answer=answer,
            steps=steps,
            sources=[],
            usage=AgentUsage(
                latency_ms=self._latency_ms(
                    timer_started
                )
            ),
            started_at=started_at,
            completed_at=completed_at,
        )

    def _required_agent_id(
        self,
        request: AgentRunRequest,
    ) -> str:
        if not request.agent_id:
            raise ValueError(
                "A resolved agent_id is required."
            )

        return request.agent_id

    def _latency_ms(
        self,
        timer_started: float,
    ) -> float:
        return round(
            (
                perf_counter()
                - timer_started
            )
            * 1000,
            2,
        )

    def _as_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:
        if isinstance(value, dict):
            return value

        if hasattr(value, "model_dump"):
            dumped = value.model_dump()

            if isinstance(dumped, dict):
                return dumped

        return {}

    def _as_list_of_dicts(
        self,
        value: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        items: list[dict[str, Any]] = []

        for item in value:
            if isinstance(item, dict):
                items.append(item)
                continue

            if hasattr(item, "model_dump"):
                dumped = item.model_dump()

                if isinstance(dumped, dict):
                    items.append(dumped)

        return items

    async def _execute_workflow(
        self,
        workflow: Workflow,
    ) -> dict[str, Any]:
        """
        Execute an ordered declarative workflow.

        v0.12.2 introduces the orchestration boundary
        without changing the active agent execution path.
        Step-specific handlers will be connected to the
        existing tool and generation implementations in
        subsequent commits.
        """
        completed_step_ids: set[str] = set()
        outputs: dict[str, Any] = {}

        for workflow_step in workflow.steps:
            missing_dependencies = [
                dependency_id
                for dependency_id
                in workflow_step.depends_on
                if dependency_id
                not in completed_step_ids
            ]

            if missing_dependencies:
                missing = ", ".join(
                    missing_dependencies
                )

                raise ValueError(
                    "Workflow step "
                    f"{workflow_step.id!r} has "
                    "unmet dependencies: "
                    f"{missing}"
                )

            try:
                outputs[workflow_step.id] = (
                    await self._execute_workflow_step(
                        workflow_step=workflow_step,
                        previous_outputs=outputs,
                    )
                )
            except Exception as exc:
                if not workflow_step.continue_on_error:
                    raise

                outputs[workflow_step.id] = {
                    "success": False,
                    "error": str(exc),
                }

            completed_step_ids.add(
                workflow_step.id
            )

        return outputs

    async def _execute_workflow_step(
        self,
        workflow_step: WorkflowStep,
        previous_outputs: dict[str, Any],
    ) -> Any:
        """
        Dispatch a workflow step by its declarative kind.
        """
        if workflow_step.kind == "tool":
            return (
                await self._execute_tool_workflow_step(
                    workflow_step=workflow_step,
                    previous_outputs=previous_outputs,
                )
            )

        if workflow_step.kind == "generation":
            return (
                await self._execute_generation_workflow_step(
                    workflow_step=workflow_step,
                    previous_outputs=previous_outputs,
                )
            )

        raise ValueError(
            "Unsupported workflow step kind: "
            f"{workflow_step.kind!r}"
        )

    async def _execute_tool_workflow_step(
        self,
        workflow_step: WorkflowStep,
        previous_outputs: dict[str, Any],
    ) -> Any:
        """
        Placeholder tool-step boundary.

        The existing executor remains responsible for live
        tool execution until the next migration commit.
        """
        del previous_outputs

        raise NotImplementedError(
            "Workflow tool execution is not connected yet "
            f"for step {workflow_step.id!r}."
        )

    async def _execute_generation_workflow_step(
        self,
        workflow_step: WorkflowStep,
        previous_outputs: dict[str, Any],
    ) -> Any:
        """
        Placeholder generation-step boundary.

        The existing agent handlers remain responsible for
        model generation until the next migration commit.
        """
        del previous_outputs

        raise NotImplementedError(
            "Workflow generation execution is not connected "
            f"yet for step {workflow_step.id!r}."
        )

    def _extract_sources(
        self,
        search_output: dict[str, Any],
    ) -> list[dict[str, Any]]:
        for key in (
            "sources",
            "results",
            "matches",
            "documents",
            "chunks",
        ):
            sources = self._as_list_of_dicts(
                search_output.get(key)
            )

            if sources:
                return sources

        nested_data = self._as_dict(
            search_output.get("data")
        )

        for key in (
            "sources",
            "results",
            "matches",
            "documents",
            "chunks",
        ):
            sources = self._as_list_of_dicts(
                nested_data.get(key)
            )

            if sources:
                return sources

        return []


agent_executor = AgentExecutor()
