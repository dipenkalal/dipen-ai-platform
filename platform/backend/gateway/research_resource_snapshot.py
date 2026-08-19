from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

import psutil
from pydantic import BaseModel, ConfigDict, Field


class ResearchResourceSnapshot(BaseModel):
    """Read-only backend process snapshot shown beside research reliability metrics."""

    model_config = ConfigDict(frozen=True)

    process_id: int = Field(ge=1)
    process_user_cpu_seconds: float = Field(ge=0)
    process_system_cpu_seconds: float = Field(ge=0)
    process_rss_bytes: int = Field(ge=0)
    process_rss_mib: float = Field(ge=0)
    system_memory_percent: float = Field(ge=0, le=100)
    system_cpu_percent: float = Field(ge=0, le=100)
    captured_at: datetime
    scope: Literal["dap-backend-process"] = "dap-backend-process"
    research_specific_attribution: Literal[False] = False
    read_only: Literal[True] = True
    network_authority_granted: Literal[False] = False
    mutation_authority_granted: Literal[False] = False
    service_control_authority_granted: Literal[False] = False


def capture_research_resource_snapshot() -> ResearchResourceSnapshot:
    process = psutil.Process(os.getpid())
    cpu_times = process.cpu_times()
    memory = process.memory_info()
    system_memory = psutil.virtual_memory()
    return ResearchResourceSnapshot(
        process_id=process.pid,
        process_user_cpu_seconds=float(cpu_times.user),
        process_system_cpu_seconds=float(cpu_times.system),
        process_rss_bytes=int(memory.rss),
        process_rss_mib=round(float(memory.rss) / (1024 * 1024), 2),
        system_memory_percent=float(system_memory.percent),
        system_cpu_percent=float(psutil.cpu_percent(interval=None)),
        captured_at=datetime.now(timezone.utc),
    )
