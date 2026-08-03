export type GuardianHealth = {
  service: string;
  status: string;
  timestamp: string;
};

export type GuardianAnswer = {
  answer: string;
  source: string;
  model: string | null;
  fallback: boolean;
};

export type GuardianActionEvent = {
  event_id: number;
  event_type: string;
  event_at: string;
  details: Record<string, unknown>;
};

export type GuardianActionPlan = {
  plan_id: string;
  created_at: string;
  expires_at: string;
  action: string;
  target: string;
  status: string;
  risk: string | null;
  approved: boolean;
  approved_at: string | null;
  execution_reserved_at: string | null;
  execution_started_at: string | null;
  execution_completed_at: string | null;
  execution: Record<string, unknown> | null;
  events: GuardianActionEvent[];
};

export type GuardianActionHistory = {
  read_only: true;
  database_present: boolean;
  generated_at: string;
  count: number;
  plans: GuardianActionPlan[];
};

export type GuardianVoiceState =
  | "locked"
  | "insecure"
  | "unsupported"
  | "preparing"
  | "sleeping"
  | "listening"
  | "thinking"
  | "speaking"
  | "muted"
  | "error";
