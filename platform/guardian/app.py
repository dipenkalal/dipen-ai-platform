from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
            "mode": "read-only",
            "generated_at": utc_now(),
        },
        "host": {
            "hostname": socket.gethostname(),
            "uptime_seconds": read_uptime_seconds(),
            "load_average": load_average,
            "memory": read_memory(),
            "disks": disks,
        },
        "services": services,
        "dependencies": dependencies,
        "docker": read_containers(),
        "warnings": warnings,
        "healthy": len(warnings) == 0,
    }


STATUS_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DAP Guardian</title>
  <style>
    body {
      margin: 0;
      background: #020617;
      color: #e2e8f0;
      font-family: system-ui, sans-serif;
    }
    main {
      max-width: 1100px;
      margin: auto;
      padding: 32px 20px;
    }
    h1 {
      color: #67e8f9;
    }
    pre {
      overflow: auto;
      border: 1px solid #1e293b;
      border-radius: 16px;
      background: #0f172a;
      padding: 20px;
      line-height: 1.5;
    }
    .status {
      margin-bottom: 18px;
      color: #94a3b8;
    }
  </style>
</head>
<body>
  <main>
    <h1>DAP Guardian</h1>
    <p class="status" id="status">Loading machine awareness...</p>
    <pre id="state"></pre>
  </main>
  <script>
    async function refresh() {
      const status = document.getElementById("status");
      const state = document.getElementById("state");

      try {
        const response = await fetch("/api/v1/state");
        const data = await response.json();

        status.textContent = data.healthy
          ? "Guardian is healthy"
          : `Guardian detected ${data.warnings.length} warning(s)`;

        state.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        status.textContent = "Unable to load Guardian state";
        state.textContent = String(error);
      }
    }

    refresh();
    setInterval(refresh, 15000);
  </script>
</body>
</html>
"""


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
