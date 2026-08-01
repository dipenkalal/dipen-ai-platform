export type ServiceStatus =
  | "healthy"
  | "degraded"
  | "offline";

export type CpuMetric = {
  usage_percent: number;
  physical_cores: number | null;
  logical_threads: number | null;
};

export type SystemResourceMetric = {
  used: number;
  total: number;
  percent: number;
  unit: string;
};

export type SystemMonitoring = {
  cpu: CpuMetric;
  memory: SystemResourceMetric;
  disk: SystemResourceMetric;
  uptime_seconds: number;
  uptime_formatted: string;
};

export type ServiceHealth = {
  name: string;
  status: ServiceStatus;
  online: boolean;
  latency_ms: number | null;
  message: string | null;
  details: Record<string, unknown>;
};

export type PlatformCounts = {
  total_agents: number;
  enabled_agents: number;
  disabled_agents: number;
  registered_tools: number;
  stored_runs: number;
  knowledge_documents: number;
  knowledge_chunks: number;
};

export type InstalledModel = {
  name?: string | null;
  model?: string | null;
  size?: number | null;
  modified_at?: string | null;
  details?: Record<string, unknown>;
};

export type LoadedModel = {
  name?: string | null;
  size?: number | null;
  size_vram?: number | null;
  expires_at?: string | null;
};

export type ModelMonitoring = {
  loaded_models: LoadedModel[];
  loaded_model_count: number;
  installed_models: InstalledModel[];
  installed_model_count: number;
  embedding_model: string;
};

export type KnowledgeMonitoring = {
  qdrant_collection: string;
  collection_exists: boolean;
  documents: number;
  chunks: number;
  points: number;
  vector_size: number | null;
};

export type DatabaseMonitoring = {
  path: string;
  exists: boolean;
  size_bytes: number;
  stored_runs: number;
};

export type MonitoringOverview = {
  status: ServiceStatus;
  version: string;
  timestamp: string;
  system: SystemMonitoring;
  services: ServiceHealth[];
  platform: PlatformCounts;
  models: ModelMonitoring;
  knowledge: KnowledgeMonitoring;
  database: DatabaseMonitoring;
};
