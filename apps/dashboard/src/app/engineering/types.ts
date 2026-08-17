export type EngineeringWorkspaceState =
  | "queued"
  | "active"
  | "completed"
  | "failed";

export type EngineeringProvenanceState =
  | "evidence_unavailable"
  | "consistent"
  | "requires_reconciliation";

export type EngineeringCheck = {
  name: string;
  category: "lint" | "typecheck" | "compile" | "test" | "ci" | "policy";
  status: "passed" | "failed" | "skipped";
  source: string;
  detail: string;
};

export type EngineeringPolicyDecision = {
  policy_id: string;
  authority: "dap" | "guardian" | "owner";
  decision: "allow" | "deny" | "require";
  detail: string;
};

export type EngineeringAuditEvidence = {
  evidence_version: "phase11f.1";
  evidence_id: string;
  source_execution_id: string;
  source_delegation_id: string;
  source_parent_task_id: string;
  source_task_id: string;
  source_task_sha256: string;
  source_admission_sha256: string;
  work_order_id: string;
  work_order_sha256: string;
  ticket_id: string;
  ticket_sha256: string;
  guardian_admission_id: string;
  guardian_admission_sha256: string;
  guardian_risk_class: "non_privileged_workspace";
  executor_runtime_identity: string;
  command_sha256: string | null;
  allowed_paths: string[];
  admitted_actions: string[];
  policy_decisions: EngineeringPolicyDecision[];
  execution_receipt_sha256: string | null;
  execution_disposition: "not_started" | "succeeded" | "failed" | "rejected";
  execution_exit_code: number | null;
  execution_findings: string[];
  changed_files: string[];
  diff_sha256: string | null;
  checks: EngineeringCheck[];
  delivery_id: string | null;
  delivery_plan_sha256: string | null;
  delivery_receipt_sha256: string | null;
  commit_sha: string | null;
  publication_id: string | null;
  publication_plan_sha256: string | null;
  publication_receipt_sha256: string | null;
  delivery_branch: string | null;
  remote_commit_sha: string | null;
  draft_pull_request_number: number | null;
  draft_pull_request_url: string | null;
  draft_pull_request_is_draft: boolean;
  outcome: "succeeded" | "failed" | "rejected" | "cancelled";
  terminal_stage:
    | "codex_execution"
    | "git_delivery"
    | "remote_publication"
    | "post_publication_checks"
    | null;
  failure_information: string | null;
  cancellation_information: string | null;
  owner_review_required: true;
  github_credentials_exposed_to_codex: false;
  github_credentials_exposed_to_ruflo: false;
  codex_git_authority: false;
  ruflo_git_authority: false;
  force_push_performed: false;
  protected_branch_updated: false;
  pull_request_auto_merge_enabled: false;
  main_merge_performed: false;
  tag_created: false;
  release_created: false;
  deployment_performed: false;
  task_ledger_mutated: false;
};

export type EngineeringEvidenceRecord = {
  evidence: EngineeringAuditEvidence;
  evidence_sha256: string;
  stored_at: string;
};

export type EngineeringTask = {
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

export type EngineeringWorkspaceItem = {
  task: EngineeringTask;
  workspace_state: EngineeringWorkspaceState;
  provenance_state: EngineeringProvenanceState;
  work_order_id: string | null;
  evidence_count: number;
  latest_evidence: EngineeringEvidenceRecord | null;
  owner_review_required: true;
  ui_execution_authority: false;
  ui_guardian_authority: false;
  ui_merge_authority: false;
  ui_deployment_authority: false;
};

export type EngineeringWorkspaceResponse = {
  summary: {
    total: number;
    queued: number;
    active: number;
    completed: number;
    failed: number;
    requires_reconciliation: number;
  };
  items: EngineeringWorkspaceItem[];
  read_only: true;
  execution_controls_exposed: false;
};
