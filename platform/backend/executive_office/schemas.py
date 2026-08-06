from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high", "blocked"]
DecisionDisposition = Literal[
    "advisory",
    "ready_for_delegation",
    "approval_required",
    "blocked",
]
WorkStatus = Literal["planned", "approval_required", "blocked"]


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


class ExecutiveOfficeCapability(BaseModel):
    service_id: str
    acting_role_id: str
    registry_employment_status: str
    mode: Literal["deterministic_advisory"] = "deterministic_advisory"
    active_runtime_employee: bool = False
    description: str


class ExecutiveOfficeStatusResponse(BaseModel):
    version: str
    generated_at: datetime = Field(default_factory=utc_now)
    read_only: bool = True
    execution_enabled: bool = False
    capabilities: list[ExecutiveOfficeCapability]
