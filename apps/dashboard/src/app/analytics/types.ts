export type AnalyticsOverview = {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  running_runs: number;
  cancelled_runs: number;
  success_rate: number;
  average_latency_ms: number;
  total_tokens: number;
  runs_today: number;
  most_used_agent: string | null;
};

export type AgentAnalytics = {
  agent_id: string;
  runs: number;
  completed_runs: number;
  failed_runs: number;
  success_rate: number;
  average_latency_ms: number;
  total_tokens: number;
  last_used_at: string | null;
};

export type AnalyticsRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type RecentAnalyticsRun = {
  run_id: string;
  agent_id: string;
  objective: string;
  model: string | null;
  provider: string;
  status: AnalyticsRunStatus;
  total_tokens: number | null;
  latency_ms: number;
  started_at: string;
  completed_at: string | null;
};

export type AnalyticsDashboardResponse = {
  overview: AnalyticsOverview;
  agents: AgentAnalytics[];
  recent_runs: RecentAnalyticsRun[];
};

export type AnalyticsDashboardQuery = {
  agentLimit?: number;
  recentLimit?: number;
};
