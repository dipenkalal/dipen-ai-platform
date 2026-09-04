export type CareerVerdict =
  | "APPLY"
  | "CONSIDER";

export type CareerDashboardJob = {
  job_id: string;
  snapshot_id: string;
  assessment_id: string;

  title: string;
  employer_name: string;

  location_text: string | null;
  work_mode: string | null;
  employment_type: string | null;
  salary_text: string | null;

  posted_at: string | null;
  closing_at: string | null;
  observed_at: string;
  last_seen_at: string;

  freshness_state: string;
  verification_state: string;
  lifecycle_state: string;

  fit_score: number;
  verdict: CareerVerdict;

  hard_exclusion_codes: string[];
  score_breakdown: Record<string, unknown>;
  explanation: unknown;

  canonical_job_url: string;
  canonical_apply_url: string | null;
  manual_apply_url: string;

  application_id: string | null;
  application_state: string | null;
};

export type CareerDashboardListResponse = {
  total: number;
  items: CareerDashboardJob[];
};

export type CareerDashboardSummary = {
  verified_active_jobs: number;
  apply_jobs: number;
  consider_jobs: number;
  visible_jobs: number;
  application_records: number;

  production_database_write_enabled: false;
  application_submission_enabled: false;
  auto_apply_enabled: false;
};

// DAP_V2_CAREER_COCKPIT_TYPES_BEGIN
// Generated from the sealed live Career OpenAPI contract.

export type CareerCockpitCreateApplicationRequest =
  { notes?: string | null; reason: string; };

export type CareerCockpitCreateApplicationResponse =
  { application_id: string; applied_confirmation_kind?: "OWNER_MANUAL" | "FUTURE_BROKER_EVIDENCE" | null; applied_confirmed_at?: string | null; created_at: string; job_id: string; notes?: string | null; owner_approved_at?: string | null; state: "SHORTLISTED" | "PREPARING" | "READY_FOR_REVIEW" | "OWNER_APPROVED" | "APPLIED_CONFIRMED" | "INTERVIEW" | "REJECTED" | "WITHDRAWN" | "OFFER" | "CLOSED"; updated_at: string; };

export type CareerCockpitApplicationResponse =
  { application_id: string; applied_confirmation_kind?: "OWNER_MANUAL" | "FUTURE_BROKER_EVIDENCE" | null; applied_confirmed_at?: string | null; created_at: string; job_id: string; notes?: string | null; owner_approved_at?: string | null; state: "SHORTLISTED" | "PREPARING" | "READY_FOR_REVIEW" | "OWNER_APPROVED" | "APPLIED_CONFIRMED" | "INTERVIEW" | "REJECTED" | "WITHDRAWN" | "OFFER" | "CLOSED"; updated_at: string; };

export type CareerCockpitApplicationEventsResponse =
  { items: ({ actor_id: string; actor_kind: "OWNER" | "DETERMINISTIC_SYSTEM"; application_id: string; event_id: string; evidence_id?: string | null; from_state?: "SHORTLISTED" | "PREPARING" | "READY_FOR_REVIEW" | "OWNER_APPROVED" | "APPLIED_CONFIRMED" | "INTERVIEW" | "REJECTED" | "WITHDRAWN" | "OFFER" | "CLOSED" | null; occurred_at: string; reason: string; to_state: "SHORTLISTED" | "PREPARING" | "READY_FOR_REVIEW" | "OWNER_APPROVED" | "APPLIED_CONFIRMED" | "INTERVIEW" | "REJECTED" | "WITHDRAWN" | "OFFER" | "CLOSED"; })[]; total: number; };

export type CareerCockpitTransitionRequest =
  { evidence_id?: string | null; reason: string; to_state: "SHORTLISTED" | "PREPARING" | "READY_FOR_REVIEW" | "OWNER_APPROVED" | "APPLIED_CONFIRMED" | "INTERVIEW" | "REJECTED" | "WITHDRAWN" | "OFFER" | "CLOSED"; };

export type CareerCockpitTransitionResponse =
  { application_id: string; applied_confirmation_kind?: "OWNER_MANUAL" | "FUTURE_BROKER_EVIDENCE" | null; applied_confirmed_at?: string | null; created_at: string; job_id: string; notes?: string | null; owner_approved_at?: string | null; state: "SHORTLISTED" | "PREPARING" | "READY_FOR_REVIEW" | "OWNER_APPROVED" | "APPLIED_CONFIRMED" | "INTERVIEW" | "REJECTED" | "WITHDRAWN" | "OFFER" | "CLOSED"; updated_at: string; };

