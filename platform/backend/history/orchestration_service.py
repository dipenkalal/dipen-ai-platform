from fastapi import HTTPException

from agents.orchestration.schemas import (
    OrchestrationRunResponse,
)
from history.orchestration_repository import (
    orchestration_run_repository,
)
from history.orchestration_schemas import (
    OrchestrationRunClearResponse,
    OrchestrationRunDeleteResponse,
    OrchestrationRunListResponse,
    OrchestrationRunRecord,
)


class OrchestrationHistoryService:
    def save(
        self,
        response: OrchestrationRunResponse,
    ) -> OrchestrationRunRecord:
        try:
            return orchestration_run_repository.save(
                response,
            )
        except Exception as exc:
            raise RuntimeError(f"Unable to persist orchestration run: {exc}") from exc

    def get(
        self,
        run_id: str,
    ) -> OrchestrationRunRecord:
        record = orchestration_run_repository.get(
            run_id,
        )

        if record is None:
            raise HTTPException(
                status_code=404,
                detail=(f"Orchestration run was not found: {run_id}"),
            )

        return record

    def list_runs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        execution_mode: str | None = None,
        lead_agent_id: str | None = None,
        validation_status: str | None = None,
        search: str | None = None,
    ) -> OrchestrationRunListResponse:
        runs, total = orchestration_run_repository.list(
            limit=limit,
            offset=offset,
            status=status,
            execution_mode=execution_mode,
            lead_agent_id=lead_agent_id,
            validation_status=validation_status,
            search=search,
        )

        return OrchestrationRunListResponse(
            runs=runs,
            total=total,
            limit=limit,
            offset=offset,
        )

    def delete(
        self,
        run_id: str,
    ) -> OrchestrationRunDeleteResponse:
        deleted = orchestration_run_repository.delete(
            run_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=(f"Orchestration run was not found: {run_id}"),
            )

        return OrchestrationRunDeleteResponse(
            deleted=True,
            run_id=run_id,
        )

    def clear(
        self,
    ) -> OrchestrationRunClearResponse:
        deleted_count = orchestration_run_repository.clear()

        return OrchestrationRunClearResponse(
            deleted_count=deleted_count,
        )


orchestration_history_service = OrchestrationHistoryService()
