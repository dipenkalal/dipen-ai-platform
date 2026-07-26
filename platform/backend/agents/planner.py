from dataclasses import dataclass

from agents.schemas import (
    AgentDefinition,
    AgentRunRequest,
    Workflow,
    WorkflowStep,
)


@dataclass(frozen=True)
class ToolPlan:
    """
    Backward-compatible tool selection result.

    The executor currently consumes this contract.
    v0.12 also converts it into a declarative Workflow.
    """

    tool_ids: tuple[str, ...]
    reason: str

    @property
    def requires_tools(self) -> bool:
        return bool(self.tool_ids)


class AgentToolPlanner:
    """
    Selects only the tools required for an agent run.

    Tool selection remains deterministic and rule-based.
    v0.12 adds workflow generation without changing the
    existing ToolPlan behaviour.
    """

    _SYSTEM_STATUS_PHRASES = (
        "system status",
        "server status",
        "server health",
        "system health",
        "host health",
        "machine health",
        "resource usage",
        "cpu usage",
        "memory usage",
        "ram usage",
        "disk usage",
        "disk space",
        "free space",
        "uptime",
        "ollama status",
        "ollama health",
        "is my server",
        "is the server",
        "check server",
        "check system",
        "inspect server",
        "inspect system",
        "monitor server",
        "monitor system",
        "performance issue",
        "resource issue",
        "resource warning",
        "server warning",
        "server slow",
        "system slow",
        "out of memory",
        "high cpu",
        "high memory",
        "low disk",
    )

    _KNOWLEDGE_PHRASES = (
        "indexed document",
        "indexed documents",
        "knowledge base",
        "uploaded document",
        "uploaded documents",
        "uploaded file",
        "uploaded files",
        "search document",
        "search documents",
        "find in document",
        "find in documents",
        "according to the document",
        "according to the documents",
        "based on the document",
        "based on the documents",
        "from the document",
        "from the documents",
        "cite the document",
        "cite the documents",
        "provide sources",
        "with sources",
        "source citation",
        "source citations",
    )

    def plan(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
    ) -> ToolPlan:
        """
        Produce the existing flat ToolPlan contract.

        This method remains unchanged for backward
        compatibility during the v0.12 migration.
        """

        objective = self._normalise(
            request.objective
        )

        if agent.id == "system-agent":
            return self._plan_system_agent(
                agent=agent,
            )

        if agent.id == "devops-agent":
            return self._plan_devops_agent(
                objective=objective,
                agent=agent,
            )

        if agent.id == "knowledge-agent":
            return self._plan_knowledge_agent(
                request=request,
                objective=objective,
                agent=agent,
            )

        if agent.id == "research-agent":
            return self._plan_research_agent(
                request=request,
                objective=objective,
                agent=agent,
            )

        return ToolPlan(
            tool_ids=(),
            reason=(
                f"{agent.name} can complete this "
                "objective without registered tools."
            ),
        )

    def build_workflow(
        self,
        request: AgentRunRequest,
        agent: AgentDefinition,
    ) -> Workflow:
        """
        Convert the planner's ToolPlan into an ordered
        declarative workflow.

        v0.12.1 produces zero or more tool steps followed
        by exactly one generation step.
        """

        tool_plan = self.plan(
            request=request,
            agent=agent,
        )

        workflow_steps: list[WorkflowStep] = []
        dependency_ids: list[str] = []

        for index, tool_id in enumerate(
            tool_plan.tool_ids,
            start=1,
        ):
            step_id = f"tool-{index}"

            workflow_steps.append(
                WorkflowStep(
                    id=step_id,
                    kind="tool",
                    name=self._tool_step_name(
                        tool_id=tool_id,
                    ),
                    tool_id=tool_id,
                    input=self._tool_input(
                        tool_id=tool_id,
                        request=request,
                    ),
                )
            )

            dependency_ids.append(step_id)

        workflow_steps.append(
            WorkflowStep(
                id="generation-1",
                kind="generation",
                name="Generate final response",
                depends_on=dependency_ids,
            )
        )

        return Workflow(
            reason=tool_plan.reason,
            steps=workflow_steps,
            metadata={
                "version": "0.12",
                "planner": "deterministic",
                "agent_id": agent.id,
                "tool_ids": list(
                    tool_plan.tool_ids
                ),
            },
        )

    def _plan_system_agent(
        self,
        agent: AgentDefinition,
    ) -> ToolPlan:
        return ToolPlan(
            tool_ids=self._available_tools(
                agent=agent,
                requested=("system.status",),
            ),
            reason=(
                "The System Agent requires live system "
                "measurements to answer accurately."
            ),
        )

    def _plan_devops_agent(
        self,
        objective: str,
        agent: AgentDefinition,
    ) -> ToolPlan:
        matches = self._find_matches(
            objective=objective,
            phrases=self._SYSTEM_STATUS_PHRASES,
        )

        if not matches:
            return ToolPlan(
                tool_ids=(),
                reason=(
                    "The DevOps objective requests guidance "
                    "or configuration generation and does not "
                    "require live host measurements."
                ),
            )

        tools = self._available_tools(
            agent=agent,
            requested=("system.status",),
        )

        if not tools:
            return ToolPlan(
                tool_ids=(),
                reason=(
                    "Live system information appears useful, "
                    "but the DevOps Agent has no compatible "
                    "status tool assigned."
                ),
            )

        return ToolPlan(
            tool_ids=tools,
            reason=(
                "Live system status is required because the "
                "objective matched: "
                + ", ".join(matches)
                + "."
            ),
        )

    def _plan_knowledge_agent(
        self,
        request: AgentRunRequest,
        objective: str,
        agent: AgentDefinition,
    ) -> ToolPlan:
        if request.document_id:
            return ToolPlan(
                tool_ids=self._available_tools(
                    agent=agent,
                    requested=("knowledge.ask",),
                ),
                reason=(
                    "A document ID was provided, so the answer "
                    "must be grounded in indexed knowledge."
                ),
            )

        matches = self._find_matches(
            objective=objective,
            phrases=self._KNOWLEDGE_PHRASES,
        )

        reason = (
            "The Knowledge Agent is designed to answer "
            "questions using indexed documents."
        )

        if matches:
            reason = (
                "Indexed knowledge is required because the "
                "objective matched: "
                + ", ".join(matches)
                + "."
            )

        return ToolPlan(
            tool_ids=self._available_tools(
                agent=agent,
                requested=("knowledge.ask",),
            ),
            reason=reason,
        )

    def _plan_research_agent(
        self,
        request: AgentRunRequest,
        objective: str,
        agent: AgentDefinition,
    ) -> ToolPlan:
        if request.document_id:
            reason = (
                "A document ID was provided, so the research "
                "must retrieve evidence from that document."
            )
        else:
            matches = self._find_matches(
                objective=objective,
                phrases=self._KNOWLEDGE_PHRASES,
            )

            if matches:
                reason = (
                    "Research retrieval is required because "
                    "the objective matched: "
                    + ", ".join(matches)
                    + "."
                )
            else:
                reason = (
                    "The Research Agent requires indexed "
                    "evidence before synthesising findings."
                )

        return ToolPlan(
            tool_ids=self._available_tools(
                agent=agent,
                requested=("knowledge.search",),
            ),
            reason=reason,
        )

    def _available_tools(
        self,
        agent: AgentDefinition,
        requested: tuple[str, ...],
    ) -> tuple[str, ...]:
        assigned = set(agent.tools)

        return tuple(
            tool_id
            for tool_id in requested
            if tool_id in assigned
        )

    def _tool_step_name(
        self,
        tool_id: str,
    ) -> str:
        names = {
            "system.status": "Collect system status",
            "knowledge.ask": "Ask indexed knowledge",
            "knowledge.search": "Search indexed knowledge",
        }

        return names.get(
            tool_id,
            f"Execute {tool_id}",
        )

    def _tool_input(
        self,
        tool_id: str,
        request: AgentRunRequest,
    ) -> dict[str, object]:
        if tool_id == "system.status":
            return {}

        if tool_id == "knowledge.ask":
            return {
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
                "document_id": request.document_id,
            }

        if tool_id == "knowledge.search":
            return {
                "query": request.objective,
                "document_id": request.document_id,
                "limit": request.retrieval_limit,
                "score_threshold": (
                    request.score_threshold
                ),
            }

        return {}

    def _find_matches(
        self,
        objective: str,
        phrases: tuple[str, ...],
    ) -> list[str]:
        matches: list[str] = []

        for phrase in phrases:
            if phrase in objective:
                matches.append(phrase)

        return matches[:5]

    def _normalise(
        self,
        value: str,
    ) -> str:
        return " ".join(
            value.lower().split()
        )


agent_tool_planner = AgentToolPlanner()
