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
                "Agent already registered: "
                f"{agent.id}"
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
            "health, identify warnings, and explain "
            "the current server state."
        ),
        category="system",
        icon="server",
        accent="cyan",
        tools=[
            "system.status",
        ],
        capabilities=[
            "CPU and memory analysis",
            "Disk capacity monitoring",
            "Ollama health checks",
            "Server warning detection",
        ],
        recommended_model="qwen3:1.7b",
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
            "and return grounded sources from the DAP "
            "knowledge base."
        ),
        category="knowledge",
        icon="book-open",
        accent="violet",
        tools=[
            "knowledge.search",
            "knowledge.ask",
        ],
        capabilities=[
            "Document question answering",
            "Semantic retrieval",
            "Grounded answers",
            "Source citations",
        ],
        recommended_model="qwen3:1.7b",
        safe=True,
        enabled=True,
    )
)


agent_registry.register(
    AgentDefinition(
        id="research-agent",
        name="Research Agent",
        description=(
            "Investigate a topic using indexed knowledge and explicit bounded "
            "public-web evidence, compare sources, and produce a cited research summary."
        ),
        category="research",
        icon="search",
        accent="emerald",
        tools=[
            "knowledge.search",
            "internet.research.retrieve",
        ],
        capabilities=[
            "Topic investigation",
            "Evidence synthesis",
            "Source comparison",
            "Bounded public-web retrieval",
            "Research citations",
        ],
        recommended_model="qwen3:1.7b",
        safe=True,
        enabled=True,
    )
)


agent_registry.register(
    AgentDefinition(
        id="devops-agent",
        name="DevOps Agent",
        description=(
            "Analyse infrastructure and server health, "
            "explain operational risks, and recommend "
            "safe troubleshooting steps."
        ),
        category="devops",
        icon="terminal",
        accent="amber",
        tools=[
            "system.status",
        ],
        capabilities=[
            "Infrastructure analysis",
            "Operational troubleshooting",
            "Docker guidance",
            "Safe remediation planning",
        ],
        recommended_model="qwen3:1.7b",
        safe=True,
        enabled=True,
    )
)


agent_registry.register(
    AgentDefinition(
        id="coding-agent",
        name="Coding Agent",
        description=(
            "Design, explain, review, and troubleshoot "
            "software while producing clear and "
            "maintainable implementation guidance."
        ),
        category="coding",
        icon="code-2",
        accent="blue",
        tools=[],
        capabilities=[
            "Code generation",
            "Code review",
            "Debugging assistance",
            "Architecture guidance",
        ],
        recommended_model="qwen3:1.7b",
        safe=True,
        enabled=True,
    )
)


agent_registry.register(
    AgentDefinition(
        id="engineering-agent",
        name="Engineering Agent",
        description=(
            "Prepare and deliver DAP-authorized repository engineering work "
            "through bounded work orders, controlled execution, evidence, and "
            "owner-reviewed Git delivery."
        ),
        category="coding",
        icon="git-pull-request",
        accent="blue",
        tools=[],
        capabilities=[
            "Bounded engineering work-order preparation",
            "Repository change planning",
            "Test and verification planning",
            "Owner-reviewed delivery preparation",
        ],
        recommended_model="qwen3:1.7b",
        safe=True,
        enabled=True,
    )
)


agent_registry.register(
    AgentDefinition(
        id="documentation-agent",
        name="Documentation Agent",
        description=(
            "Create technical documentation, runbooks, "
            "release notes, implementation plans, and "
            "clear operational instructions."
        ),
        category="documentation",
        icon="file-text",
        accent="rose",
        tools=[],
        capabilities=[
            "Technical documentation",
            "Runbook creation",
            "Release notes",
            "Process documentation",
        ],
        recommended_model="qwen3:1.7b",
        safe=True,
        enabled=True,
    )
)


agent_registry.register(
    AgentDefinition(
        id="sql-agent",
        name="SQL Agent",
        description=(
            "Analyse structured datasets and generate "
            "safe SQL queries. Database execution tools "
            "will be added in a later release."
        ),
        category="data",
        icon="database",
        accent="orange",
        tools=[],
        capabilities=[
            "SQL query design",
            "Schema reasoning",
            "Data analysis planning",
            "Query optimisation guidance",
        ],
        recommended_model="qwen3:1.7b",
        safe=True,
        enabled=False,
    )
)
