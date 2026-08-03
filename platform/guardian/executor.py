from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_UNIT = "dap-backend.service"

BACKEND_RESTART_COMMAND = (
    "/usr/bin/systemctl",
    "restart",
    BACKEND_UNIT,
)

BACKEND_VERIFY_COMMAND = (
    "/usr/bin/systemctl",
    "is-active",
    BACKEND_UNIT,
)

BACKEND_HEALTH_URL = "http://127.0.0.1:8002/health"
BACKEND_HEALTH_MAX_BYTES = 16 * 1024


class BackendRestartError(Exception):
    def __init__(
        self,
        message: str,
        *,
        attempted: bool,
        performed: bool,
    ) -> None:
        super().__init__(message)
        self.attempted = attempted
        self.performed = performed


class BackendHealthError(Exception):
    pass


def safe_output(value: str | None, limit: int = 500) -> str:
    if not value:
        return ""

    return value.strip()[:limit]


def verify_backend_http_health(
    *,
    timeout: float,
) -> dict[str, Any]:
    request = Request(
        BACKEND_HEALTH_URL,
        headers={
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            status_code = getattr(response, "status", None)
            body = response.read(
                BACKEND_HEALTH_MAX_BYTES + 1
            )
    except HTTPError as error:
        status_code = error.code
        error.close()
        raise BackendHealthError(
            "Backend health endpoint returned "
            f"HTTP {status_code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise BackendHealthError(
            "Backend health endpoint could not be reached: "
            f"{error}"
        ) from error

    if status_code != 200:
        raise BackendHealthError(
            "Backend health endpoint returned "
            f"HTTP {status_code}."
        )

    if len(body) > BACKEND_HEALTH_MAX_BYTES:
        raise BackendHealthError(
            "Backend health response exceeded the size limit."
        )

    try:
        payload = json.loads(
            body.decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BackendHealthError(
            "Backend health response was not valid UTF-8 JSON."
        ) from error

    if not isinstance(payload, dict):
        raise BackendHealthError(
            "Backend health response was not a JSON object."
        )

    if payload.get("status") != "healthy":
        reported_status = safe_output(
            str(payload.get("status")),
            limit=100,
        )
        raise BackendHealthError(
            "Backend health endpoint did not report healthy. "
            f"Reported status: {reported_status or 'missing'}."
        )

    result = {
        "url": BACKEND_HEALTH_URL,
        "status_code": status_code,
        "status": "healthy",
    }

    version = payload.get("version")

    if isinstance(version, str) and version:
        result["version"] = version

    return result


def restart_backend_service(
    *,
    restart_timeout: float = 30.0,
    verification_timeout: float = 5.0,
    health_timeout: float = 2.0,
    verification_attempts: int = 10,
    verification_interval: float = 1.0,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise BackendRestartError(
            "Backend restart execution requires root.",
            attempted=False,
            performed=False,
        )

    if (
        restart_timeout <= 0
        or verification_timeout <= 0
        or health_timeout <= 0
    ):
        raise BackendRestartError(
            "Execution timeouts must be positive.",
            attempted=False,
            performed=False,
        )

    if verification_attempts < 1:
        raise BackendRestartError(
            "At least one verification attempt is required.",
            attempted=False,
            performed=False,
        )

    if verification_interval < 0:
        raise BackendRestartError(
            "Verification interval cannot be negative.",
            attempted=False,
            performed=False,
        )

    started_at = datetime.now(timezone.utc)

    try:
        restart_result = subprocess.run(
            BACKEND_RESTART_COMMAND,
            check=False,
            capture_output=True,
            text=True,
            timeout=restart_timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise BackendRestartError(
            "Backend restart command timed out.",
            attempted=True,
            performed=False,
        ) from error
    except OSError as error:
        raise BackendRestartError(
            f"Backend restart command failed to start: {error}",
            attempted=True,
            performed=False,
        ) from error

    if restart_result.returncode != 0:
        detail = safe_output(
            restart_result.stderr or restart_result.stdout
        )

        message = "Backend restart command returned a failure."

        if detail:
            message = f"{message} {detail}"

        raise BackendRestartError(
            message,
            attempted=True,
            performed=False,
        )

    last_state = "unknown"
    last_health_error: str | None = None
    saw_systemd_active = False

    for attempt in range(1, verification_attempts + 1):
        try:
            verification_result = subprocess.run(
                BACKEND_VERIFY_COMMAND,
                check=False,
                capture_output=True,
                text=True,
                timeout=verification_timeout,
            )
        except subprocess.TimeoutExpired:
            last_state = "verification-timeout"
        except OSError as error:
            last_state = f"verification-error: {error}"
        else:
            reported_state = safe_output(
                verification_result.stdout,
                limit=100,
            )

            last_state = reported_state or "unknown"

            if (
                verification_result.returncode == 0
                and reported_state == "active"
            ):
                saw_systemd_active = True

                try:
                    health = verify_backend_http_health(
                        timeout=health_timeout,
                    )
                except BackendHealthError as error:
                    last_health_error = str(error)
                else:
                    completed_at = datetime.now(timezone.utc)

                    return {
                        "attempted": True,
                        "performed": True,
                        "verified": True,
                        "unit": BACKEND_UNIT,
                        "command": list(BACKEND_RESTART_COMMAND),
                        "verification_command": list(
                            BACKEND_VERIFY_COMMAND
                        ),
                        "verification_attempts": attempt,
                        "service_state": "active",
                        "health": health,
                        "started_at": started_at.isoformat(),
                        "completed_at": completed_at.isoformat(),
                    }

        if attempt < verification_attempts:
            time.sleep(verification_interval)

    if saw_systemd_active and last_health_error:
        message = (
            "Backend restart completed and systemd reported active, "
            "but HTTP health verification failed. "
            f"Last health error: {last_health_error}"
        )
    else:
        message = (
            "Backend restart completed, but systemd verification "
            f"did not report active. Last state: {last_state}"
        )

    raise BackendRestartError(
        message,
        attempted=True,
        performed=True,
    )
