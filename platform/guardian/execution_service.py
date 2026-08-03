from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from broker import (
    PlanValidationError,
    begin_execution_state,
    complete_execution_state,
    transition_execution_state,
)
from executor import (
    BackendRestartError,
    restart_backend_service,
)
from root_authorization import (
    RootAuthorizationError,
    consume_backend_restart_authorization,
    validate_reserved_backend_plan,
)


class BackendExecutionOrchestrationError(Exception):
    pass


def mark_authorization_failure_for_manual_review(
    *,
    guardian_database_path: Path,
    plan_id: str,
    reservation_id: str,
    reason: str,
    dry_run: bool,
) -> dict[str, Any]:
    try:
        return transition_execution_state(
            database_path=guardian_database_path,
            plan_id=plan_id,
            reservation_id=reservation_id,
            expected_status="executing",
            new_status="manual_review",
            event_type="execution_authorization_failed",
            details={
                "reason": reason,
                "automatic_replay": False,
                "manual_review_required": True,
            },
            attempted=False,
            performed=False,
            dry_run=dry_run,
        )
    except PlanValidationError as error:
        raise BackendExecutionOrchestrationError(
            "Root authorization failed after execution state was entered, "
            "and Guardian could not move the plan to manual review."
        ) from error


def execute_authorized_backend_restart(
    *,
    guardian_database_path: Path,
    authorization_database_path: Path,
    plan_id: str,
    reservation_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not isinstance(dry_run, bool):
        raise BackendExecutionOrchestrationError(
            "Backend execution dry_run state must be boolean."
        )

    if os.geteuid() != 0:
        raise BackendExecutionOrchestrationError(
            "Authorized backend execution requires root."
        )

    try:
        plan_validation = validate_reserved_backend_plan(
            guardian_database_path=guardian_database_path,
            plan_id=plan_id,
            reservation_id=reservation_id,
        )
    except RootAuthorizationError as error:
        if "not execution_reserved" in str(error):
            raise RootAuthorizationError(
                "Guardian plan is not execution_reserved; replay is rejected."
            ) from error
        raise

    started = begin_execution_state(
        database_path=guardian_database_path,
        plan_id=plan_id,
        reservation_id=reservation_id,
        dry_run=dry_run,
    )

    try:
        authorization = consume_backend_restart_authorization(
            database_path=authorization_database_path,
            plan_id=plan_id,
            reservation_id=reservation_id,
        )
    except RootAuthorizationError as error:
        mark_authorization_failure_for_manual_review(
            guardian_database_path=guardian_database_path,
            plan_id=plan_id,
            reservation_id=reservation_id,
            reason=str(error),
            dry_run=dry_run,
        )

        raise BackendExecutionOrchestrationError(
            "Root authorization could not be consumed. The plan was moved "
            "to manual_review and will not be replayed automatically."
        ) from error

    if dry_run:
        execution = {
            "attempted": False,
            "performed": False,
            "verified": False,
            "dry_run": True,
            "authorization_consumed": True,
            "reason": (
                "Dry-run completed; the backend restart command was "
                "not invoked."
            ),
        }

        completed = complete_execution_state(
            database_path=guardian_database_path,
            plan_id=plan_id,
            reservation_id=reservation_id,
            outcome="succeeded",
            result_summary=(
                "Authorized backend restart dry-run completed. The "
                "single-use authorization was consumed and no command "
                "was attempted or performed."
            ),
            attempted=False,
            performed=False,
            dry_run=True,
        )

        return {
            "ok": True,
            "plan_id": plan_id,
            "reservation_id": reservation_id,
            "plan_validation": plan_validation,
            "authorization": authorization,
            "started": started,
            "completed": completed,
            "execution": execution,
        }

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
            "plan_validation": plan_validation,
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
            "Backend restart completed, systemd reported the service "
            "active, and the backend HTTP health endpoint reported healthy."
        ),
        attempted=execution["attempted"],
        performed=execution["performed"],
        dry_run=False,
    )

    return {
        "ok": True,
        "plan_id": plan_id,
        "reservation_id": reservation_id,
        "plan_validation": plan_validation,
        "authorization": authorization,
        "started": started,
        "completed": completed,
        "execution": execution,
    }
