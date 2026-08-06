import hashlib
import json
from typing import Any, cast

from agents.runtime import instrumented_agent_executor
from agents.schemas import AgentRunRequest
from agents.truth_service import (
    AgentTruthService,
    agent_truth_service,
)
from company.catalog import company_registry
from executive_office.execution_reservation_service import (
    ExecutiveReservationService,
    executive_reservation_service,
)
from executive_office.execution_runner import (
    ExecutiveExistingTaskRunner,
    ExistingTaskExecutionError,
)
from executive_office.execution_start_repository import (
    ExecutionStartClaim,
    ExecutionStartStateConflictError,
    ExecutiveExecutionStartRepository,
    executive_execution_start_repository,
)
from executive_office.execution_start_schemas import (
    ExecutionTaskResultStatus,
    ExecutiveExecutionStartRequest,
    ExecutiveExecutionStartResponse,
    ExecutiveTaskExecutionResult,
    OwnerExecutionStartAuthorization,
)
from executive_office.schemas import (
    ExecutiveOfficeCapability,
    ExecutiveOfficeStatusResponse,
)


class ExecutiveExecutionStartService:
    version = "0.5.0"

    def __init__(
        self,
        *,
        reservation_service: ExecutiveReservationService = (
            executive_reservation_service
        ),
        truth_service: AgentTruthService = agent_truth_service,
        start_repository: ExecutiveExecutionStartRepository = (
            executive_execution_start_repository
        ),
        runner: ExecutiveExistingTaskRunner | None = None,
    ) -> None:
        self.reservation_service = reservation_service
        self.truth_service = truth_service
        self.start_repository = start_repository
        self.runner = runner or ExecutiveExistingTaskRunner(
            instrumented_agent_executor,
            truth_service=truth_service,
        )

    def status(self) -> ExecutiveOfficeStatusResponse:
        reservation_status = self.reservation_service.status()
        guardian_role = company_registry.get_role("guardian-ceo")
        capability = ExecutiveOfficeCapability(
            service_id="bounded-owner-triggered-agent-execution",
            acting_role_id="guardian-ceo",
            registry_employment_status=guardian_role.employment_status,
            mode="execution_admission",
            description=(
                "Start a separately authorized reserved execution through the "
                "existing instrumented on-demand agent executor with exact task "
                "and agent binding, sequential limits, and broker isolation."
            ),
        )
        return reservation_status.model_copy(
            update={
                "version": self.version,
                "execution_enabled": True,
                "broker_activation_enabled": False,
                "capabilities": [
                    *reservation_status.capabilities,
                    capability,
                ],
            }
        )

    async def start(
        self,
        *,
        execution_id: str,
        request: ExecutiveExecutionStartRequest,
    ) -> ExecutiveExecutionStartResponse:
        request_hash = self._request_hash(execution_id, request)
        replay = self.start_repository.get_replay(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
        )

        if replay is not None:
            return replay

        identity = self.start_repository.get_identity(execution_id)

        if identity is None:
            return self._state_conflict(
                execution_id=execution_id,
                delegation_id="unknown-delegation",
                child_task_ids=[],
                message="The requested reserved execution does not exist.",
            )

        authorization_error = self._authorization_error(
            authorization=request.owner_authorization,
            execution_id=execution_id,
            delegation_id=identity.delegation_id,
            child_task_ids=list(identity.child_task_ids),
        )

        if authorization_error is not None:
            return ExecutiveExecutionStartResponse(
                execution_id=execution_id,
                delegation_id=identity.delegation_id,
                child_task_ids=list(identity.child_task_ids),
                disposition="authorization_required",
                state="rejected",
                message=authorization_error,
            )

        if identity.state != "reserved":
            return self._state_conflict(
                execution_id=execution_id,
                delegation_id=identity.delegation_id,
                child_task_ids=list(identity.child_task_ids),
                message=(
                    f"Execution {execution_id} is {identity.state}, not reserved."
                ),
            )

        try:
            claimed = self.start_repository.claim(
                execution_id=execution_id,
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
            )
        except ExecutionStartStateConflictError as error:
            return self._state_conflict(
                execution_id=execution_id,
                delegation_id=identity.delegation_id,
                child_task_ids=list(identity.child_task_ids),
                message=str(error),
            )

        if isinstance(claimed, ExecutiveExecutionStartResponse):
            return claimed

        worker_error = self._worker_error(claimed.selected_agent_ids)

        if worker_error is not None:
            response = ExecutiveExecutionStartResponse(
                execution_id=claimed.execution_id,
                delegation_id=claimed.delegation_id,
                child_task_ids=list(claimed.child_task_ids),
                disposition="manual_review",
                state="manual_review",
                execution_started=False,
                reservation_released=False,
                broker_activated=False,
                message=(
                    "Execution entered manual review before agent invocation. "
                    f"Active reservations were retained: {worker_error}"
                ),
            )
            return self.start_repository.mark_manual_review(
                idempotency_key=request.idempotency_key,
                response=response,
            )

        return await self._run_claimed_execution(
            claim=claimed,
            idempotency_key=request.idempotency_key,
        )

    async def _run_claimed_execution(
        self,
        *,
        claim: ExecutionStartClaim,
        idempotency_key: str,
    ) -> ExecutiveExecutionStartResponse:
        results: list[ExecutiveTaskExecutionResult] = []

        try:
            for task_id, agent_id in zip(
                claim.child_task_ids,
                claim.selected_agent_ids,
                strict=True,
            ):
                task = self.truth_service.get_task(task_id)
                agent_response = await self.runner.run(
                    request=AgentRunRequest(
                        mode="manual",
                        agent_id=agent_id,
                        objective=task.objective,
                        provider="auto",
                        temperature=0.2,
                        max_tokens=700,
                        max_steps=4,
                    ),
                    task=task,
                    delegation_id=claim.delegation_id,
                )

                if agent_response.status not in {"completed", "failed"}:
                    raise RuntimeError(
                        "The bounded agent returned a non-terminal status: "
                        f"{agent_response.status}."
                    )

                terminal_status = cast(
                    ExecutionTaskResultStatus,
                    agent_response.status,
                )
                results.append(
                    ExecutiveTaskExecutionResult(
                        task_id=task_id,
                        agent_id=agent_id,
                        run_id=agent_response.run_id,
                        status=terminal_status,
                        answer=agent_response.answer,
                        started_at=agent_response.started_at,
                        completed_at=agent_response.completed_at,
                    )
                )
        except ExistingTaskExecutionError as error:
            response = ExecutiveExecutionStartResponse(
                execution_id=claim.execution_id,
                delegation_id=claim.delegation_id,
                child_task_ids=list(claim.child_task_ids),
                disposition="manual_review",
                state="manual_review",
                task_results=results,
                execution_started=bool(results),
                reservation_released=False,
                broker_activated=False,
                message=(
                    "Execution entered manual review after queued-task identity "
                    f"validation failed. Active reservations were retained: {error}"
                ),
            )
            return self.start_repository.mark_manual_review(
                idempotency_key=idempotency_key,
                response=response,
            )
        except Exception as error:
            response = ExecutiveExecutionStartResponse(
                execution_id=claim.execution_id,
                delegation_id=claim.delegation_id,
                child_task_ids=list(claim.child_task_ids),
                disposition="manual_review",
                state="manual_review",
                task_results=results,
                execution_started=True,
                reservation_released=False,
                broker_activated=False,
                message=(
                    "Execution entered manual review after an ambiguous runner "
                    f"failure. Active reservations were retained: {error}"
                ),
            )
            return self.start_repository.mark_manual_review(
                idempotency_key=idempotency_key,
                response=response,
            )

        terminal_state: ExecutionTaskResultStatus = (
            "completed"
            if all(result.status == "completed" for result in results)
            else "failed"
        )
        response = ExecutiveExecutionStartResponse(
            execution_id=claim.execution_id,
            delegation_id=claim.delegation_id,
            child_task_ids=list(claim.child_task_ids),
            disposition=terminal_state,
            state=terminal_state,
            task_results=results,
            execution_started=True,
            reservation_released=True,
            broker_activated=False,
            message=(
                "Reserved execution completed through the bounded agent runner; "
                "reservations were released and the broker remained inactive."
                if terminal_state == "completed"
                else (
                    "Reserved execution reached a deterministic failed outcome; "
                    "reservations were released and the broker remained inactive."
                )
            ),
        )
        return self.start_repository.complete(
            idempotency_key=idempotency_key,
            response=response,
        )

    def _worker_error(
        self,
        agent_ids: tuple[str, ...],
    ) -> str | None:
        for agent_id in agent_ids:
            try:
                state = self.truth_service.get_agent_state(agent_id)
            except KeyError:
                return f"Machine agent {agent_id} is not registered."

            if not state.agent.enabled:
                return f"Machine agent {agent_id} is disabled."
            if not state.agent.safe:
                return f"Machine agent {agent_id} is not marked safe."
            if state.runtime_status != "available":
                return (
                    f"Machine agent {agent_id} is {state.runtime_status}, "
                    "not available."
                )

        return None

    @staticmethod
    def _authorization_error(
        *,
        authorization: OwnerExecutionStartAuthorization,
        execution_id: str,
        delegation_id: str,
        child_task_ids: list[str],
    ) -> str | None:
        if not authorization.approved:
            return "The execution-start authorization is not affirmative."
        if authorization.authorized_by != "dipen-owner":
            return "The execution-start authorization was not issued by Dipen."
        if authorization.scope != "start_reserved_execution":
            return "The execution-start authorization has the wrong purpose."
        if authorization.execution_id != execution_id:
            return "The authorization is bound to a different execution."
        if authorization.delegation_id != delegation_id:
            return "The authorization is bound to a different delegation."
        if sorted(authorization.child_task_ids) != sorted(child_task_ids):
            return "The authorization is bound to a different child task set."

        return None

    @staticmethod
    def _request_hash(
        execution_id: str,
        request: ExecutiveExecutionStartRequest,
    ) -> str:
        authorization = request.owner_authorization
        authorization_payload: dict[str, Any] = {
            "authorization_id": authorization.authorization_id,
            "execution_id": authorization.execution_id,
            "delegation_id": authorization.delegation_id,
            "child_task_ids": sorted(authorization.child_task_ids),
            "authorized_by": authorization.authorized_by,
            "approved": authorization.approved,
            "scope": authorization.scope,
            "statement": authorization.statement,
        }
        canonical = json.dumps(
            {
                "execution_id": execution_id,
                "owner_authorization": authorization_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _state_conflict(
        *,
        execution_id: str,
        delegation_id: str,
        child_task_ids: list[str],
        message: str,
    ) -> ExecutiveExecutionStartResponse:
        return ExecutiveExecutionStartResponse(
            execution_id=execution_id,
            delegation_id=delegation_id,
            child_task_ids=child_task_ids,
            disposition="state_conflict",
            state="rejected",
            message=message,
        )


executive_execution_start_service = ExecutiveExecutionStartService()
