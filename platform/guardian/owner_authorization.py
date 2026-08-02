from __future__ import annotations

import secrets


def validate_owner_authorization(
    authorization_header: str | None,
    configured_token: str,
) -> tuple[bool, int, str | None]:
    """Validate the dedicated owner token for Guardian reasoning requests."""
    if not configured_token:
        return (
            False,
            503,
            (
                "Guardian owner API is disabled because no owner token "
                "is configured."
            ),
        )

    if not authorization_header:
        return False, 401, "Authorization header is required."

    scheme, separator, supplied_token = authorization_header.partition(" ")

    if (
        separator != " "
        or scheme.lower() != "bearer"
        or not supplied_token
    ):
        return False, 401, "A valid Bearer token is required."

    if not secrets.compare_digest(
        supplied_token,
        configured_token,
    ):
        return False, 403, "Owner authorization failed."

    return True, 200, None
