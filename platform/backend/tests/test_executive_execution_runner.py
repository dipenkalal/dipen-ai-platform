import unittest
from datetime import datetime, timezone

from agents.runtime_instrumentation import (
    InstrumentedAgentExecutor,
    RuntimeInstrumentation,
)
from agents.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentUsage,
)
from agents.truth_schemas import AgentHeartbeat, TaskLedgerRecord
from executive_office.execution_runner import (
    ExecutiveExistingTaskRunner,
    ExistingTaskExecutionError,
)


class RecordingTruthService:
    def __init__(self, task: TaskLedgerRecord) -> None:
        self.tasks = {task.task_id: task}
        self.task_writes: list[TaskLedgerRecord] = []
        self.heartbeats: list[AgentHeartbeat] = []

    def get_task(self, task_id: str) -> TaskLedgerRecord:
        return self.tasks[task_id]

    def upsert_task(
        self,
        task: TaskLedgerRecord,
    ) -> TaskLedgerRecord:
        self.tasks[task.task_id] = task
        self.task_writes.append(task)
        return task

    def record_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeat:
        self.heartbeats.append(heartbeat)
        return heartbeat


class FakeAgentExecutor:
    def __init__(self, response: AgentRunResponse) -> None:
        self.response = response
        self.requests: list[AgentRunRequest] = []

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        self.requests.append(request)
        return self.response


class ExecutiveExistingTaskRunnerTests(unittest.IsolatedAsyncioTestCase):
    delegation_id = "executive-delegation-runner-tests"

    @staticmethod
    def queued_task() -> TaskLedgerRecord:
        created_at = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
        return TaskLedgerRecord(
            task_id="executive-child-runner-tests",
            task_type="agent",
            objective="Research storage upgrade options",
            status="queued",
            priority="high",
            requested_by="dipen-owner",
            assigned_agent_ids=["research-agent"],
            source_run_id=(
                ExecutiveExistingTaskRunnerTests.delegation_id
            ),
            parent_task_id="executive-parent-runner-tests",
            current_step="Reserved for owner-triggered execution",
            progress_percent=0.0,
            created_at=created_at,
            updated_at=created_at,
        )

    @staticmethod
    def response(
        *,
        status: str = "completed",
        answer: str = "Storage research completed.",
    ) -> AgentRunResponse:
        now = datetime.now(timezone.utc)
        return AgentRunResponse(
            run_id="agent-run-runner-tests",
            agent_id="research-agent",
            objective="Research storage upgrade options",
            status=status,
            answer=answer,
            steps=[],
            usage=AgentUsage(latency_ms=1.0),
            started_at=now,
            completed_at=now,
        )

    @staticmethod
    def request(
        *,
        agent_id: str = "research-agent",
        mode: str = "manual",
        objective: str = "Research storage upgrade options",
    ) -> AgentRunRequest:
        return AgentRunRequest(
            mode=mode,
            agent_id=agent_id,
            objective=objective,
        )

    @staticmethod
    def runner(
        *,
        truth: RecordingTruthService,
        raw_executor: FakeAgentExecutor,
    ) -> ExecutiveExistingTaskRunner:
        instrumented = InstrumentedAgentExecutor(
            raw_executor,
            RuntimeInstrumentation(truth),
            heartbeat_interval_seconds=60.0,
        )
        return ExecutiveExistingTaskRunner(
            instrumented,
            truth_service=truth,
        )

    async def test_completed_run_preserves_identity_and_heartbeats(self) -> None:
        original = self.queued_task()
        truth = RecordingTruthService(original)
        raw_executor = FakeAgentExecutor(self.response())
        runner = self.runner(
            truth=truth,
            raw_executor=raw_executor,
        )

        response = await runner.run(
            request=self.request(),
            task=original,
            delegation_id=self.delegation_id,
        )

        self.assertEqual(response.status, "completed")
        self.assertEqual(len(raw_executor.requests), 1)
        self.assertEqual(
            [task.status for task in truth.task_writes],
            ["running", "completed"],
        )
        final = truth.get_task(original.task_id)
        self.assertEqual(final.status, "completed")
        self.assertEqual(final.source_run_id, self.delegation_id)
        self.assertEqual(final.created_at, original.created_at)
        self.assertEqual(final.priority, original.priority)
        self.assertEqual(final.objective, original.objective)
        self.assertEqual(
            final.assigned_agent_ids,
            original.assigned_agent_ids,
        )
        self.assertEqual(final.parent_task_id, original.parent_task_id)
        self.assertEqual(
            [heartbeat.status for heartbeat in truth.heartbeats],
            ["busy", "available"],
        )
        self.assertEqual(
            truth.heartbeats[0].current_task_id,
            original.task_id,
        )
        self.assertIsNone(truth.heartbeats[-1].current_task_id)

    async def test_failed_result_writes_failed_terminal_state(self) -> None:
        original = self.queued_task()
        truth = RecordingTruthService(original)
        raw_executor = FakeAgentExecutor(
            self.response(
                status="failed",
                answer="Research provider failed.",
            )
        )
        runner = self.runner(
            truth=truth,
            raw_executor=raw_executor,
        )

        response = await runner.run(
            request=self.request(),
            task=original,
            delegation_id=self.delegation_id,
        )

        self.assertEqual(response.status, "failed")
        self.assertEqual(
            [task.status for task in truth.task_writes],
            ["running", "failed"],
        )
        final = truth.get_task(original.task_id)
        self.assertEqual(final.status, "failed")
        self.assertEqual(final.error, "Research provider failed.")
        self.assertEqual(final.source_run_id, self.delegation_id)
        self.assertEqual(
            [heartbeat.status for heartbeat in truth.heartbeats],
            ["busy", "available"],
        )

    async def test_nonqueued_task_is_rejected_before_executor(self) -> None:
        task = self.queued_task().model_copy(
            update={"status": "running"}
        )
        truth = RecordingTruthService(task)
        raw_executor = FakeAgentExecutor(self.response())
        runner = self.runner(
            truth=truth,
            raw_executor=raw_executor,
        )

        with self.assertRaises(ExistingTaskExecutionError):
            await runner.run(
                request=self.request(),
                task=task,
                delegation_id=self.delegation_id,
            )

        self.assertEqual(raw_executor.requests, [])
        self.assertEqual(truth.task_writes, [])
        self.assertEqual(truth.heartbeats, [])

    async def test_agent_mismatch_is_rejected_before_executor(self) -> None:
        task = self.queued_task()
        truth = RecordingTruthService(task)
        raw_executor = FakeAgentExecutor(self.response())
        runner = self.runner(
            truth=truth,
            raw_executor=raw_executor,
        )

        with self.assertRaises(ExistingTaskExecutionError):
            await runner.run(
                request=self.request(agent_id="system-agent"),
                task=task,
                delegation_id=self.delegation_id,
            )

        self.assertEqual(raw_executor.requests, [])
        self.assertEqual(truth.task_writes, [])
        self.assertEqual(truth.heartbeats, [])

    async def test_smart_routing_is_rejected_before_executor(self) -> None:
        task = self.queued_task()
        truth = RecordingTruthService(task)
        raw_executor = FakeAgentExecutor(self.response())
        runner = self.runner(
            truth=truth,
            raw_executor=raw_executor,
        )

        with self.assertRaises(ExistingTaskExecutionError):
            await runner.run(
                request=self.request(mode="smart"),
                task=task,
                delegation_id=self.delegation_id,
            )

        self.assertEqual(raw_executor.requests, [])
        self.assertEqual(truth.task_writes, [])
        self.assertEqual(truth.heartbeats, [])


if __name__ == "__main__":
    unittest.main()
