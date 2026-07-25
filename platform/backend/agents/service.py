import json
from collections.abc import AsyncIterator

from fastapi import HTTPException

from agents.executor import agent_executor
from agents.registry import agent_registry
from agents.schemas import (
    AgentDefinition,
    AgentRunRequest,
    AgentRunResponse,
)
from history.service import (
    agent_run_history_service,
)
from tools.registry import tool_registry


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
            for definition in (
                tool_registry
                .list_definitions()
            )
        ]

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        try:
            response = await agent_executor.run(
                request
            )

            agent_run_history_service.save(
                request=request,
                response=response,
                error=(
                    response.answer
                    if response.status == "failed"
                    else None
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
                detail=(
                    "Agent execution failed: "
                    f"{exc}"
                ),
            ) from exc

    async def stream(
        self,
        request: AgentRunRequest,
    ) -> AsyncIterator[str]:
        yield (
            json.dumps(
                {
                    "type": "status",
                    "status": "running",
                    "agent_id": request.agent_id,
                    "message": (
                        "Starting agent execution..."
                    ),
                },
                default=str,
            )
            + "\n"
        )

        try:
            response = await agent_executor.run(
                request
            )

            for step in response.steps:
                yield (
                    json.dumps(
                        {
                            "type": "step",
                            "step": step.model_dump(
                                mode="json"
                            ),
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
                request=request,
                response=response,
                error=(
                    response.answer
                    if response.status == "failed"
                    else None
                ),
            )

            yield (
                json.dumps(
                    {
                        "type": "done",
                        "run": response.model_dump(
                            mode="json"
                        ),
                    },
                    default=str,
                )
                + "\n"
            )

        except Exception as exc:
            message = (
                "Agent execution failed: "
                f"{exc}"
            )

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
