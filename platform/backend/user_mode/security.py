from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from argon2.low_level import Type


_PASSWORD_HASHER = PasswordHasher(
    type=Type.ID,
)


def normalize_email(
    value: str,
) -> str:
    normalized = value.strip().casefold()

    if (
        not normalized
        or len(normalized) > 320
        or normalized.count("@") != 1
    ):
        raise ValueError(
            "A valid email address is required"
        )

    local_part, domain = normalized.split(
        "@",
        1,
    )

    if (
        not local_part
        or not domain
        or "." not in domain
    ):
        raise ValueError(
            "A valid email address is required"
        )

    return normalized


def hash_password(
    password: str,
) -> str:
    return _PASSWORD_HASHER.hash(
        password
    )


def verify_password(
    password_hash: str,
    password: str,
) -> bool:
    try:
        return _PASSWORD_HASHER.verify(
            password_hash,
            password,
        )

    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(
    token: str,
) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()
