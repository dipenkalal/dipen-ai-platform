from typing import (
    Literal,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


DepartmentStatus = Literal[
    "active",
    "planned",
    "suspended",
    "retired",
]

EmploymentStatus = Literal[
    "active",
    "planned",
    "disabled",
    "suspended",
    "retired",
    "temporary",
]

RoleKind = Literal[
    "owner",
    "executive",
    "manager",
    "specialist",
    "control",
]

CareerLevel = Literal[
    "associate",
    "specialist",
    "senior",
    "lead",
    "manager",
    "director",
    "executive",
    "owner",
]

RuntimeKind = Literal[
    "human_authority",
    "executive_service",
    "deterministic_service",
    "model_agent",
]

AutonomyMode = Literal[
    "observe",
    "assist",
    "operate",
]


class DepartmentDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=160)
    mission: str = Field(min_length=2, max_length=1000)
    status: DepartmentStatus = "active"
    head_role_id: str = Field(min_length=2, max_length=100)
    independent_control: bool = False
    leads_cross_department_projects: bool = False
    permanent: bool = True
    source_document: str = "docs/dap-company-operating-constitution.md"


class RoleDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=180)
    department_id: str | None = None
    reports_to_role_id: str | None = None

    role_kind: RoleKind
    career_level: CareerLevel
    runtime_kind: RuntimeKind
    employment_status: EmploymentStatus

    permanent: bool = True
    manager_only: bool = False
    machine_agent_id: str | None = None

    mission: str = Field(min_length=2, max_length=1400)
    responsibilities: list[str] = Field(default_factory=list)
    authority: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    approved_systems: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    approval_requirements: list[str] = Field(default_factory=list)
    escalation_role_ids: list[str] = Field(default_factory=list)

    autonomy_ceiling: AutonomyMode = "assist"
    source_document: str = "docs/dap-company-operating-constitution.md"


class OrganizationSummary(BaseModel):
    department_count: int = 0
    role_count: int = 0
    active_roles: int = 0
    planned_roles: int = 0
    disabled_roles: int = 0
    active_specialists: int = 0
    manager_roles: int = 0
    mapped_agent_roles: int = 0


class OrganizationSnapshot(BaseModel):
    organization_id: str
    organization_name: str
    registry_version: str
    owner_role_id: str
    ceo_role_id: str
    summary: OrganizationSummary
    departments: list[DepartmentDefinition] = Field(default_factory=list)
    roles: list[RoleDefinition] = Field(default_factory=list)


class DepartmentListResponse(BaseModel):
    total: int
    departments: list[DepartmentDefinition] = Field(default_factory=list)


class RoleListResponse(BaseModel):
    total: int
    roles: list[RoleDefinition] = Field(default_factory=list)


class ReportingChainResponse(BaseModel):
    role: RoleDefinition
    chain: list[RoleDefinition] = Field(default_factory=list)
