from typing import Protocol

from agents.cancellation import CancellationCheck
from agents.runtime_instrumentation import (
    AgentExecutionContext,
    InstrumentedAgentExecutor,
    RuntimeInstrumentation,
)
from agents.schemas import AgentRunRequest, AgentRunResponse
from agents.truth_schemas import AgentHeartbeat, TaskLedgerRecord
from agents.truth_service import agent_truth_service


class ExistingTaskExecutionError(RuntimeError):
    """Raised when a reserved task cannot enter bounded execution."""


class ExistingTaskTruthWriterProtocol(Protocol):
    def get_task(self, task_id: str) -> TaskLedgerRecord: ...

    def upsert_task(
        self,
        task: TaskLedgerRecord,
    ) -> TaskLedgerRecord: ...

    def record_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeat: ...


class _ExistingTaskTruthWriter:
    def __init__(
        self,
        truth_service: ExistingTaskTruthWriterProtocol,
        *,
        task_id: str,
        delegation_id: str,
    ) -> None:
        self.truth_service = truth_service
        self.task_id = task_id
        self.delegation_id = delegation_id

    def upsert_task(
        self,
        task: TaskLedgerRecord,
    ) -> TaskLedgerRecord:
        if task.task_id != self.task_id:
            raise ExistingTaskExecutionError(
                "Instrumented execution attempted to mutate a different task."
            )

        existing = self.truth_service.get_task(self.task_id)

        if task.status in {"created", "assigned"}:
            return existing

        if existing.source_run_id != self.delegation_id:
            raise ExistingTaskExecutionError(
                "The existing task lost its delegation identity during execution."
            )

        lifecycle_update = {
            "status": task.status,
            "current_step": task.current_step,
            "progress_percent": task.progress_percent,
            "error": task.error,
            "updated_at": task.updated_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }
        preserved = existing.model_copy(update=lifecycle_update)
        return self.truth_service.upsert_task(preserved)

    def record_heartbeat(
        self,
        heartbeat: AgentHeartbeat,
    ) -> AgentHeartbeat:
        return self.truth_service.record_heartbeat(heartbeat)


class ExecutiveExistingTaskRunner:
    def __init__(
        self,
        executor: InstrumentedAgentExecutor,
        *,
        truth_service: ExistingTaskTruthWriterProtocol = agent_truth_service,
    ) -> None:
        self.executor = executor
        self.truth_service = truth_service

    async def run(
        self,
        *,
        request: AgentRunRequest,
        task: TaskLedgerRecord,
        delegation_id: str,
        cancellation_check: CancellationCheck | None = None,
    ) -> AgentRunResponse:
        current_task = self.truth_service.get_task(task.task_id)
        self._validate_request(
            request=request,
            task=current_task,
            delegation_id=delegation_id,
        )
        writer = _ExistingTaskTruthWriter(
            self.truth_service,
            task_id=current_task.task_id,
            delegation_id=delegation_id,
        )
        runtime = RuntimeInstrumentation(writer)
        instrumented = InstrumentedAgentExecutor(
            self.executor.executor,
            runtime,
            heartbeat_interval_seconds=(
                self.executor.heartbeat_interval_seconds
            ),
        )
        return await instrumented.run(
            request,
            context=AgentExecutionContext(
                task_id=current_task.task_id,
                parent_task_id=current_task.parent_task_id,
                requested_by=current_task.requested_by,
                objective=current_task.objective,
            ),
            cancellation_check=cancellation_check,
        )

    @staticmethod
    def _validate_request(
        *,
        request: AgentRunRequest,
        task: TaskLedgerRecord,
        delegation_id: str,
    ) -> None:
        if task.status != "queued":
            raise ExistingTaskExecutionError(
                f"Task {task.task_id} is {task.status}, not queued."
            )
        if task.source_run_id != delegation_id:
            raise ExistingTaskExecutionError(
                "The queued task is not linked to the execution delegation."
            )
        if len(task.assigned_agent_ids) != 1:
            raise ExistingTaskExecutionError(
                "A queued execution task must have exactly one assigned agent."
            )

        assigned_agent_id = task.assigned_agent_ids[0]

        if request.agent_id != assigned_agent_id:
            raise ExistingTaskExecutionError(
                "The requested agent does not match the queued task assignment."
            )
        if request.mode != "manual":
            raise ExistingTaskExecutionError(
                "Executive execution requires deterministic manual routing."
            )
        if request.objective != task.objective:
            raise ExistingTaskExecutionError(
                "The execution objective does not match the queued task."
            )
