import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.registry import AgentRegistry
from agents.schemas import AgentDefinition
from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import (
    AgentHeartbeat,
    TaskLedgerRecord,
)
from agents.truth_service import AgentTruthService

FIXED_NOW = datetime(
    2026,
    8,
    5,
    12,
    0,
    tzinfo=timezone.utc,
)


class AgentTruthFoundationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )
        database_path = (
            Path(self.temporary_directory.name)
            / "agent-truth.db"
        )
        self.repository = AgentTruthRepository(
            database_path
        )
        self.registry = AgentRegistry()
        self.registry.register(
            AgentDefinition(
                id="research-agent",
                name="Research Agent",
                description="Researches evidence.",
                category="research",
                capabilities=["Research"],
                enabled=True,
            )
        )
        self.registry.register(
            AgentDefinition(
                id="coding-agent",
                name="Coding Agent",
                description="Reviews code.",
                category="coding",
                capabilities=["Code review"],
                enabled=True,
            )
        )
        self.registry.register(
            AgentDefinition(
                id="sql-agent",
                name="SQL Agent",
                description="Designs SQL.",
                category="data",
                capabilities=["SQL design"],
                enabled=False,
            )
        )
        self.service = AgentTruthService(
            self.registry,
            self.repository,
            heartbeat_ttl_seconds=90,
            now_provider=lambda: FIXED_NOW,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_registry_state_is_truthful_without_heartbeats(
        self,
    ) -> None:
        response = self.service.list_agent_states()

        self.assertEqual(response.summary.registered, 3)
        self.assertEqual(response.summary.enabled, 2)
        self.assertEqual(response.summary.unreported, 2)
        self.assertEqual(response.summary.disabled, 1)
        self.assertEqual(response.summary.available, 0)

        states = {
            state.agent.id: state
            for state in response.agents
        }
        self.assertEqual(
            states["research-agent"].runtime_status,
            "unreported",
        )
        self.assertEqual(
            states["sql-agent"].runtime_status,
            "disabled",
        )
        self.assertEqual(
            states["research-agent"].evidence[0].source,
            "agent-registry",
        )

    def test_fresh_heartbeat_reports_live_assignment(
        self,
    ) -> None:
        self.service.record_heartbeat(
            AgentHeartbeat(
                agent_id="research-agent",
                worker_id="worker-01",
                status="busy",
                current_task_id="task-001",
                model="qwen3:1.7b",
                process_id=4242,
                container_id="dap-agent-worker",
                observed_at=(
                    FIXED_NOW
                    - timedelta(seconds=15)
                ),
            )
        )

        state = self.service.get_agent_state(
            "research-agent"
        )

        self.assertEqual(state.runtime_status, "busy")
        self.assertEqual(state.current_task_id, "task-001")
        self.assertEqual(state.worker_id, "worker-01")
        self.assertEqual(state.process_id, 4242)
        self.assertEqual(
            state.container_id,
            "dap-agent-worker",
        )
        self.assertEqual(state.heartbeat_age_seconds, 15.0)
        self.assertEqual(
            [evidence.source for evidence in state.evidence],
            [
                "agent-registry",
                "runtime-heartbeat",
                "task-ledger",
            ],
        )

    def test_stale_heartbeat_is_offline_not_available(
        self,
    ) -> None:
        self.service.record_heartbeat(
            AgentHeartbeat(
                agent_id="coding-agent",
                worker_id="worker-02",
                status="available",
                observed_at=(
                    FIXED_NOW
                    - timedelta(seconds=91)
                ),
            )
        )

        state = self.service.get_agent_state(
            "coding-agent"
        )

        self.assertEqual(state.runtime_status, "offline")
        self.assertEqual(state.heartbeat_age_seconds, 91.0)

    def test_unknown_agent_heartbeat_is_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            KeyError,
            "Unknown agent",
        ):
            self.service.record_heartbeat(
                AgentHeartbeat(
                    agent_id="missing-agent",
                    worker_id="worker-03",
                    status="available",
                    observed_at=FIXED_NOW,
                )
            )

    def test_task_ledger_is_durable_and_filterable(
        self,
    ) -> None:
        task = TaskLedgerRecord(
            task_id="task-001",
            task_type="agent",
            objective="Investigate dashboard latency.",
            status="running",
            priority="high",
            requested_by="owner",
            assigned_agent_ids=["research-agent"],
            current_step="Reviewing evidence",
            progress_percent=45.0,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
            started_at=FIXED_NOW,
        )

        stored = self.service.upsert_task(task)
        response = self.service.list_tasks(
            status="running"
        )

        self.assertEqual(stored.task_id, "task-001")
        self.assertEqual(response.total, 1)
        self.assertEqual(response.tasks[0].status, "running")
        self.assertEqual(
            response.tasks[0].assigned_agent_ids,
            ["research-agent"],
        )
        self.assertEqual(
            self.service.get_task("task-001").current_step,
            "Reviewing evidence",
        )

    def test_task_rejects_unknown_assigned_agent(
        self,
    ) -> None:
        task = TaskLedgerRecord(
            task_id="task-002",
            task_type="agent",
            objective="Run an unsupported task.",
            status="created",
            requested_by="owner",
            assigned_agent_ids=["missing-agent"],
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )

        with self.assertRaisesRegex(
            KeyError,
            "Unknown assigned agents",
        ):
            self.service.upsert_task(task)


if __name__ == "__main__":
    unittest.main()
