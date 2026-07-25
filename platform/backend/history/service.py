from fastapi import HTTPException

from agents.schemas import (
    AgentRunRequest,
    AgentRunResponse,
)
from history.repository import (
    agent_run_repository,
)
from history.schemas import (
    AgentRunClearResponse,
    AgentRunDeleteResponse,
    AgentRunListResponse,
    AgentRunRecord,
)


class AgentRunHistoryService:
    def save(
        self,
        request: AgentRunRequest,
        response: AgentRunResponse,
        error: str | None = None,
    ) -> AgentRunRecord:
        return agent_run_repository.save(
            request=request,
            response=response,
            error=error,
        )

    def get(
        self,
        run_id: str,
    ) -> AgentRunRecord:
        record = agent_run_repository.get(
            run_id
        )

        if record is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Agent run '{run_id}' "
                    "was not found."
                ),
            )

        return record

    def list(
        self,
        *,
        limit: int,
        offset: int,
        agent_id: str | None,
        status: str | None,
        model: str | None,
        search: str | None,
    ) -> AgentRunListResponse:
        runs, total = agent_run_repository.list(
            limit=limit,
            offset=offset,
            agent_id=agent_id,
            status=status,
            model=model,
            search=search,
        )

        return AgentRunListResponse(
            runs=runs,
            total=total,
            limit=limit,
            offset=offset,
        )

    def delete(
        self,
        run_id: str,
    ) -> AgentRunDeleteResponse:
        deleted = agent_run_repository.delete(
            run_id
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Agent run '{run_id}' "
                    "was not found."
                ),
            )

        return AgentRunDeleteResponse(
            deleted=True,
            run_id=run_id,
        )

    def clear(
        self,
    ) -> AgentRunClearResponse:
        deleted_count = (
            agent_run_repository.clear()
        )

        return AgentRunClearResponse(
            deleted_count=deleted_count
        )


agent_run_history_service = (
    AgentRunHistoryService()
)
