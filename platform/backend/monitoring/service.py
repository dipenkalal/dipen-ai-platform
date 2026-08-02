import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from agents.registry import agent_registry
from collectors.ollama import (
    OLLAMA_BASE_URL,
    get_ollama_status,
)
from collectors.system import get_system_status
from history.database import history_database
from knowledge.config import (
    OLLAMA_EMBEDDING_MODEL,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from tools.registry import tool_registry
from shared_http import (
    shared_http_client,
)

from monitoring.schemas import (
    CpuMetric,
    DatabaseMonitoring,
    KnowledgeMonitoring,
    ModelMonitoring,
    MonitoringOverview,
    PlatformCounts,
    ServiceHealth,
    SystemMonitoring,
    SystemResourceMetric,
)



APP_VERSION = "0.8.1"

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _database_stats() -> DatabaseMonitoring:
    database_path = history_database.database_path
    exists = database_path.exists()

    size_bytes = (
        database_path.stat().st_size
        if exists
        else 0
    )

    stored_runs = 0

    if exists:
        try:
            with history_database.connection() as connection:
                row = connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM agent_runs
                    """
                ).fetchone()

                stored_runs = (
                    int(row["total"])
                    if row is not None
                    else 0
                )
        except sqlite3.Error:
            stored_runs = 0

    return DatabaseMonitoring(
        path=str(database_path),
        exists=exists,
        size_bytes=size_bytes,
        stored_runs=stored_runs,
    )


async def _check_history_database(
    database: DatabaseMonitoring,
) -> ServiceHealth:
    started = perf_counter()

    try:
        with history_database.connection() as connection:
            connection.execute(
                "SELECT 1"
            ).fetchone()

        latency_ms = (
            perf_counter() - started
        ) * 1000

        return ServiceHealth(
            name="History Database",
            status="healthy",
            online=True,
            latency_ms=round(latency_ms, 2),
            message="SQLite database is responding.",
            details={
                "path": database.path,
                "size_bytes": database.size_bytes,
                "stored_runs": database.stored_runs,
            },
        )

    except sqlite3.Error as exc:
        latency_ms = (
            perf_counter() - started
        ) * 1000

        return ServiceHealth(
            name="History Database",
            status="offline",
            online=False,
            latency_ms=round(latency_ms, 2),
            message=str(exc),
            details={
                "path": database.path,
            },
        )


async def _get_ollama_details() -> tuple[
    ServiceHealth,
    ModelMonitoring,
]:
    started = perf_counter()

    collector_status = await get_ollama_status()

    loaded_models = collector_status.get(
        "loaded_models",
        [],
    )

    installed_models: list[dict[str, Any]] = []

    error_message: str | None = None

    try:
        async with shared_http_client() as client:
            response = await client.get(
                f"{OLLAMA_BASE_URL}/api/tags"
            )
            response.raise_for_status()

        payload = response.json()

        installed_models = [
            {
                "name": model.get("name"),
                "model": model.get("model"),
                "size": model.get("size"),
                "modified_at": model.get(
                    "modified_at"
                ),
                "details": model.get(
                    "details",
                    {},
                ),
            }
            for model in payload.get(
                "models",
                [],
            )
        ]

    except (
        httpx.HTTPError,
        ValueError,
    ) as exc:
        error_message = str(exc)

    latency_ms = (
        perf_counter() - started
    ) * 1000

    online = bool(
        collector_status.get(
            "online",
            False,
        )
    )

    if online:
        status = "healthy"
        message = "Ollama is online."
    else:
        status = "offline"
        message = (
            collector_status.get("error")
            or error_message
            or "Ollama is not responding."
        )

    service = ServiceHealth(
        name="Ollama",
        status=status,
        online=online,
        latency_ms=round(latency_ms, 2),
        message=message,
        details={
            "base_url": OLLAMA_BASE_URL,
            "loaded_model_count": len(
                loaded_models
            ),
            "installed_model_count": len(
                installed_models
            ),
        },
    )

    models = ModelMonitoring(
        loaded_models=loaded_models,
        loaded_model_count=len(
            loaded_models
        ),
        installed_models=installed_models,
        installed_model_count=len(
            installed_models
        ),
        embedding_model=(
            OLLAMA_EMBEDDING_MODEL
        ),
    )

    return service, models


async def _get_qdrant_details() -> tuple[
    ServiceHealth,
    KnowledgeMonitoring,
]:
    started = perf_counter()

    collection_exists = False
    points_count = 0
    documents = 0
    chunks = 0
    vector_size: int | None = None

    try:
        async with shared_http_client() as client:
            collections_response = (
                await client.get(
                    f"{QDRANT_URL}/collections"
                )
            )
            collections_response.raise_for_status()

            collections_payload = (
                collections_response.json()
            )

            collections = (
                collections_payload
                .get("result", {})
                .get("collections", [])
            )

            collection_exists = any(
                collection.get("name")
                == QDRANT_COLLECTION
                for collection in collections
            )

            if collection_exists:
                collection_response = (
                    await client.get(
                        f"{QDRANT_URL}/collections/"
                        f"{QDRANT_COLLECTION}"
                    )
                )
                collection_response.raise_for_status()

                collection_payload = (
                    collection_response.json()
                )

                result = collection_payload.get(
                    "result",
                    {},
                )

                points_count = _safe_int(
                    result.get(
                        "points_count",
                        0,
                    )
                )

                chunks = points_count

                vectors_config = (
                    result.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                )

                if isinstance(
                    vectors_config,
                    dict,
                ):
                    vector_size_value = (
                        vectors_config.get("size")
                    )

                    if vector_size_value is not None:
                        vector_size = _safe_int(
                            vector_size_value
                        )

                scroll_response = (
                    await client.post(
                        f"{QDRANT_URL}/collections/"
                        f"{QDRANT_COLLECTION}/points/scroll",
                        json={
                            "limit": 10000,
                            "with_payload": True,
                            "with_vector": False,
                        },
                    )
                )
                scroll_response.raise_for_status()

                scroll_payload = (
                    scroll_response.json()
                )

                points = (
                    scroll_payload
                    .get("result", {})
                    .get("points", [])
                )

                document_ids: set[str] = set()

                for point in points:
                    payload = point.get(
                        "payload",
                        {},
                    )

                    document_id = (
                        payload.get("document_id")
                        or payload.get("source_id")
                        or payload.get("filename")
                    )

                    if document_id:
                        document_ids.add(
                            str(document_id)
                        )

                documents = len(
                    document_ids
                )

        latency_ms = (
            perf_counter() - started
        ) * 1000

        status = (
            "healthy"
            if collection_exists
            else "degraded"
        )

        message = (
            "Qdrant collection is available."
            if collection_exists
            else (
                "Qdrant is online, but the "
                "knowledge collection is missing."
            )
        )

        service = ServiceHealth(
            name="Qdrant",
            status=status,
            online=True,
            latency_ms=round(
                latency_ms,
                2,
            ),
            message=message,
            details={
                "url": QDRANT_URL,
                "collection": (
                    QDRANT_COLLECTION
                ),
                "collection_exists": (
                    collection_exists
                ),
                "points": points_count,
            },
        )

    except (
        httpx.HTTPError,
        ValueError,
    ) as exc:
        latency_ms = (
            perf_counter() - started
        ) * 1000

        service = ServiceHealth(
            name="Qdrant",
            status="offline",
            online=False,
            latency_ms=round(
                latency_ms,
                2,
            ),
            message=str(exc),
            details={
                "url": QDRANT_URL,
                "collection": (
                    QDRANT_COLLECTION
                ),
            },
        )

    knowledge = KnowledgeMonitoring(
        qdrant_collection=QDRANT_COLLECTION,
        collection_exists=collection_exists,
        documents=documents,
        chunks=chunks,
        points=points_count,
        vector_size=vector_size,
    )

    return service, knowledge


def _build_system_monitoring(
    payload: dict[str, Any],
) -> SystemMonitoring:
    cpu = payload.get("cpu", {})
    memory = payload.get("memory", {})
    uptime = payload.get("uptime", {})
    disks = payload.get("disks", {})

    system_disk = disks.get(
        "system",
        {},
    )

    return SystemMonitoring(
        cpu=CpuMetric(
            usage_percent=_safe_float(
                cpu.get("usage_percent")
            ),
            physical_cores=cpu.get(
                "physical_cores"
            ),
            logical_threads=cpu.get(
                "logical_threads"
            ),
        ),
        memory=SystemResourceMetric(
            used=_safe_float(
                memory.get("used_gb")
            ),
            total=_safe_float(
                memory.get("total_gb")
            ),
            percent=_safe_float(
                memory.get("percent")
            ),
            unit="GB",
        ),
        disk=SystemResourceMetric(
            used=_safe_float(
                system_disk.get("used_gb")
            ),
            total=_safe_float(
                system_disk.get("total_gb")
            ),
            percent=_safe_float(
                system_disk.get("percent")
            ),
            unit="GB",
        ),
        uptime_seconds=_safe_int(
            uptime.get("seconds")
        ),
        uptime_formatted=str(
            uptime.get(
                "formatted",
                "Unknown",
            )
        ),
    )


def _overall_status(
    services: list[ServiceHealth],
) -> str:
    statuses = {
        service.status
        for service in services
    }

    if "offline" in statuses:
        return "degraded"

    if "degraded" in statuses:
        return "degraded"

    return "healthy"


async def get_monitoring_overview() -> MonitoringOverview:
    system_payload = await asyncio.to_thread(
        get_system_status
    )

    database = await asyncio.to_thread(
        _database_stats
    )

    (
        ollama_result,
        qdrant_result,
        database_service,
    ) = await asyncio.gather(
        _get_ollama_details(),
        _get_qdrant_details(),
        _check_history_database(database),
    )

    ollama_service, models = ollama_result
    qdrant_service, knowledge = qdrant_result

    agents = agent_registry.list()
    tools = tool_registry.list_definitions()

    enabled_agents = sum(
        1
        for agent in agents
        if agent.enabled
    )

    platform = PlatformCounts(
        total_agents=len(agents),
        enabled_agents=enabled_agents,
        disabled_agents=(
            len(agents) - enabled_agents
        ),
        registered_tools=len(tools),
        stored_runs=database.stored_runs,
        knowledge_documents=(
            knowledge.documents
        ),
        knowledge_chunks=knowledge.chunks,
    )

    backend_service = ServiceHealth(
        name="Backend API",
        status="healthy",
        online=True,
        latency_ms=None,
        message="FastAPI backend is online.",
        details={
            "version": APP_VERSION,
        },
    )

    services = [
        backend_service,
        ollama_service,
        qdrant_service,
        database_service,
    ]

    return MonitoringOverview(
        status=_overall_status(
            services
        ),
        version=APP_VERSION,
        timestamp=datetime.now(
            timezone.utc
        ).isoformat(),
        system=_build_system_monitoring(
            system_payload
        ),
        services=services,
        platform=platform,
        models=models,
        knowledge=knowledge,
        database=database,
    )
