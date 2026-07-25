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
        saved = False

        async for event in (
            agent_executor.stream(request)
        ):
            if not saved:
                try:
                    payload = json.loads(
                        event
                    )

                    if payload.get("type") == "done":
                        response = (
                            AgentRunResponse
                            .model_validate(
                                payload["run"]
                            )
                        )

                        agent_run_history_service.save(
                            request=request,
                            response=response,
                            error=(
                                response.answer
                                if response.status
                                == "failed"
                                else None
                            ),
                        )

                        saved = True

                except (
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    pass

            yield event


agent_service = AgentService()