export type CareerCockpitReadinessResponse =
  { application_id: string; blockers?: ({ code: "APPLICATION_NOT_PREPARING" | "PRIMARY_RESUME_MISSING" | "BLOCKING_MATERIAL_HAS_NO_VERSION" | "CURRENT_SNAPSHOT_MISSING" | "LATEST_VERSION_SNAPSHOT_STALE" | "SNAPSHOT_JOB_MISMATCH" | "CREATED_EVENT_MISSING" | "READY_EVENT_MISSING" | "LATEST_VERSION_REJECTED"; material_id?: string | null; material_version_id?: string | null; })[]; ready: boolean; };

export type CareerCockpitAdvanceToReviewRequest =
  { reason: string; };

export type CareerCockpitAdvanceToReviewResponse =
  { application_id: string; applied_confirmation_kind?: "OWNER_MANUAL" | "FUTURE_BROKER_EVIDENCE" | null; applied_confirmed_at?: string | null; created_at: string; job_id: string; notes?: string | null; owner_approved_at?: string | null; state: "SHORTLISTED" | "PREPARING" | "READY_FOR_REVIEW" | "OWNER_APPROVED" | "APPLIED_CONFIRMED" | "INTERVIEW" | "REJECTED" | "WITHDRAWN" | "OFFER" | "CLOSED"; updated_at: string; };

export type CareerCockpitApproveApplicationRequest =
  { reason: string; };

export type CareerCockpitApproveApplicationResponse =
  { application_id: string; applied_confirmation_kind?: "OWNER_MANUAL" | "FUTURE_BROKER_EVIDENCE" | null; applied_confirmed_at?: string | null; created_at: string; job_id: string; notes?: string | null; owner_approved_at?: string | null; state: "SHORTLISTED" | "PREPARING" | "READY_FOR_REVIEW" | "OWNER_APPROVED" | "APPLIED_CONFIRMED" | "INTERVIEW" | "REJECTED" | "WITHDRAWN" | "OFFER" | "CLOSED"; updated_at: string; };

export type CareerCockpitConfirmAppliedRequest =
  { reason: string; };

export type CareerCockpitConfirmAppliedResponse =
  CareerCockpitApplicationResponse;

export type CareerCockpitApplicationMaterialsResponse =
  { items: ({ application_id: string; created_at: string; label: string; material_id: string; material_kind: "RESUME" | "COVER_LETTER" | "APPLICATION_NOTES"; })[]; total: number; };

export type CareerCockpitCreateMaterialRequest =
  { label: string; material_kind: "RESUME" | "COVER_LETTER" | "APPLICATION_NOTES"; };

export type CareerCockpitCreateMaterialResponse =
  { application_id: string; created_at: string; label: string; material_id: string; material_kind: "RESUME" | "COVER_LETTER" | "APPLICATION_NOTES"; };

export type CareerCockpitMaterialVersionsResponse =
  { items: ({ content_format: "TEXT" | "MARKDOWN" | "LATEX" | "JSON"; content_sha256: string; content_text: string; created_at: string; created_by_id: string; created_by_kind: "OWNER" | "DAP_GENERATOR"; material_id: string; material_version_id: string; parent_material_version_id?: string | null; provenance: { application_id: string; creation_mechanism: string; generator_kind: "OWNER" | "DAP_GENERATOR"; job_id: string; model_name?: string | null; model_provider?: string | null; parent_material_version_id?: string | null; profile_version?: string | null; snapshot_id: string; source_material_version_ids?: string[]; }; source_snapshot_id: string; version_number: number; })[]; total: number; };

export type CareerCockpitCreateMaterialVersionRequest =
  { content_format: "TEXT" | "MARKDOWN" | "LATEX" | "JSON"; content_text: string; parent_material_version_id?: string | null; profile_version?: string | null; source_snapshot_id: string; };

