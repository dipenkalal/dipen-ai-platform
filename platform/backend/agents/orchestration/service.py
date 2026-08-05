from agents.orchestration.executor import (
    orchestration_executor,
)
from agents.orchestration.planner import (
    orchestration_planner,
)
from agents.orchestration.schemas import (
    OrchestrationPlan,
    OrchestrationPlanRequest,
    OrchestrationRunResponse,
)
from agents.runtime_instrumentation import (
    runtime_instrumentation,
)
from history.orchestration_service import (
    orchestration_history_service,
)


class OrchestrationService:
    def create_plan(
        self,
        request: OrchestrationPlanRequest,
    ) -> OrchestrationPlan:
        return orchestration_planner.plan(
            request,
        )

    async def run(
        self,
        request: OrchestrationPlanRequest,
    ) -> OrchestrationRunResponse:
        plan = self.create_plan(
            request,
        )
        task_handle = (
            runtime_instrumentation.start_task(
                task_type="orchestration",
                objective=request.objective,
                requested_by="orchestration-api",
                assigned_agent_ids=(
                    plan.selected_agent_ids
                ),
                current_step=(
                    "Executing orchestration plan"
                ),
            )
        )

        try:
            response = await orchestration_executor.run(
                request=request,
                plan=plan,
                parent_task_id=task_handle.task_id,
            )
        except Exception as exc:
            runtime_instrumentation.finish_task(
                task_handle,
                status="failed",
                current_step=(
                    "Orchestration execution raised "
                    "an error"
                ),
                error=str(exc),
            )
            raise

        runtime_instrumentation.finish_task(
            task_handle,
            status=(
                "completed"
                if response.status == "completed"
                else "failed"
            ),
            source_run_id=(
                response.orchestration_run_id
            ),
            current_step=(
                "Orchestration completed"
                if response.status == "completed"
                else "Orchestration failed"
            ),
            error=response.error,
        )

        orchestration_history_service.save(
            response,
        )

        return response


orchestration_service = OrchestrationService()
