from dataclasses import dataclass
from uuid import uuid4

from agents.orchestration.schemas import (
    OrchestrationPlan,
    OrchestrationPlanRequest,
    OrchestrationTask,
    OrchestrationTaskRole,
)
from agents.registry import agent_registry
from agents.router import agent_router
from agents.schemas import AgentDefinition, AgentRunRequest

DOCUMENTATION_TERMS: tuple[str, ...] = (
    "document",
    "documentation",
    "runbook",
    "guide",
    "report",
    "procedure",
    "instructions",
    "implementation plan",
    "troubleshooting plan",
    "release notes",
)

KNOWLEDGE_TERMS: tuple[str, ...] = (
    "document",
    "pdf",
    "knowledge",
    "indexed",
    "source",
    "citation",
    "according to",
    "uploaded file",
)

RESEARCH_TERMS: tuple[str, ...] = (
    "research",
    "compare",
    "comparison",
    "evidence",
    "investigate",
    "literature",
    "study",
)

DEVOPS_TERMS: tuple[str, ...] = (
    "docker",
    "kubernetes",
    "deployment",
    "deploy",
    "server",
    "linux",
    "nginx",
    "terraform",
    "aws",
    "pipeline",
    "ci/cd",
    "container",
    "ssh",
)

SYSTEM_TERMS: tuple[str, ...] = (
    "cpu",
    "memory",
    "ram",
    "disk",
    "uptime",
    "server health",
    "system status",
    "resource usage",
    "ollama health",
)

CODING_TERMS: tuple[str, ...] = (
    "code",
    "python",
    "javascript",
    "typescript",
    "react",
    "next.js",
    "fastapi",
    "api",
    "bug",
    "debug",
    "error",
    "refactor",
    "implement",
)


@dataclass(frozen=True)
class PlannerCandidate:
    agent: AgentDefinition
    score: int
    reason: str


