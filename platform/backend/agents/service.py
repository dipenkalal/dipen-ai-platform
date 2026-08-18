import json
from collections.abc import AsyncIterator

from fastapi import HTTPException

from agents.research_executor import research_enabled_agent_executor as agent_executor
from agents.registry import agent_registry
from agents.router import AgentRoute, agent_router
from agents.runtime import instrumented_agent_executor
from agents.schemas import (
    AgentDefinition,
    AgentRoutingMetadata,
    AgentRunRequest,
    AgentRunResponse,
)
from history.service import agent_run_history_service
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
            definition.model_dump() for definition in tool_registry.list_definitions()
        ]

    @staticmethod
    def _request_for_history(
        request: AgentRunRequest,
    ) -> AgentRunRequest:
        if request.supplemental_context is None:
            return request

        return request.model_copy(
            update={
                "supplemental_context": None,
            }
        )

    def resolve_request(
        self,
        request: AgentRunRequest,
    ) -> tuple[
        AgentRunRequest,
        AgentRoute | None,
    ]:
        if request.mode == "smart":
            routing_request = request.model_copy(
                update={
                    "supplemental_context": None,
                }
            )

            route = agent_router.route(routing_request)

            routing = AgentRoutingMetadata(
                mode="smart",
                selected_agent_id=route.agent_id,
                confidence=route.confidence,
                reason=route.reason,
                matched_terms=route.matched_terms,
                candidate_scores=route.candidate_scores,
                routing_latency_ms=route.routing_latency_ms,
            )

            resolved_request = request.model_copy(
                update={
                    "agent_id": route.agent_id,
                    "model": route.model,
                    "routing": routing,
                }
            )

            return resolved_request, route

        if not request.agent_id:
            raise ValueError("agent_id is required in manual mode")

        agent = agent_registry.get(request.agent_id)

        routing = AgentRoutingMetadata(
            mode="manual",
            selected_agent_id=request.agent_id,
            reason=("Agent selected manually by the user."),
        )

        resolved_request = request.model_copy(
            update={
                "model": (request.model or agent.recommended_model),
                "routing": routing,
            }
        )

        return resolved_request, None

    async def run(
        self,
        request: AgentRunRequest,
    ) -> AgentRunResponse:
        try:
            resolved_request, _ = self.resolve_request(request)

            response = await instrumented_agent_executor.run(resolved_request)

            agent_run_history_service.save(
                request=self._request_for_history(resolved_request),
                response=response,
                error=(response.answer if response.status == "failed" else None),
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
                detail=(f"Agent execution failed: {exc}"),
            ) from exc

    async def stream(
        self,
        request: AgentRunRequest,
    ) -> AsyncIterator[str]:
        async for event in self._stream(
            request,
            instrument_runtime=True,
        ):
            yield event

    async def stream_chat(
        self,
        request: AgentRunRequest,
    ) -> AsyncIterator[str]:
        async for event in self._stream(
            request,
            instrument_runtime=False,
        ):
            yield event

    async def _stream(
        self,
        request: AgentRunRequest,
        *,
        instrument_runtime: bool,
    ) -> AsyncIterator[str]:
        try:
            resolved_request, route = self.resolve_request(request)

            if route is not None:
                yield (
                    json.dumps(
                        {
                            "type": "routing",
                            "mode": "smart",
                            "agent_id": route.agent_id,
                            "model": route.model,
                            "confidence": (route.confidence),
                            "reason": route.reason,
                            "matched_terms": (route.matched_terms),
                            "candidate_scores": (route.candidate_scores),
                            "routing_latency_ms": (route.routing_latency_ms),
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
                        "message": ("Starting agent execution..."),
                    },
                    default=str,
                )
                + "\n"
            )

            executor = (
                instrumented_agent_executor if instrument_runtime else agent_executor
            )

            response = await executor.run(resolved_request)

            for step in response.steps:
                yield (
                    json.dumps(
                        {
                            "type": "step",
                            "step": step.model_dump(mode="json"),
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
                request=self._request_for_history(resolved_request),
                response=response,
                error=(response.answer if response.status == "failed" else None),
            )

            yield (
                json.dumps(
                    {
                        "type": "done",
                        "run": response.model_dump(mode="json"),
                    },
                    default=str,
                )
                + "\n"
            )

        except Exception as exc:  # noqa: BLE001
            message = f"Agent execution failed: {exc}"

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
