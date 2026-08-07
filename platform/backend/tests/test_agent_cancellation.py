import unittest
from datetime import datetime, timezone

from agents.cancellation import (
    CooperativeCancellationRequested,
    raise_if_cancellation_requested,
)
from agents.runtime_instrumentation import (
    AgentExecutionContext,
    InstrumentedAgentExecutor,
    RuntimeInstrumentation,
)
from agents.schemas import AgentRunRequest, AgentRunResponse
from agents.truth_schemas import AgentHeartbeat, TaskLedgerRecord


class AgentCancellationProbeTests(unittest.TestCase):
    def test_missing_probe_is_noop(self) -> None:
        raise_if_cancellation_requested(
            None,
            boundary="before-dispatch",
        )

    def test_false_probe_is_noop(self) -> None:
        raise_if_cancellation_requested(
            lambda: False,
            boundary="before-dispatch",
        )

    def test_true_probe_raises_dedicated_exception(self) -> None:
        with self.assertRaises(CooperativeCancellationRequested) as context:
            raise_if_cancellation_requested(
                lambda: True,
                boundary="before-tool-call",
            )

        self.assertEqual(context.exception.boundary, "before-tool-call")
        self.assertIn("before-tool-call", str(context.exception))


class RecordingTruthWriter:
    def __init__(self) -> None:
        self.tasks: list[TaskLedgerRecord] = []
        self.heartbeats: list[AgentHeartbeat] = []

    def upsert_task(self, task: TaskLedgerRecord) -> TaskLedgerRecord:
        stored = task.model_copy(deep=True)
        self.tasks.append(stored)
        return stored

    def record_heartbeat(self, heartbeat: AgentHeartbeat) -> AgentHeartbeat:
        stored = heartbeat.model_copy(deep=True)
        self.heartbeats.append(stored)
        return stored


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, request: AgentRunRequest) -> AgentRunResponse:
        self.calls += 1
        raise AssertionError(
            f"Raw executor must not run after cancellation: {request.objective}"
        )


class AgentCancellationRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_probe_cancels_task_before_raw_dispatch(self) -> None:
        writer = RecordingTruthWriter()
        raw_executor = RecordingExecutor()
        runtime = RuntimeInstrumentation(
            writer,
            now_provider=lambda: datetime.now(timezone.utc),
            worker_id_provider=lambda: "test-worker",
            process_id_provider=lambda: 1234,
            container_id_provider=lambda: None,
        )
        executor = InstrumentedAgentExecutor(
            raw_executor,
            runtime,
            heartbeat_interval_seconds=60.0,
        )
        request = AgentRunRequest(
            mode="manual",
            agent_id="coding-agent",
            objective="Do not dispatch this cancelled task.",
        )

        with self.assertRaises(CooperativeCancellationRequested) as context:
            await executor.run(
                request,
                context=AgentExecutionContext(
                    task_id="task-cancel-runtime-001",
                    parent_task_id="parent-cancel-runtime-001",
                    requested_by="dipen-owner",
                ),
                cancellation_check=lambda: True,
            )

        self.assertEqual(context.exception.boundary, "before-agent-dispatch")
        self.assertEqual(raw_executor.calls, 0)
        self.assertEqual(
            [task.status for task in writer.tasks],
            ["created", "assigned", "running", "cancelled"],
        )
        self.assertEqual(
            writer.tasks[-1].current_step,
            "Agent execution observed cooperative cancellation",
        )
        self.assertIn(
            "before-agent-dispatch",
            writer.tasks[-1].error or "",
        )
        self.assertEqual(
            [heartbeat.status for heartbeat in writer.heartbeats],
            ["busy", "available"],
        )


if __name__ == "__main__":
    unittest.main()
