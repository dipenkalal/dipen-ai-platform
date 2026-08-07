import json
from typing import cast

from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from agents.truth_service import AgentTruthService, agent_truth_service
from executive_office.execution_cancellation_repository import (
    ExecutiveExecutionCancellationRepository,
    executive_execution_cancellation_repository,
)
from executive_office.execution_start_schemas import (
    ExecutionStatusState,
    ExecutiveExecutionStartResponse,
    ExecutiveExecutionStatusResponse,
)


class ExecutiveExecutionStatusService:
    def __init__(
        self,
        *,
        truth_service: AgentTruthService = agent_truth_service,
        truth_repository: AgentTruthRepository = agent_truth_repository,
        cancellation_repository: ExecutiveExecutionCancellationRepository = (
            executive_execution_cancellation_repository
        ),
    ) -> None:
        self.truth_service = truth_service
        self.truth_repository = truth_repository
        self.cancellation_repository = cancellation_repository

    def get(self, execution_id: str) -> ExecutiveExecutionStatusResponse:
        with self.truth_repository.connection() as connection:
            record = connection.execute(
                """
                SELECT
                    delegation_id,
                    parent_task_id,
                    child_task_ids_json,
                    state
                FROM executive_execution_records
                WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()

            if record is None:
                raise KeyError(f"Unknown execution: {execution_id}")

            reservations = connection.execute(
                """
                SELECT reservation_id
                FROM executive_execution_reservations
                WHERE execution_id = ? AND released_at IS NULL
                ORDER BY reservation_id
                """,
                (execution_id,),
            ).fetchall()
            start_row = connection.execute(
                """
                SELECT response_json
                FROM executive_execution_starts
                WHERE execution_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (execution_id,),
            ).fetchone()

        child_task_ids = [
            str(item)
            for item in json.loads(str(record["child_task_ids_json"]))
        ]
        parent_task = self.truth_service.get_task(str(record["parent_task_id"]))
        child_tasks = [self.truth_service.get_task(task_id) for task_id in child_task_ids]
        task_results = []
        acceptance_evidence = []

        if start_row is not None and start_row["response_json"] is not None:
            stored = ExecutiveExecutionStartResponse.model_validate_json(
                str(start_row["response_json"])
            )
            task_results = stored.task_results
            acceptance_evidence = stored.acceptance_evidence

        return ExecutiveExecutionStatusResponse(
            execution_id=execution_id,
            delegation_id=str(record["delegation_id"]),
            state=cast(ExecutionStatusState, str(record["state"])),
            parent_task=parent_task,
            child_tasks=child_tasks,
            active_reservation_ids=[str(row["reservation_id"]) for row in reservations],
            task_results=task_results,
            acceptance_evidence=acceptance_evidence,
            cancellation=self.cancellation_repository.get_for_execution(execution_id),
            broker_activated=False,
        )


executive_execution_status_service = ExecutiveExecutionStatusService()
