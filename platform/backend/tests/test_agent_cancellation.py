import unittest
from datetime import datetime, timezone
from typing import Any

from agents.cancellation import (
    CooperativeCancellationRequested,
    cancellation_scope,
    raise_if_cancellation_requested,
    raise_if_current_cancellation_requested,
)
from agents.runtime_instrumentation import (
    AgentExecutionContext,
    InstrumentedAgentExecutor,
    RuntimeInstrumentation,
)
from agents.schemas import AgentRunRequest, AgentRunResponse
from agents.truth_schemas import AgentHeartbeat, TaskLedgerRecord
from gateway.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    UsageMetrics,
)
from gateway.service import GatewayService
from tools.base import BaseTool, ToolDefinition, ToolExecutionResult
from tools.registry import ToolRegistry


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

    def test_cancellation_scope_resets_context(self) -> None:
        with (
            cancellation_scope(lambda: True),
            self.assertRaises(CooperativeCancellationRequested),
        ):
            raise_if_current_cancellation_requested(
                boundary="inside-scope"
            )

        raise_if_current_cancellation_requested(
            boundary="after-scope"
        )


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


class FakeOllama:
    def __init__(self, cancellation_state: dict[str, bool]) -> None:
        self.cancellation_state = cancellation_state
        self.chat_calls = 0

    async def health(self) -> bool:
        return True

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.chat_calls += 1
        self.cancellation_state["requested"] = True
        return ChatResponse(
            provider="ollama",
            model=request.model or "test-model",
            message=ChatMessage(role="assistant", content="finished model call"),
            usage=UsageMetrics(latency_ms=1.0),
        )


class GatewayCancellationBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_during_model_call_is_observed_after_return(self) -> None:
        cancellation_state = {"requested": False}
        service = GatewayService()
        fake_ollama = FakeOllama(cancellation_state)
        service.ollama = fake_ollama
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="run bounded model work")],
            model="test-model",
        )

        with (
            cancellation_scope(lambda: cancellation_state["requested"]),
            self.assertRaises(CooperativeCancellationRequested) as context,
        ):
            await service.chat(request)

        self.assertEqual(fake_ollama.chat_calls, 1)
        self.assertEqual(context.exception.boundary, "after-model-call")


class FakeTool(BaseTool):
    definition = ToolDefinition(
        id="test.cancellable",
        name="Cancellable test tool",
        description="Test cooperative cancellation around a tool call.",
        category="test",
    )

    def __init__(
        self,
        cancellation_state: dict[str, bool],
        *,
        request_during_call: bool,
    ) -> None:
        self.cancellation_state = cancellation_state
        self.request_during_call = request_during_call
        self.calls = 0

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        self.calls += 1
        if self.request_during_call:
            self.cancellation_state["requested"] = True
        return ToolExecutionResult(
            tool_id=self.definition.id,
            success=True,
            output=arguments,
        )


class ToolCancellationBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_requested_cancellation_prevents_tool_start(self) -> None:
        cancellation_state = {"requested": True}
        registry = ToolRegistry()
        tool = FakeTool(cancellation_state, request_during_call=False)
        registry.register(tool)

        with (
            cancellation_scope(lambda: cancellation_state["requested"]),
            self.assertRaises(CooperativeCancellationRequested) as context,
        ):
            await registry.get(tool.definition.id).execute({"value": 1})

        self.assertEqual(tool.calls, 0)
        self.assertEqual(context.exception.boundary, "before-tool-call")

    async def test_cancellation_during_tool_is_observed_after_return(self) -> None:
        cancellation_state = {"requested": False}
        registry = ToolRegistry()
        tool = FakeTool(cancellation_state, request_during_call=True)
        registry.register(tool)

        with (
            cancellation_scope(lambda: cancellation_state["requested"]),
            self.assertRaises(CooperativeCancellationRequested) as context,
        ):
            await registry.get(tool.definition.id).execute({"value": 1})

        self.assertEqual(tool.calls, 1)
        self.assertEqual(context.exception.boundary, "after-tool-call")


if __name__ == "__main__":
    unittest.main()
