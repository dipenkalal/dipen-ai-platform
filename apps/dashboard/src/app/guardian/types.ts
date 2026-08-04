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
  intent?: GuardianIntent;
};

export type GuardianIntent =
  | "greeting"
  | "casual"
  | "gratitude"
  | "farewell"
  | "identity"
  | "system_status"
  | "technical"
  | "action";

export type GuardianConversationContext = {
  previous_user: string;
  previous_assistant: string;
  previous_intent?: GuardianIntent;
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
  | "connecting"
  | "sleeping"
  | "listening"
  | "processing"
  | "thinking"
  | "speaking"
  | "muted"
  | "error";

export type VoiceServerMessage =
  | {
      type: "ready";
      state: "sleeping";
      stt_model: string;
      tts_voice: string;
    }
  | {
      type: "wake";
      state: "listening";
      heard: string;
      awaiting_command: boolean;
    }
  | {
      type: "processing";
      segment_ms: number;
    }
  | {
      type: "idle";
      state: "sleeping";
    }
  | {
      type: "command";
      text: string;
      heard: string;
      state: "sleeping";
    }
  | {
      type: "timeout";
      state: "sleeping";
    }
  | {
      type: "error";
      message: string;
    };

export type GuardianAudioFrame = {
  type: "audio";
  pcm: ArrayBuffer;
  level: number;
};
