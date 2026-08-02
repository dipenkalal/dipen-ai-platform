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
