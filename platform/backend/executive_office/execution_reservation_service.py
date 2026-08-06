import hashlib
from typing import cast

from agents.truth_service import (
    AgentTruthService,
    agent_truth_service,
)
from company.catalog import company_registry
from executive_office.delegation_service import (
    ExecutiveDelegationService,
    executive_delegation_service,
)
from executive_office.execution_repository import (
    ExecutionStateConflictError,
    ExecutiveExecutionRepository,
    ReservationConflictError,
    executive_execution_repository,
)
from executive_office.execution_service import ExecutiveExecutionService
from executive_office.schemas import (
    ExecutiveDelegationResponse,
    ExecutiveExecutionRequest,
    ExecutiveExecutionResponse,
    ExecutiveOfficeCapability,
    ExecutiveOfficeStatusResponse,
    ExecutionValidationEvidence,
)
from executive_office.service import (
    ExecutiveOfficeService,
    executive_office_service,
)


class _ValidationOnlyRepository:
    def __init__(
        self,
        repository: ExecutiveExecutionRepository,
    ) -> None:
        self.repository = repository

    def get_replay(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> None:
        del idempotency_key, request_hash
        return None

    def get_delegation(
        self,
        delegation_id: str,
    ) -> ExecutiveDelegationResponse | None:
        return self.repository.get_delegation(delegation_id)

    @staticmethod
    def persist(
        *,
        idempotency_key: str,
        request_hash: str,
        response: ExecutiveExecutionResponse,
    ) -> ExecutiveExecutionResponse:
        del idempotency_key, request_hash
        return response


class ExecutiveReservationService(ExecutiveExecutionService):
    version = "0.4.0"

    def __init__(
        self,
        *,
        delegation_service: ExecutiveDelegationService = (
            executive_delegation_service
        ),
        advisory_service: ExecutiveOfficeService = executive_office_service,
        truth_service: AgentTruthService = agent_truth_service,
        execution_repository: ExecutiveExecutionRepository = (
            executive_execution_repository
        ),
    ) -> None:
        super().__init__(
            delegation_service=delegation_service,
            advisory_service=advisory_service,
            truth_service=truth_service,
            execution_repository=execution_repository,
        )

    def status(self) -> ExecutiveOfficeStatusResponse:
        admission_status = super().status()
        guardian_role = company_registry.get_role("guardian-ceo")
        capability = ExecutiveOfficeCapability(
            service_id="controlled-execution-reservation",
            acting_role_id="guardian-ceo",
            registry_employment_status=guardian_role.employment_status,
            mode="execution_admission",
            description=(
                "Atomically reserve one slot per selected machine agent and "
                "transition admitted child tasks from assigned to queued "
                "without invoking an executor or activating the broker."
            ),
        )
        return admission_status.model_copy(
            update={
                "version": self.version,
                "execution_reservation_enabled": True,
                "execution_enabled": False,
                "broker_activation_enabled": False,
                "capabilities": [
                    *admission_status.capabilities,
                    capability,
                ],
            }
        )

    def admit(
        self,
        request: ExecutiveExecutionRequest,
    ) -> ExecutiveExecutionResponse:
        request_hash = self._request_hash(request)
        replay = self.execution_repository.get_replay(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
        )

        if replay is not None:
            return replay

        validation_request = self._validation_request(request)
        validation_repository = _ValidationOnlyRepository(
            self.execution_repository
        )
        validation_service = ExecutiveExecutionService(
            delegation_service=self.delegation_service,
            advisory_service=self.advisory_service,
            truth_service=self.truth_service,
            execution_repository=cast(
                ExecutiveExecutionRepository,
                validation_repository,
            ),
        )
        validation = validation_service.admit(validation_request)

        if validation.disposition != "validated":
            message = validation.message

            if not request.validation_only:
                message = (
                    "Execution reservation rejected during admission: "
                    + validation.message
                )

            response = validation.model_copy(
                update={
                    "validation_only": request.validation_only,
                    "message": message,
                }
            )
            return self.execution_repository.persist(
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                response=response,
            )

        selected_agent_ids = validation.selected_agent_ids
        reserved_agent_ids = (
            self.execution_repository.list_active_reserved_agents(
                selected_agent_ids
            )
        )

        if reserved_agent_ids:
            response = self._reservation_rejection(
                validation=validation,
                validation_only=request.validation_only,
                detail=(
                    "Active execution reservations already exist for: "
                    + ", ".join(reserved_agent_ids)
                    + "."
                ),
            )
            return self.execution_repository.persist(
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                response=response,
            )

        if request.validation_only:
            return self.execution_repository.persist(
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                response=validation,
            )

        authorization = request.owner_authorization

        if authorization is None:
            raise RuntimeError(
                "Validated execution request lost its owner authorization."
            )

        task_agent_pairs = list(
            zip(
                request.child_task_ids,
                selected_agent_ids,
                strict=True,
            )
        )
        reservation_ids = self._reservation_ids(
            execution_id=validation.execution_id,
            task_agent_pairs=task_agent_pairs,
        )
        evidence = [
            *validation.validation_evidence,
            ExecutionValidationEvidence(
                check_id="execution-mode",
                passed=True,
                detail=(
                    "Execution-enabled admission is limited to atomic resource "
                    "reservation and assigned-to-queued task transitions. The "
                    "executor remains disabled."
                ),
            ),
        ]
        response = validation.model_copy(
            update={
                "disposition": "reserved",
                "state": "reserved",
                "reservation_ids": reservation_ids,
                "validation_evidence": evidence,
                "validation_only": False,
                "admission_validated": True,
                "task_ledger_mutated": True,
                "reservation_acquired": True,
                "execution_started": False,
                "broker_activated": False,
                "message": (
                    "Execution resources were reserved atomically and selected "
                    "tasks were queued. No executor or broker was started."
                ),
            }
        )

        try:
            return self.execution_repository.reserve_and_queue(
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                response=response,
                authorization=authorization,
                task_agent_pairs=task_agent_pairs,
            )
        except ReservationConflictError as error:
            rejected = self._reservation_rejection(
                validation=validation,
                validation_only=False,
                detail=str(error),
            )
            return self.execution_repository.persist(
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                response=rejected,
            )
        except ExecutionStateConflictError as error:
            rejected = validation.model_copy(
                update={
                    "disposition": "task_state_conflict",
                    "state": "rejected",
                    "validation_only": False,
                    "admission_validated": False,
                    "validation_evidence": [
                        *validation.validation_evidence,
                        ExecutionValidationEvidence(
                            check_id="atomic-task-transition",
                            passed=False,
                            detail=str(error),
                        ),
                    ],
                    "message": (
                        "Execution reservation rejected because task state "
                        "changed before the atomic transaction committed."
                    ),
                }
            )
            return self.execution_repository.persist(
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                response=rejected,
            )

    @staticmethod
    def _validation_request(
        request: ExecutiveExecutionRequest,
    ) -> ExecutiveExecutionRequest:
        authorization = request.owner_authorization
        validation_authorization = (
            authorization.model_copy(
                update={"validation_only": True}
            )
            if authorization is not None
            else None
        )
        return request.model_copy(
            update={
                "validation_only": True,
                "owner_authorization": validation_authorization,
            }
        )

    @staticmethod
    def _reservation_rejection(
        *,
        validation: ExecutiveExecutionResponse,
        validation_only: bool,
        detail: str,
    ) -> ExecutiveExecutionResponse:
        return validation.model_copy(
            update={
                "disposition": "reservation_conflict",
                "state": "rejected",
                "reservation_ids": [],
                "validation_only": validation_only,
                "admission_validated": False,
                "task_ledger_mutated": False,
                "reservation_acquired": False,
                "execution_started": False,
                "broker_activated": False,
                "validation_evidence": [
                    *validation.validation_evidence,
                    ExecutionValidationEvidence(
                        check_id="resource-reservation",
                        passed=False,
                        detail=detail,
                    ),
                ],
                "message": (
                    "Execution reservation rejected because an active machine-"
                    "agent reservation already exists."
                ),
            }
        )

    @staticmethod
    def _reservation_ids(
        *,
        execution_id: str,
        task_agent_pairs: list[tuple[str, str]],
    ) -> list[str]:
        reservation_ids: list[str] = []

        for task_id, agent_id in task_agent_pairs:
            digest = hashlib.sha256(
                f"{execution_id}|{task_id}|{agent_id}".encode()
            ).hexdigest()[:20]
            reservation_ids.append(
                f"executive-reservation-{digest}"
            )

        return reservation_ids


executive_reservation_service = ExecutiveReservationService()
