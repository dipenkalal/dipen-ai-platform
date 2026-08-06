import os
import socket
from collections.abc import Callable
from datetime import datetime, timezone

from agents.registry import (
    AgentRegistry,
    agent_registry,
)
from agents.schemas import AgentDefinition
from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from agents.truth_schemas import (
    AgentFleetStateResponse,
    AgentFleetSummary,
    AgentHeartbeat,
    AgentRuntimeState,
    TaskLedgerListResponse,
    TaskLedgerRecord,
    TruthEvidence,
)


class AgentTruthService:
    def __init__(
        self,
        registry: AgentRegistry,
        repository: AgentTruthRepository,
        *,
        heartbeat_ttl_seconds: int = 90,
        now_provider: Callable[[], datetime] | None = None,
        backend_worker_id_provider: Callable[[], str] | None = None,
        backend_process_id_provider: Callable[[], int] | None = None,
        backend_container_id_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self.registry = registry
        self.repository = repository
        self.heartbeat_ttl_seconds = heartbeat_ttl_seconds
        self.now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )
        self.backend_worker_id_provider = (
            backend_worker_id_provider
            or self._default_backend_worker_id
        )
        self.backend_process_id_provider = (
            backend_process_id_provider
            or os.getpid
        )
        self.backend_container_id_provider = (
            backend_container_id_provider
            or self._default_backend_container_id
        )

    def record_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeat:
        registered_ids = {
            agent.id
            for agent in self.registry.list()
        }

        if heartbeat.agent_id not in registered_ids:
            raise KeyError(
                f"Unknown agent: {heartbeat.agent_id}"
            )

        return self.repository.record_heartbeat(
            heartbeat
        )

    def upsert_task(
        self,
        task: TaskLedgerRecord,
    ) -> TaskLedgerRecord:
        registered_ids = {
            agent.id
            for agent in self.registry.list()
        }
        unknown_ids = sorted(
            set(task.assigned_agent_ids)
            - registered_ids
        )

        if unknown_ids:
            raise KeyError(
                "Unknown assigned agents: "
                + ", ".join(unknown_ids)
            )

        return self.repository.upsert_task(task)

    def list_agent_states(
        self,
    ) -> AgentFleetStateResponse:
        now = self._as_utc(self.now_provider())
        heartbeats = (
            self.repository.list_latest_heartbeats()
        )
        states = [
            self._build_agent_state(
                agent,
                heartbeats.get(agent.id),
                now,
            )
            for agent in self.registry.list()
        ]

        counts = {
            status: sum(
                state.runtime_status == status
                for state in states
            )
            for status in (
                "available",
                "busy",
                "degraded",
                "offline",
                "unreported",
                "disabled",
            )
        }

        return AgentFleetStateResponse(
            generated_at=now,
            summary=AgentFleetSummary(
                registered=len(states),
                enabled=sum(
                    state.agent.enabled
                    for state in states
                ),
                available=counts["available"],
                busy=counts["busy"],
                degraded=counts["degraded"],
                offline=counts["offline"],
                unreported=counts["unreported"],
                disabled=counts["disabled"],
            ),
            agents=states,
        )

    def get_agent_state(
        self,
        agent_id: str,
    ) -> AgentRuntimeState:
        fleet = self.list_agent_states()

        for state in fleet.agents:
            if state.agent.id == agent_id:
                return state

        raise KeyError(f"Unknown agent: {agent_id}")

    def list_tasks(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> TaskLedgerListResponse:
        tasks, total = self.repository.list_tasks(
            limit=limit,
            offset=offset,
            status=status,
        )

        return TaskLedgerListResponse(
            generated_at=self._as_utc(
                self.now_provider()
            ),
            tasks=tasks,
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_task(
        self,
        task_id: str,
    ) -> TaskLedgerRecord:
        task = self.repository.get_task(task_id)

        if task is None:
            raise KeyError(f"Unknown task: {task_id}")

        return task

    def _build_agent_state(
        self,
        agent: AgentDefinition,
        heartbeat: AgentHeartbeat | None,
        now: datetime,
    ) -> AgentRuntimeState:
        evidence = [
            TruthEvidence(
                source="agent-registry",
                detail=(
                    "Static registered agent definition."
                ),
            )
        ]

        if not agent.enabled:
            return AgentRuntimeState(
                agent=agent,
                runtime_status="disabled",
                evidence=evidence,
            )

        if heartbeat is None:
            return self._build_backend_ready_state(
                agent,
                evidence,
                now,
            )

        observed_at = self._as_utc(
            heartbeat.observed_at
        )
        age_seconds = max(
            (now - observed_at).total_seconds(),
            0.0,
        )

        if age_seconds > self.heartbeat_ttl_seconds:
            evidence.append(
                TruthEvidence(
                    source="runtime-heartbeat",
                    observed_at=observed_at,
                    detail=(
                        "The last task-specific heartbeat is stale."
                    ),
                )
            )

            if heartbeat.status in {
                "busy",
                "degraded",
            }:
                if heartbeat.current_task_id:
                    evidence.append(
                        TruthEvidence(
                            source="task-ledger",
                            detail=(
                                "Stale heartbeat reports task "
                                f"{heartbeat.current_task_id}."
                            ),
                        )
                    )

                return AgentRuntimeState(
                    agent=agent,
                    runtime_status="offline",
                    worker_id=heartbeat.worker_id,
                    current_task_id=(
                        heartbeat.current_task_id
                    ),
                    model=heartbeat.model,
                    process_id=heartbeat.process_id,
                    container_id=heartbeat.container_id,
                    last_heartbeat_at=observed_at,
                    heartbeat_age_seconds=round(
                        age_seconds,
                        3,
                    ),
                    evidence=evidence,
                )

            return self._build_backend_ready_state(
                agent,
                evidence,
                now,
                last_heartbeat_at=observed_at,
                heartbeat_age_seconds=age_seconds,
            )

        evidence.append(
            TruthEvidence(
                source="runtime-heartbeat",
                observed_at=observed_at,
                detail=(
                    f"Latest heartbeat from "
                    f"{heartbeat.worker_id}."
                ),
            )
        )

        if heartbeat.current_task_id:
            evidence.append(
                TruthEvidence(
                    source="task-ledger",
                    detail=(
                        "Heartbeat reports current task "
                        f"{heartbeat.current_task_id}."
                    ),
                )
            )

        return AgentRuntimeState(
            agent=agent,
            runtime_status=heartbeat.status,
            worker_id=heartbeat.worker_id,
            current_task_id=(
                heartbeat.current_task_id
            ),
            model=heartbeat.model,
            process_id=heartbeat.process_id,
            container_id=heartbeat.container_id,
            last_heartbeat_at=observed_at,
            heartbeat_age_seconds=round(
                age_seconds,
                3,
            ),
            evidence=evidence,
        )

    def _build_backend_ready_state(
        self,
        agent: AgentDefinition,
        evidence: list[TruthEvidence],
        now: datetime,
        *,
        last_heartbeat_at: datetime | None = None,
        heartbeat_age_seconds: float | None = None,
    ) -> AgentRuntimeState:
        evidence.append(
            TruthEvidence(
                source="backend-runtime",
                observed_at=now,
                detail=(
                    "The active backend process can route this enabled "
                    "on-demand agent and no fresh busy heartbeat exists."
                ),
            )
        )

        return AgentRuntimeState(
            agent=agent,
            runtime_status="available",
            worker_id=self.backend_worker_id_provider(),
            process_id=self.backend_process_id_provider(),
            container_id=self.backend_container_id_provider(),
            last_heartbeat_at=last_heartbeat_at,
            heartbeat_age_seconds=(
                round(heartbeat_age_seconds, 3)
                if heartbeat_age_seconds is not None
                else None
            ),
            evidence=evidence,
        )

    @staticmethod
    def _default_backend_worker_id() -> str:
        return (
            "dap-backend:"
            f"{socket.gethostname()}:"
            f"{os.getpid()}"
        )

    @staticmethod
    def _default_backend_container_id() -> str | None:
        return os.getenv(
            "DAP_RUNTIME_CONTAINER_ID"
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)


agent_truth_service = AgentTruthService(
    agent_registry,
    agent_truth_repository,
)
