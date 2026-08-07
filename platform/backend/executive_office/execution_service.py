import hashlib
import json
from typing import Any

from agents.truth_schemas import TaskLedgerRecord
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
    ExecutiveExecutionRepository,
    executive_execution_repository,
)
from executive_office.schemas import (
    ExecutionDisposition,
    ExecutionValidationEvidence,
    ExecutiveExecutionRequest,
    ExecutiveExecutionResponse,
    ExecutiveOfficeCapability,
    ExecutiveOfficeStatusResponse,
    ExecutivePlanRequest,
    OwnerExecutionAuthorization,
)
from executive_office.service import (
    ExecutiveOfficeService,
    executive_office_service,
)


class ExecutiveExecutionService:
    version = "0.3.0"
    max_tasks_per_request = 6

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
        self.delegation_service = delegation_service
        self.advisory_service = advisory_service
        self.truth_service = truth_service
        self.execution_repository = execution_repository

    def status(self) -> ExecutiveOfficeStatusResponse:
        delegation_status = self.delegation_service.status()
        guardian_role = company_registry.get_role("guardian-ceo")
        capability = ExecutiveOfficeCapability(
            service_id="owner-triggered-execution-admission",
            acting_role_id="guardian-ceo",
            registry_employment_status=guardian_role.employment_status,
            mode="execution_admission",
            description=(
                "Validate owner-triggered execution requests against stored "
                "delegations, task truth, policy, and worker capacity without "
                "starting workers or the broker."
            ),
        )
        return delegation_status.model_copy(
            update={
                "version": self.version,
                "execution_admission_enabled": True,
                "execution_enabled": False,
                "broker_activation_enabled": False,
                "capabilities": [
                    *delegation_status.capabilities,
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

        execution_id = self._execution_id(
            request.delegation_id,
            request.idempotency_key,
        )
        evidence: list[ExecutionValidationEvidence] = []

        if len(set(request.child_task_ids)) != len(request.child_task_ids):
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="rejected",
                evidence=[
                    ExecutionValidationEvidence(
                        check_id="task-selection",
                        passed=False,
                        detail="Child task IDs must be unique.",
                    )
                ],
                message="Execution admission rejected because task IDs repeat.",
            )

        delegation = self.execution_repository.get_delegation(
            request.delegation_id
        )

        if delegation is None:
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="rejected",
                evidence=[
                    ExecutionValidationEvidence(
                        check_id="delegation",
                        passed=False,
                        detail="The requested delegation does not exist.",
                    )
                ],
                message="Execution admission rejected for an unknown delegation.",
            )

        evidence.append(
            ExecutionValidationEvidence(
                check_id="delegation",
                passed=True,
                detail=(
                    "The stored delegation exists and was created through the "
                    "controlled delegation path."
                ),
            )
        )

        stored_parent = delegation.parent_task
        stored_children = {
            task.task_id: task for task in delegation.child_tasks
        }

        if (
            stored_parent is None
            or stored_parent.task_id != request.parent_task_id
            or any(
                task_id not in stored_children
                for task_id in request.child_task_ids
            )
        ):
            evidence.append(
                ExecutionValidationEvidence(
                    check_id="task-identity",
                    passed=False,
                    detail=(
                        "The supplied parent or child task IDs do not match the "
                        "stored delegation."
                    ),
                )
            )
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="rejected",
                evidence=evidence,
                message=(
                    "Execution admission rejected because task ownership does "
                    "not match the stored delegation."
                ),
            )

        selected_stored_children = [
            stored_children[task_id]
            for task_id in request.child_task_ids
        ]
        identity_error = self._task_identity_error(
            delegation_id=request.delegation_id,
            parent=stored_parent,
            children=selected_stored_children,
        )

        if identity_error is not None:
            evidence.append(
                ExecutionValidationEvidence(
                    check_id="task-identity",
                    passed=False,
                    detail=identity_error,
                )
            )
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="rejected",
                evidence=evidence,
                message=(
                    "Execution admission rejected because stored task identity "
                    "evidence is inconsistent."
                ),
            )

        evidence.append(
            ExecutionValidationEvidence(
                check_id="task-identity",
                passed=True,
                detail=(
                    "The parent and selected children belong to the exact "
                    "delegation and share the expected parent relationship."
                ),
            )
        )

        try:
            current_parent = self.truth_service.get_task(
                request.parent_task_id
            )
            current_children = [
                self.truth_service.get_task(task_id)
                for task_id in request.child_task_ids
            ]
        except KeyError:
            evidence.append(
                ExecutionValidationEvidence(
                    check_id="task-state",
                    passed=False,
                    detail=(
                        "At least one delegated task is missing from the live "
                        "task ledger."
                    ),
                )
            )
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="task_state_conflict",
                evidence=evidence,
                message=(
                    "Execution admission rejected because live task state is "
                    "missing or stale."
                ),
            )

        state_error = self._task_state_error(
            delegation_id=request.delegation_id,
            parent=current_parent,
            children=current_children,
        )

        if state_error is not None:
            evidence.append(
                ExecutionValidationEvidence(
                    check_id="task-state",
                    passed=False,
                    detail=state_error,
                )
            )
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="task_state_conflict",
                evidence=evidence,
                message=(
                    "Execution admission rejected because one or more task "
                    "states are no longer executable."
                ),
            )

        evidence.append(
            ExecutionValidationEvidence(
                check_id="task-state",
                passed=True,
                detail=(
                    "The parent remains planned and every selected child "
                    "remains assigned in the live task ledger."
                ),
            )
        )

        authorization_error = self._authorization_error(
            request.owner_authorization,
            request,
        )

        if authorization_error is not None:
            evidence.append(
                ExecutionValidationEvidence(
                    check_id="owner-authorization",
                    passed=False,
                    detail=authorization_error,
                )
            )
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="authorization_required",
                evidence=evidence,
                message=(
                    "A matching affirmative dipen-owner execution "
                    "authorization is required."
                ),
            )

        evidence.append(
            ExecutionValidationEvidence(
                check_id="owner-authorization",
                passed=True,
                detail=(
                    "The authorization is affirmative, single-purpose, and "
                    "bound to the exact delegation and selected task set."
                ),
            )
        )

        policy_error = self._policy_error(current_children)

        if policy_error is not None:
            evidence.append(
                ExecutionValidationEvidence(
                    check_id="policy",
                    passed=False,
                    detail=policy_error,
                )
            )
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="rejected",
                evidence=evidence,
                message=(
                    "Execution admission rejected because Phase 4.1 permits "
                    "only low-risk internal agent work."
                ),
            )

        evidence.append(
            ExecutionValidationEvidence(
                check_id="policy",
                passed=True,
                detail=(
                    "A fresh policy review classified every selected objective "
                    "as low-risk internal work."
                ),
            )
        )

        selected_agent_ids, worker_error = self._worker_error(
            current_children
        )

        if worker_error is not None:
            evidence.append(
                ExecutionValidationEvidence(
                    check_id="worker-state",
                    passed=False,
                    detail=worker_error,
                )
            )
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="worker_unavailable",
                evidence=evidence,
                selected_agent_ids=selected_agent_ids,
                message=(
                    "Execution admission rejected because worker truth or "
                    "deterministic capacity is unavailable."
                ),
            )

        evidence.extend(
            [
                ExecutionValidationEvidence(
                    check_id="worker-state",
                    passed=True,
                    detail=(
                        "Every selected machine agent is enabled, safe, and "
                        "reported available by Agent Truth."
                    ),
                ),
                ExecutionValidationEvidence(
                    check_id="orchestration-bounds",
                    passed=True,
                    detail=(
                        "The bounded sequential plan contains no more than six "
                        "tasks and allocates one deterministic slot per agent."
                    ),
                ),
                ExecutionValidationEvidence(
                    check_id="reservation-simulation",
                    passed=True,
                    detail=(
                        "Capacity can be reserved deterministically, but no "
                        "durable reservation was acquired in validation-only "
                        "mode."
                    ),
                ),
            ]
        )

        if not request.validation_only:
            evidence.append(
                ExecutionValidationEvidence(
                    check_id="execution-mode",
                    passed=False,
                    detail=(
                        "Execution-enabled requests remain disabled until the "
                        "Phase 4.2 reservation and task-transition slice."
                    ),
                )
            )
            return self._persist_rejection(
                request=request,
                request_hash=request_hash,
                execution_id=execution_id,
                disposition="execution_disabled",
                evidence=evidence,
                selected_agent_ids=selected_agent_ids,
                message=(
                    "Admission checks passed, but runtime execution is not "
                    "enabled in Phase 4.1."
                ),
            )

        evidence.append(
            ExecutionValidationEvidence(
                check_id="execution-mode",
                passed=True,
                detail=(
                    "Validation-only mode prevents task mutation, durable "
                    "reservation, executor invocation, and broker activation."
                ),
            )
        )
        response = ExecutiveExecutionResponse(
            execution_id=execution_id,
            delegation_id=request.delegation_id,
            parent_task_id=request.parent_task_id,
            child_task_ids=list(request.child_task_ids),
            disposition="validated",
            state="validated",
            selected_agent_ids=selected_agent_ids,
            validation_evidence=evidence,
            validation_only=True,
            admission_validated=True,
            message=(
                "Execution admission validated. No task state changed, no "
                "reservation was acquired, and no worker or broker was started."
            ),
        )
        return self.execution_repository.persist(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            response=response,
        )

    def _persist_rejection(
        self,
        *,
        request: ExecutiveExecutionRequest,
        request_hash: str,
        execution_id: str,
        disposition: ExecutionDisposition,
        evidence: list[ExecutionValidationEvidence],
        message: str,
        selected_agent_ids: list[str] | None = None,
    ) -> ExecutiveExecutionResponse:
        response = ExecutiveExecutionResponse(
            execution_id=execution_id,
            delegation_id=request.delegation_id,
            parent_task_id=request.parent_task_id,
            child_task_ids=list(request.child_task_ids),
            disposition=disposition,
            state="rejected",
            selected_agent_ids=selected_agent_ids or [],
            validation_evidence=evidence,
            validation_only=request.validation_only,
            message=message,
        )
        return self.execution_repository.persist(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            response=response,
        )

    @staticmethod
    def _task_identity_error(
        *,
        delegation_id: str,
        parent: TaskLedgerRecord,
        children: list[TaskLedgerRecord],
    ) -> str | None:
        if parent.source_run_id != delegation_id:
            return "The stored parent task is not linked to the delegation."

        for child in children:
            if child.source_run_id != delegation_id:
                return (
                    f"Child task {child.task_id} is not linked to the "
                    "delegation."
                )
            if child.parent_task_id != parent.task_id:
                return (
                    f"Child task {child.task_id} does not reference the "
                    "supplied parent."
                )

        return None

    @staticmethod
    def _task_state_error(
        *,
        delegation_id: str,
        parent: TaskLedgerRecord,
        children: list[TaskLedgerRecord],
    ) -> str | None:
        if parent.status != "planned":
            return (
                f"Parent task {parent.task_id} is {parent.status}, not planned."
            )
        if parent.source_run_id != delegation_id:
            return "The live parent task no longer belongs to the delegation."

        for child in children:
            if child.status != "assigned":
                return (
                    f"Child task {child.task_id} is {child.status}, not "
                    "assigned."
                )
            if child.source_run_id != delegation_id:
                return (
                    f"Child task {child.task_id} no longer belongs to the "
                    "delegation."
                )
            if child.parent_task_id != parent.task_id:
                return (
                    f"Child task {child.task_id} no longer references the "
                    "expected parent."
                )

        return None

    @staticmethod
    def _authorization_error(
        authorization: OwnerExecutionAuthorization | None,
        request: ExecutiveExecutionRequest,
    ) -> str | None:
        if authorization is None:
            return "No owner execution authorization was supplied."
        if not authorization.approved:
            return "The owner execution authorization is not affirmative."
        if authorization.authorized_by != "dipen-owner":
            return "The execution authorization was not issued by dipen-owner."
        if authorization.scope != "execute_delegated_tasks":
            return "The execution authorization has the wrong purpose."
        if authorization.delegation_id != request.delegation_id:
            return "The authorization is bound to a different delegation."
        if authorization.parent_task_id != request.parent_task_id:
            return "The authorization is bound to a different parent task."
        if sorted(authorization.child_task_ids) != sorted(
            request.child_task_ids
        ):
            return "The authorization is bound to a different child task set."
        if authorization.validation_only != request.validation_only:
            return "The authorization execution mode does not match the request."

        return None

    def _policy_error(
        self,
        children: list[TaskLedgerRecord],
    ) -> str | None:
        review = self.advisory_service.plan(
            ExecutivePlanRequest(
                objectives=[child.objective for child in children],
                requested_by="dipen-owner",
                allow_external_actions=False,
            )
        )

        for finding in review.risk_policy.findings:
            if (
                finding.risk_level != "low"
                or finding.approval_required
                or finding.prohibited_actions
            ):
                reason = (
                    finding.reasons[0]
                    if finding.reasons
                    else "Policy did not classify the task as low risk."
                )
                return (
                    f"Selected task {finding.task_id} failed execution policy: "
                    f"{reason}"
                )

        return None

    def _worker_error(
        self,
        children: list[TaskLedgerRecord],
    ) -> tuple[list[str], str | None]:
        selected_agent_ids: list[str] = []

        for child in children:
            if len(child.assigned_agent_ids) != 1:
                return (
                    selected_agent_ids,
                    (
                        f"Child task {child.task_id} must have exactly one "
                        "assigned machine agent."
                    ),
                )

            agent_id = child.assigned_agent_ids[0]

            if agent_id in selected_agent_ids:
                return (
                    selected_agent_ids,
                    (
                        f"Machine agent {agent_id} exceeds the one-task "
                        "deterministic capacity limit."
                    ),
                )

            selected_agent_ids.append(agent_id)

            try:
                state = self.truth_service.get_agent_state(agent_id)
            except KeyError:
                return (
                    selected_agent_ids,
                    f"Machine agent {agent_id} is not registered.",
                )

            if not state.agent.enabled:
                return (
                    selected_agent_ids,
                    f"Machine agent {agent_id} is disabled.",
                )
            if not state.agent.safe:
                return (
                    selected_agent_ids,
                    f"Machine agent {agent_id} is not marked safe.",
                )
            if state.runtime_status != "available":
                return (
                    selected_agent_ids,
                    (
                        f"Machine agent {agent_id} is "
                        f"{state.runtime_status}, not available."
                    ),
                )

        return selected_agent_ids, None

    @staticmethod
    def _request_hash(
        request: ExecutiveExecutionRequest,
    ) -> str:
        authorization_payload: dict[str, Any] | None = None

        if request.owner_authorization is not None:
            authorization_payload = {
                "authorization_id": (
                    request.owner_authorization.authorization_id
                ),
                "delegation_id": request.owner_authorization.delegation_id,
                "parent_task_id": request.owner_authorization.parent_task_id,
                "child_task_ids": sorted(
                    request.owner_authorization.child_task_ids
                ),
                "authorized_by": request.owner_authorization.authorized_by,
                "approved": request.owner_authorization.approved,
                "scope": request.owner_authorization.scope,
                "validation_only": (
                    request.owner_authorization.validation_only
                ),
                "statement": request.owner_authorization.statement,
            }

        canonical = json.dumps(
            {
                "delegation_id": request.delegation_id,
                "parent_task_id": request.parent_task_id,
                "child_task_ids": sorted(request.child_task_ids),
                "validation_only": request.validation_only,
                "owner_authorization": authorization_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _execution_id(
        delegation_id: str,
        idempotency_key: str,
    ) -> str:
        digest = hashlib.sha256(
            f"{delegation_id}|{idempotency_key}".encode()
        ).hexdigest()[:20]
        return f"executive-execution-{digest}"


executive_execution_service = ExecutiveExecutionService()