export type CareerCockpitCreateMaterialVersionResponse =
  { content_format: "TEXT" | "MARKDOWN" | "LATEX" | "JSON"; content_sha256: string; content_text: string; created_at: string; created_by_id: string; created_by_kind: "OWNER" | "DAP_GENERATOR"; material_id: string; material_version_id: string; parent_material_version_id?: string | null; provenance: { application_id: string; creation_mechanism: string; generator_kind: "OWNER" | "DAP_GENERATOR"; job_id: string; model_name?: string | null; model_provider?: string | null; parent_material_version_id?: string | null; profile_version?: string | null; snapshot_id: string; source_material_version_ids?: string[]; }; source_snapshot_id: string; version_number: number; };

export type CareerCockpitMaterialVersionEventsResponse =
  { items: ({ actor_id: string; actor_kind: "OWNER" | "DAP_SYSTEM"; event_kind: "CREATED" | "MARKED_READY_FOR_REVIEW" | "APPROVED" | "REJECTED"; evidence_id?: string | null; material_event_id: string; material_version_id: string; occurred_at: string; reason: string; })[]; total: number; };

export type CareerCockpitMarkMaterialReadyRequest =
  { reason: string; };

export type CareerCockpitMarkMaterialReadyResponse =
  { actor_id: string; actor_kind: "OWNER" | "DAP_SYSTEM"; event_kind: "CREATED" | "MARKED_READY_FOR_REVIEW" | "APPROVED" | "REJECTED"; evidence_id?: string | null; material_event_id: string; material_version_id: string; occurred_at: string; reason: string; };

export type CareerCockpitMaterialDecisionRequest =
  { decision: "approve" | "reject"; reason?: string; };

export type CareerCockpitMaterialDecisionResponse =
  { actor_id: string; actor_kind: "OWNER" | "DAP_SYSTEM"; event_kind: "CREATED" | "MARKED_READY_FOR_REVIEW" | "APPROVED" | "REJECTED"; evidence_id?: string | null; material_event_id: string; material_version_id: string; occurred_at: string; reason: string; };

// DAP_V2_CAREER_COCKPIT_TYPES_END

// DAP_V2_OWNER_REVIEW_TYPES_BEGIN

export type CareerOwnerReviewJob = {
  job_id: string;
  employer_name: string;
  requisition_id?: string | null;
  canonical_job_url: string;
  canonical_apply_url?: string | null;
  current_snapshot_id?: string | null;
  verification_state: string;
  lifecycle_state: string;
  first_seen_at: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
};

export type CareerOwnerReviewSnapshot = {
  snapshot_id: string;
  job_id: string;
  source_id: string;
  title: string;
  employer_name: string;
  location_text?: string | null;
  work_mode?: string | null;
  employment_type?: string | null;
  description_text: string;
  description_sha256: string;
  posted_at?: string | null;
  closing_at?: string | null;
  freshness_state: string;
  salary_text?: string | null;
  requirements: Record<string, unknown>;
  normalized_text_sha256: string;
  observed_at: string;
};

export type CareerOwnerReviewApprovalBlocker = {
  code: string;
  material_id?: string | null;
  material_version_id?: string | null;
};

export type CareerOwnerReviewApproval = {
  application_id: string;
  approved: boolean;
  blockers: CareerOwnerReviewApprovalBlocker[];
};

export type CareerOwnerReviewQueueItem = {
  application:
    CareerCockpitApplicationResponse;
  job: CareerOwnerReviewJob;
  current_snapshot:
    CareerOwnerReviewSnapshot | null;
  readiness:
    CareerCockpitReadinessResponse;
  approval:
    CareerOwnerReviewApproval;
};

export type CareerOwnerReviewQueueResponse = {
  total: number;
  items: CareerOwnerReviewQueueItem[];
};

export type CareerOwnerReviewMaterial = {
  material:
    CareerCockpitApplicationMaterialsResponse[
      "items"
    ][number];
  latest_version:
    CareerCockpitMaterialVersionsResponse[
      "items"
    ][number]
    | null;
  latest_version_events:
    CareerCockpitMaterialVersionEventsResponse[
      "items"
    ];
};

export type CareerOwnerReviewPackageResponse = {
  application:
    CareerCockpitApplicationResponse;
  job: CareerOwnerReviewJob;
  current_snapshot:
    CareerOwnerReviewSnapshot | null;
  readiness:
    CareerCockpitReadinessResponse;
  approval:
    CareerOwnerReviewApproval;
  application_events:
    CareerCockpitApplicationEventsResponse[
      "items"
    ];
  materials:
    CareerOwnerReviewMaterial[];
};

// DAP_V2_OWNER_REVIEW_TYPES_END
