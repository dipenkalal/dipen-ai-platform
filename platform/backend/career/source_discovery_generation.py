"""Pure offline mapping from ATS identification to source-discovery candidates.

Phase 19.3F.2 authority boundary:

* no network
* no database access
* no repository access
* no career_sources authority
* no admission authority
* maximum generated state is ENDPOINT_CANDIDATE
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from career.ats_identification import (
    ATSIdentificationResult,
    ATSIdentificationStatus,
)
from career.source_discovery import (
    CareerSourceDiscoveryCandidate,
    DiscoveryState,
)


_DISCOVERY_CANDIDATE_PREFIX = "career-discovery-candidate-"
_WHITESPACE_RE = re.compile(r"\s+")


class DiscoveryGenerationError(ValueError):
    """Raised when a discovery observation cannot be generated safely."""


def _required_exact_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise DiscoveryGenerationError(f"{field_name} must be a string")
    if not value:
        raise DiscoveryGenerationError(f"{field_name} must not be empty")
    if value.strip() != value:
        raise DiscoveryGenerationError(
            f"{field_name} must not contain surrounding whitespace"
        )
    return value


def _normalized_employer_identity(value: str) -> str:
    exact = _required_exact_text(value, "employer_name")
    normalized = unicodedata.normalize("NFKC", exact)
    normalized = _WHITESPACE_RE.sub(" ", normalized).casefold()

    if not normalized:
        raise DiscoveryGenerationError(
            "employer_name must remain non-empty after normalization"
        )

    return normalized


def _split_input_url(identification: ATSIdentificationResult):
    try:
        parsed = urlsplit(identification.input_url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise DiscoveryGenerationError(
            "identification input_url is not safely parseable"
        ) from exc

    if parsed.scheme.lower() != "https" or not host:
        raise DiscoveryGenerationError(
            "identification input_url must be an absolute HTTPS URL"
        )

    return parsed, host.lower(), port


def _host_identity(identification: ATSIdentificationResult) -> str:
    _, host, port = _split_input_url(identification)

    if port not in (None, 443):
        return f"{host}:{port}"

    return host


def _normalized_observation_url(
    identification: ATSIdentificationResult,
) -> str:
    parsed, host, port = _split_input_url(identification)

    if ":" in host:
        host_text = f"[{host}]"
    else:
        host_text = host

    if port not in (None, 443):
        netloc = f"{host_text}:{port}"
    else:
        netloc = host_text

    path = parsed.path or "/"

    return urlunsplit(
        (
            "https",
            netloc,
            path,
            "",
            "",
        )
    )


def _candidate_identity_payload(
    *,
    employer_name: str,
    identification: ATSIdentificationResult,
) -> dict[str, str | int]:
    employer_identity = _normalized_employer_identity(employer_name)

    if identification.status is ATSIdentificationStatus.ENDPOINT_IDENTIFIED:
        provider_identity_key = identification.provider_identity_key
        if provider_identity_key is None:
            raise DiscoveryGenerationError(
                "ENDPOINT_IDENTIFIED result lacks provider_identity_key"
            )

        return {
            "version": 1,
            "scope": "provider_endpoint",
            "provider_identity_key": provider_identity_key,
        }

    if identification.status is ATSIdentificationStatus.ATS_IDENTIFIED:
        provider_kind = identification.provider_kind
        if provider_kind is None:
            raise DiscoveryGenerationError(
                "ATS_IDENTIFIED result lacks provider_kind"
            )

        return {
            "version": 1,
            "scope": "provider_family_observation",
            "employer": employer_identity,
            "provider_kind": provider_kind,
            "provider_host": _host_identity(identification),
        }

    if identification.status is ATSIdentificationStatus.UNRECOGNIZED:
        return {
            "version": 1,
            "scope": "unrecognized_observation",
            "employer": employer_identity,
            "observation_url": _normalized_observation_url(
                identification
            ),
        }

    raise DiscoveryGenerationError(
        f"unsupported ATS identification status: {identification.status!r}"
    )


def discovery_candidate_id_for(
    *,
    employer_name: str,
    identification: ATSIdentificationResult,
) -> str:
    """Return the stable identity for one discovery observation.

    Fully identified provider endpoints intentionally converge solely on
    provider_identity_key. Discovery evidence IDs and observation timestamps
    are not identity inputs.
    """

    if not isinstance(identification, ATSIdentificationResult):
        raise DiscoveryGenerationError(
            "identification must be an ATSIdentificationResult"
        )

    payload = _candidate_identity_payload(
        employer_name=employer_name,
        identification=identification,
    )

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return f"{_DISCOVERY_CANDIDATE_PREFIX}{digest[:32]}"


def generate_discovery_candidate(
    *,
    employer_name: str,
    identification: ATSIdentificationResult,
    discovery_research_evidence_id: str,
    observed_at: datetime,
) -> CareerSourceDiscoveryCandidate:
    """Map a sealed ATS identification result into the discovery domain."""

    evidence_id = _required_exact_text(
        discovery_research_evidence_id,
        "discovery_research_evidence_id",
    )

    candidate_id = discovery_candidate_id_for(
        employer_name=employer_name,
        identification=identification,
    )

    common = {
        "discovery_candidate_id": candidate_id,
        "employer_name": employer_name,
        "first_seen_at": observed_at,
        "last_seen_at": observed_at,
        "state_changed_at": observed_at,
        "created_at": observed_at,
        "updated_at": observed_at,
        "discovery_research_evidence_id": evidence_id,
        "listing_research_evidence_id": None,
        "detail_research_evidence_id": None,
        "last_error_code": None,
        "admitted_source_id": None,
    }

    if identification.status is ATSIdentificationStatus.UNRECOGNIZED:
        return CareerSourceDiscoveryCandidate(
            state=DiscoveryState.DISCOVERED,
            provider_kind=None,
            provider_identity_key=None,
            provider_identity_json=None,
            provider_identity_sha256=None,
            canonical_career_url=None,
            **common,
        )

    if identification.status is ATSIdentificationStatus.ATS_IDENTIFIED:
        return CareerSourceDiscoveryCandidate(
            state=DiscoveryState.ATS_IDENTIFIED,
            provider_kind=identification.provider_kind,
            provider_identity_key=None,
            provider_identity_json=None,
            provider_identity_sha256=None,
            canonical_career_url=None,
            **common,
        )

    if identification.status is ATSIdentificationStatus.ENDPOINT_IDENTIFIED:
        return CareerSourceDiscoveryCandidate(
            state=DiscoveryState.ENDPOINT_CANDIDATE,
            provider_kind=identification.provider_kind,
            provider_identity_key=identification.provider_identity_key,
            provider_identity_json=identification.provider_identity_json,
            provider_identity_sha256=identification.provider_identity_sha256,
            canonical_career_url=identification.canonical_career_url,
            **common,
        )

    raise DiscoveryGenerationError(
        f"unsupported ATS identification status: {identification.status!r}"
    )
