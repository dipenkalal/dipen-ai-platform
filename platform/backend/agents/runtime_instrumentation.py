import asyncio
import logging
import os
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from agents.executor import agent_executor
from agents.schemas import AgentRunRequest, AgentRunResponse
from agents.truth_schemas import (
    AgentHeartbeat,
    HeartbeatStatus,
    TaskLedgerRecord,
    TaskLedgerStatus,
    TaskType,
)
from agents.truth_service import agent_truth_service

logger = logging.getLogger(__name__)


class AgentExecutorProtocol(Protocol):
    def run(
        self,
        request: AgentRunRequest,
    ) -> Awaitable[AgentRunResponse]: ...


class TruthWriterProtocol(Protocol):
    def upsert_task(
        self,
        task: TaskLedgerRecord,
    ) -> TaskLedgerRecord: ...

    def record_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeat: ...


@dataclass(frozen=True)
class AgentExecutionContext:
    task_id: str | None = None
    parent_task_id: str | None = None
    requested_by: str = "agent-api"
    objective: str | None = None


@dataclass(frozen=True)
class RuntimeTaskHandle:
    task_id: str
    task_type: TaskType
    objective: str
    requested_by: str
    assigned_agent_ids: tuple[str, ...]
    parent_task_id: str | None
    created_at: datetime
    started_at: datetime


@dataclass(frozen=True)
class ActiveAgentTask:
    task_id: str
    model: str | None
    started_at: datetime


class RuntimeInstrumentation:
    def __init__(
        self,
        truth_writer: TruthWriterProtocol,
        *,
        now_provider: Callable[[], datetime] | None = None,
        worker_id_provider: Callable[[], str] | None = None,
        process_id_provider: Callable[[], int] | None = None,
        container_id_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self.truth_writer = truth_writer
        self.now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )
        self.worker_id_provider = (
            worker_id_provider
            or self._default_worker_id
        )
        self.process_id_provider = (
            process_id_provider
            or os.getpid
        )
        self.container_id_provider = (
            container_id_provider
            or self._default_container_id
        )

    def start_task(
        self,
        *,
        task_type: TaskType,
        objective: str,
        requested_by: str,
        assigned_agent_ids: list[str],
        task_id: str | None = None,
        parent_task_id: str | None = None,
        current_step: str = "Starting task",
    ) -> RuntimeTaskHandle:
        created_at = self._now()
        handle = RuntimeTaskHandle(
            task_id=(
                task_id
                or f"{task_type}-task-{uuid4()}"
            ),
            task_type=task_type,
            objective=objective,
            requested_by=requested_by,
            assigned_agent_ids=tuple(
                assigned_agent_ids
            ),
            parent_task_id=parent_task_id,
            created_at=created_at,
            started_at=created_at,
        )

        self._write_task(
            handle,
            status="created",
            current_step="Task created",
            progress_percent=0.0,
        )
        self._write_task(
            handle,
            status="assigned",
            current_step=(
                "Assigned to "
                + ", ".join(assigned_agent_ids)
                if assigned_agent_ids
                else "Awaiting assignment"
            ),
            progress_percent=5.0,
        )
        self._write_task(
            handle,
            status="running",
            current_step=current_step,
            progress_percent=10.0,
        )

        return handle

    def finish_task(
        self,
        handle: RuntimeTaskHandle,
        *,
        status: TaskLedgerStatus,
        source_run_id: str | None = None,
        current_step: str | None = None,
        error: str | None = None,
    ) -> None:
        completed = status in {
            "completed",
            "failed",
            "cancelled",
        }
        progress_percent = (
            100.0
            if completed
            else None
        )

        if current_step is None:
            current_step = {
                "completed": "Task completed",
                "failed": "Task failed",
                "cancelled": "Task cancelled",
            }.get(status, "Task updated")

        self._write_task(
            handle,
            status=status,
            current_step=current_step,
            progress_percent=progress_percent,
            source_run_id=source_run_id,
            error=error,
            completed_at=(
                self._now()
                if completed
                else None
            ),
        )

    def record_agent_heartbeat(
        self,
        *,
        agent_id: str,
        status: HeartbeatStatus,
        current_task_id: str | None,
        model: str | None,
        active_task_ids: list[str],
    ) -> None:
        details = {
            "runtime": "dap-backend",
            "active_task_count": len(
                active_task_ids
            ),
            "active_task_ids": active_task_ids,
        }

        heartbeat = AgentHeartbeat(
            agent_id=agent_id,
            worker_id=self.worker_id_provider(),
            status=status,
            current_task_id=current_task_id,
            model=model,
            process_id=self.process_id_provider(),
            container_id=self.container_id_provider(),
            details=details,
            observed_at=self._now(),
        )

        try:
            self.truth_writer.record_heartbeat(
                heartbeat
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Runtime heartbeat write failed.",
                exc_info=True,
            )

    def _write_task(
        self,
        handle: RuntimeTaskHandle,
        *,
        status: TaskLedgerStatus,
        current_step: str,
        progress_percent: float | None,
        source_run_id: str | None = None,
        error: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        task = TaskLedgerRecord(
            task_id=handle.task_id,
            task_type=handle.task_type,
            objective=handle.objective,
            status=status,
            priority="normal",
            requested_by=handle.requested_by,
            assigned_agent_ids=list(
                handle.assigned_agent_ids
            ),
            source_run_id=source_run_id,
            parent_task_id=handle.parent_task_id,
            current_step=current_step,
            progress_percent=progress_percent,
            error=error,
            created_at=handle.created_at,
            updated_at=self._now(),
            started_at=handle.started_at,
            completed_at=completed_at,
        )

        try:
            self.truth_writer.upsert_task(task)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Runtime task-ledger write failed.",
                exc_info=True,
            )

    def _now(self) -> datetime:
        value = self.now_provider()

        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(timezone.utc)

    @staticmethod
    def _default_worker_id() -> str:
        return (
            "dap-backend:"
            f"{socket.gethostname()}:"
            f"{os.getpid()}"
        )

    @staticmethod
    def _default_container_id() -> str | None:
        return os.getenv(
            "DAP_RUNTIME_CONTAINER_ID"
        )


