from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any


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


def safe_output(value: str | None, limit: int = 500) -> str:
    if not value:
        return ""

    return value.strip()[:limit]


def restart_backend_service(
    *,
    restart_timeout: float = 30.0,
    verification_timeout: float = 5.0,
    verification_attempts: int = 10,
    verification_interval: float = 1.0,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise BackendRestartError(
            "Backend restart execution requires root.",
            attempted=False,
            performed=False,
        )

    if restart_timeout <= 0 or verification_timeout <= 0:
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
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                }

        if attempt < verification_attempts:
            time.sleep(verification_interval)

    raise BackendRestartError(
        (
            "Backend restart completed, but systemd verification "
            f"did not report active. Last state: {last_state}"
        ),
        attempted=True,
        performed=True,
    )
