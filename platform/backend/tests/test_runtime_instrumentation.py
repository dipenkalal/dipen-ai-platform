import asyncio
import unittest
from datetime import datetime, timedelta, timezone

from agents.runtime_instrumentation import (
    AgentExecutionContext,
    InstrumentedAgentExecutor,
    RuntimeInstrumentation,
)
from agents.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentUsage,
)
from agents.truth_schemas import (
    AgentHeartbeat,
    TaskLedgerRecord,
)


class StepClock:
    def __init__(self) -> None:
        self.current = datetime(
            2026,
            8,
            5,
            18,
            0,
            tzinfo=timezone.utc,
        )

    def __call__(self) -> datetime:
        value = self.current
        self.current += timedelta(
            milliseconds=10
        )
        return value


class RecordingTruthWriter:
    def __init__(
        self,
        *,
        fail_writes: bool = False,
    ) -> None:
        self.fail_writes = fail_writes
        self.tasks: list[TaskLedgerRecord] = []
        self.heartbeats: list[AgentHeartbeat] = []

    def upsert_task(
        self,
        task: TaskLedgerRecord,
    ) -> TaskLedgerRecord:
        if self.fail_writes:
            raise RuntimeError(
                "task write unavailable"
            )

        stored = task.model_copy(deep=True)
        self.tasks.append(stored)
        return stored

    def record_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeat:
        if self.fail_writes:
            raise RuntimeError(
                "heartbeat write unavailable"
            )

        stored = heartbeat.model_copy(
            deep=True
        )
        self.heartbeats.append(stored)
        return stored


class FakeExecutor:
    def __init__(
        self,
        *,
        status: str = "completed",
        delay_seconds: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.delay_seconds = delay_seconds
        self.error = error

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        if self.delay_seconds:
            await asyncio.sleep(
                self.delay_seconds
            )

        if self.error is not None:
            raise self.error

        now = datetime.now(timezone.utc)

        return AgentRunResponse(
            run_id="run-001",
            agent_id=request.agent_id or "",
            objective=request.objective,
            status=self.status,
            answer=(
                "Completed."
                if self.status == "completed"
                else "Execution failed."
            ),
            steps=[],
            usage=AgentUsage(),
            started_at=now,
            completed_at=now,
        )


class RuntimeInstrumentationTestCase(
    unittest.IsolatedAsyncioTestCase
):
    def setUp(self) -> None:
        self.clock = StepClock()
        self.writer = RecordingTruthWriter()
        self.runtime = RuntimeInstrumentation(
            self.writer,
            now_provider=self.clock,
            worker_id_provider=(
                lambda: "backend-worker-01"
            ),
            process_id_provider=lambda: 4242,
            container_id_provider=lambda: None,
        )

    async def test_completed_agent_run_writes_lifecycle_and_heartbeats(
        self,
    ) -> None:
        executor = InstrumentedAgentExecutor(
            FakeExecutor(
                delay_seconds=0.035
            ),
            self.runtime,
            heartbeat_interval_seconds=0.01,
        )
        request = AgentRunRequest(
            agent_id="coding-agent",
            objective="Review this module.",
            model="qwen3:1.7b",
        )

        response = await executor.run(
            request,
            context=AgentExecutionContext(
                task_id="task-agent-001",
                requested_by="test-suite",
            ),
        )

        self.assertEqual(
            response.status,
            "completed",
        )
        self.assertEqual(
            [
                task.status
                for task in self.writer.tasks
            ],
            [
                "created",
                "assigned",
                "running",
                "completed",
            ],
        )
        self.assertEqual(
            self.writer.tasks[-1].source_run_id,
            "run-001",
        )
        self.assertEqual(
            self.writer.tasks[-1].progress_percent,
            100.0,
        )
        self.assertEqual(
            self.writer.heartbeats[0].status,
            "busy",
        )
        self.assertEqual(
            self.writer.heartbeats[-1].status,
            "available",
        )
        self.assertGreaterEqual(
            sum(
                heartbeat.status == "busy"
                for heartbeat
                in self.writer.heartbeats
            ),
            2,
        )
        self.assertEqual(
            self.writer.heartbeats[0].process_id,
            4242,
        )
        self.assertEqual(
            self.writer.heartbeats[0].details[
                "active_task_count"
            ],
            1,
        )
        self.assertEqual(
            self.writer.heartbeats[-1].details[
                "active_task_count"
            ],
            0,
        )

    async def test_failed_agent_response_marks_task_failed(
        self,
    ) -> None:
        executor = InstrumentedAgentExecutor(
            FakeExecutor(status="failed"),
            self.runtime,
        )
        request = AgentRunRequest(
            agent_id="research-agent",
            objective="Research unavailable data.",
        )

        response = await executor.run(request)

        self.assertEqual(response.status, "failed")
        self.assertEqual(
            self.writer.tasks[-1].status,
            "failed",
        )
        self.assertEqual(
            self.writer.tasks[-1].error,
            "Execution failed.",
        )
        self.assertEqual(
            self.writer.heartbeats[-1].status,
            "available",
        )

    async def test_executor_exception_is_recorded_and_reraised(
        self,
    ) -> None:
        executor = InstrumentedAgentExecutor(
            FakeExecutor(
                error=RuntimeError(
                    "model unavailable"
                )
            ),
            self.runtime,
        )
        request = AgentRunRequest(
            agent_id="knowledge-agent",
            objective="Answer a question.",
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "model unavailable",
        ):
            await executor.run(request)

        self.assertEqual(
            self.writer.tasks[-1].status,
            "failed",
        )
        self.assertEqual(
            self.writer.tasks[-1].error,
            "model unavailable",
        )
        self.assertEqual(
            self.writer.heartbeats[-1].status,
            "available",
        )

    async def test_observability_failure_does_not_break_agent_run(
        self,
    ) -> None:
        failing_runtime = RuntimeInstrumentation(
            RecordingTruthWriter(
                fail_writes=True
            ),
            now_provider=self.clock,
            worker_id_provider=(
                lambda: "backend-worker-01"
            ),
        )
        executor = InstrumentedAgentExecutor(
            FakeExecutor(),
            failing_runtime,
        )
        request = AgentRunRequest(
            agent_id="documentation-agent",
            objective="Write a runbook.",
        )

        response = await executor.run(request)

        self.assertEqual(
            response.status,
            "completed",
        )

    def test_orchestration_parent_uses_same_task_lifecycle(
        self,
    ) -> None:
        handle = self.runtime.start_task(
            task_type="orchestration",
            objective="Coordinate agents.",
            requested_by="orchestration-api",
            assigned_agent_ids=[
                "research-agent",
                "documentation-agent",
            ],
            task_id="orchestration-task-001",
            current_step=(
                "Executing orchestration plan"
            ),
        )

        self.runtime.finish_task(
            handle,
            status="failed",
            source_run_id="orchestration-run-001",
            current_step="Orchestration failed",
            error="Synthesis failed.",
        )

        self.assertEqual(
            [
                task.status
                for task in self.writer.tasks
            ],
            [
                "created",
                "assigned",
                "running",
                "failed",
            ],
        )
        final_task = self.writer.tasks[-1]
        self.assertEqual(
            final_task.task_type,
            "orchestration",
        )
        self.assertEqual(
            final_task.source_run_id,
            "orchestration-run-001",
        )
        self.assertEqual(
            final_task.assigned_agent_ids,
            [
                "research-agent",
                "documentation-agent",
            ],
        )
        self.assertEqual(
            final_task.error,
            "Synthesis failed.",
        )


if __name__ == "__main__":
    unittest.main()
