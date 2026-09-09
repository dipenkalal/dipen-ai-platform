from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4

from user_mode.config import (
    SESSION_ABSOLUTE_DAYS,
    SESSION_IDLE_HOURS,
)
from user_mode.repository import (
    UserModeRepository,
)
from user_mode.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    normalize_email,
    verify_password,
)


class AuthenticationError(
    ValueError
):
    pass


class UserValidationError(
    ValueError
):
    pass


@dataclass(frozen=True)
class LoginResult:
    user: dict[str, object]
    session_token: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _timestamp(
    value: datetime,
) -> str:
    return value.astimezone(
        UTC
    ).isoformat()


def _parse_timestamp(
    value: str,
) -> datetime:
    parsed = datetime.fromisoformat(
        value
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=UTC
        )

    return parsed.astimezone(UTC)


class UserModeService:
    def __init__(
        self,
        path: Path,
        *,
        now_provider: Callable[
            [],
            datetime,
        ] = _utc_now,
    ) -> None:
        self._repository = (
            UserModeRepository(path)
        )

        self._now_provider = (
            now_provider
        )

    @property
    def repository(
        self,
    ) -> UserModeRepository:
        return self._repository

    def _now(
        self,
    ) -> datetime:
        value = self._now_provider()

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=UTC
            )

        return value.astimezone(UTC)

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        role: Literal[
            "user",
            "admin",
        ] = "user",
    ) -> dict[str, object]:
        try:
            normalized_email = (
                normalize_email(email)
            )

        except ValueError as exc:
            raise UserValidationError(
                "Invalid user data"
            ) from exc

        clean_name = (
            display_name.strip()
        )

        if (
            not clean_name
            or len(clean_name) > 120
        ):
            raise UserValidationError(
                "Invalid user data"
            )

        if (
            len(password) < 8
            or len(password) > 1024
        ):
            raise UserValidationError(
                "Invalid user data"
            )

        now = _timestamp(
            self._now()
        )

        return self._repository.create_user(
            user_id=str(uuid4()),
            email_normalized=(
                normalized_email
            ),
            display_name=clean_name,
            password_hash=(
                hash_password(password)
            ),
            role=role,
            created_at=now,
        )

    def login(
        self,
        *,
        email: str,
        password: str,
    ) -> LoginResult:
        try:
            normalized_email = (
                normalize_email(email)
            )

        except ValueError as exc:
            raise AuthenticationError(
                "Invalid email or password"
            ) from exc

        user = (
            self._repository
            .get_user_by_email(
                normalized_email
            )
        )

        if (
            user is None
            or not bool(
                user["is_active"]
            )
            or not verify_password(
                str(
                    user[
                        "password_hash"
                    ]
                ),
                password,
            )
        ):
            raise AuthenticationError(
                "Invalid email or password"
            )

        now = self._now()

        absolute_expires = (
            now
            + timedelta(
                days=(
                    SESSION_ABSOLUTE_DAYS
                )
            )
        )

        idle_expires = min(
            now
            + timedelta(
                hours=(
                    SESSION_IDLE_HOURS
                )
            ),
            absolute_expires,
        )

        raw_token = (
            new_session_token()
        )

        self._repository.create_session(
            session_id=str(uuid4()),
            user_id=str(
                user["user_id"]
            ),
            token_hash=(
                hash_session_token(
                    raw_token
                )
            ),
            created_at=(
                _timestamp(now)
            ),
            idle_expires_at=(
                _timestamp(
                    idle_expires
                )
            ),
            absolute_expires_at=(
                _timestamp(
                    absolute_expires
                )
            ),
        )

        return LoginResult(
            user=user,
            session_token=raw_token,
        )

    def authenticate_session(
        self,
        token: str,
    ) -> dict[str, object]:
        if not token:
            raise AuthenticationError(
                "Authentication required"
            )

        token_hash = (
            hash_session_token(
                token
            )
        )

        session = (
            self._repository
            .get_session_by_token_hash(
                token_hash
            )
        )

        if session is None:
            raise AuthenticationError(
                "Authentication required"
            )

        if (
            session["revoked_at"]
            is not None
            or not bool(
                session["is_active"]
            )
        ):
            raise AuthenticationError(
                "Authentication required"
            )

        now = self._now()

        idle_expires = (
            _parse_timestamp(
                str(
                    session[
                        "idle_expires_at"
                    ]
                )
            )
        )

        absolute_expires = (
            _parse_timestamp(
                str(
                    session[
                        "absolute_expires_at"
                    ]
                )
            )
        )

        if (
            now >= idle_expires
            or now >= absolute_expires
        ):
            raise AuthenticationError(
                "Authentication required"
            )

        next_idle = min(
            now
            + timedelta(
                hours=(
                    SESSION_IDLE_HOURS
                )
            ),
            absolute_expires,
        )

        self._repository.touch_session(
            session_id=str(
                session["session_id"]
            ),
            last_seen_at=(
                _timestamp(now)
            ),
            idle_expires_at=(
                _timestamp(
                    next_idle
                )
            ),
        )

        return session

    def logout(
        self,
        token: str | None,
    ) -> None:
        if not token:
            return

        self._repository.revoke_session(
            token_hash=(
                hash_session_token(
                    token
                )
            ),
            revoked_at=(
                _timestamp(
                    self._now()
                )
            ),
        )
