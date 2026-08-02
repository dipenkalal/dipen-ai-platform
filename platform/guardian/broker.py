from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BROKER_ACTIONS = {
    "restart_service": {
        "backend": {
            "unit": "dap-backend.service",
            "command": [
                "systemctl",
                "restart",
                "dap-backend.service",
            ],
        },
        "guardian": {
            "unit": "dap-guardian.service",
            "command": [
                "systemctl",
                "restart",
                "dap-guardian.service",
            ],
        },
        "docker": {
            "unit": "docker.service",
            "command": [
                "systemctl",
                "restart",
                "docker.service",
            ],
        },
    },
}


class PlanValidationError(Exception):
    pass


def parse_timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise PlanValidationError(
            f"{field_name} must be an ISO-8601 timestamp.",
        )

    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise PlanValidationError(
            f"{field_name} is not a valid ISO-8601 timestamp.",
        ) from error

    if timestamp.tzinfo is None:
        raise PlanValidationError(
            f"{field_name} must include a timezone.",
        )

    return timestamp.astimezone(timezone.utc)


def load_plan(
    database_path: Path,
    plan_id: str,
) -> tuple[sqlite3.Row, dict[str, Any]]:
    if not database_path.is_file():
        raise PlanValidationError(
            f"Action database does not exist: {database_path}",
        )

    database_uri = (
        f"file:{database_path.resolve().as_posix()}?mode=ro"
    )

    try:
        connection = sqlite3.connect(
            database_uri,
            uri=True,
            timeout=5.0,
        )
    except sqlite3.Error as error:
        raise PlanValidationError(
            f"Could not open action database: {error}",
        ) from error

    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            """
            SELECT
                plan_id,
                created_at,
                expires_at,
                action,
                target,
                status,
                plan_json
            FROM action_plans
            WHERE plan_id = ?
            """,
            (plan_id,),
        ).fetchone()
    except sqlite3.Error as error:
        raise PlanValidationError(
            f"Could not read action plan: {error}",
        ) from error
    finally:
        connection.close()

    if row is None:
        raise PlanValidationError(
            "Action plan was not found.",
        )

    try:
        plan = json.loads(row["plan_json"])
    except (json.JSONDecodeError, TypeError) as error:
        raise PlanValidationError(
            "Stored action plan is not valid JSON.",
        ) from error

    if not isinstance(plan, dict):
        raise PlanValidationError(
            "Stored action plan must be a JSON object.",
        )

    return row, plan


