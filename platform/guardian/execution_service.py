from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from broker import (
    begin_execution_state,
    complete_execution_state,
)
from executor import (
    BackendRestartError,
    restart_backend_service,
)
from root_authorization import (
    consume_backend_restart_authorization,
)


class BackendExecutionOrchestrationError(Exception):
    pass


def execute_authorized_backend_restart(
    *,
    guardian_database_path: Path,
    authorization_database_path: Path,
    plan_id: str,
    reservation_id: str,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise BackendExecutionOrchestrationError(
            "Authorized backend execution requires root."
        )

    authorization = (
        consume_backend_restart_authorization(
            database_path=authorization_database_path,
            plan_id=plan_id,
            reservation_id=reservation_id,
        )
    )

    started = begin_execution_state(
        database_path=guardian_database_path,
        plan_id=plan_id,
        reservation_id=reservation_id,
        dry_run=False,
    )

    try:
        execution = restart_backend_service()
    except BackendRestartError as error:
        completed = complete_execution_state(
            database_path=guardian_database_path,
            plan_id=plan_id,
            reservation_id=reservation_id,
            outcome="failed",
            result_summary=str(error),
            attempted=error.attempted,
            performed=error.performed,
            dry_run=False,
        )

        return {
            "ok": False,
            "plan_id": plan_id,
            "reservation_id": reservation_id,
            "authorization": authorization,
            "started": started,
            "completed": completed,
            "execution": {
                "attempted": error.attempted,
                "performed": error.performed,
                "verified": False,
                "error": str(error),
            },
        }

    completed = complete_execution_state(
        database_path=guardian_database_path,
        plan_id=plan_id,
        reservation_id=reservation_id,
        outcome="succeeded",
        result_summary=(
            "Backend restart completed and systemd "
            "reported the service active."
        ),
        attempted=execution["attempted"],
        performed=execution["performed"],
        dry_run=False,
    )

    return {
        "ok": True,
        "plan_id": plan_id,
        "reservation_id": reservation_id,
        "authorization": authorization,
        "started": started,
        "completed": completed,
        "execution": execution,
    }
