from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from user_mode.config import (
    INITIAL_ACCOUNT_CEILING,
    MAXIMUM_ADMIN_ACCOUNTS,
)
from user_mode.database import connect_rw


class DuplicateUserError(
    ValueError
):
    pass


class AccountLimitError(
    ValueError
):
    pass


class AdminLimitError(
    ValueError
):
    pass


class UserModeRepository:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self._path = Path(path)

    @staticmethod
    def _dict(
        row: sqlite3.Row | None,
    ) -> dict[str, Any] | None:
        if row is None:
            return None

        return dict(row)

    def create_user(
        self,
        *,
        user_id: str,
        email_normalized: str,
        display_name: str,
        password_hash: str,
        role: str,
        created_at: str,
    ) -> dict[str, Any]:
        connection = connect_rw(
            self._path
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            total_accounts = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM users
                    """
                ).fetchone()[0]
            )

            if (
                total_accounts
                >= INITIAL_ACCOUNT_CEILING
            ):
                raise AccountLimitError(
                    "Initial account ceiling reached"
                )

            if role == "admin":
                admin_accounts = int(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM users
                        WHERE role = 'admin'
                        """
                    ).fetchone()[0]
                )

                if (
                    admin_accounts
                    >= MAXIMUM_ADMIN_ACCOUNTS
                ):
                    raise AdminLimitError(
                        "Maximum admin account count reached"
                    )

            try:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id,
                        email_normalized,
                        display_name,
                        password_hash,
                        role,
                        is_active,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        user_id,
                        email_normalized,
                        display_name,
                        password_hash,
                        role,
                        created_at,
                        created_at,
                    ),
                )

            except sqlite3.IntegrityError as exc:
                raise DuplicateUserError(
                    "User already exists"
                ) from exc

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        created = self.get_user_by_id(
            user_id
        )

        if created is None:
            raise RuntimeError(
                "Created user could not be read"
            )

        return created

    def get_user_by_email(
        self,
        email_normalized: str,
    ) -> dict[str, Any] | None:
        connection = connect_rw(
            self._path
        )

        try:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    email_normalized,
                    display_name,
                    password_hash,
                    role,
                    is_active,
                    created_at,
                    updated_at
                FROM users
                WHERE email_normalized = ?
                """,
                (
                    email_normalized,
                ),
            ).fetchone()

            return self._dict(row)

        finally:
            connection.close()

    def get_user_by_id(
        self,
        user_id: str,
    ) -> dict[str, Any] | None:
        connection = connect_rw(
            self._path
        )

        try:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    email_normalized,
                    display_name,
                    password_hash,
                    role,
                    is_active,
                    created_at,
                    updated_at
                FROM users
                WHERE user_id = ?
                """,
                (
                    user_id,
                ),
            ).fetchone()

            return self._dict(row)

        finally:
            connection.close()

    def set_user_active(
        self,
        *,
        user_id: str,
        is_active: bool,
        updated_at: str,
    ) -> None:
        connection = connect_rw(
            self._path
        )

        try:
            connection.execute(
                """
                UPDATE users
                SET
                    is_active = ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    1 if is_active else 0,
                    updated_at,
                    user_id,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        token_hash: str,
        created_at: str,
        idle_expires_at: str,
        absolute_expires_at: str,
    ) -> None:
        connection = connect_rw(
            self._path
        )

        try:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    user_id,
                    token_hash,
                    created_at,
                    last_seen_at,
                    idle_expires_at,
                    absolute_expires_at,
                    revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    session_id,
                    user_id,
                    token_hash,
                    created_at,
                    created_at,
                    idle_expires_at,
                    absolute_expires_at,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def get_session_by_token_hash(
        self,
        token_hash: str,
    ) -> dict[str, Any] | None:
        connection = connect_rw(
            self._path
        )

        try:
            row = connection.execute(
                """
                SELECT
                    s.session_id,
                    s.user_id,
                    s.token_hash,
                    s.created_at,
                    s.last_seen_at,
                    s.idle_expires_at,
                    s.absolute_expires_at,
                    s.revoked_at,
                    u.email_normalized,
                    u.display_name,
                    u.password_hash,
                    u.role,
                    u.is_active,
                    u.updated_at
                FROM sessions AS s
                JOIN users AS u
                    ON u.user_id = s.user_id
                WHERE s.token_hash = ?
                """,
                (
                    token_hash,
                ),
            ).fetchone()

            return self._dict(row)

        finally:
            connection.close()

    def touch_session(
        self,
        *,
        session_id: str,
        last_seen_at: str,
        idle_expires_at: str,
    ) -> None:
        connection = connect_rw(
            self._path
        )

        try:
            connection.execute(
                """
                UPDATE sessions
                SET
                    last_seen_at = ?,
                    idle_expires_at = ?
                WHERE session_id = ?
                  AND revoked_at IS NULL
                """,
                (
                    last_seen_at,
                    idle_expires_at,
                    session_id,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def revoke_session(
        self,
        *,
        token_hash: str,
        revoked_at: str,
    ) -> None:
        connection = connect_rw(
            self._path
        )

        try:
            connection.execute(
                """
                UPDATE sessions
                SET revoked_at = ?
                WHERE token_hash = ?
                  AND revoked_at IS NULL
                """,
                (
                    revoked_at,
                    token_hash,
                ),
            )

            connection.commit()

        finally:
            connection.close()
