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
