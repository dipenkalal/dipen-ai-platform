"""Pure configured ATS endpoint shadow population.

Shadow targets represent configured provider endpoint identity only.
They do not create research evidence, mutate the authoritative
source registry, admit a source, or carry application authority.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from career.ats_identification import (
    identify_career_url,
)


class ShadowPopulationError(
    ValueError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowTargetInput:
    provider_kind: str
    employer_name: str
    career_url: str


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowSourceTarget:
    shadow_target_id: str
    provider_kind: str
    employer_name: str
    canonical_career_url: str
    provider_identity_key: str
    provider_identity_json: str
    provider_identity_sha256: str

    authoritative_registry_member: Literal[False] = False

    research_evidence_present: Literal[False] = False

    admission_authority_granted: Literal[False] = False

    application_authority_granted: Literal[False] = False


def _required(
    value: str,
    field: str,
) -> str:

    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
    ):
        raise ShadowPopulationError(
            f"{field} is invalid"
        )

    return value


def _status(
    value: object,
) -> str:

    return str(
        getattr(
            value,
            "value",
            value,
        )
    ).upper()


def build_shadow_target(
    value: ShadowTargetInput,
) -> ShadowSourceTarget:

    if not isinstance(
        value,
        ShadowTargetInput,
    ):
        raise ShadowPopulationError(
            "invalid shadow input"
        )

    provider = _required(
        value.provider_kind,
        "provider_kind",
    ).casefold()

    employer = _required(
        value.employer_name,
        "employer_name",
    )

    url = _required(
        value.career_url,
        "career_url",
    )

    identified = identify_career_url(
        url
    )

    if (
        _status(
            identified.status
        )
        != "ENDPOINT_IDENTIFIED"
    ):
        raise ShadowPopulationError(
            "configured target is not "
            "endpoint identified"
        )

    if (
        identified.provider_kind
        != provider
    ):
        raise ShadowPopulationError(
            "provider kind mismatch"
        )

    required = (
        identified.canonical_career_url,
        identified.provider_identity_key,
        identified.provider_identity_json,
        identified.provider_identity_sha256,
    )

    if any(
        item is None
        for item in required
    ):
        raise ShadowPopulationError(
            "provider identity incomplete"
        )

    digest = hashlib.sha256(
        identified
        .provider_identity_key
        .encode("utf-8")
    ).hexdigest()

    return ShadowSourceTarget(
        shadow_target_id=(
            "career-shadow-target-"
            + digest[:32]
        ),
        provider_kind=provider,
        employer_name=employer,
        canonical_career_url=(
            identified.canonical_career_url
        ),
        provider_identity_key=(
            identified.provider_identity_key
        ),
        provider_identity_json=(
            identified.provider_identity_json
        ),
        provider_identity_sha256=(
            identified.provider_identity_sha256
        ),
    )


def build_shadow_population(
    values: tuple[
        ShadowTargetInput,
        ...
    ],
) -> tuple[
    ShadowSourceTarget,
    ...
]:

    population = tuple(
        build_shadow_target(
            value
        )
        for value in values
    )

    provider_keys = {
        value.provider_identity_key
        for value in population
    }

    shadow_ids = {
        value.shadow_target_id
        for value in population
    }

    if (
        len(provider_keys)
        != len(population)
    ):
        raise ShadowPopulationError(
            "duplicate provider endpoint"
        )

    if (
        len(shadow_ids)
        != len(population)
    ):
        raise ShadowPopulationError(
            "shadow identity collision"
        )

    return tuple(
        sorted(
            population,
            key=lambda value: (
                value.provider_kind,
                value.employer_name.casefold(),
                value.provider_identity_key,
            ),
        )
    )
