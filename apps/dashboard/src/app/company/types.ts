export type DepartmentStatus =
  | "active"
  | "planned"
  | "suspended"
  | "retired";

export type EmploymentStatus =
  | "active"
  | "planned"
  | "disabled"
  | "suspended"
  | "retired"
  | "temporary";

export type AgentRuntimeStatus =
  | "unreported"
  | "available"
  | "busy"
  | "degraded"
  | "offline"
  | "disabled";

export type DisplayRuntimeStatus =
  | AgentRuntimeStatus
  | "planned"
  | "human"
  | "management"
  | "unknown";

export type DepartmentDefinition = {
  id: string;
  name: string;
  mission: string;
  status: DepartmentStatus;
  head_role_id: string;
  independent_control: boolean;
  leads_cross_department_projects: boolean;
  permanent: boolean;
  source_document: string;
};

export type RoleDefinition = {
  id: string;
  title: string;
  department_id: string | null;
  reports_to_role_id: string | null;
  role_kind:
    | "owner"
    | "executive"
    | "manager"
    | "specialist"
    | "control";
  career_level: string;
  runtime_kind: string;
  employment_status: EmploymentStatus;
  permanent: boolean;
  manager_only: boolean;
  machine_agent_id: string | null;
  mission: string;
  responsibilities: string[];
  authority: string[];
  prohibited_actions: string[];
  approved_systems: string[];
  evidence_requirements: string[];
  approval_requirements: string[];
  escalation_role_ids: string[];
  autonomy_ceiling: "observe" | "assist" | "operate";
  source_document: string;
};

export type OrganizationSnapshot = {
  organization_id: string;
  organization_name: string;
  registry_version: string;
  owner_role_id: string;
  ceo_role_id: string;
  summary: {
    department_count: number;
    role_count: number;
    active_roles: number;
    planned_roles: number;
    disabled_roles: number;
    active_specialists: number;
    manager_roles: number;
    mapped_agent_roles: number;
  };
  departments: DepartmentDefinition[];
  roles: RoleDefinition[];
};

export type TruthEvidence = {
  source: string;
  observed_at: string | null;
  detail: string;
};

export type AgentRuntimeState = {
  agent: {
    id: string;
    name?: string;
    enabled: boolean;
  };
  runtime_status: AgentRuntimeStatus;
  worker_id: string | null;
  current_task_id: string | null;
  model: string | null;
  process_id: number | null;
  container_id: string | null;
  last_heartbeat_at: string | null;
  heartbeat_age_seconds: number | null;
  evidence: TruthEvidence[];
};

export type AgentFleetStateResponse = {
  generated_at: string;
  summary: {
    registered: number;
    enabled: number;
    available: number;
    busy: number;
    degraded: number;
    offline: number;
    unreported: number;
    disabled: number;
  };
  agents: AgentRuntimeState[];
};

export type TaskLedgerRecord = {
  task_id: string;
  task_type: string;
  objective: string;
  status: string;
  priority: string;
  requested_by: string;
  assigned_agent_ids: string[];
  source_run_id: string | null;
  parent_task_id: string | null;
  current_step: string | null;
  progress_percent: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type TaskLedgerListResponse = {
  generated_at: string;
  tasks: TaskLedgerRecord[];
  total: number;
  limit: number;
  offset: number;
};

export type ServiceHealth = {
  name: string;
  status: "healthy" | "degraded" | "offline";
  online: boolean;
  latency_ms: number | null;
  message: string | null;
  details: Record<string, unknown>;
};

export type MonitoringOverview = {
  status: "healthy" | "degraded" | "offline";
  version: string;
  timestamp: string;
  services: ServiceHealth[];
  system: {
    cpu: {
      usage_percent: number;
    };
    memory: {
      percent: number;
    };
    disk: {
      percent: number;
    };
    uptime_formatted: string;
  };
};

export type SourceEnvelope<T> = {
  ok: boolean;
  status: number;
  data: T | null;
  error: string | null;
};

export type CompanyOperationsPayload = {
  generated_at: string;
  organization: SourceEnvelope<OrganizationSnapshot>;
  fleet: SourceEnvelope<AgentFleetStateResponse>;
  tasks: SourceEnvelope<TaskLedgerListResponse>;
  monitoring: SourceEnvelope<MonitoringOverview>;
};

export type EmployeeView = {
  role: RoleDefinition;
  department: DepartmentDefinition | null;
  manager: RoleDefinition | null;
  runtime: AgentRuntimeState | null;
  display_status: DisplayRuntimeStatus;
};
