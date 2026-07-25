export type AgentCategory =
  | "system"
  | "knowledge"
  | "research"
  | "devops"
  | "coding"
  | "documentation"
  | "data"
  | "general";

export type AgentAccent =
  | "cyan"
  | "violet"
  | "emerald"
  | "amber"
  | "blue"
  | "rose"
  | "orange"
  | "slate";

export type AgentInfo = {
  id: string;
  name: string;
  description: string;
  category: AgentCategory;
  icon: string;
  accent: AgentAccent;
  tools: string[];
  capabilities: string[];
  recommended_model: string | null;
  safe: boolean;
  enabled: boolean;
};

export type ToolInfo = {
  id: string;
  name: string;
  description: string;
  category: string;
  safe: boolean;
  requires_confirmation: boolean;
};

export type ModelInfo = {
  provider: string;
  id: string;
  name: string;
  local: boolean;
  available: boolean;
  size_bytes: number | null;
};

export type AgentStepType =
  | "planning"
  | "tool"
  | "generation"
  | "result";

export type AgentStep = {
  step_number: number;
  type: AgentStepType;
  title: string;
  tool_id: string | null;
  success: boolean;
  input: unknown;
  output: unknown;
  error: string | null;
  started_at: string;
  completed_at: string;
};

export type AgentSource = {
  document_id?: string;
  filename?: string;
  title?: string;
  content?: string;
  score?: number;
  page?: number;
  chunk_index?: number;
  [key: string]: unknown;
};

export type UsageMetrics = {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number;
};

export type AgentRunStatus =
  | "idle"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentRun = {
  run_id: string;
  agent_id: string;
  objective: string;
  status: AgentRunStatus;
  answer: string;
  steps: AgentStep[];
  sources: AgentSource[];
  usage: UsageMetrics;
  started_at: string;
  completed_at: string | null;
};

export type AgentRunRequest = {
  agent_id: string;
  objective: string;
  model: string;
};

export type AgentStatusEvent = {
  type: "status";
  status: string;
  agent_id: string;
  message: string;
};

export type AgentStepEvent = {
  type: "step";
  step: AgentStep;
};

export type AgentAnswerEvent = {
  type: "answer";
  content: string;
  sources: AgentSource[];
};

export type AgentDoneEvent = {
  type: "done";
  run: AgentRun;
};

export type AgentErrorEvent = {
  type: "error";
  error?: string;
  message?: string;
};

export type AgentStreamEvent =
  | AgentStatusEvent
  | AgentStepEvent
  | AgentAnswerEvent
  | AgentDoneEvent
  | AgentErrorEvent;

export type AgentsResponse = {
  agents: AgentInfo[];
};

export type ToolsResponse = {
  tools: ToolInfo[];
};

export type ModelsResponse = {
  models: ModelInfo[];
};

export type AgentRunHistoryStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentRunSummary = {
  run_id: string;
  agent_id: string;
  objective: string;
  model: string | null;
  provider: string;
  status: AgentRunHistoryStatus;
  answer_preview: string;
  error: string | null;
  step_count: number;
  source_count: number;
  total_tokens: number | null;
  latency_ms: number;
  started_at: string;
  completed_at: string;
  created_at: string;
};

export type AgentRunHistoryResponse = {
  runs: AgentRunSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type AgentRunRecord = {
  run_id: string;
  agent_id: string;
  objective: string;
  model: string | null;
  provider: string;
  status: AgentRunHistoryStatus;
  answer: string;
  error: string | null;
  steps: AgentStep[];
  sources: AgentSource[];
  usage: UsageMetrics;
  request: {
    agent_id: string;
    objective: string;
    model: string | null;
    provider: string;
    temperature: number;
    max_tokens: number;
    max_steps: number;
    retrieval_limit: number;
    score_threshold: number | null;
    document_id: string | null;
  };
  started_at: string;
  completed_at: string;
  created_at: string;
  updated_at: string;
};
