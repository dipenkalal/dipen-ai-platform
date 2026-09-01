from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
import json
import re
from typing import Any
from urllib.parse import urlparse

from career.provider_identity import (
    canonicalize_provider_identity,
    supported_provider_kinds,
)


_PROVIDER_KEY_RE = re.compile(
    r"^career-provider-key-[0-9a-f]{24}$"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class DiscoveryState(StrEnum):
    DISCOVERED = "discovered"
    ATS_IDENTIFIED = "ats_identified"
    ENDPOINT_CANDIDATE = "endpoint_candidate"
    LISTING_PROVEN = "listing_proven"
    DETAIL_PROVEN = "detail_proven"
    ADMISSION_READY = "admission_ready"
    ADMITTED = "admitted"
    DEGRADED = "degraded"
    REJECTED = "rejected"
    DISABLED = "disabled"


class DiscoveryDomainError(ValueError):
    pass


class DiscoveryTransitionError(
    DiscoveryDomainError
):
    pass


_MAIN_STATES = frozenset({
    DiscoveryState.DISCOVERED,
    DiscoveryState.ATS_IDENTIFIED,
    DiscoveryState.ENDPOINT_CANDIDATE,
    DiscoveryState.LISTING_PROVEN,
    DiscoveryState.DETAIL_PROVEN,
    DiscoveryState.ADMISSION_READY,
    DiscoveryState.ADMITTED,
})


_IDENTITY_REQUIRED_STATES = frozenset({
    DiscoveryState.ENDPOINT_CANDIDATE,
    DiscoveryState.LISTING_PROVEN,
    DiscoveryState.DETAIL_PROVEN,
    DiscoveryState.ADMISSION_READY,
    DiscoveryState.ADMITTED,
})


_LISTING_EVIDENCE_REQUIRED_STATES = (
    frozenset({
        DiscoveryState.LISTING_PROVEN,
        DiscoveryState.DETAIL_PROVEN,
        DiscoveryState.ADMISSION_READY,
        DiscoveryState.ADMITTED,
    })
)


_DETAIL_EVIDENCE_REQUIRED_STATES = (
    frozenset({
        DiscoveryState.DETAIL_PROVEN,
        DiscoveryState.ADMISSION_READY,
        DiscoveryState.ADMITTED,
    })
)


_ALLOWED_TRANSITIONS = {
    DiscoveryState.DISCOVERED: frozenset({
        DiscoveryState.ATS_IDENTIFIED,
        DiscoveryState.REJECTED,
        DiscoveryState.DISABLED,
    }),

    DiscoveryState.ATS_IDENTIFIED: frozenset({
        DiscoveryState.ENDPOINT_CANDIDATE,
        DiscoveryState.DEGRADED,
        DiscoveryState.REJECTED,
        DiscoveryState.DISABLED,
    }),

    DiscoveryState.ENDPOINT_CANDIDATE: frozenset({
        DiscoveryState.LISTING_PROVEN,
        DiscoveryState.DEGRADED,
        DiscoveryState.REJECTED,
        DiscoveryState.DISABLED,
    }),

    DiscoveryState.LISTING_PROVEN: frozenset({
        DiscoveryState.DETAIL_PROVEN,
        DiscoveryState.DEGRADED,
        DiscoveryState.REJECTED,
        DiscoveryState.DISABLED,
    }),

    DiscoveryState.DETAIL_PROVEN: frozenset({
        DiscoveryState.ADMISSION_READY,
        DiscoveryState.DEGRADED,
        DiscoveryState.REJECTED,
        DiscoveryState.DISABLED,
    }),

    DiscoveryState.ADMISSION_READY: frozenset({
        DiscoveryState.ADMITTED,
        DiscoveryState.DEGRADED,
        DiscoveryState.REJECTED,
        DiscoveryState.DISABLED,
    }),

    DiscoveryState.DEGRADED: frozenset({
        DiscoveryState.ATS_IDENTIFIED,
        DiscoveryState.ENDPOINT_CANDIDATE,
        DiscoveryState.LISTING_PROVEN,
        DiscoveryState.DETAIL_PROVEN,
        DiscoveryState.ADMISSION_READY,
        DiscoveryState.REJECTED,
        DiscoveryState.DISABLED,
    }),

    DiscoveryState.ADMITTED: frozenset(),
    DiscoveryState.REJECTED: frozenset(),
    DiscoveryState.DISABLED: frozenset(),
}


def allowed_transitions(
    state: DiscoveryState,
) -> tuple[DiscoveryState, ...]:

    normalized = DiscoveryState(state)

    return tuple(
        sorted(
            _ALLOWED_TRANSITIONS[normalized],
            key=lambda item: item.value,
        )
    )


def can_transition(
    current: DiscoveryState,
    target: DiscoveryState,
) -> bool:

    current_state = DiscoveryState(current)
    target_state = DiscoveryState(target)

    return (
        target_state
        in _ALLOWED_TRANSITIONS[current_state]
    )


def _required_text(
    value: str,
    field_name: str,
) -> str:

    if not isinstance(value, str):
        raise DiscoveryDomainError(
            f"{field_name} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise DiscoveryDomainError(
            f"{field_name} may not be empty"
        )

    if "\x00" in normalized:
        raise DiscoveryDomainError(
            f"{field_name} may not contain NUL"
        )

    return normalized


def _optional_text(
    value: str | None,
    field_name: str,
) -> str | None:

    if value is None:
        return None

    return _required_text(
        value,
        field_name,
    )


def _exact_identity_text(
    value: str | None,
    field_name: str,
) -> str:

    if not isinstance(value, str):
        raise DiscoveryDomainError(
            f"{field_name} must be a string"
        )

    if value != value.strip():
        raise DiscoveryDomainError(
            f"{field_name} must already be normalized"
        )

    return _required_text(
        value,
        field_name,
    )


def _aware_datetime(
    value: datetime,
    field_name: str,
) -> datetime:

    if not isinstance(value, datetime):
        raise DiscoveryDomainError(
            f"{field_name} must be datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise DiscoveryDomainError(
            f"{field_name} must be timezone-aware"
        )

    return value


def _canonical_https_url(
    value: str | None,
) -> str | None:

    if value is None:
        return None

    normalized = _required_text(
        value,
        "canonical_career_url",
    )

    parsed = urlparse(normalized)

    if parsed.scheme != "https":
        raise DiscoveryDomainError(
            "canonical_career_url must use https"
        )

    if not parsed.hostname:
        raise DiscoveryDomainError(
            "canonical_career_url requires host"
        )

    if parsed.username or parsed.password:
        raise DiscoveryDomainError(
            "canonical_career_url may not contain credentials"
        )

    return normalized


@dataclass(
    frozen=True,
    slots=True,
)
class CareerSourceDiscoveryCandidate:

    discovery_candidate_id: str
    employer_name: str
    state: DiscoveryState

    first_seen_at: datetime
    last_seen_at: datetime
    state_changed_at: datetime
    created_at: datetime
    updated_at: datetime

    provider_kind: str | None = None

    provider_identity_key: str | None = None
    provider_identity_json: str | None = None
    provider_identity_sha256: str | None = None

    canonical_career_url: str | None = None

    discovery_research_evidence_id: str | None = None
    listing_research_evidence_id: str | None = None
    detail_research_evidence_id: str | None = None

    last_error_code: str | None = None
    admitted_source_id: str | None = None

    def __post_init__(self) -> None:

        object.__setattr__(
            self,
            "discovery_candidate_id",
            _required_text(
                self.discovery_candidate_id,
                "discovery_candidate_id",
            ),
        )

        object.__setattr__(
            self,
            "employer_name",
            _required_text(
                self.employer_name,
                "employer_name",
            ),
        )

        object.__setattr__(
            self,
            "state",
            DiscoveryState(self.state),
        )

        for field_name in (
            "first_seen_at",
            "last_seen_at",
            "state_changed_at",
            "created_at",
            "updated_at",
        ):

            object.__setattr__(
                self,
                field_name,
                _aware_datetime(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        if self.first_seen_at > self.last_seen_at:
            raise DiscoveryDomainError(
                "first_seen_at may not exceed last_seen_at"
            )

        if self.created_at > self.updated_at:
            raise DiscoveryDomainError(
                "created_at may not exceed updated_at"
            )

        if self.state_changed_at > self.updated_at:
            raise DiscoveryDomainError(
                "state_changed_at may not exceed updated_at"
            )

        provider_kind = _optional_text(
            self.provider_kind,
            "provider_kind",
        )

        if provider_kind is not None:
            provider_kind = provider_kind.casefold()

            if (
                provider_kind
                not in supported_provider_kinds()
            ):
                raise DiscoveryDomainError(
                    "unsupported provider_kind"
                )

        object.__setattr__(
            self,
            "provider_kind",
            provider_kind,
        )

        object.__setattr__(
            self,
            "canonical_career_url",
            _canonical_https_url(
                self.canonical_career_url
            ),
        )

        for field_name in (
            "discovery_research_evidence_id",
            "listing_research_evidence_id",
            "detail_research_evidence_id",
            "last_error_code",
            "admitted_source_id",
        ):

            object.__setattr__(
                self,
                field_name,
                _optional_text(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        self._validate_provider_identity()
        self._validate_state_requirements()

    def _validate_provider_identity(
        self,
    ) -> None:

        identity_values = (
            self.provider_identity_key,
            self.provider_identity_json,
            self.provider_identity_sha256,
        )

        present = [
            value is not None
            for value in identity_values
        ]

        if any(present) and not all(present):
            raise DiscoveryDomainError(
                "provider identity fields must be "
                "all present or all absent"
            )

        if not any(present):
            return

        if self.provider_kind is None:
            raise DiscoveryDomainError(
                "provider_kind required with "
                "provider identity"
            )

        key = _exact_identity_text(
            self.provider_identity_key,
            "provider_identity_key",
        )

        sha = _exact_identity_text(
            self.provider_identity_sha256,
            "provider_identity_sha256",
        )

        raw_json = _exact_identity_text(
            self.provider_identity_json,
            "provider_identity_json",
        )

        if not _PROVIDER_KEY_RE.fullmatch(key):
            raise DiscoveryDomainError(
                "provider_identity_key has invalid namespace"
            )

        if not _SHA256_RE.fullmatch(sha):
            raise DiscoveryDomainError(
                "provider_identity_sha256 invalid"
            )

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise DiscoveryDomainError(
                "provider_identity_json invalid"
            ) from exc

        if not isinstance(payload, dict):
            raise DiscoveryDomainError(
                "provider_identity_json must be object"
            )

        payload = dict(payload)

        payload_kind = payload.pop(
            "provider_kind",
            None,
        )

        if payload_kind != self.provider_kind:
            raise DiscoveryDomainError(
                "provider identity provider_kind mismatch"
            )

        canonical = canonicalize_provider_identity(
            self.provider_kind,
            payload,
        )

        if canonical.provider_identity_key != key:
            raise DiscoveryDomainError(
                "provider_identity_key mismatch"
            )

        if canonical.identity_sha256 != sha:
            raise DiscoveryDomainError(
                "provider_identity_sha256 mismatch"
            )

        if canonical.canonical_json != raw_json:
            raise DiscoveryDomainError(
                "provider_identity_json is not canonical"
            )

    def _validate_state_requirements(
        self,
    ) -> None:

        state = self.state

        if (
            state == DiscoveryState.ATS_IDENTIFIED
            and self.provider_kind is None
        ):
            raise DiscoveryDomainError(
                "ats_identified requires provider_kind"
            )

        if state in _IDENTITY_REQUIRED_STATES:

            if self.provider_kind is None:
                raise DiscoveryDomainError(
                    f"{state.value} requires provider_kind"
                )

            if self.provider_identity_key is None:
                raise DiscoveryDomainError(
                    f"{state.value} requires provider identity"
                )

            if self.canonical_career_url is None:
                raise DiscoveryDomainError(
                    f"{state.value} requires canonical_career_url"
                )

        if (
            state
            in _LISTING_EVIDENCE_REQUIRED_STATES
            and self.listing_research_evidence_id
            is None
        ):
            raise DiscoveryDomainError(
                f"{state.value} requires listing evidence"
            )

        if (
            state
            in _DETAIL_EVIDENCE_REQUIRED_STATES
            and self.detail_research_evidence_id
            is None
        ):
            raise DiscoveryDomainError(
                f"{state.value} requires detail evidence"
            )

        if state == DiscoveryState.ADMITTED:

            if self.admitted_source_id is None:
                raise DiscoveryDomainError(
                    "admitted requires admitted_source_id"
                )

        elif self.admitted_source_id is not None:

            raise DiscoveryDomainError(
                "admitted_source_id forbidden "
                "outside admitted state"
            )

        if (
            state
            in {
                DiscoveryState.DEGRADED,
                DiscoveryState.REJECTED,
            }
            and self.last_error_code is None
        ):
            raise DiscoveryDomainError(
                f"{state.value} requires last_error_code"
            )


def transition_candidate(
    candidate: CareerSourceDiscoveryCandidate,
    target: DiscoveryState,
    *,
    at: datetime,
    last_error_code: str | None = None,
    **updates: Any,
) -> CareerSourceDiscoveryCandidate:

    target_state = DiscoveryState(target)

    if not can_transition(
        candidate.state,
        target_state,
    ):
        raise DiscoveryTransitionError(
            f"illegal discovery transition: "
            f"{candidate.state.value} -> "
            f"{target_state.value}"
        )

    transition_at = _aware_datetime(
        at,
        "at",
    )

    if transition_at < candidate.state_changed_at:
        raise DiscoveryTransitionError(
            "transition timestamp precedes "
            "current state timestamp"
        )

    protected_identity_fields = (
        "provider_kind",
        "provider_identity_key",
        "provider_identity_json",
        "provider_identity_sha256",
    )

    if candidate.provider_identity_key is not None:

        for field_name in protected_identity_fields:

            if (
                field_name in updates
                and updates[field_name]
                != getattr(candidate, field_name)
            ):
                raise DiscoveryTransitionError(
                    "established provider identity "
                    "may not mutate during transition"
                )

    if target_state in {
        DiscoveryState.DEGRADED,
        DiscoveryState.REJECTED,
    }:

        effective_error = (
            last_error_code
            if last_error_code is not None
            else updates.pop(
                "last_error_code",
                None,
            )
        )

        if effective_error is None:
            raise DiscoveryTransitionError(
                f"{target_state.value} requires "
                "explicit last_error_code"
            )

    else:
        effective_error = updates.pop(
            "last_error_code",
            None,
        )

        if (
            effective_error is None
            and candidate.state
            == DiscoveryState.DEGRADED
        ):
            effective_error = None

        elif effective_error is None:
            effective_error = candidate.last_error_code

    if "state" in updates:
        raise DiscoveryTransitionError(
            "state may not be supplied in updates"
        )

    for forbidden in (
        "state_changed_at",
        "last_seen_at",
        "updated_at",
    ):
        if forbidden in updates:
            raise DiscoveryTransitionError(
                f"{forbidden} is controlled by "
                "transition_candidate"
            )

    if candidate.state == DiscoveryState.DEGRADED:
        if target_state not in {
            DiscoveryState.REJECTED,
            DiscoveryState.DISABLED,
        }:
            effective_error = None

    return replace(
        candidate,
        state=target_state,
        state_changed_at=transition_at,
        last_seen_at=max(
            candidate.last_seen_at,
            transition_at,
        ),
        updated_at=max(
            candidate.updated_at,
            transition_at,
        ),
        last_error_code=effective_error,
        **updates,
    )
