import json
from collections.abc import AsyncIterator

from fastapi import HTTPException
from history.service import (
    agent_run_history_service,
)
from tools.registry import tool_registry

from agents.executor import agent_executor
from agents.registry import agent_registry
from agents.router import (
    AgentRoute,
    agent_router,
)
from agents.schemas import (
    AgentDefinition,
    AgentRunRequest,
    AgentRunResponse,
)


class AgentService:
    def list_agents(
        self,
    ) -> list[AgentDefinition]:
        return agent_registry.list()

    def list_tools(
        self,
    ) -> list[dict]:
        return [
            definition.model_dump()
            for definition in (tool_registry.list_definitions())
        ]

    def resolve_request(
        self,
        request: AgentRunRequest,
    ) -> tuple[
        AgentRunRequest,
        AgentRoute | None,
    ]:
        if request.mode == "smart":
            route = agent_router.route(request)

            resolved_request = request.model_copy(
                update={
                    "agent_id": route.agent_id,
                    "model": route.model,
                }
            )

            return resolved_request, route

        if not request.agent_id:
            raise ValueError("agent_id is required in " "manual mode")

        agent = agent_registry.get(request.agent_id)

        resolved_request = request.model_copy(
            update={
                "model": (request.model or agent.recommended_model),
            }
        )

        return resolved_request, None

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        try:
            resolved_request, _ = self.resolve_request(request)

            response = await agent_executor.run(resolved_request)

            agent_run_history_service.save(
                request=resolved_request,
                response=response,
                error=(
                    response.answer if response.status == "failed" else None
                ),
            )

            return response

        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        except HTTPException:
            raise

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=("Agent execution failed: " f"{exc}"),
            ) from exc

    async def stream(
        self,
        request: AgentRunRequest,
    ) -> AsyncIterator[str]:
        try:
            resolved_request, route = self.resolve_request(request)

            if route is not None:
                yield (
                    json.dumps(
                        {
                            "type": "routing",
                            "mode": "smart",
                            "agent_id": (route.agent_id),
                            "model": route.model,
                            "confidence": (route.confidence),
                            "reason": route.reason,
                        },
                        default=str,
                    )
                    + "\n"
                )

            yield (
                json.dumps(
                    {
                        "type": "status",
                        "status": "running",
                        "agent_id": (resolved_request.agent_id),
                        "message": ("Starting agent " "execution..."),
                    },
                    default=str,
                )
                + "\n"
            )

            response = await agent_executor.run(resolved_request)

            for step in response.steps:
                yield (
                    json.dumps(
                        {
                            "type": "step",
                            "step": (step.model_dump(mode="json")),
                        },
                        default=str,
                    )
                    + "\n"
                )

            yield (
                json.dumps(
                    {
                        "type": "answer",
                        "content": response.answer,
                        "sources": response.sources,
                    },
                    default=str,
                )
                + "\n"
            )

            agent_run_history_service.save(
                request=resolved_request,
                response=response,
                error=(
                    response.answer if response.status == "failed" else None
                ),
            )

            yield (
                json.dumps(
                    {
                        "type": "done",
                        "run": (response.model_dump(mode="json")),
                    },
                    default=str,
                )
                + "\n"
            )

        except Exception as exc:
            message = "Agent execution failed: " f"{exc}"

            yield (
                json.dumps(
                    {
                        "type": "error",
                        "error": message,
                        "message": message,
                    },
                    default=str,
                )
                + "\n"
            )


agent_service = AgentService()
