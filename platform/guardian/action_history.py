from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_HISTORY_LIMIT = 25
MAX_HISTORY_LIMIT = 100
MAX_SANITIZE_DEPTH = 8

SENSITIVE_KEYS = {
    "authorization_id",
    "canonical_command",
    "command",
    "confirmation",
    "effective_uid",
    "reservation_id",
    "reserved_by_uid",
    "token",
}


class ActionHistoryError(Exception):
    pass


def _sanitize_value(value: Any, depth: int = 0) -> Any:
    if depth > MAX_SANITIZE_DEPTH:
        return "[truncated]"

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}

        for raw_key, raw_value in value.items():
            key = str(raw_key)

            if key.lower() in SENSITIVE_KEYS:
                continue

            sanitized[key] = _sanitize_value(
                raw_value,
                depth + 1,
            )

        return sanitized

    if isinstance(value, list):
        return [
            _sanitize_value(item, depth + 1)
            for item in value[:100]
        ]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)[:500]


def _load_json_object(
    raw_value: Any,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(raw_value, str):
        raise ActionHistoryError(
            f"Stored {field_name} must be JSON text."
        )

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise ActionHistoryError(
            f"Stored {field_name} is not valid JSON."
        ) from error

    if not isinstance(value, dict):
        raise ActionHistoryError(
            f"Stored {field_name} must be a JSON object."
        )

    return value


def _safe_execution_summary(
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    execution = plan.get("execution")

    if not isinstance(execution, dict):
        return None

    allowed_fields = (
        "state",
        "available",
        "attempted",
        "performed",
        "verified",
        "dry_run",
        "outcome_known",
        "automatic_replay",
        "reason",
        "details",
    )

    result = {
        field: _sanitize_value(execution[field])
        for field in allowed_fields
        if field in execution
    }

    return result or None


def _build_plan_summary(
    row: sqlite3.Row,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    plan = _load_json_object(
        row["plan_json"],
        "action plan",
    )

    plan_id = row["plan_id"]
    status = row["status"]
    action = row["action"]
    target = row["target"]

    if plan.get("plan_id") != plan_id:
        raise ActionHistoryError(
            "Stored action plan ID does not match its database row."
        )

    if plan.get("status") != status:
        raise ActionHistoryError(
            "Stored action plan status does not match its database row."
        )

    if plan.get("action") != action:
        raise ActionHistoryError(
            "Stored action plan action does not match its database row."
        )

    if plan.get("target") != target:
        raise ActionHistoryError(
            "Stored action plan target does not match its database row."
        )

    approval = plan.get("approval")
    approved = (
        isinstance(approval, dict)
        and approval.get("approved") is True
    )

    return {
        "plan_id": plan_id,
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "action": action,
        "target": target,
        "status": status,
        "risk": plan.get("risk"),
        "approved": approved,
        "approved_at": plan.get("approved_at"),
        "execution_reserved_at": plan.get(
            "execution_reserved_at"
        ),
        "execution_started_at": plan.get(
            "execution_started_at"
        ),
        "execution_completed_at": plan.get(
            "execution_completed_at"
        ),
        "execution": _safe_execution_summary(plan),
        "events": events,
    }


def read_action_history(
    database_path: Path,
    *,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> dict[str, Any]:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ActionHistoryError("History limit must be an integer.")

    if limit < 1 or limit > MAX_HISTORY_LIMIT:
        raise ActionHistoryError(
            f"History limit must be between 1 and {MAX_HISTORY_LIMIT}."
        )

    generated_at = datetime.now(timezone.utc).isoformat()

    if not database_path.exists():
        return {
            "read_only": True,
            "database_present": False,
            "generated_at": generated_at,
            "count": 0,
            "plans": [],
        }

    if not database_path.is_file():
        raise ActionHistoryError(
            "Guardian action database path is not a regular file."
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
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")

        plan_rows = connection.execute(
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
            ORDER BY created_at DESC, plan_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        plans: list[dict[str, Any]] = []

        for row in plan_rows:
            event_rows = connection.execute(
                """
                SELECT
                    event_id,
                    event_type,
                    event_at,
                    details_json
                FROM action_events
                WHERE plan_id = ?
                ORDER BY event_id
                """,
                (row["plan_id"],),
            ).fetchall()

            events: list[dict[str, Any]] = []

            for event_row in event_rows:
                details = _load_json_object(
                    event_row["details_json"],
                    "action event details",
                )

                events.append(
                    {
                        "event_id": event_row["event_id"],
                        "event_type": event_row["event_type"],
                        "event_at": event_row["event_at"],
                        "details": _sanitize_value(details),
                    }
                )

            plans.append(
                _build_plan_summary(
                    row,
                    events,
                )
            )
    except ActionHistoryError:
        raise
    except sqlite3.Error as error:
        raise ActionHistoryError(
            f"Could not read Guardian action history: {error}"
        ) from error
    finally:
        if "connection" in locals():
            connection.close()

    return {
        "read_only": True,
        "database_present": True,
        "generated_at": generated_at,
        "count": len(plans),
        "plans": plans,
    }
