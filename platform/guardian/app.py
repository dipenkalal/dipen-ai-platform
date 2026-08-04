from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlite_support import managed_connection
from personality import (
    ConversationContext,
    classify_intent,
    conversational_response,
    parse_context,
    resolve_topic,
)


SERVICE_UNITS = {
    "guardian": "dap-guardian.service",
    "backend": "dap-backend.service",
    "docker": "docker.service",
    "backup_timer": "dap-backup.timer",
}

HTTP_DEPENDENCIES = {
    "backend": "http://127.0.0.1:8002/health",
    "dashboard": "http://127.0.0.1/",
    "ollama": "http://127.0.0.1:11434/api/tags",
    "qdrant": "http://127.0.0.1:6333/healthz",
}

DISK_PATHS = {
    "root": Path("/"),
    "data": Path("/data"),
}

ACTION_CATALOG = {
    "restart_service": {
        "backend": {
            "unit": SERVICE_UNITS["backend"],
            "risk": "medium",
            "impact": (
                "The backend API will be briefly unavailable while "
                "systemd restarts it."
            ),
            "verification": [
                "Confirm dap-backend.service is active.",
                "Confirm http://127.0.0.1:8002/health returns HTTP 200.",
            ],
        },
        "guardian": {
            "unit": SERVICE_UNITS["guardian"],
            "risk": "medium",
            "impact": (
                "Guardian will briefly disconnect while its own "
                "systemd service restarts."
            ),
            "verification": [
                "Confirm dap-guardian.service is active.",
                "Confirm http://127.0.0.1:8001/health returns HTTP 200.",
            ],
        },
        "docker": {
            "unit": SERVICE_UNITS["docker"],
            "risk": "high",
            "impact": (
                "Docker and all managed containers may be unavailable "
                "during the restart."
            ),
            "verification": [
                "Confirm docker.service is active.",
                "Confirm expected DAP containers are running.",
                "Confirm monitored HTTP dependencies are healthy.",
            ],
        },
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_uptime_seconds() -> float | None:
    try:
        value = Path("/proc/uptime").read_text().split()[0]
        return round(float(value), 2)
    except (OSError, ValueError, IndexError):
        return None


def read_memory() -> dict[str, int | float | None]:
    values: dict[str, int] = {}

    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, raw_value = line.split(":", 1)
            value_kib = int(raw_value.strip().split()[0])
            values[key] = value_kib * 1024
    except (OSError, ValueError, IndexError):
        return {
            "total_bytes": None,
            "available_bytes": None,
            "used_bytes": None,
            "used_percent": None,
        }

    total = values.get("MemTotal")
    available = values.get("MemAvailable")

    if total is None or available is None or total <= 0:
        used = None
        used_percent = None
    else:
        used = total - available
        used_percent = round((used / total) * 100, 2)

    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": used,
        "used_percent": used_percent,
    }


def read_disk(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "available": False,
        }

    try:
        usage = shutil.disk_usage(path)
    except OSError as error:
        return {
            "path": str(path),
            "available": False,
            "error": str(error),
        }

    used_percent = (
        round((usage.used / usage.total) * 100, 2)
        if usage.total > 0
        else None
    )

    return {
        "path": str(path),
        "available": True,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": used_percent,
    }


def run_command(command: list[str], timeout: float = 3.0) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Command not found: {command[0]}",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out",
        }
    except OSError as error:
        return {
            "success": False,
            "error": str(error),
        }

    return {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def read_service_state(unit: str) -> dict[str, Any]:
    result = run_command(
        [
            "systemctl",
            "show",
            unit,
            "--property=LoadState",
            "--property=ActiveState",
            "--property=SubState",
            "--no-pager",
        ],
    )

    if not result["success"]:
        return {
            "unit": unit,
            "load_state": "unknown",
            "active_state": "unknown",
            "sub_state": "unknown",
            "error": result.get("stderr") or result.get("error"),
        }

    properties: dict[str, str] = {}

    for line in result["stdout"].splitlines():
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        properties[key] = value

    return {
        "unit": unit,
        "load_state": properties.get("LoadState", "unknown"),
        "active_state": properties.get("ActiveState", "unknown"),
        "sub_state": properties.get("SubState", "unknown"),
    }


def check_http(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={"User-Agent": "dap-guardian/0.1"},
    )

    try:
        with urlopen(request, timeout=2.0) as response:
            return {
                "url": url,
                "healthy": 200 <= response.status < 400,
                "status_code": response.status,
            }
    except HTTPError as error:
        return {
            "url": url,
            "healthy": False,
            "status_code": error.code,
            "error": str(error),
        }
    except (URLError, TimeoutError, OSError) as error:
        return {
            "url": url,
            "healthy": False,
            "status_code": None,
            "error": str(error),
        }


def read_containers() -> dict[str, Any]:
    result = run_command(
        [
            "docker",
            "ps",
            "--format",
            "{{json .}}",
        ],
        timeout=5.0,
    )

    if not result["success"]:
        return {
            "available": False,
            "containers": [],
            "error": result.get("stderr") or result.get("error"),
        }

    containers: list[dict[str, Any]] = []

    for line in result["stdout"].splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        containers.append(
            {
                "name": item.get("Names"),
                "image": item.get("Image"),
                "status": item.get("Status"),
                "state": item.get("State"),
                "ports": item.get("Ports"),
            },
        )

    return {
        "available": True,
        "count": len(containers),
        "containers": containers,
    }


def build_warnings(
    services: dict[str, dict[str, Any]],
    dependencies: dict[str, dict[str, Any]],
    disks: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []

    for name, state in services.items():
        if name == "guardian":
            continue

        if state.get("active_state") != "active":
            warnings.append(
                {
                    "severity": "warning",
                    "component": name,
                    "message": (
                        f"{state.get('unit')} is "
                        f"{state.get('active_state')}/"
                        f"{state.get('sub_state')}."
                    ),
                },
            )

    for name, state in dependencies.items():
        if not state.get("healthy"):
            warnings.append(
                {
                    "severity": "warning",
                    "component": name,
                    "message": (
                        f"{name} is not reachable at "
                        f"{state.get('url')}."
                    ),
                },
            )

    for name, state in disks.items():
        used_percent = state.get("used_percent")

        if isinstance(used_percent, (int, float)) and used_percent >= 90:
            warnings.append(
                {
                    "severity": "critical",
                    "component": f"disk:{name}",
                    "message": (
                        f"{state.get('path')} is "
                        f"{used_percent}% full."
                    ),
                },
            )

    return warnings


def read_top_processes(
    limit: int = 10,
) -> list[dict[str, Any]]:
    try:
        completed = subprocess.run(
            [
                "ps",
                "-eo",
                "pid=,user=,comm=,rss=,%mem=,etimes=",
                "--sort=-rss",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    if completed.returncode != 0:
        return []

    processes: list[dict[str, Any]] = []

    for line in completed.stdout.splitlines():
        fields = line.strip().split()

        if len(fields) < 6:
            continue

        (
            pid_value,
            user,
            command,
            rss_kb_value,
            memory_percent_value,
            elapsed_seconds_value,
        ) = fields[:6]

        try:
            process = {
                "pid": int(pid_value),
                "user": user,
                "command": command,
                "rss_bytes": int(rss_kb_value) * 1024,
                "memory_percent": float(
                    memory_percent_value
                ),
                "elapsed_seconds": int(
                    elapsed_seconds_value
                ),
            }
        except ValueError:
            continue

        processes.append(process)

        if len(processes) >= limit:
            break

    return processes


def build_state() -> dict[str, Any]:
    services = {
        name: read_service_state(unit)
        for name, unit in SERVICE_UNITS.items()
    }

    dependencies = {
        name: check_http(url)
        for name, url in HTTP_DEPENDENCIES.items()
    }

    disks = {
        name: read_disk(path)
        for name, path in DISK_PATHS.items()
    }

    warnings = build_warnings(
        services=services,
        dependencies=dependencies,
        disks=disks,
    )

    try:
        load_average = list(os.getloadavg())
    except OSError:
        load_average = []

    return {
        "guardian": {
            "name": "DAP Guardian",
            "version": "0.1.0",
            "mode": "approval-recording",
            "generated_at": utc_now(),
        },
        "host": {
            "hostname": socket.gethostname(),
            "uptime_seconds": read_uptime_seconds(),
            "load_average": load_average,
            "memory": read_memory(),
            "top_processes": read_top_processes(),
            "disks": disks,
        },
        "services": services,
        "dependencies": dependencies,
        "docker": read_containers(),
        "warnings": warnings,
        "healthy": len(warnings) == 0,
    }



OLLAMA_CHAT_URL = os.getenv(
    "DAP_GUARDIAN_OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat",
)
GUARDIAN_MODEL = os.getenv(
    "DAP_GUARDIAN_MODEL",
    "qwen3:1.7b",
)
GUARDIAN_OLLAMA_TIMEOUT_SECONDS = float(
    os.getenv("DAP_GUARDIAN_OLLAMA_TIMEOUT_SECONDS", "90"),
)
GUARDIAN_KEEP_ALIVE = int(
    os.getenv("DAP_GUARDIAN_KEEP_ALIVE", "0"),
)
GUARDIAN_MAX_RESPONSE_TOKENS = int(
    os.getenv("DAP_GUARDIAN_MAX_RESPONSE_TOKENS", "220"),
)
GUARDIAN_TEMPERATURE = float(
    os.getenv("DAP_GUARDIAN_TEMPERATURE", "0.0"),
)
MAX_QUESTION_BYTES = 16_384
GUARDIAN_ACTION_TOKEN = os.getenv(
    "DAP_GUARDIAN_ACTION_TOKEN",
    "",
)
GUARDIAN_STATE_DIR = Path(
    os.getenv(
        "DAP_GUARDIAN_STATE_DIR",
        str(Path.home() / "dap" / "data" / "guardian"),
    ),
)
GUARDIAN_ACTION_DB = GUARDIAN_STATE_DIR / "actions.sqlite3"
GUARDIAN_ACTION_PLAN_TTL_SECONDS = int(
    os.getenv("DAP_GUARDIAN_ACTION_PLAN_TTL_SECONDS", "600"),
)


def format_bytes(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "unknown"

    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(value)
    unit_index = 0

    while amount >= 1024 and unit_index < len(units) - 1:
        amount /= 1024
        unit_index += 1

    precision = 1 if amount >= 10 else 2
    return f"{amount:.{precision}f} {units[unit_index]}"


def deterministic_answer(
    question: str,
    state: dict[str, Any],
    topic: str | None = None,
) -> str:
    lowered = question.lower()
    topic = topic or resolve_topic(question)
    warnings = state.get("warnings", [])
    host = state.get("host", {})
    memory = host.get("memory", {})
    top_processes = host.get("top_processes", [])
    disks = host.get("disks", {})
    services = state.get("services", {})
    containers = state.get("docker", {}).get("containers", [])

    if topic == "memory":
        process_summary = "; ".join(
            (
                f"{process.get('command', 'unknown')} "
                f"({format_bytes(process.get('rss_bytes'))})"
            )
            for process in top_processes[:5]
        )

        answer = (
            f"Memory usage is currently "
            f"{memory.get('used_percent', 'unknown')}%. "
            f"Guardian reports "
            f"{format_bytes(memory.get('used_bytes'))} used and "
            f"{format_bytes(memory.get('available_bytes'))} available."
        )

        if process_summary:
            answer += (
                " Largest processes by resident memory: "
                f"{process_summary}."
            )

        return answer

    if any(word in lowered for word in ("wrong", "problem", "warning", "fail")):
        if not warnings:
            return (
                "I do not detect an active monitored failure. The monitored "
                "services and HTTP dependencies are currently responding."
            )

        return "\n".join(
            f"{item.get('component', 'unknown')}: "
            f"{item.get('message', 'warning detected')}"
            for item in warnings
        )

    if "backup" in lowered:
        backup = services.get("backup_timer", {})
        return (
            "The backup timer is currently "
            f"{backup.get('active_state', 'unknown')}/"
            f"{backup.get('sub_state', 'unknown')}."
        )

    if topic == "storage":
        root = disks.get("root", {})
        data = disks.get("data", {})
        media_note = ""
        if any(word in lowered for word in ("ssd", "hdd")):
            media_note = (
                "The live snapshot reports filesystem capacity but does not "
                "identify whether the underlying device is SSD or HDD. "
            )

        return (
            f"{media_note}"
            f"The root filesystem is {root.get('used_percent', 'unknown')}% full "
            f"with {format_bytes(root.get('free_bytes'))} free. "
            f"The /data filesystem is {data.get('used_percent', 'unknown')}% full "
            f"with {format_bytes(data.get('free_bytes'))} free."
        )

    if topic == "docker":
        if not containers:
            return "Guardian does not currently see any running containers."

        details = "\n".join(
            f"- {item.get('name', 'unknown')}: "
            f"{item.get('status', item.get('state', 'unknown'))}"
            for item in containers
        )
        return f"Guardian sees {len(containers)} containers:\n{details}"

    return (
        f"Guardian currently reports {len(warnings)} active warnings, "
        f"{len(containers)} visible containers, "
        f"{memory.get('used_percent', 'unknown')}% memory usage, and "
        f"{disks.get('root', {}).get('used_percent', 'unknown')}% root disk usage."
    )


def build_grounded_context(
    state: dict[str, Any],
) -> str:
    guardian = state.get("guardian", {})
    host = state.get("host", {})
    memory = host.get("memory", {})
    disks = host.get("disks", {})
    load_average = host.get("load_average", [])
    processes = host.get("top_processes", [])
    services = state.get("services", {})
    dependencies = state.get("dependencies", {})
    containers = state.get("docker", {}).get(
        "containers",
        [],
    )
    warnings = state.get("warnings", [])

    lines = [
        "LIVE DAP GUARDIAN SNAPSHOT",
        (
            f"generated_at={guardian.get('generated_at', 'unknown')} "
            f"hostname={host.get('hostname', 'unknown')} "
            f"uptime_seconds={host.get('uptime_seconds', 'unknown')}"
        ),
        (
            "MEMORY "
            f"used_percent={memory.get('used_percent', 'unknown')} "
            f"used={format_bytes(memory.get('used_bytes'))} "
            f"available={format_bytes(memory.get('available_bytes'))} "
            f"total={format_bytes(memory.get('total_bytes'))}"
        ),
    ]

    if load_average:
        lines.append(
            "LOAD_AVERAGE "
            + ",".join(
                str(round(float(value), 3))
                for value in load_average
            )
        )

    lines.append(
        "TOP_PROCESSES "
        "(each line is one exact PID/command pairing)"
    )

    for process in processes[:8]:
        lines.append(
            "PROCESS "
            f"pid={process.get('pid', 'unknown')} "
            f"command={process.get('command', 'unknown')} "
            f"user={process.get('user', 'unknown')} "
            f"rss={format_bytes(process.get('rss_bytes'))} "
            f"memory_percent="
            f"{process.get('memory_percent', 'unknown')} "
            f"elapsed_seconds="
            f"{process.get('elapsed_seconds', 'unknown')}"
        )

    for name, disk in disks.items():
        lines.append(
            "DISK "
            f"name={name} "
            f"path={disk.get('path', 'unknown')} "
            f"used_percent={disk.get('used_percent', 'unknown')} "
            f"free={format_bytes(disk.get('free_bytes'))}"
        )

    for name, service in services.items():
        lines.append(
            "SERVICE "
            f"name={name} "
            f"unit={service.get('unit', 'unknown')} "
            f"active={service.get('active_state', 'unknown')} "
            f"substate={service.get('sub_state', 'unknown')}"
        )

    for name, dependency in dependencies.items():
        lines.append(
            "DEPENDENCY "
            f"name={name} "
            f"healthy={dependency.get('healthy', False)} "
            f"http_status="
            f"{dependency.get('status_code', 'unknown')}"
        )

    for container in containers:
        lines.append(
            "CONTAINER "
            f"name={container.get('name', 'unknown')} "
            f"state={container.get('state', 'unknown')} "
            f"status={container.get('status', 'unknown')}"
        )

    if warnings:
        for warning in warnings:
            lines.append(
                "WARNING "
                f"component={warning.get('component', 'unknown')} "
                f"message={warning.get('message', 'unknown')}"
            )
    else:
        lines.append("WARNINGS none")

    return "\n".join(lines)


def call_ollama(
    question: str,
    state: dict[str, Any],
    context: ConversationContext | None = None,
) -> tuple[str, dict[str, Any]]:
    system_prompt = """
You are DAP Guardian, the always-on operations supervisor for Dipen's Acer server.

A live machine-state JSON snapshot will be provided with each question.

Rules:
- Answer the user's question directly and clearly.
- Base current factual claims only on the supplied live snapshot.
- Previous user and assistant messages are conversational context only and may be stale.
- Use the previous turn only to resolve references, corrections, and the requested subject.
- Stay within the requested focus; do not append a generic full-system report.
- A storage snapshot does not prove whether the device is SSD or HDD.
- If media type is not explicitly present, say that Guardian cannot distinguish SSD from HDD.
- Every PROCESS line is an exact PID, command and memory pairing.
- Copy process names and PIDs exactly; never relabel or rearrange them.
- Do not infer an application identity from generic process names such as python3, node, or uvicorn.
- Clearly separate measured facts from possible explanations.
- Describe listed processes as observed contributors, not the complete cause of total memory use.
- Never say memory usage is "due to" a process unless the supplied measurements prove that conclusion.
- Do not call usage high, low, excessive or minimal unless a defined threshold supports that label.
- Total memory can also include kernel memory, filesystem cache and processes outside the displayed top list.
- Never invent measurements, failures, commands or completed actions.
- Do not claim that you executed or changed anything.
- The approval and execution engine is not connected yet.
- For action requests, provide a plan and state whether root approval is required.
- Never expose internal reasoning.
- Answer in no more than six short sentences or six concise bullets.
- Finish the answer completely.
""".strip()

    focus = resolve_topic(question, context) or "technical"
    full_context = build_grounded_context(state)
    context_lines = full_context.splitlines()
    header = context_lines[:2]

    if focus == "storage":
        focused_lines = header + [
            line for line in context_lines if line.startswith("DISK ")
        ]
        focused_lines.append(
            "DISK_MEDIA_TYPE unavailable; the snapshot does not identify SSD or HDD"
        )
    elif focus == "memory":
        focused_lines = header + [
            line
            for line in context_lines
            if line.startswith(("MEMORY ", "LOAD_AVERAGE ", "TOP_PROCESSES ", "PROCESS "))
        ]
    elif focus == "docker":
        focused_lines = header + [
            line
            for line in context_lines
            if line.startswith(("CONTAINER ", "SERVICE name=docker"))
            or (line.startswith("WARNING ") and "docker" in line.lower())
        ]
        if len(focused_lines) == len(header):
            focused_lines.append("CONTAINERS none visible in the supplied snapshot")
    else:
        focused_lines = context_lines

    grounded_context = "\n".join(focused_lines)
    user_prompt = (
        f"Current user question:\n{question}\n\n"
        f"REQUESTED_FOCUS {focus}\n"
        f"{grounded_context}"
    )

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]
    if context is not None and context.previous_user:
        messages.append(
            {
                "role": "user",
                "content": context.previous_user,
            }
        )
        if context.previous_assistant:
            messages.append(
                {
                    "role": "assistant",
                    "content": context.previous_assistant,
                }
            )
    messages.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )

    request_body = {
        "model": GUARDIAN_MODEL,
        "stream": False,
        "think": False,
        "keep_alive": GUARDIAN_KEEP_ALIVE,
        "options": {
            "num_predict": GUARDIAN_MAX_RESPONSE_TOKENS,
            "temperature": GUARDIAN_TEMPERATURE,
            "top_p": 0.8,
        },
        "messages": messages,
    }

    request = Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(request_body).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urlopen(
        request,
        timeout=GUARDIAN_OLLAMA_TIMEOUT_SECONDS,
    ) as response:
        result = json.loads(response.read())

    message = result.get("message", {})
    answer = message.get("content", "").strip()

    if not answer:
        raise ValueError("Ollama returned an empty answer")

    usage = {
        "total_duration": result.get("total_duration"),
        "load_duration": result.get("load_duration"),
        "prompt_eval_count": result.get("prompt_eval_count"),
        "eval_count": result.get("eval_count"),
        "done_reason": result.get("done_reason"),
    }

    return answer, usage


def ask_guardian(
    question: str,
    context: ConversationContext | None = None,
) -> dict[str, Any]:
    intent = classify_intent(question, context)
    conversational = conversational_response(intent, question)
    if conversational is not None:
        return {
            "answer": conversational,
            "source": "guardian-personality",
            "model": None,
            "fallback": False,
            "generated_at": utc_now(),
            "intent": intent,
        }

    state = build_state()

    try:
        answer, usage = call_ollama(question, state, context)

        return {
            "answer": answer,
            "source": "ollama",
            "model": GUARDIAN_MODEL,
            "fallback": False,
            "generated_at": utc_now(),
            "state_generated_at": state["guardian"]["generated_at"],
            "usage": usage,
            "intent": intent,
        }
    except (
        HTTPError,
        URLError,
        TimeoutError,
        socket.timeout,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        return {
            "answer": deterministic_answer(
                question,
                state,
                resolve_topic(question, context),
            ),
            "source": "deterministic-fallback",
            "model": None,
            "fallback": True,
            "generated_at": utc_now(),
            "state_generated_at": state["guardian"]["generated_at"],
            "reason": f"{type(error).__name__}: {error}",
            "intent": intent,
        }


def validate_action_authorization(
    authorization_header: str | None,
) -> tuple[bool, int, str | None]:
    if not GUARDIAN_ACTION_TOKEN:
        return (
            False,
            503,
            "Guardian action API is disabled because no action token is configured.",
        )

    if not authorization_header:
        return False, 401, "Authorization header is required."

    scheme, separator, supplied_token = authorization_header.partition(" ")

    if (
        separator != " "
        or scheme.lower() != "bearer"
        or not supplied_token
    ):
        return False, 401, "A valid Bearer token is required."

    if not secrets.compare_digest(
        supplied_token,
        GUARDIAN_ACTION_TOKEN,
    ):
        return False, 403, "Action authorization failed."

    return True, 200, None


@contextmanager
def open_action_store() -> Iterator[sqlite3.Connection]:
    GUARDIAN_STATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o770,
    )

    try:
        GUARDIAN_STATE_DIR.chmod(0o770)
    except OSError:
        pass

    with managed_connection(
        GUARDIAN_ACTION_DB,
        timeout=5.0,
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS action_plans (
                plan_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                plan_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS action_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_at TEXT NOT NULL,
                details_json TEXT NOT NULL
            )
            """
        )

        try:
            GUARDIAN_ACTION_DB.chmod(0o660)
        except OSError:
            pass

        yield connection


def record_action_event(
    connection: sqlite3.Connection,
    plan_id: str,
    event_type: str,
    details: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO action_events (
            plan_id,
            event_type,
            event_at,
            details_json
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            plan_id,
            event_type,
            utc_now(),
            json.dumps(
                details,
                separators=(",", ":"),
                sort_keys=True,
            ),
        ),
    )


def persist_action_plan(plan: dict[str, Any]) -> None:
    serialized_plan = json.dumps(
        plan,
        separators=(",", ":"),
        sort_keys=True,
    )

    with open_action_store() as connection:
        connection.execute(
            """
            INSERT INTO action_plans (
                plan_id,
                created_at,
                expires_at,
                action,
                target,
                status,
                plan_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan["plan_id"],
                plan["generated_at"],
                plan["expires_at"],
                plan["action"],
                plan["target"],
                plan["status"],
                serialized_plan,
            ),
        )

        record_action_event(
            connection,
            plan["plan_id"],
            "plan_created",
            {
                "action": plan["action"],
                "target": plan["target"],
                "risk": plan["risk"],
                "expires_at": plan["expires_at"],
            },
        )


def build_action_plan(
    action: str,
    target: str,
) -> dict[str, Any]:
    action_targets = ACTION_CATALOG[action]
    definition = action_targets[target]
    unit = definition["unit"]

    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(
        seconds=GUARDIAN_ACTION_PLAN_TTL_SECONDS,
    )

    plan = {
        "plan_id": secrets.token_hex(16),
        "status": "approval_required",
        "generated_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "action": action,
        "target": target,
        "description": f"Restart {unit} through systemd.",
        "risk": definition["risk"],
        "impact": definition["impact"],
        "command": [
            "systemctl",
            "restart",
            unit,
        ],
        "approval": {
            "required": True,
            "level": "explicit",
            "root_required": True,
        },
        "verification": definition["verification"],
        "rollback": (
            "Restore the previous known-good configuration or code, "
            "then restart the same unit and repeat verification."
        ),
        "execution": {
            "available": False,
            "reason": (
                "The privileged action broker is not connected yet. "
                "This endpoint only creates a proposed plan."
            ),
        },
        "persisted": True,
    }

    persist_action_plan(plan)
    return plan


def approve_action_plan(
    plan_id: str,
    confirmation: str,
) -> tuple[dict[str, Any], int]:
    expected_confirmation = f"APPROVE {plan_id}"

    if not secrets.compare_digest(
        confirmation,
        expected_confirmation,
    ):
        return (
            {
                "error": "Explicit confirmation did not match.",
                "expected_confirmation": expected_confirmation,
            },
            400,
        )

    approved_at = datetime.now(timezone.utc)

    with open_action_store() as connection:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            """
            SELECT
                plan_id,
                expires_at,
                status,
                plan_json
            FROM action_plans
            WHERE plan_id = ?
            """,
            (plan_id,),
        ).fetchone()

        if row is None:
            return {"error": "Action plan not found."}, 404

        plan = json.loads(row["plan_json"])
        expires_at = datetime.fromisoformat(row["expires_at"])

        if approved_at >= expires_at:
            plan["status"] = "expired"
            plan["expired_at"] = approved_at.isoformat()

            connection.execute(
                """
                UPDATE action_plans
                SET status = ?, plan_json = ?
                WHERE plan_id = ?
                """,
                (
                    "expired",
                    json.dumps(
                        plan,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    plan_id,
                ),
            )

            record_action_event(
                connection,
                plan_id,
                "plan_expired",
                {
                    "previous_status": row["status"],
                    "expired_at": approved_at.isoformat(),
                },
            )

            return (
                {
                    "error": "Action plan has expired.",
                    "plan": plan,
                },
                409,
            )

        if row["status"] != "approval_required":
            return (
                {
                    "error": (
                        "Action plan cannot be approved because its "
                        f"status is {row['status']}."
                    ),
                    "plan": plan,
                },
                409,
            )

        plan["status"] = "approved"
        plan["approved_at"] = approved_at.isoformat()
        plan["approval"]["approved"] = True
        plan["approval"]["approved_at"] = approved_at.isoformat()
        plan["execution"] = {
            "available": False,
            "reason": (
                "Approval has been recorded, but the privileged "
                "action broker is not connected yet."
            ),
        }

        serialized_plan = json.dumps(
            plan,
            separators=(",", ":"),
            sort_keys=True,
        )

        connection.execute(
            """
            UPDATE action_plans
            SET status = ?, plan_json = ?
            WHERE plan_id = ?
              AND status = ?
            """,
            (
                "approved",
                serialized_plan,
                plan_id,
                "approval_required",
            ),
        )

        record_action_event(
            connection,
            plan_id,
            "plan_approved",
            {
                "approved_at": approved_at.isoformat(),
                "approval_level": plan["approval"]["level"],
                "root_required": plan["approval"]["root_required"],
            },
        )

    return plan, 200


STATIC_DIR = Path(__file__).parent / "static"
STATUS_PAGE = (STATIC_DIR / "index.html").read_text(encoding="utf-8")


class GuardianHandler(BaseHTTPRequestHandler):
    server_version = "DAPGuardian/0.1"

    def send_json(
        self,
        payload: dict[str, Any],
        status_code: int = 200,
    ) -> None:
        content = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ).encode()

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        supported_paths = {
            "/api/v1/ask",
            "/api/v1/actions/plan",
            "/api/v1/actions/approve",
        }

        if self.path not in supported_paths:
            self.send_json(
                {
                    "error": "Not found",
                    "path": self.path,
                },
                status_code=404,
            )
            return

        try:
            content_length = int(
                self.headers.get("Content-Length", "0"),
            )
        except ValueError:
            self.send_json(
                {"error": "Invalid Content-Length"},
                status_code=400,
            )
            return

        if content_length <= 0:
            self.send_json(
                {"error": "Request body is required"},
                status_code=400,
            )
            return

        if content_length > MAX_QUESTION_BYTES:
            self.send_json(
                {"error": "Request body is too large"},
                status_code=413,
            )
            return

        try:
            payload = json.loads(
                self.rfile.read(content_length),
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(
                {"error": "Request body must be valid JSON"},
                status_code=400,
            )
            return

        if not isinstance(payload, dict):
            self.send_json(
                {"error": "Request body must be a JSON object"},
                status_code=400,
            )
            return

        if self.path == "/api/v1/ask":
            question = payload.get("question")

            if not isinstance(question, str) or not question.strip():
                self.send_json(
                    {"error": "A non-empty question is required"},
                    status_code=400,
                )
                return

            context = payload.get("context")
            self.send_json(
                ask_guardian(question.strip(), parse_context(context))
                if context is not None
                else ask_guardian(question.strip()),
            )
            return

        authorized, status_code, authorization_error = (
            validate_action_authorization(
                self.headers.get("Authorization"),
            )
        )

        if not authorized:
            self.send_json(
                {"error": authorization_error},
                status_code=status_code,
            )
            return

        if self.path == "/api/v1/actions/approve":
            plan_id = payload.get("plan_id")
            confirmation = payload.get("confirmation")

            if not isinstance(plan_id, str) or not plan_id.strip():
                self.send_json(
                    {"error": "A non-empty plan_id is required."},
                    status_code=400,
                )
                return

            if (
                not isinstance(confirmation, str)
                or not confirmation.strip()
            ):
                self.send_json(
                    {"error": "Explicit confirmation is required."},
                    status_code=400,
                )
                return

            response, response_status = approve_action_plan(
                plan_id.strip(),
                confirmation.strip(),
            )

            self.send_json(
                response,
                status_code=response_status,
            )
            return

        action = payload.get("action")
        target = payload.get("target")

        if action not in ACTION_CATALOG:
            self.send_json(
                {
                    "error": "Unsupported action",
                    "allowed_actions": sorted(ACTION_CATALOG),
                },
                status_code=400,
            )
            return

        allowed_targets = ACTION_CATALOG[action]

        if target not in allowed_targets:
            self.send_json(
                {
                    "error": "Unsupported target",
                    "allowed_targets": sorted(allowed_targets),
                },
                status_code=400,
            )
            return

        self.send_json(
            build_action_plan(action, target),
            status_code=201,
        )

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(
                {
                    "status": "ok",
                    "service": "dap-guardian",
                    "timestamp": utc_now(),
                },
            )
            return

        if self.path == "/api/v1/state":
            self.send_json(build_state())
            return

        if self.path == "/":
            content = STATUS_PAGE.encode()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_json(
            {
                "error": "Not found",
                "path": self.path,
            },
            status_code=404,
        )

    def log_message(self, format: str, *args: Any) -> None:
        print(
            f"{self.address_string()} "
            f"[{self.log_date_time_string()}] "
            f"{format % args}",
            flush=True,
        )


def main() -> None:
    host = os.getenv("DAP_GUARDIAN_HOST", "127.0.0.1")
    port = int(os.getenv("DAP_GUARDIAN_PORT", "8001"))

    server = ThreadingHTTPServer(
        (host, port),
        GuardianHandler,
    )

    print(
        f"DAP Guardian listening on http://{host}:{port}",
        flush=True,
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
