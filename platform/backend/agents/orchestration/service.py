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

        response = await orchestration_executor.run(
            request=request,
            plan=plan,
        )

        orchestration_history_service.save(
            response,
        )

        return response


orchestration_service = OrchestrationService()