class InstrumentedAgentExecutor:
    def __init__(
        self,
        executor: AgentExecutorProtocol,
        runtime: RuntimeInstrumentation,
        *,
        heartbeat_interval_seconds: float = 30.0,
    ) -> None:
        self.executor = executor
        self.runtime = runtime
        self.heartbeat_interval_seconds = (
            heartbeat_interval_seconds
        )
        self._active_tasks: dict[
            str,
            dict[str, ActiveAgentTask],
        ] = {}
        self._active_tasks_lock = asyncio.Lock()

    async def run(
        self,
        request: AgentRunRequest,
        *,
        context: AgentExecutionContext | None = None,
    ) -> AgentRunResponse:
        agent_id = request.agent_id

        if agent_id is None:
            return await self.executor.run(request)

        execution_context = (
            context
            or AgentExecutionContext()
        )
        task_handle = self.runtime.start_task(
            task_type="agent",
            objective=(
                execution_context.objective
                or request.objective
            ),
            requested_by=(
                execution_context.requested_by
            ),
            assigned_agent_ids=[agent_id],
            task_id=execution_context.task_id,
            parent_task_id=(
                execution_context.parent_task_id
            ),
            current_step=(
                f"Running {agent_id}"
            ),
        )

        await self._activate_task(
            agent_id=agent_id,
            task_id=task_handle.task_id,
            model=request.model,
            started_at=task_handle.started_at,
        )

        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(agent_id)
        )

        try:
            response = await self.executor.run(
                request
            )

            if response.status == "completed":
                self.runtime.finish_task(
                    task_handle,
                    status="completed",
                    source_run_id=response.run_id,
                    current_step=(
                        "Agent execution completed"
                    ),
                )
            else:
                self.runtime.finish_task(
                    task_handle,
                    status="failed",
                    source_run_id=response.run_id,
                    current_step=(
                        "Agent execution failed"
                    ),
                    error=response.answer,
                )

            return response

        except asyncio.CancelledError:
            self.runtime.finish_task(
                task_handle,
                status="cancelled",
                current_step=(
                    "Agent execution cancelled"
                ),
                error="Execution cancelled.",
            )
            raise

        except Exception as exc:
            self.runtime.finish_task(
                task_handle,
                status="failed",
                current_step=(
                    "Agent execution raised an error"
                ),
                error=str(exc),
            )
            raise

        finally:
            heartbeat_task.cancel()

            with suppress(
                asyncio.CancelledError
            ):
                await heartbeat_task

            await self._deactivate_task(
                agent_id=agent_id,
                task_id=task_handle.task_id,
            )

    async def _activate_task(
        self,
        *,
        agent_id: str,
        task_id: str,
        model: str | None,
        started_at: datetime,
    ) -> None:
        async with self._active_tasks_lock:
            tasks = self._active_tasks.setdefault(
                agent_id,
                {},
            )
            tasks[task_id] = ActiveAgentTask(
                task_id=task_id,
                model=model,
                started_at=started_at,
            )

        await self._refresh_agent_heartbeat(
            agent_id
        )

    async def _deactivate_task(
        self,
        *,
        agent_id: str,
        task_id: str,
    ) -> None:
        async with self._active_tasks_lock:
            tasks = self._active_tasks.get(
                agent_id,
                {},
            )
            tasks.pop(task_id, None)

            if not tasks:
                self._active_tasks.pop(
                    agent_id,
                    None,
                )

        await self._refresh_agent_heartbeat(
            agent_id
        )

    async def _heartbeat_loop(
        self,
        agent_id: str,
    ) -> None:
        while True:
            await asyncio.sleep(
                self.heartbeat_interval_seconds
            )
            await self._refresh_agent_heartbeat(
                agent_id
            )

    async def _refresh_agent_heartbeat(
        self,
        agent_id: str,
    ) -> None:
        async with self._active_tasks_lock:
            active = list(
                self._active_tasks.get(
                    agent_id,
                    {},
                ).values()
            )

        if active:
            selected = max(
                active,
                key=lambda item: item.started_at,
            )
            self.runtime.record_agent_heartbeat(
                agent_id=agent_id,
                status="busy",
                current_task_id=selected.task_id,
                model=selected.model,
                active_task_ids=sorted(
                    item.task_id
                    for item in active
                ),
            )
            return

        self.runtime.record_agent_heartbeat(
            agent_id=agent_id,
            status="available",
            current_task_id=None,
            model=None,
            active_task_ids=[],
        )


runtime_instrumentation = RuntimeInstrumentation(
    agent_truth_service
)

instrumented_agent_executor = InstrumentedAgentExecutor(
    agent_executor,
    runtime_instrumentation,
)
