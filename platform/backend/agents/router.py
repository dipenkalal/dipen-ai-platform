from dataclasses import dataclass

from agents.registry import agent_registry
from agents.schemas import AgentRunRequest


@dataclass(frozen=True)
class AgentRoute:
    agent_id: str
    model: str | None
    confidence: float
    reason: str


class AgentRouter:
    _keyword_weights: dict[
        str,
        dict[str, int],
    ] = {
        "system-agent": {
            "cpu": 5,
            "memory": 5,
            "ram": 5,
            "disk": 5,
            "ollama health": 6,
            "server health": 6,
            "resource usage": 5,
            "system status": 5,
        },
        "knowledge-agent": {
            "pdf": 5,
            "document": 3,
            "uploaded file": 5,
            "knowledge base": 6,
            "indexed": 5,
            "source": 2,
            "citation": 3,
            "according to": 3,
        },
        "research-agent": {
            "research": 6,
            "investigate": 5,
            "compare": 4,
            "comparison": 4,
            "evidence": 4,
            "literature": 5,
            "study": 3,
            "analyse sources": 5,
            "analyze sources": 5,
        },
        "devops-agent": {
            "docker": 6,
            "docker compose": 7,
            "kubernetes": 7,
            "k8s": 7,
            "deployment": 5,
            "deploy": 5,
            "linux": 3,
            "nginx": 5,
            "server": 2,
            "ssh": 4,
            "container": 4,
            "terraform": 6,
            "aws": 5,
            "ci/cd": 6,
            "pipeline": 3,
        },
        "coding-agent": {
            "code": 4,
            "python": 5,
            "javascript": 5,
            "typescript": 5,
            "function": 3,
            "class": 2,
            "api": 3,
            "fastapi": 5,
            "react": 5,
            "next.js": 5,
            "bug": 5,
            "debug": 5,
            "error": 3,
            "refactor": 5,
            "implement": 4,
            "program": 4,
        },
        "documentation-agent": {
            "documentation": 6,
            "document this": 6,
            "readme": 7,
            "runbook": 7,
            "release notes": 7,
            "user guide": 6,
            "technical guide": 6,
            "instructions": 3,
            "write a guide": 5,
            "implementation plan": 5,
        },
    }

    _priority: tuple[str, ...] = (
        "system-agent",
        "knowledge-agent",
        "research-agent",
        "devops-agent",
        "coding-agent",
        "documentation-agent",
    )

    def route(
        self,
        request: AgentRunRequest,
    ) -> AgentRoute:
        objective = request.objective.lower().strip()

        scores: dict[str, int] = {
            agent_id: 0 for agent_id in self._keyword_weights
        }

        matched_terms: dict[
            str,
            list[str],
        ] = {agent_id: [] for agent_id in self._keyword_weights}

        for (
            agent_id,
            keywords,
        ) in self._keyword_weights.items():
            for keyword, weight in keywords.items():
                if keyword in objective:
                    scores[agent_id] += weight
                    matched_terms[agent_id].append(keyword)

        selected_agent_id = max(
            self._priority,
            key=lambda agent_id: (
                scores[agent_id],
                -self._priority.index(agent_id),
            ),
        )

        selected_score = scores[selected_agent_id]

        if selected_score == 0:
            selected_agent_id = (
                "knowledge-agent" if request.document_id else "coding-agent"
            )

            reason = (
                "A document was supplied, so the "
                "Knowledge Agent was selected."
                if request.document_id
                else (
                    "No specialised routing keywords "
                    "were detected, so the Coding "
                    "Agent was selected as the "
                    "general implementation agent."
                )
            )

            confidence = 0.50
        else:
            total_score = sum(scores.values())

            confidence = min(
                0.99,
                max(
                    0.55,
                    selected_score / max(total_score, 1),
                ),
            )

            terms = ", ".join(matched_terms[selected_agent_id][:4])

            agent = agent_registry.get(selected_agent_id)

            reason = f"{agent.name} matched the request " f"based on: {terms}."

        agent = agent_registry.get(selected_agent_id)

        return AgentRoute(
            agent_id=selected_agent_id,
            model=(request.model or agent.recommended_model),
            confidence=round(
                confidence,
                2,
            ),
            reason=reason,
        )


agent_router = AgentRouter()
