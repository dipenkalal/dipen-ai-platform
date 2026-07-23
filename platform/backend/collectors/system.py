from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil


def bytes_to_gb(value: int) -> float:
    """Convert bytes to gigabytes and round to two decimal places."""
    return round(value / (1024**3), 2)


def format_uptime(total_seconds: float) -> str:
    """Convert uptime seconds into a readable value."""
    seconds = int(total_seconds)

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts: list[str] = []

    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")

    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")

    if not days and minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    return ", ".join(parts) if parts else "Less than one minute"


def get_disk_usage(path: str) -> dict[str, Any]:
    """Return disk statistics for a filesystem path."""
    disk = psutil.disk_usage(path)

    return {
        "path": path,
        "total_gb": bytes_to_gb(disk.total),
        "used_gb": bytes_to_gb(disk.used),
        "free_gb": bytes_to_gb(disk.free),
        "percent": round(disk.percent, 1),
    }


def get_system_status() -> dict[str, Any]:
    """Collect current host system metrics."""
    memory = psutil.virtual_memory()
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    now = datetime.now(tz=timezone.utc)

    disks = {
        "system": get_disk_usage(str(Path.home().anchor or "/")),
    }

    return {
        "cpu": {
            "usage_percent": round(psutil.cpu_percent(interval=0.2), 1),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_threads": psutil.cpu_count(logical=True),
        },
        "memory": {
            "total_gb": bytes_to_gb(memory.total),
            "used_gb": bytes_to_gb(memory.used),
            "available_gb": bytes_to_gb(memory.available),
            "percent": round(memory.percent, 1),
        },
        "uptime": {
            "seconds": int((now - boot_time).total_seconds()),
            "formatted": format_uptime((now - boot_time).total_seconds()),
        },
        "disks": disks,
    }