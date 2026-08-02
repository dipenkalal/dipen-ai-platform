from __future__ import annotations

import argparse
import json
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

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        result = validate_plan(
            database_path=arguments.database,
            plan_id=arguments.plan_id,
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
