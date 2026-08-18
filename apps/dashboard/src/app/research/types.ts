export type ResearchRetrievalOutcome =
  | "succeeded"
  | "failed"
  | "cancelled";

export type ResearchRetrievalStage =
  | "preflight"
  | "dns"
  | "destination-admission"
  | "connect"
  | "response"
  | "content-normalization"
  | "completed"
  | "cancelled";

export type ResearchRetrievalHopEvidence = {
  redirect_depth: number;
  canonical_url: string;
  destination_admission_id: string;
  destination_admission_sha256: string;
  connected_address: string;
  status_code: number;
  redirect_location: string | null;
};

export type ResearchCitation = {
  citation_id: string;
  citation_sha256: string;
  request_id: string;
  source_kind: "public_web";
  provider_id: string;
  source_url: string;
  source_title: string | null;
  content_evidence_id: string;
  normalized_text_sha256: string;
  retrieved_at: string;
};

export type ResearchRetrievalEvidence = {
  evidence_id: string;
  evidence_sha256: string;
  request_id: string;
  request_sha256: string;
  source_registry_sha256: string;
  canonical_task_id: string | null;
  canonical_admission_sha256: string | null;
  source_kind: "public_web";
  provider_id: string;
  outcome: ResearchRetrievalOutcome;
  stage: ResearchRetrievalStage;
  requested_url: string;
  final_url: string | null;
  method: "GET" | "HEAD";
  transport_id: string;
  status_code: number | null;
  content_type: string | null;
  byte_count: number | null;
  source_body_sha256: string | null;
  content_evidence_id: string | null;
  content_evidence_sha256: string | null;
  normalized_text_sha256: string | null;
  source_title: string | null;
  prompt_injection_finding_rule_ids: string[];
  hops: ResearchRetrievalHopEvidence[];
  citation: ResearchCitation | null;
  observed_at: string;
  error_code: string | null;
  error_detail: string | null;
  evidence_is_additive_only: true;
  task_ledger_mutation_performed: false;
  automatic_knowledge_mutation_performed: false;
  agent_tool_registration_performed: false;
  guardian_contacted: false;
  privileged_host_action_performed: false;
};

export type ResearchWorkspaceRunContext = {
  run_id: string;
  agent_id: string;
  objective: string;
  status: string;
  started_at: string;
  completed_at: string;
  provenance_source: "agent_run_history";
};

export type ResearchWorkspaceEvidenceItem = {
  evidence: ResearchRetrievalEvidence;
  stored_at: string;
  run: ResearchWorkspaceRunContext | null;
  provenance_kind: "internet_evidence";
  provenance_label: "Internet Evidence";
  knowledge_record: false;
  search_candidate_metadata_included: false;
  ui_network_authority_granted: false;
  ui_mutation_authority_granted: false;
};

export type ResearchWorkspaceListResponse = {
  items: ResearchWorkspaceEvidenceItem[];
  total: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  limit: number;
  workspace_mode: "read_only";
  network_authority_granted: false;
  mutation_authority_granted: false;
  search_candidate_metadata_included: false;
};

export type ResearchOperationsThresholds = {
  policy_id: "dap-research-reliability-slo-v1";
  minimum_success_rate: number;
  maximum_p95_source_duration_ms: number;
  maximum_failure_rate: number;
  maximum_duplicate_content_rate: number;
  minimum_unique_source_family_rate: number;
  factual_correctness_measured: false;
};

export type ResearchErrorCount = {
  error_code: string;
  count: number;
};

export type ResearchSourceFamilyCount = {
  source_family: string;
  count: number;
};

export type ResearchDuplicateContentGroup = {
  normalized_text_sha256: string;
  evidence_ids: string[];
  source_families: string[];
  duplicate_count: number;
};

export type ResearchProvenanceQuality = {
  evidence_id: string;
  score: number;
  outcome: string;
  citation_present: boolean;
  content_hash_present: boolean;
  normalized_hash_present: boolean;
  source_family: string | null;
  prompt_injection_finding_count: number;
  score_is_factual_credibility: false;
};

export type ResearchOperationsSummary = {
  window_event_count: number;
  evidence_total: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  success_rate: number;
  failure_rate: number;
  unique_source_family_count: number;
  unique_source_family_rate: number;
  duplicate_content_group_count: number;
  duplicate_content_evidence_count: number;
  duplicate_content_rate: number;
  average_source_duration_ms: number | null;
  p50_source_duration_ms: number | null;
  p95_source_duration_ms: number | null;
  retrieval_attempt_count: number;
  transient_retry_count: number;
  recovered_after_retry_count: number;
  prompt_injection_evidence_count: number;
  average_provenance_quality_score: number | null;
  errors: ResearchErrorCount[];
  source_families: ResearchSourceFamilyCount[];
  duplicate_content_groups: ResearchDuplicateContentGroup[];
  provenance_quality: ResearchProvenanceQuality[];
  thresholds: ResearchOperationsThresholds;
  meets_current_reliability_thresholds: boolean;
  reliability_posture:
    | "insufficient-data"
    | "within-thresholds"
    | "degraded";
  factual_correctness_measured: false;
  workspace_mode: "read_only";
  network_authority_granted: false;
  mutation_authority_granted: false;
};

export type ResearchRetentionPolicy = {
  policy_id: "dap-research-retention-dry-run-v1";
  default_preserve_all: true;
  duplicate_candidate_after_days: number;
  failed_candidate_after_days: number;
  succeeded_candidate_after_days: number;
  automatic_deletion_enabled: false;
  automatic_archive_enabled: false;
  owner_action_required_for_future_cleanup: true;
};

export type ResearchRetentionCandidate = {
  evidence_id: string;
  classification:
    | "preserve"
    | "future-archive-duplicate"
    | "future-archive-failed"
    | "future-archive-aged-success";
  reason: string;
  age_days: number;
  destructive_action_performed: false;
};

export type ResearchRetentionPlan = {
  mode: "dry_run";
  policy: ResearchRetentionPolicy;
  total_evidence: number;
  preserve_count: number;
  future_archive_candidate_count: number;
  candidates: ResearchRetentionCandidate[];
  evidence_deleted: false;
  evidence_mutated: false;
};

export type ResearchProviderHealth = {
  provider_id: "searxng-local-v1";
  endpoint: "http://127.0.0.1:8888/";
  healthy: boolean;
  status_code: number | null;
  latency_ms: number;
  error_code: string | null;
  checked_at: string;
  provider_is_local_only: true;
  loopback_contract_valid: true;
  network_authority_granted: false;
  mutation_authority_granted: false;
  service_control_authority_granted: false;
  credentials_used: false;
};
