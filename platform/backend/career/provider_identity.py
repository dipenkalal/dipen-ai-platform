"""Deterministic ATS provider source identity canonicalization.

Phase 19.3D.

This module is intentionally pure:

* no network
* no database access
* no filesystem access
* no production admission authority

Provider identity describes stable endpoint identity only.
Operational scan settings such as max_pages, locale, retries, and
search text are deliberately excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping


_PROVIDER_IDENTITY_PREFIX = "career-provider-key-"

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_PROVIDER_FIELDS: dict[str, tuple[str, ...]] = {
    "workday": (
        "host",
        "tenant",
        "site",
    ),
    "greenhouse": (
        "host",
        "board_token",
    ),
    "lever": (
        "host",
        "site",
    ),
    "ashby": (
        "host",
        "board",
    ),
    "smartrecruiters": (
        "host",
        "company_identifier",
    ),
}


class ProviderIdentityError(ValueError):
    """Provider identity cannot be canonicalized safely."""


@dataclass(frozen=True, slots=True)
class CanonicalProviderIdentity:
    """Immutable canonical provider source identity."""

    provider_kind: str
    identity: Mapping[str, str]
    canonical_json: str
    identity_sha256: str
    provider_identity_key: str

    def __post_init__(self) -> None:
        if not _SHA256_RE.fullmatch(
            self.identity_sha256
        ):
            raise ProviderIdentityError(
                "identity_sha256 must be lowercase SHA-256 hex."
            )

        expected_key = (
            _PROVIDER_IDENTITY_PREFIX
            + self.identity_sha256[:24]
        )

        if self.provider_identity_key != expected_key:
            raise ProviderIdentityError(
                "provider_identity_key does not match identity SHA."
            )


def supported_provider_kinds() -> tuple[str, ...]:
    """Return supported provider kinds in deterministic order."""

    return tuple(
        sorted(_PROVIDER_FIELDS)
    )


def _normalize_provider_kind(
    value: str,
) -> str:

    if not isinstance(value, str):
        raise ProviderIdentityError(
            "provider_kind must be a string."
        )

    normalized = value.strip().lower()

    if normalized not in _PROVIDER_FIELDS:
        raise ProviderIdentityError(
            f"Unsupported provider_kind: {value!r}"
        )

    return normalized


def _normalize_host(
    value: str,
) -> str:

    if not isinstance(value, str):
        raise ProviderIdentityError(
            "host must be a string."
        )

    host = value.strip().lower()

    if host.endswith("."):
        host = host[:-1]

    if not host:
        raise ProviderIdentityError(
            "host must not be empty."
        )

    forbidden = (
        "://",
        "/",
        "?",
        "#",
        "@",
    )

    if any(
        token in host
        for token in forbidden
    ):
        raise ProviderIdentityError(
            "host must be a hostname only."
        )

    if ":" in host:
        raise ProviderIdentityError(
            "host must not contain a port."
        )

    labels = host.split(".")

    if (
        len(labels) < 2
        or any(not label for label in labels)
    ):
        raise ProviderIdentityError(
            "host must be a qualified hostname."
        )

    label_re = re.compile(
        r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
    )

    if any(
        not label_re.fullmatch(label)
        for label in labels
    ):
        raise ProviderIdentityError(
            "host contains an invalid DNS label."
        )

    return host


def _normalize_opaque(
    field_name: str,
    value: str,
) -> str:

    if not isinstance(value, str):
        raise ProviderIdentityError(
            f"{field_name} must be a string."
        )

    normalized = value.strip()

    if not normalized:
        raise ProviderIdentityError(
            f"{field_name} must not be empty."
        )

    if "\x00" in normalized:
        raise ProviderIdentityError(
            f"{field_name} contains NUL."
        )

    return normalized


def canonicalize_provider_identity(
    provider_kind: str,
    identity: Mapping[str, str],
) -> CanonicalProviderIdentity:
    """Canonicalize a stable provider source identity.

    The input must contain exactly the provider's stable identity
    fields. Extra operational fields are rejected so that settings
    such as pagination limits cannot accidentally alter source
    identity.
    """

    kind = _normalize_provider_kind(
        provider_kind
    )

    if not isinstance(identity, Mapping):
        raise ProviderIdentityError(
            "identity must be a mapping."
        )

    required = _PROVIDER_FIELDS[kind]

    supplied = set(identity)
    expected = set(required)

    missing = sorted(
        expected - supplied
    )

    extra = sorted(
        supplied - expected
    )

    if missing:
        raise ProviderIdentityError(
            "Missing provider identity fields: "
            + ", ".join(missing)
        )

    if extra:
        raise ProviderIdentityError(
            "Unexpected provider identity fields: "
            + ", ".join(extra)
        )

    normalized: dict[str, str] = {
        "provider_kind": kind,
    }

    for field_name in required:

        raw = identity[field_name]

        if field_name == "host":
            normalized[field_name] = (
                _normalize_host(raw)
            )
        else:
            normalized[field_name] = (
                _normalize_opaque(
                    field_name,
                    raw,
                )
            )

    canonical_json = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    identity_sha256 = hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()

    provider_identity_key = (
        _PROVIDER_IDENTITY_PREFIX
        + identity_sha256[:24]
    )

    return CanonicalProviderIdentity(
        provider_kind=kind,
        identity=MappingProxyType(
            dict(normalized)
        ),
        canonical_json=canonical_json,
        identity_sha256=identity_sha256,
        provider_identity_key=provider_identity_key,
    )