class OrchestrationPlanner:
    def plan(
        self,
        request: OrchestrationPlanRequest,
    ) -> OrchestrationPlan:
        objective = request.objective.strip()
        objective_lower = objective.lower()

        routing_request = AgentRunRequest(
            mode="smart",
            agent_id=None,
            objective=objective,
            model=request.model,
            provider=request.provider,
            max_steps=request.max_steps_per_agent,
            document_id=request.document_id,
        )

        route = agent_router.route(
            routing_request,
        )

        enabled_agents = {
            agent.id: agent for agent in agent_registry.list() if agent.enabled
        }

        candidates = self._build_candidates(
            objective_lower=objective_lower,
            candidate_scores=route.candidate_scores,
            enabled_agents=enabled_agents,
            document_id=request.document_id,
        )

        selected_ids = self._select_agents(
            lead_agent_id=route.agent_id,
            candidates=candidates,
            objective_lower=objective_lower,
            include_documentation=(request.include_documentation),
            max_agents=request.max_agents,
            enabled_agents=enabled_agents,
        )

        tasks = self._build_tasks(
            objective=objective,
            selected_ids=selected_ids,
            candidates=candidates,
            enabled_agents=enabled_agents,
            requested_model=request.model,
        )

        selected_names = [enabled_agents[agent_id].name for agent_id in selected_ids]

        reason = (
            f"{enabled_agents[route.agent_id].name} was "
            "selected as the lead agent. "
            f"The plan also includes: "
            f"{', '.join(selected_names[1:])}."
            if len(selected_names) > 1
            else (
                f"{enabled_agents[route.agent_id].name} "
                "can handle the objective without an "
                "additional specialist."
            )
        )

        return OrchestrationPlan(
            plan_id=str(uuid4()),
            objective=objective,
            execution_mode="sequential",
            lead_agent_id=route.agent_id,
            selected_agent_ids=selected_ids,
            tasks=tasks,
            candidate_scores=route.candidate_scores,
            matched_terms=route.matched_terms,
            confidence=route.confidence,
            reason=reason,
            estimated_agent_runs=len(tasks),
            max_steps_per_agent=(request.max_steps_per_agent),
        )

    def _build_candidates(
        self,
        *,
        objective_lower: str,
        candidate_scores: dict[str, int],
        enabled_agents: dict[str, AgentDefinition],
        document_id: str | None,
    ) -> dict[str, PlannerCandidate]:
        candidates: dict[
            str,
            PlannerCandidate,
        ] = {}

        for agent_id, agent in enabled_agents.items():
            score = candidate_scores.get(
                agent_id,
                0,
            )

            bonus, reason = self._planner_bonus(
                agent_id=agent_id,
                objective_lower=objective_lower,
                document_id=document_id,
            )

            final_score = score + bonus

            candidates[agent_id] = PlannerCandidate(
                agent=agent,
                score=final_score,
                reason=reason,
            )

        return candidates

    def _planner_bonus(
        self,
        *,
        agent_id: str,
        objective_lower: str,
        document_id: str | None,
    ) -> tuple[int, str]:
        if agent_id == "system-agent":
            matches = self._matching_terms(
                objective_lower,
                SYSTEM_TERMS,
            )

            return (
                len(matches) * 2,
                self._reason_for_matches(
                    "System inspection",
                    matches,
                ),
            )

        if agent_id == "knowledge-agent":
            matches = self._matching_terms(
                objective_lower,
                KNOWLEDGE_TERMS,
            )

            bonus = len(matches) * 2

            if document_id:
                bonus += 8
                matches.append(
                    "document supplied",
                )

            return (
                bonus,
                self._reason_for_matches(
                    "Knowledge retrieval",
                    matches,
                ),
            )

        if agent_id == "research-agent":
            matches = self._matching_terms(
                objective_lower,
                RESEARCH_TERMS,
            )

            return (
                len(matches) * 2,
                self._reason_for_matches(
                    "Research and comparison",
                    matches,
                ),
            )

        if agent_id == "devops-agent":
            matches = self._matching_terms(
                objective_lower,
                DEVOPS_TERMS,
            )

            return (
                len(matches) * 2,
                self._reason_for_matches(
                    "Infrastructure analysis",
                    matches,
                ),
            )

        if agent_id == "coding-agent":
            matches = self._matching_terms(
                objective_lower,
                CODING_TERMS,
            )

            return (
                len(matches) * 2,
                self._reason_for_matches(
                    "Software implementation",
                    matches,
                ),
            )

        if agent_id == "documentation-agent":
            matches = self._matching_terms(
                objective_lower,
                DOCUMENTATION_TERMS,
            )

            return (
                len(matches) * 3,
                self._reason_for_matches(
                    "Documentation output",
                    matches,
                ),
            )

        return (
            0,
            "No orchestration-specific match.",
        )

    def _select_agents(
        self,
        *,
        lead_agent_id: str,
        candidates: dict[str, PlannerCandidate],
        objective_lower: str,
        include_documentation: bool,
        max_agents: int,
        enabled_agents: dict[str, AgentDefinition],
    ) -> list[str]:
        selected: list[str] = [
            lead_agent_id,
        ]

        ordered_candidates = sorted(
            candidates.values(),
            key=lambda candidate: (
                candidate.score,
                candidate.agent.id == lead_agent_id,
            ),
            reverse=True,
        )

        for candidate in ordered_candidates:
            agent_id = candidate.agent.id

            if agent_id in selected:
                continue

            if candidate.score <= 0:
                continue

            if agent_id == "documentation-agent" and not include_documentation:
                continue

            selected.append(agent_id)

            if len(selected) >= max_agents:
                break

        should_add_documentation = (
            include_documentation
            and "documentation-agent" in enabled_agents
            and self._contains_any(
                objective_lower,
                DOCUMENTATION_TERMS,
            )
        )

        if should_add_documentation and "documentation-agent" not in selected:
            if len(selected) >= max_agents:
                selected[-1] = "documentation-agent"
            else:
                selected.append("documentation-agent")

        selected = selected[:max_agents]

        if "documentation-agent" in selected and len(selected) > 1:
            selected = [
                agent_id for agent_id in selected if agent_id != "documentation-agent"
            ] + ["documentation-agent"]

        return selected

    def _build_tasks(
        self,
        *,
        objective: str,
        selected_ids: list[str],
        candidates: dict[str, PlannerCandidate],
        enabled_agents: dict[str, AgentDefinition],
        requested_model: str | None,
    ) -> list[OrchestrationTask]:
        tasks: list[OrchestrationTask] = []
        previous_task_id: str | None = None

        for index, agent_id in enumerate(
            selected_ids,
            start=1,
        ):
            agent = enabled_agents[agent_id]
            candidate = candidates[agent_id]

            task_id = f"task-{index}-{agent_id}"

            role = self._task_role(
                index=index,
                agent_id=agent_id,
            )

            dependencies = [previous_task_id] if previous_task_id else []

            tasks.append(
                OrchestrationTask(
                    task_id=task_id,
                    sequence=index,
                    agent_id=agent.id,
                    agent_name=agent.name,
                    role=role,
                    objective=objective,
                    instructions=(
                        self._task_instructions(
                            agent=agent,
                            role=role,
                        )
                    ),
                    model=(requested_model or agent.recommended_model),
                    tools=agent.tools,
                    capabilities=(agent.capabilities),
                    depends_on=dependencies,
                    confidence=(
                        self._candidate_confidence(
                            candidate.score,
                            candidates,
                        )
                    ),
                    score=candidate.score,
                    reason=candidate.reason,
                )
            )

            previous_task_id = task_id

        return tasks

    @staticmethod
    def _task_role(
        *,
        index: int,
        agent_id: str,
    ) -> OrchestrationTaskRole:
        if index == 1:
            return "lead"

        if agent_id == "documentation-agent":
            return "formatter"

        return "specialist"

    @staticmethod
    def _task_instructions(
        *,
        agent: AgentDefinition,
        role: str,
    ) -> str:
        if role == "lead":
            return (
                "Analyse the original objective and "
                "produce the primary findings that "
                "later specialists can build upon."
            )

        if role == "formatter":
            return (
                "Use the original objective and all "
                "preceding agent outputs to produce a "
                "clear, structured final deliverable."
            )

        return (
            "Analyse the original objective from the "
            f"{agent.name} perspective. Use preceding "
            "agent outputs as context, avoid repeating "
            "their work, and add specialist findings."
        )

    @staticmethod
    def _candidate_confidence(
        score: int,
        candidates: dict[str, PlannerCandidate],
    ) -> float:
        maximum_score = max(
            (candidate.score for candidate in candidates.values()),
            default=1,
        )

        if score <= 0:
            return 0.50

        confidence = score / max(
            maximum_score,
            1,
        )

        return round(
            min(
                0.99,
                max(
                    0.55,
                    confidence,
                ),
            ),
            2,
        )

    @staticmethod
    def _matching_terms(
        objective_lower: str,
        terms: tuple[str, ...],
    ) -> list[str]:
        return [term for term in terms if term in objective_lower]

    @staticmethod
    def _contains_any(
        objective_lower: str,
        terms: tuple[str, ...],
    ) -> bool:
        return any(term in objective_lower for term in terms)

    @staticmethod
    def _reason_for_matches(
        capability: str,
        matches: list[str],
    ) -> str:
        if not matches:
            return f"{capability} was not explicitly requested."

        return f"{capability} matched: {', '.join(matches[:5])}."


orchestration_planner = OrchestrationPlanner()