def validate_loaded_plan(
    row: sqlite3.Row,
    plan: dict[str, Any],
    plan_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    current_time = current_time.astimezone(timezone.utc)

    if row["plan_id"] != plan_id:
        raise PlanValidationError(
            "Database plan ID does not match the request.",
        )

    if row["status"] != "approved":
        raise PlanValidationError(
            f"Plan status is {row['status']}, not approved.",
        )

    if plan.get("status") != "approved":
        raise PlanValidationError(
            "Stored JSON plan status is not approved.",
        )

    if plan.get("plan_id") != plan_id:
        raise PlanValidationError(
            "Stored JSON plan ID does not match.",
        )

    action = row["action"]
    target = row["target"]

    if plan.get("action") != action:
        raise PlanValidationError(
            "Plan action does not match its database record.",
        )

    if plan.get("target") != target:
        raise PlanValidationError(
            "Plan target does not match its database record.",
        )

    action_targets = BROKER_ACTIONS.get(action)

    if action_targets is None:
        raise PlanValidationError(
            f"Action is not broker-allowlisted: {action}",
        )

    definition = action_targets.get(target)

    if definition is None:
        raise PlanValidationError(
            f"Target is not broker-allowlisted: {target}",
        )

    expires_at = parse_timestamp(
        row["expires_at"],
        "expires_at",
    )

    if current_time >= expires_at:
        raise PlanValidationError(
            "Approved action plan has expired.",
        )

    if plan.get("expires_at") != row["expires_at"]:
        raise PlanValidationError(
            "Plan expiration does not match its database record.",
        )

    approval = plan.get("approval")

    if not isinstance(approval, dict):
        raise PlanValidationError(
            "Plan approval record is missing.",
        )

    if approval.get("approved") is not True:
        raise PlanValidationError(
            "Plan does not contain recorded approval.",
        )

    if approval.get("root_required") is not True:
        raise PlanValidationError(
            "Plan root-approval requirement is missing.",
        )

    expected_command = definition["command"]

    if plan.get("command") != expected_command:
        raise PlanValidationError(
            "Stored command does not match the broker allowlist.",
        )

    return {
        "validated": True,
        "plan_id": plan_id,
        "action": action,
        "target": target,
        "unit": definition["unit"],
        "canonical_command": expected_command,
        "approved_at": plan.get("approved_at"),
        "expires_at": row["expires_at"],
        "validated_at": current_time.isoformat(),
        "execution": {
            "performed": False,
            "reason": (
                "Broker validation only; execution is not implemented."
            ),
        },
    }


def validate_plan(
    database_path: Path,
    plan_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not plan_id:
        raise PlanValidationError(
            "A non-empty plan ID is required.",
        )

    row, plan = load_plan(database_path, plan_id)

    return validate_loaded_plan(
        row=row,
        plan=plan,
        plan_id=plan_id,
        now=now,
    )

def authorize_operator_execution(
    plan_id: str,
    confirmation: str | None,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise PlanValidationError(
            "Execution authorization requires an interactive root operator.",
        )

    expected_confirmation = f"EXECUTE {plan_id}"

    if not isinstance(confirmation, str):
        raise PlanValidationError(
            "Execution confirmation is required.",
        )

    if not secrets.compare_digest(
        confirmation,
        expected_confirmation,
    ):
        raise PlanValidationError(
            "Execution confirmation did not match the approved plan.",
        )

    return {
        "authorized": True,
        "method": "local-root-cli",
        "effective_uid": os.geteuid(),
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "execution": {
            "performed": False,
            "reason": (
                "Root operator authorization passed, but command "
                "execution is not implemented."
            ),
        },
    }


def reserve_execution(
    database_path: Path,
    plan_id: str,
    confirmation: str | None,
) -> dict[str, Any]:
    if not database_path.is_file():
        raise PlanValidationError(
            f"Action database does not exist: {database_path}",
        )

    reserved_at = datetime.now(timezone.utc)
    reservation_id = secrets.token_hex(16)

    try:
        with sqlite3.connect(
            database_path,
            timeout=5.0,
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT
                    plan_id,
                    created_at,
                    expires_at,
                    action,
                    target,
                    status,
                    plan_json
                FROM action_plans
                WHERE plan_id = ?
                """,
                (plan_id,),
            ).fetchone()

            if row is None:
                raise PlanValidationError(
                    "Action plan was not found.",
                )

            try:
                plan = json.loads(row["plan_json"])
            except (json.JSONDecodeError, TypeError) as error:
                raise PlanValidationError(
                    "Stored action plan is not valid JSON.",
                ) from error

            if not isinstance(plan, dict):
                raise PlanValidationError(
                    "Stored action plan must be a JSON object.",
                )

            validation = validate_loaded_plan(
                row=row,
                plan=plan,
                plan_id=plan_id,
                now=reserved_at,
            )

            operator_authorization = (
                authorize_operator_execution(
                    plan_id=plan_id,
                    confirmation=confirmation,
                )
            )

            plan["status"] = "execution_reserved"
            plan["execution_reserved_at"] = (
                reserved_at.isoformat()
            )
            plan["execution_reservation"] = {
                "reservation_id": reservation_id,
                "reserved_at": reserved_at.isoformat(),
                "reserved_by_uid": os.geteuid(),
                "single_use": True,
            }
            plan["execution"] = {
                "available": False,
                "performed": False,
                "reason": (
                    "Execution has been reserved exactly once, "
                    "but command execution is not implemented."
                ),
            }

            serialized_plan = json.dumps(
                plan,
                separators=(",", ":"),
                sort_keys=True,
            )

            update = connection.execute(
                """
                UPDATE action_plans
                SET status = ?, plan_json = ?
                WHERE plan_id = ?
                  AND status = ?
                """,
                (
                    "execution_reserved",
                    serialized_plan,
                    plan_id,
                    "approved",
                ),
            )

            if update.rowcount != 1:
                raise PlanValidationError(
                    "Execution reservation lost an atomic status race.",
                )

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
                    "execution_reserved",
                    reserved_at.isoformat(),
                    json.dumps(
                        {
                            "reservation_id": reservation_id,
                            "reserved_by_uid": os.geteuid(),
                            "single_use": True,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
    except sqlite3.Error as error:
        raise PlanValidationError(
            f"Could not reserve execution: {error}",
        ) from error

    validation["operator_authorization"] = (
        operator_authorization
    )
    validation["reservation"] = {
        "reservation_id": reservation_id,
        "reserved_at": reserved_at.isoformat(),
        "single_use": True,
    }
    validation["execution"] = {
        "performed": False,
        "reason": (
            "Single-use execution reservation recorded; "
            "command execution is not implemented."
        ),
    }

    return validation


def transition_execution_state(
    database_path: Path,
    plan_id: str,
    reservation_id: str,
    expected_status: str,
    new_status: str,
    event_type: str,
    details: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise PlanValidationError(
            "Execution-state transitions require root."
        )

    if not database_path.is_file():
        raise PlanValidationError(
            f"Action database does not exist: {database_path}"
        )

    transitioned_at = datetime.now(timezone.utc)

    try:
        with sqlite3.connect(
            database_path,
            timeout=5.0,
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT
                    plan_id,
                    status,
                    plan_json
                FROM action_plans
                WHERE plan_id = ?
                """,
                (plan_id,),
            ).fetchone()

            if row is None:
                raise PlanValidationError(
                    "Action plan was not found."
                )

            try:
                plan = json.loads(row["plan_json"])
            except (json.JSONDecodeError, TypeError) as error:
                raise PlanValidationError(
                    "Stored action plan is not valid JSON."
                ) from error

            if not isinstance(plan, dict):
                raise PlanValidationError(
                    "Stored action plan must be a JSON object."
                )

            if row["plan_id"] != plan_id:
                raise PlanValidationError(
                    "Database plan ID does not match."
                )

            if plan.get("plan_id") != plan_id:
                raise PlanValidationError(
                    "Stored JSON plan ID does not match."
                )

            if row["status"] != expected_status:
                raise PlanValidationError(
                    f"Plan status is {row['status']}, "
                    f"not {expected_status}."
                )

            if plan.get("status") != expected_status:
                raise PlanValidationError(
                    "Stored JSON status does not match "
                    "the database status."
                )

            reservation = plan.get(
                "execution_reservation"
            )

            if not isinstance(reservation, dict):
                raise PlanValidationError(
                    "Execution reservation is missing."
                )

            stored_reservation_id = reservation.get(
                "reservation_id"
            )

            if not isinstance(stored_reservation_id, str):
                raise PlanValidationError(
                    "Stored reservation ID is invalid."
                )

            if not secrets.compare_digest(
                reservation_id,
                stored_reservation_id,
            ):
                raise PlanValidationError(
                    "Execution reservation ID did not match."
                )

            plan["status"] = new_status

            if new_status == "executing":
                plan["execution_started_at"] = (
                    transitioned_at.isoformat()
                )
            else:
                plan["execution_completed_at"] = (
                    transitioned_at.isoformat()
                )

            plan["execution"] = {
                "state": new_status,
                "performed": not dry_run,
                "dry_run": dry_run,
                "details": details,
            }

            serialized_plan = json.dumps(
                plan,
                separators=(",", ":"),
                sort_keys=True,
            )

            update = connection.execute(
                """
                UPDATE action_plans
                SET status = ?, plan_json = ?
                WHERE plan_id = ?
                  AND status = ?
                """,
                (
                    new_status,
                    serialized_plan,
                    plan_id,
                    expected_status,
                ),
            )

            if update.rowcount != 1:
                raise PlanValidationError(
                    "Execution-state transition lost "
                    "an atomic status race."
                )

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
                    transitioned_at.isoformat(),
                    json.dumps(
                        {
                            "reservation_id": reservation_id,
                            "previous_status": expected_status,
                            "new_status": new_status,
                            "dry_run": dry_run,
                            "details": details,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
    except sqlite3.Error as error:
        raise PlanValidationError(
            f"Could not transition execution state: {error}"
        ) from error

    return {
        "plan_id": plan_id,
        "reservation_id": reservation_id,
        "previous_status": expected_status,
        "status": new_status,
        "transitioned_at": transitioned_at.isoformat(),
        "dry_run": dry_run,
        "execution": {
            "performed": not dry_run,
        },
    }


def begin_execution_state(
    database_path: Path,
    plan_id: str,
    reservation_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    return transition_execution_state(
        database_path=database_path,
        plan_id=plan_id,
        reservation_id=reservation_id,
        expected_status="execution_reserved",
        new_status="executing",
        event_type="execution_started",
        details={
            "message": (
                "Execution lifecycle entered the executing state."
            ),
        },
        dry_run=dry_run,
    )


def complete_execution_state(
    database_path: Path,
    plan_id: str,
    reservation_id: str,
    outcome: str,
    result_summary: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    if outcome not in {"succeeded", "failed"}:
        raise PlanValidationError(
            "Execution outcome must be succeeded or failed."
        )

    if not isinstance(result_summary, str):
        raise PlanValidationError(
            "Execution result summary must be text."
        )

    cleaned_summary = result_summary.strip()

    if not cleaned_summary:
        raise PlanValidationError(
            "Execution result summary cannot be empty."
        )

    if len(cleaned_summary) > 1000:
        raise PlanValidationError(
            "Execution result summary is too long."
        )

    return transition_execution_state(
        database_path=database_path,
        plan_id=plan_id,
        reservation_id=reservation_id,
        expected_status="executing",
        new_status=outcome,
        event_type=f"execution_{outcome}",
        details={
            "result_summary": cleaned_summary,
        },
        dry_run=dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate an approved DAP Guardian action plan "
            "without executing it."
        ),
    )

    parser.add_argument(
        "--database",
        required=True,
        type=Path,
        help="Path to the Guardian actions SQLite database.",
    )
    parser.add_argument(
        "--plan-id",
        required=True,
        help="Approved Guardian action-plan ID.",
    )
    parser.add_argument(
        "--authorize-execution",
        action="store_true",
        help=(
            "Validate a second, root-only operator authorization. "
            "No command is executed."
        ),
    )
    parser.add_argument(
        "--confirmation",
        help="Exact phrase: EXECUTE <plan_id>",
    )
    parser.add_argument(
        "--reserve-execution",
        action="store_true",
        help=(
            "Atomically reserve an approved plan for one execution. "
            "No command is executed."
        ),
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        if (
            arguments.authorize_execution
            and arguments.reserve_execution
        ):
            raise PlanValidationError(
                "--authorize-execution and --reserve-execution "
                "cannot be used together.",
            )

        if (
            arguments.confirmation
            and not arguments.authorize_execution
            and not arguments.reserve_execution
        ):
            raise PlanValidationError(
                "--confirmation requires --authorize-execution "
                "or --reserve-execution.",
            )

        if arguments.reserve_execution:
            result = reserve_execution(
                database_path=arguments.database,
                plan_id=arguments.plan_id,
                confirmation=arguments.confirmation,
            )
        else:
            result = validate_plan(
                database_path=arguments.database,
                plan_id=arguments.plan_id,
            )

            if arguments.authorize_execution:
                result["operator_authorization"] = (
                    authorize_operator_execution(
                        plan_id=arguments.plan_id,
                        confirmation=arguments.confirmation,
                    )
                )
    except PlanValidationError as error:
        print(
            json.dumps(
                {
                    "validated": False,
                    "error": str(error),
                    "execution": {
                        "performed": False,
                    },
                },
                indent=2,
                sort_keys=True,
            ),
        )
        return 2

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
