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
