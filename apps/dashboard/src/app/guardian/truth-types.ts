import type { AgentInfo } from "@/app/agents/types";

export type AgentRuntimeStatus =
  | "unreported"
  | "available"
  | "busy"
  | "degraded"
  | "offline"
  | "disabled";

export type TruthEvidenceSource =
  | "agent-registry"
  | "runtime-heartbeat"
  | "task-ledger";

export type TruthEvidence = {
  source: TruthEvidenceSource;
  observed_at: string | null;
  detail: string;
};

export type AgentRuntimeState = {
  agent: AgentInfo;
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

export type AgentFleetSummary = {
  registered: number;
  enabled: number;
  available: number;
  busy: number;
  degraded: number;
  offline: number;
  unreported: number;
  disabled: number;
};

export type AgentFleetStateResponse = {
  generated_at: string;
  summary: AgentFleetSummary;
  agents: AgentRuntimeState[];
};

export type TaskLedgerStatus =
  | "created"
  | "planned"
  | "queued"
  | "assigned"
  | "running"
  | "waiting"
  | "completed"
  | "failed"
  | "cancelled"
  | "manual_review";

export type TaskLedgerRecord = {
  task_id: string;
  task_type: "agent" | "orchestration" | "system" | "personal";
  objective: string;
  status: TaskLedgerStatus;
  priority: "critical" | "high" | "normal" | "background" | "maintenance";
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
