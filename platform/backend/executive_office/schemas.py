from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from agents.truth_schemas import TaskLedgerRecord

RiskLevel = Literal["low", "medium", "high", "blocked"]
DecisionDisposition = Literal[
    "advisory",
    "ready_for_delegation",
    "approval_required",
    "blocked",
]
WorkStatus = Literal["planned", "approval_required", "blocked"]
DelegationDisposition = Literal[
    "delegated",
    "approval_required",
    "blocked",
    "capacity_unavailable",
    "idempotent_replay",
]
ExecutionDisposition = Literal[
    "validated",
    "reserved",
    "authorization_required",
    "rejected",
    "task_state_conflict",
    "worker_unavailable",
    "reservation_conflict",
    "execution_disabled",
    "idempotent_replay",
]
ExecutionAdmissionState = Literal[
    "requested",
    "validated",
    "reserved",
    "rejected",
]
ExecutiveOfficeMode = Literal[
    "deterministic_advisory",
    "controlled_delegation",
    "execution_admission",
]
WorkerAdmissionStatus = Literal[
    "available",
    "busy",
    "degraded",
    "offline",
    "unreported",
    "disabled",
    "unmapped",
    "capacity_exhausted",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutivePlanRequest(BaseModel):
    objectives: list[str] = Field(min_length=1, max_length=20)
    requested_by: str = Field(default="dipen-owner", min_length=2, max_length=120)
    constraints: list[str] = Field(default_factory=list, max_length=30)
    allow_external_actions: bool = False


class ChiefOfStaffTask(BaseModel):
    task_id: str
    objective: str
    sequence: int = Field(ge=1)
    depends_on: list[str] = Field(default_factory=list)
    suggested_role_id: str
    suggested_machine_agent_id: str | None = None
    rationale: str


class ChiefOfStaffDecision(BaseModel):
    role_id: str = "chief-of-staff"
    objective_count: int
    tasks: list[ChiefOfStaffTask]
    parallelizable_task_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RiskFinding(BaseModel):
    task_id: str
    risk_level: RiskLevel
    approval_required: bool
    reasons: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)


class RiskPolicyDecision(BaseModel):
    role_id: str = "chief-risk-policy"
    overall_risk: RiskLevel
    findings: list[RiskFinding]
    owner_approval_required: bool
    execution_allowed: bool = False


class ProjectWorkItem(BaseModel):
    work_item_id: str
    task_id: str
    department_id: str | None = None
    assigned_role_id: str
    assigned_machine_agent_id: str | None = None
    status: WorkStatus
    acceptance_evidence: list[str] = Field(default_factory=list)


class ProjectPlanDecision(BaseModel):
    role_id: str = "senior-project-manager"
    parent_plan_id: str
    work_items: list[ProjectWorkItem]
    execution_mode: Literal["sequential", "parallel", "mixed"]
    completion_definition: list[str] = Field(default_factory=list)


class AuditEntry(BaseModel):
    sequence: int = Field(ge=1)
    actor_role_id: str
    action: str
    evidence: str


class AuditDecision(BaseModel):
    role_id: str = "chief-audit-compliance"
    entries: list[AuditEntry]
    immutable_claims: list[str] = Field(default_factory=list)


class ExecutivePlanResponse(BaseModel):
    decision_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    requested_by: str
    disposition: DecisionDisposition
    chief_of_staff: ChiefOfStaffDecision
    risk_policy: RiskPolicyDecision
    project_plan: ProjectPlanDecision
    audit: AuditDecision
    execution_started: bool = False
    message: str


class OwnerApprovalRecord(BaseModel):
    approval_id: str = Field(min_length=4, max_length=160)
    decision_id: str = Field(min_length=4, max_length=160)
    approved_by: Literal["dipen-owner"] = "dipen-owner"
    approved: bool = True
    statement: str = Field(min_length=4, max_length=2000)
    approved_at: datetime = Field(default_factory=utc_now)


class ExecutiveDelegationRequest(BaseModel):
    plan: ExecutivePlanRequest
    idempotency_key: str = Field(min_length=8, max_length=160)
    owner_approval: OwnerApprovalRecord | None = None


class WorkerAdmissionDecision(BaseModel):
    task_id: str
    role_id: str
    machine_agent_id: str | None = None
    runtime_status: WorkerAdmissionStatus
    admitted: bool
    evidence: list[str] = Field(default_factory=list)


class ExecutiveDelegationResponse(BaseModel):
    delegation_id: str
    decision_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    disposition: DelegationDisposition
    parent_task: TaskLedgerRecord | None = None
    child_tasks: list[TaskLedgerRecord] = Field(default_factory=list)
    worker_admission: list[WorkerAdmissionDecision] = Field(default_factory=list)
    approval_recorded: bool = False
    task_ledger_written: bool = False
    execution_started: bool = False
    broker_activated: bool = False
    idempotent_replay: bool = False
    message: str


class OwnerExecutionAuthorization(BaseModel):
    authorization_id: str = Field(min_length=4, max_length=160)
    delegation_id: str = Field(min_length=4, max_length=160)
    parent_task_id: str = Field(min_length=4, max_length=160)
    child_task_ids: list[str] = Field(min_length=1, max_length=6)
    authorized_by: str = Field(
        default="dipen-owner", min_length=2, max_length=120
    )
    approved: bool = True
    scope: str = Field(
        default="execute_delegated_tasks", min_length=4, max_length=120
    )
    validation_only: bool = True
    statement: str = Field(min_length=4, max_length=2000)
    authorized_at: datetime = Field(default_factory=utc_now)


class ExecutiveExecutionRequest(BaseModel):
    delegation_id: str = Field(min_length=4, max_length=160)
    parent_task_id: str = Field(min_length=4, max_length=160)
    child_task_ids: list[str] = Field(min_length=1, max_length=6)
    idempotency_key: str = Field(min_length=8, max_length=160)
    validation_only: bool = True
    owner_authorization: OwnerExecutionAuthorization | None = None


class ExecutionValidationEvidence(BaseModel):
    check_id: str = Field(min_length=2, max_length=120)
    passed: bool
    detail: str = Field(min_length=2, max_length=2000)


class ExecutiveExecutionResponse(BaseModel):
    execution_id: str
    delegation_id: str
    parent_task_id: str
    child_task_ids: list[str]
    generated_at: datetime = Field(default_factory=utc_now)
    disposition: ExecutionDisposition
    state: ExecutionAdmissionState
    selected_agent_ids: list[str] = Field(default_factory=list)
    reservation_ids: list[str] = Field(default_factory=list)
    validation_evidence: list[ExecutionValidationEvidence] = Field(
        default_factory=list
    )
    validation_only: bool = True
    admission_validated: bool = False
    task_ledger_mutated: bool = False
    reservation_acquired: bool = False
    execution_started: bool = False
    broker_activated: bool = False
    idempotent_replay: bool = False
    message: str


class ExecutiveOfficeCapability(BaseModel):
    service_id: str
    acting_role_id: str
    registry_employment_status: str
    mode: ExecutiveOfficeMode = "deterministic_advisory"
    active_runtime_employee: bool = False
    description: str


class ExecutiveOfficeStatusResponse(BaseModel):
    version: str
    generated_at: datetime = Field(default_factory=utc_now)
    read_only: bool = False
    delegation_enabled: bool = True
    task_ledger_writes_enabled: bool = True
    execution_admission_enabled: bool = False
    execution_reservation_enabled: bool = False
    execution_enabled: bool = False
    broker_activation_enabled: bool = False
    capabilities: list[ExecutiveOfficeCapability]
