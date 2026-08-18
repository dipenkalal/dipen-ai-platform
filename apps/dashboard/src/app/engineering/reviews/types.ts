export type EngineeringOwnerReviewCheck = {
  name: string;
  category: string;
  status: string;
  detail: string;
};

export type EngineeringOwnerReviewPackage = {
  review_version: "phase11i.1";
  review_id: string;
  evidence_id: string;
  evidence_sha256: string;
  source_task_id: string;
  objective: string;
  work_order_id: string;
  risk_level: "low_non_privileged_workspace";
  changed_files: string[];
  checks: EngineeringOwnerReviewCheck[];
  commit_sha: string;
  delivery_branch: string;
  draft_pull_request_number: number;
  draft_pull_request_url: string;
  evidence_outcome: "succeeded";
  owner_action_required: "approve_or_reject";
  approval_effect: "record_review_only";
  owner_review_required: true;
  git_write_authority_granted: false;
  merge_authority_granted: false;
  deployment_authority_granted: false;
  guardian_authority_granted: false;
  task_ledger_mutation_allowed: false;
};

export type EngineeringOwnerReviewDecision = {
  decision_version: "phase11i.1";
  decision_id: string;
  review_id: string;
  review_sha256: string;
  evidence_id: string;
  evidence_sha256: string;
  source_task_id: string;
  owner_id: "dipen-owner";
  decision: "approve" | "reject";
  reason: string;
  review_recorded: true;
  owner_merge_action_still_required: true;
  git_write_performed: false;
  pull_request_merged: false;
  main_merge_performed: false;
  deployment_performed: false;
  guardian_contacted: false;
  task_ledger_mutated: false;
};

export type EngineeringOwnerReviewView = {
  package: EngineeringOwnerReviewPackage;
  decision: EngineeringOwnerReviewDecision | null;
};

export type EngineeringOwnerReviewListResponse = {
  reviews: EngineeringOwnerReviewView[];
  review_count: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  merge_controls_exposed: false;
  deployment_controls_exposed: false;
  guardian_controls_exposed: false;
};
