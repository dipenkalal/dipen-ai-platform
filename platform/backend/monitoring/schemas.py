from typing import Any, Literal

from pydantic import BaseModel, Field


ServiceStatus = Literal[
    "healthy",
    "degraded",
    "offline",
]


class SystemResourceMetric(BaseModel):
    used: float
    total: float
    percent: float
    unit: str


class CpuMetric(BaseModel):
    usage_percent: float
    physical_cores: int | None
    logical_threads: int | None


class SystemMonitoring(BaseModel):
    cpu: CpuMetric
    memory: SystemResourceMetric
    disk: SystemResourceMetric
    uptime_seconds: int
    uptime_formatted: str


class ServiceHealth(BaseModel):
    name: str
    status: ServiceStatus
    online: bool
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] = Field(
        default_factory=dict
    )


class PlatformCounts(BaseModel):
    total_agents: int
    enabled_agents: int
    disabled_agents: int
    registered_tools: int
    stored_runs: int
    knowledge_documents: int
    knowledge_chunks: int


class ModelMonitoring(BaseModel):
    loaded_models: list[dict[str, Any]]
    loaded_model_count: int
    installed_models: list[dict[str, Any]]
    installed_model_count: int
    embedding_model: str


class KnowledgeMonitoring(BaseModel):
    qdrant_collection: str
    collection_exists: bool
    documents: int
    chunks: int
    points: int
    vector_size: int | None = None


class DatabaseMonitoring(BaseModel):
    path: str
    exists: bool
    size_bytes: int
    stored_runs: int


class MonitoringOverview(BaseModel):
    status: ServiceStatus
    version: str
    timestamp: str
    system: SystemMonitoring
    services: list[ServiceHealth]
    platform: PlatformCounts
    models: ModelMonitoring
    knowledge: KnowledgeMonitoring
    database: DatabaseMonitoring
