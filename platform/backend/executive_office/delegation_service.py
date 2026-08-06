import hashlib
import json
from typing import Any

from agents.truth_schemas import TaskLedgerRecord, TaskPriority
from agents.truth_service import (
    AgentTruthService,
    agent_truth_service,
)
from company.catalog import company_registry
from executive_office.repository import (
    ExecutiveDelegationRepository,
    executive_delegation_repository,
)
from executive_office.schemas import (
    ExecutiveDelegationRequest,
    ExecutiveDelegationResponse,
    ExecutiveOfficeCapability,
    ExecutiveOfficeStatusResponse,
    ExecutivePlanResponse,
    OwnerApprovalRecord,
    WorkerAdmissionDecision,
    WorkerAdmissionStatus,
    utc_now,
)
from executive_office.service import (
    ExecutiveOfficeService,
    executive_office_service,
)


class ExecutiveDelegationService:
    version = "0.2.0"

    def __init__(
        self,
        *,
        advisory_service: ExecutiveOfficeService = executive_office_service,
        truth_service: AgentTruthService = agent_truth_service,
        delegation_repository: ExecutiveDelegationRepository = (
            executive_delegation_repository
        ),
    ) -> None:
        self.advisory_service = advisory_service
        self.truth_service = truth_service
        self.delegation_repository = delegation_repository

    def status(self) -> ExecutiveOfficeStatusResponse:
        advisory_status = self.advisory_service.status()
        guardian_role = company_registry.get_role("guardian-ceo")
        controlled_capability = ExecutiveOfficeCapability(
            service_id="controlled-task-delegation",
            acting_role_id="guardian-ceo",
            registry_employment_status=guardian_role.employment_status,
            mode="controlled_delegation",
            description=(
                "Persist approved parent and child task records after "
                "idempotency, approval, and worker-admission checks."
            ),
        )
        return advisory_status.model_copy(
            update={
                "version": self.version,
                "read_only": False,
                "delegation_enabled": True,
                "task_ledger_writes_enabled": True,
                "execution_enabled": False,
                "broker_activation_enabled": False,
                "capabilities": [
                    *advisory_status.capabilities,
                    controlled_capability,
                ],
            }
        )

    def delegate(
        self,
        request: ExecutiveDelegationRequest,
    ) -> ExecutiveDelegationResponse:
        request_hash = self._request_hash(request)
        replay = self.delegation_repository.get_replay(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
        )

        if replay is not None:
            return replay

        plan = self.advisory_service.plan(request.plan)
        delegation_id = self._delegation_id(
            plan.decision_id,
            request.idempotency_key,
        )

        if plan.disposition == "blocked":
            return ExecutiveDelegationResponse(
                delegation_id=delegation_id,
                decision_id=plan.decision_id,
                disposition="blocked",
                message=(
                    "Delegation rejected. Prohibited work was not written to "
                    "the task ledger."
                ),
            )

        approval = request.owner_approval

        if plan.risk_policy.owner_approval_required and not self._approval_valid(
            approval,
            plan.decision_id,
        ):
            return ExecutiveDelegationResponse(
                delegation_id=delegation_id,
                decision_id=plan.decision_id,
                disposition="approval_required",
                message=(
                    "A matching affirmative dipen-owner approval record is "
                    "required before task delegation."
                ),
            )

        worker_admission = self._worker_admission(plan)

        if not all(item.admitted for item in worker_admission):
            return ExecutiveDelegationResponse(
                delegation_id=delegation_id,
                decision_id=plan.decision_id,
                disposition="capacity_unavailable",
                worker_admission=worker_admission,
                message=(
                    "Delegation deferred. At least one mapped worker is "
                    "unavailable or exceeds the deterministic capacity limit."
                ),
            )

        parent_task, child_tasks = self._build_task_records(
            delegation_id=delegation_id,
            plan=plan,
        )
        response = ExecutiveDelegationResponse(
            delegation_id=delegation_id,
            decision_id=plan.decision_id,
            disposition="delegated",
            parent_task=parent_task,
            child_tasks=child_tasks,
            worker_admission=worker_admission,
            approval_recorded=approval is not None,
            task_ledger_written=True,
            message=(
                "Parent and child tasks were written atomically. Workers and "
                "the broker were not started."
            ),
        )

        return self.delegation_repository.persist(
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            response=response,
            approval=approval,
        )

    @staticmethod
    def _request_hash(
        request: ExecutiveDelegationRequest,
    ) -> str:
        approval_payload: dict[str, Any] | None = None

        if request.owner_approval is not None:
            approval_payload = {
                "approval_id": request.owner_approval.approval_id,
                "decision_id": request.owner_approval.decision_id,
                "approved_by": request.owner_approval.approved_by,
                "approved": request.owner_approval.approved,
                "statement": request.owner_approval.statement,
            }

        canonical = json.dumps(
            {
                "plan": request.plan.model_dump(mode="json"),
                "owner_approval": approval_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _delegation_id(
        decision_id: str,
        idempotency_key: str,
    ) -> str:
        digest = hashlib.sha256(
            f"{decision_id}|{idempotency_key}".encode()
        ).hexdigest()[:20]
        return f"executive-delegation-{digest}"

    @staticmethod
    def _approval_valid(
        approval: OwnerApprovalRecord | None,
        decision_id: str,
    ) -> bool:
        return bool(
            approval is not None
            and approval.approved
            and approval.approved_by == "dipen-owner"
            and approval.decision_id == decision_id
        )

    def _worker_admission(
        self,
        plan: ExecutivePlanResponse,
    ) -> list[WorkerAdmissionDecision]:
        decisions: list[WorkerAdmissionDecision] = []
        admitted_counts: dict[str, int] = {}

        for work_item in plan.project_plan.work_items:
            machine_agent_id = work_item.assigned_machine_agent_id

            if machine_agent_id is None:
                decisions.append(
                    WorkerAdmissionDecision(
                        task_id=work_item.task_id,
                        role_id=work_item.assigned_role_id,
                        runtime_status="unmapped",
                        admitted=False,
                        evidence=[
                            "The assigned role has no active machine-agent mapping."
                        ],
                    )
                )
                continue

            state = self.truth_service.get_agent_state(machine_agent_id)
            already_admitted = admitted_counts.get(machine_agent_id, 0)
            capacity_available = already_admitted < 1

            if state.runtime_status == "available" and capacity_available:
                admitted_counts[machine_agent_id] = already_admitted + 1
                decisions.append(
                    WorkerAdmissionDecision(
                        task_id=work_item.task_id,
                        role_id=work_item.assigned_role_id,
                        machine_agent_id=machine_agent_id,
                        runtime_status="available",
                        admitted=True,
                        evidence=[
                            (
                                "Agent truth reports the mapped worker available "
                                "and one deterministic delegation slot is free."
                            )
                        ],
                    )
                )
                continue

            runtime_status: WorkerAdmissionStatus = (
                "capacity_exhausted"
                if state.runtime_status == "available"
                else state.runtime_status
            )
            decisions.append(
                WorkerAdmissionDecision(
                    task_id=work_item.task_id,
                    role_id=work_item.assigned_role_id,
                    machine_agent_id=machine_agent_id,
                    runtime_status=runtime_status,
                    admitted=False,
                    evidence=[
                        (
                            "Agent truth or per-delegation capacity policy did "
                            "not admit this worker."
                        )
                    ],
                )
            )

        return decisions

    @staticmethod
    def _build_task_records(
        *,
        delegation_id: str,
        plan: ExecutivePlanResponse,
    ) -> tuple[TaskLedgerRecord, list[TaskLedgerRecord]]:
        now = utc_now()
        assigned_agent_ids = sorted(
            {
                item.assigned_machine_agent_id
                for item in plan.project_plan.work_items
                if item.assigned_machine_agent_id is not None
            }
        )
        priority: TaskPriority = (
            "high"
            if plan.risk_policy.owner_approval_required
            else "normal"
        )
        parent_task_id = f"{delegation_id}-parent"
        parent_task = TaskLedgerRecord(
            task_id=parent_task_id,
            task_type="orchestration",
            objective=(
                "Coordinate the approved Executive Office plan "
                f"{plan.decision_id} without starting runtime execution."
            ),
            status="planned",
            priority=priority,
            requested_by=plan.requested_by,
            assigned_agent_ids=assigned_agent_ids,
            source_run_id=delegation_id,
            current_step=(
                "Parent and child tasks are persisted; worker execution has "
                "not started."
            ),
            progress_percent=0.0,
            created_at=now,
            updated_at=now,
        )
        objective_by_task_id = {
            task.task_id: task.objective
            for task in plan.chief_of_staff.tasks
        }
        child_tasks = []

        for index, work_item in enumerate(
            plan.project_plan.work_items,
            start=1,
        ):
            machine_agent_id = work_item.assigned_machine_agent_id

            if machine_agent_id is None:
                raise RuntimeError(
                    "Admitted work item is missing a machine-agent mapping."
                )

            child_tasks.append(
                TaskLedgerRecord(
                    task_id=f"{delegation_id}-child-{index}",
                    task_type="agent",
                    objective=objective_by_task_id[work_item.task_id],
                    status="assigned",
                    priority=priority,
                    requested_by=plan.requested_by,
                    assigned_agent_ids=[machine_agent_id],
                    source_run_id=delegation_id,
                    parent_task_id=parent_task_id,
                    current_step=(
                        "Assigned in the task ledger; runtime execution has "
                        "not started."
                    ),
                    progress_percent=0.0,
                    created_at=now,
                    updated_at=now,
                )
            )

        return parent_task, child_tasks


executive_delegation_service = ExecutiveDelegationService()
