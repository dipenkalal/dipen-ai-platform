from agents.schemas import AgentDefinition


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[
            str,
            AgentDefinition,
        ] = {}

    def register(
        self,
        agent: AgentDefinition,
    ) -> None:
        if agent.id in self._agents:
            raise ValueError(
                f"Agent already registered: {agent.id}"
            )

        self._agents[agent.id] = agent

    def get(
        self,
        agent_id: str,
    ) -> AgentDefinition:
        agent = self._agents.get(agent_id)

        if agent is None:
            raise KeyError(
                f"Unknown agent: {agent_id}"
            )

        if not agent.enabled:
            raise ValueError(
                f"Agent is disabled: {agent_id}"
            )

        return agent

    def list(
        self,
    ) -> list[AgentDefinition]:
        return list(
            self._agents.values()
        )


agent_registry = AgentRegistry()

agent_registry.register(
    AgentDefinition(
        id="system-agent",
        name="System Agent",
        description=(
            "Inspect DAP host resources and Ollama "
            "health, then explain the current state."
        ),
        tools=[
            "system.status",
        ],
        safe=True,
        enabled=True,
    )
)

agent_registry.register(
    AgentDefinition(
        id="knowledge-agent",
        name="Knowledge Agent",
        description=(
            "Answer questions using indexed documents "
            "and return grounded source citations."
        ),
        tools=[
            "knowledge.search",
            "knowledge.ask",
        ],
        safe=True,
        enabled=True,
    )
)
