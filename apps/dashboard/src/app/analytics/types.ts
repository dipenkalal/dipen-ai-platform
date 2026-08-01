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

export type RoutingMatchedTerm = {
  term: string;
  count: number;
};

export type RoutingAnalytics = {
  smart_runs: number;
  manual_runs: number;
  smart_routing_percentage: number;
  average_confidence: number;
  average_routing_latency_ms: number;
  most_selected_agent: string | null;
  agent_selection_distribution: Record<
    string,
    number
  >;
  top_matched_terms: RoutingMatchedTerm[];
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
  routing: RoutingAnalytics;
  agents: AgentAnalytics[];
  recent_runs: RecentAnalyticsRun[];
};

export type AnalyticsDashboardQuery = {
  agentLimit?: number;
  recentLimit?: number;
};
