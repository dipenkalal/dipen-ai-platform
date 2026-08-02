from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlite_support import managed_connection


IDENTIFIER_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class ExecutionRecoveryError(Exception):
    pass


def require_root() -> None:
    if os.geteuid() != 0:
        raise ExecutionRecoveryError(
            "Execution recovery requires effective UID 0."
        )


def require_identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ExecutionRecoveryError(
            f"Stored {field_name} must be exactly 32 lowercase "
            "hexadecimal characters."
        )

    return value


def recover_interrupted_executions(
    database_path: Path,
) -> dict[str, Any]:
    """Move leftover executing plans to manual review without replaying them."""
    require_root()

    if not database_path.exists():
        return {
            "recovered_count": 0,
            "plan_ids": [],
            "database_present": False,
            "automatic_replay": False,
        }

    if not database_path.is_file():
        raise ExecutionRecoveryError(
            "Guardian action database path is not a regular file."
        )

    recovered_at = datetime.now(timezone.utc)
    recovered_plan_ids: list[str] = []

    try:
        with managed_connection(
            database_path,
            timeout=5.0,
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("BEGIN IMMEDIATE")

            rows = connection.execute(
                """
                SELECT
                    plan_id,
                    status,
                    plan_json
                FROM action_plans
                WHERE status = 'executing'
                ORDER BY created_at, plan_id
                """
            ).fetchall()

            for row in rows:
                try:
                    plan = json.loads(row["plan_json"])
                except (json.JSONDecodeError, TypeError) as error:
                    raise ExecutionRecoveryError(
                        "Stored executing plan is not valid JSON."
                    ) from error

                if not isinstance(plan, dict):
                    raise ExecutionRecoveryError(
                        "Stored executing plan must be a JSON object."
                    )

                plan_id = require_identifier(
                    row["plan_id"],
                    "plan_id",
                )

                if row["status"] != "executing":
                    raise ExecutionRecoveryError(
                        "Recovery selected a plan outside executing state."
                    )

                if plan.get("plan_id") != plan_id:
                    raise ExecutionRecoveryError(
                        "Stored executing plan ID does not match."
                    )

                if plan.get("status") != "executing":
                    raise ExecutionRecoveryError(
                        "Stored executing plan status does not match."
                    )

                reservation = plan.get("execution_reservation")

                if not isinstance(reservation, dict):
                    raise ExecutionRecoveryError(
                        "Executing plan reservation is missing."
                    )

                reservation_id = require_identifier(
                    reservation.get("reservation_id"),
                    "reservation_id",
                )

                plan["status"] = "manual_review"
                plan["execution_completed_at"] = (
                    recovered_at.isoformat()
                )
                plan["execution"] = {
                    "state": "manual_review",
                    "attempted": None,
                    "performed": None,
                    "verified": None,
                    "dry_run": False,
                    "outcome_known": False,
                    "automatic_replay": False,
                    "details": {
                        "reason": (
                            "A previous broker process ended while this "
                            "plan was executing. Manual review is required."
                        ),
                    },
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
                      AND status = 'executing'
                    """,
                    (
                        "manual_review",
                        serialized_plan,
                        plan_id,
                    ),
                )

                if update.rowcount != 1:
                    raise ExecutionRecoveryError(
                        "Interrupted execution recovery lost an atomic "
                        "status race."
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
                        "execution_interrupted",
                        recovered_at.isoformat(),
                        json.dumps(
                            {
                                "reservation_id": reservation_id,
                                "previous_status": "executing",
                                "new_status": "manual_review",
                                "outcome_known": False,
                                "automatic_replay": False,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    ),
                )

                recovered_plan_ids.append(plan_id)
    except ExecutionRecoveryError:
        raise
    except sqlite3.Error as error:
        raise ExecutionRecoveryError(
            f"Could not recover interrupted executions: {error}"
        ) from error

    return {
        "recovered_count": len(recovered_plan_ids),
        "plan_ids": recovered_plan_ids,
        "database_present": True,
        "recovered_at": recovered_at.isoformat(),
        "automatic_replay": False,
    }
