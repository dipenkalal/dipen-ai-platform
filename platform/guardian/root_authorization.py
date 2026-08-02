from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PLAN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
RESERVATION_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

BACKEND_RESTART_ACTION_KEY = "restart_service:backend"

BACKEND_RESTART_COMMAND = [
    "systemctl",
    "restart",
    "dap-backend.service",
]

MAX_AUTHORIZATION_TTL_SECONDS = 300


class RootAuthorizationError(Exception):
    pass


def require_root() -> None:
    if os.geteuid() != 0:
        raise RootAuthorizationError(
            "Root authorization operations require effective UID 0."
        )


def validate_identifier(
    value: str,
    field_name: str,
    pattern: re.Pattern[str],
) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise RootAuthorizationError(
            f"{field_name} must be exactly 32 lowercase "
            "hexadecimal characters."
        )



def validate_reserved_backend_plan(
    guardian_database_path: Path,
    plan_id: str,
    reservation_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    validate_identifier(
        plan_id,
        "plan_id",
        PLAN_ID_PATTERN,
    )
    validate_identifier(
        reservation_id,
        "reservation_id",
        RESERVATION_ID_PATTERN,
    )

    if not guardian_database_path.is_file():
        raise RootAuthorizationError(
            "Guardian action database does not exist."
        )

    database_uri = (
        f"file:{guardian_database_path.resolve().as_posix()}"
        "?mode=ro"
    )

    try:
        connection = sqlite3.connect(
            database_uri,
            uri=True,
            timeout=5.0,
        )
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT
                plan_id,
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
        raise RootAuthorizationError(
            f"Could not read Guardian action plan: {error}"
        ) from error
    finally:
        if "connection" in locals():
            connection.close()

    if row is None:
        raise RootAuthorizationError(
            "Guardian action plan was not found."
        )

    try:
        plan = json.loads(row["plan_json"])
    except (json.JSONDecodeError, TypeError) as error:
        raise RootAuthorizationError(
            "Stored Guardian plan is not valid JSON."
        ) from error

    if not isinstance(plan, dict):
        raise RootAuthorizationError(
            "Stored Guardian plan must be a JSON object."
        )

    if row["plan_id"] != plan_id:
        raise RootAuthorizationError(
            "Guardian database plan ID does not match."
        )

    if plan.get("plan_id") != plan_id:
        raise RootAuthorizationError(
            "Stored Guardian plan ID does not match."
        )

    if row["status"] != "execution_reserved":
        raise RootAuthorizationError(
            "Guardian plan is not execution_reserved."
        )

    if plan.get("status") != "execution_reserved":
        raise RootAuthorizationError(
            "Stored Guardian plan is not execution_reserved."
        )

    if row["action"] != "restart_service":
        raise RootAuthorizationError(
            "Guardian action is not an allowed service restart."
        )

    if plan.get("action") != "restart_service":
        raise RootAuthorizationError(
            "Stored Guardian action does not match."
        )

    if row["target"] != "backend":
        raise RootAuthorizationError(
            "Guardian target is not the backend."
        )

    if plan.get("target") != "backend":
        raise RootAuthorizationError(
            "Stored Guardian target does not match."
        )

    if plan.get("command") != BACKEND_RESTART_COMMAND:
        raise RootAuthorizationError(
            "Guardian command does not match the fixed "
            "backend restart command."
        )

    approval = plan.get("approval")

    if not isinstance(approval, dict):
        raise RootAuthorizationError(
            "Guardian approval record is missing."
        )

    if approval.get("approved") is not True:
        raise RootAuthorizationError(
            "Guardian plan is not approved."
        )

    if approval.get("root_required") is not True:
        raise RootAuthorizationError(
            "Guardian plan does not require root authorization."
        )

    reservation = plan.get("execution_reservation")

    if not isinstance(reservation, dict):
        raise RootAuthorizationError(
            "Guardian execution reservation is missing."
        )

    stored_reservation_id = reservation.get("reservation_id")

    if not isinstance(stored_reservation_id, str):
        raise RootAuthorizationError(
            "Stored Guardian reservation ID is invalid."
        )

    if not secrets.compare_digest(
        reservation_id,
        stored_reservation_id,
    ):
        raise RootAuthorizationError(
            "Guardian execution reservation ID did not match."
        )

    if reservation.get("single_use") is not True:
        raise RootAuthorizationError(
            "Guardian execution reservation is not single-use."
        )

    if reservation.get("reserved_by_uid") != 0:
        raise RootAuthorizationError(
            "Guardian execution reservation was not created by root."
        )

    expires_at_value = row["expires_at"]

    if plan.get("expires_at") != expires_at_value:
        raise RootAuthorizationError(
            "Guardian plan expiration does not match its record."
        )

    try:
        expires_at = datetime.fromisoformat(
            expires_at_value
        )
    except (TypeError, ValueError) as error:
        raise RootAuthorizationError(
            "Guardian plan expiration is invalid."
        ) from error

    if expires_at.tzinfo is None:
        raise RootAuthorizationError(
            "Guardian plan expiration must include a timezone."
        )

    current_time = now or datetime.now(timezone.utc)
    current_time = current_time.astimezone(timezone.utc)
    expires_at = expires_at.astimezone(timezone.utc)

    if current_time >= expires_at:
        raise RootAuthorizationError(
            "Guardian execution reservation has expired."
        )

    return {
        "validated": True,
        "plan_id": plan_id,
        "reservation_id": reservation_id,
        "action_key": BACKEND_RESTART_ACTION_KEY,
        "status": "execution_reserved",
        "expires_at": expires_at.isoformat(),
    }


def initialize_store(database_path: Path) -> None:
    require_root()

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o700,
    )
    os.chmod(database_path.parent, 0o700)

    try:
        with sqlite3.connect(
            database_path,
            timeout=5.0,
        ) as connection:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")

            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS root_authorizations (
                    authorization_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    reservation_id TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );

                CREATE UNIQUE INDEX IF NOT EXISTS
                    root_authorizations_plan_reservation
                ON root_authorizations (
                    plan_id,
                    reservation_id
                );

                CREATE TABLE IF NOT EXISTS
                    root_authorization_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        authorization_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        event_at TEXT NOT NULL,
                        details_json TEXT NOT NULL
                    );
                """
            )
    except sqlite3.Error as error:
        raise RootAuthorizationError(
            f"Could not initialize root authorization store: {error}"
        ) from error

    os.chmod(database_path, 0o600)


def issue_backend_restart_authorization(
    database_path: Path,
    guardian_database_path: Path,
    plan_id: str,
    reservation_id: str,
    *,
    ttl_seconds: int = 120,
) -> dict[str, Any]:
    require_root()

    validate_identifier(
        plan_id,
        "plan_id",
        PLAN_ID_PATTERN,
    )
    validate_identifier(
        reservation_id,
        "reservation_id",
        RESERVATION_ID_PATTERN,
    )

    if (
        not isinstance(ttl_seconds, int)
        or ttl_seconds < 1
        or ttl_seconds > MAX_AUTHORIZATION_TTL_SECONDS
    ):
        raise RootAuthorizationError(
            "Authorization TTL must be between 1 and "
            f"{MAX_AUTHORIZATION_TTL_SECONDS} seconds."
        )

    plan_validation = validate_reserved_backend_plan(
        guardian_database_path=guardian_database_path,
        plan_id=plan_id,
        reservation_id=reservation_id,
    )

    initialize_store(database_path)

    authorization_id = secrets.token_hex(16)
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)

    try:
        with sqlite3.connect(
            database_path,
            timeout=5.0,
        ) as connection:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                INSERT INTO root_authorizations (
                    authorization_id,
                    plan_id,
                    reservation_id,
                    action_key,
                    status,
                    issued_at,
                    expires_at,
                    consumed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    authorization_id,
                    plan_id,
                    reservation_id,
                    BACKEND_RESTART_ACTION_KEY,
                    "pending",
                    issued_at.isoformat(),
                    expires_at.isoformat(),
                ),
            )

            connection.execute(
                """
                INSERT INTO root_authorization_events (
                    authorization_id,
                    event_type,
                    event_at,
                    details_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    authorization_id,
                    "authorization_issued",
                    issued_at.isoformat(),
                    json.dumps(
                        {
                            "plan_id": plan_id,
                            "reservation_id": reservation_id,
                            "action_key": (
                                BACKEND_RESTART_ACTION_KEY
                            ),
                            "ttl_seconds": ttl_seconds,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
    except sqlite3.IntegrityError as error:
        raise RootAuthorizationError(
            "A root authorization already exists for this "
            "plan reservation."
        ) from error
    except sqlite3.Error as error:
        raise RootAuthorizationError(
            f"Could not issue root authorization: {error}"
        ) from error

    return {
        "authorization_id": authorization_id,
        "plan_id": plan_id,
        "reservation_id": reservation_id,
        "action_key": BACKEND_RESTART_ACTION_KEY,
        "status": "pending",
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "single_use": True,
        "plan_validation": plan_validation,
    }


def consume_backend_restart_authorization(
    database_path: Path,
    plan_id: str,
    reservation_id: str,
) -> dict[str, Any]:
    require_root()

    validate_identifier(
        plan_id,
        "plan_id",
        PLAN_ID_PATTERN,
    )
    validate_identifier(
        reservation_id,
        "reservation_id",
        RESERVATION_ID_PATTERN,
    )

    if not database_path.is_file():
        raise RootAuthorizationError(
            "Root authorization database does not exist."
        )

    consumed_at = datetime.now(timezone.utc)
    expired_authorization_id: str | None = None
    result: dict[str, Any] | None = None

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
                    authorization_id,
                    plan_id,
                    reservation_id,
                    action_key,
                    status,
                    issued_at,
                    expires_at
                FROM root_authorizations
                WHERE plan_id = ?
                  AND reservation_id = ?
                  AND action_key = ?
                """,
                (
                    plan_id,
                    reservation_id,
                    BACKEND_RESTART_ACTION_KEY,
                ),
            ).fetchone()

            if row is None:
                raise RootAuthorizationError(
                    "Matching root authorization was not found."
                )

            if row["status"] != "pending":
                raise RootAuthorizationError(
                    "Root authorization is not pending; "
                    "replay is rejected."
                )

            try:
                expires_at = datetime.fromisoformat(
                    row["expires_at"]
                ).astimezone(timezone.utc)
            except (TypeError, ValueError) as error:
                raise RootAuthorizationError(
                    "Stored authorization expiry is invalid."
                ) from error

            authorization_id = row["authorization_id"]

            if consumed_at >= expires_at:
                update = connection.execute(
                    """
                    UPDATE root_authorizations
                    SET status = ?
                    WHERE authorization_id = ?
                      AND status = ?
                    """,
                    (
                        "expired",
                        authorization_id,
                        "pending",
                    ),
                )

                if update.rowcount != 1:
                    raise RootAuthorizationError(
                        "Authorization expiry lost an atomic race."
                    )

                connection.execute(
                    """
                    INSERT INTO root_authorization_events (
                        authorization_id,
                        event_type,
                        event_at,
                        details_json
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        authorization_id,
                        "authorization_expired",
                        consumed_at.isoformat(),
                        json.dumps(
                            {
                                "plan_id": plan_id,
                                "reservation_id": reservation_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    ),
                )

                expired_authorization_id = authorization_id
            else:
                update = connection.execute(
                    """
                    UPDATE root_authorizations
                    SET status = ?, consumed_at = ?
                    WHERE authorization_id = ?
                      AND status = ?
                    """,
                    (
                        "consumed",
                        consumed_at.isoformat(),
                        authorization_id,
                        "pending",
                    ),
                )

                if update.rowcount != 1:
                    raise RootAuthorizationError(
                        "Authorization consumption lost an "
                        "atomic status race."
                    )

                connection.execute(
                    """
                    INSERT INTO root_authorization_events (
                        authorization_id,
                        event_type,
                        event_at,
                        details_json
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        authorization_id,
                        "authorization_consumed",
                        consumed_at.isoformat(),
                        json.dumps(
                            {
                                "plan_id": plan_id,
                                "reservation_id": reservation_id,
                                "action_key": (
                                    BACKEND_RESTART_ACTION_KEY
                                ),
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    ),
                )

                result = {
                    "authorization_id": authorization_id,
                    "plan_id": plan_id,
                    "reservation_id": reservation_id,
                    "action_key": BACKEND_RESTART_ACTION_KEY,
                    "status": "consumed",
                    "consumed_at": consumed_at.isoformat(),
                    "single_use": True,
                }
    except sqlite3.Error as error:
        raise RootAuthorizationError(
            f"Could not consume root authorization: {error}"
        ) from error

    if expired_authorization_id is not None:
        raise RootAuthorizationError(
            "Root authorization has expired."
        )

    if result is None:
        raise RootAuthorizationError(
            "Root authorization consumption produced no result."
        )

    return result
