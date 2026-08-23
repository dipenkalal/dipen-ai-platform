from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


CareerSourceConnectorKind = Literal[
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "workday",
    "generic_employer",
]


_NORMALIZABLE_CONNECTOR_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "text/html",
        "text/plain",
        "application/xhtml+xml",
        "application/xml",
        "text/xml",
    }
)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()

    raise TypeError(
        "Unsupported canonical JSON value: "
        f"{type(value).__name__}"
    )


def _canonical_hash(
    payload: object,
) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _content_id(
    prefix: str,
    payload: object,
) -> str:
    return (
        f"{prefix}-"
        f"{_canonical_hash(payload)[:24]}"
    )


def _require_aware(
    value: datetime,
    field_name: str,
) -> None:
    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )


def _validate_https_url(
    value: str,
    field_name: str,
) -> str:
    if value != value.strip():
        raise ValueError(
            f"{field_name} must not contain "
            "leading/trailing whitespace"
        )

    parsed = urlsplit(value)

    if parsed.scheme.lower() != "https":
        raise ValueError(
            f"{field_name} must use https"
        )

    if not parsed.hostname:
        raise ValueError(
            f"{field_name} must contain a hostname"
        )

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(
            f"{field_name} must not contain "
            "userinfo credentials"
        )

    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError(
            f"{field_name} contains an invalid port"
        ) from error

    if port not in {None, 443}:
        raise ValueError(
            f"{field_name} may only use HTTPS port 443"
        )

    if parsed.fragment:
        raise ValueError(
            f"{field_name} must not contain a fragment"
        )

    return value


def _normalized_required_text(
    value: str,
    field_name: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def _normalized_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    return normalized or None


class CareerConnectorDescriptor(BaseModel):
    """
    Static connector capabilities.

    A connector is a deterministic parser/URL adapter.
    It does not own network transport or submission.
    """

    model_config = ConfigDict(frozen=True)

    connector_id: str = Field(
        pattern=(
            r"^career-connector-"
            r"[a-z0-9][a-z0-9._-]{1,80}$"
        )
    )

    connector_kind: CareerSourceConnectorKind

    display_name: str = Field(
        min_length=1,
        max_length=200,
    )

    priority: int = Field(
        ge=1,
        le=3,
    )

    response_media_types: tuple[
        str,
        ...
    ] = Field(
        min_length=1,
        max_length=6,
    )

    connector_owns_network: Literal[False] = False
    credentials_required: Literal[False] = False

    application_submission_supported: Literal[
        False
    ] = False

    browser_authority_granted: Literal[
        False
    ] = False

    candidate_metadata_is_job_truth: Literal[
        False
    ] = False

    @model_validator(mode="after")
    def validate_descriptor(
        self,
    ) -> CareerConnectorDescriptor:
        if self.display_name != self.display_name.strip():
            raise ValueError(
                "display_name must already be normalized"
            )

        if len(set(self.response_media_types)) != len(
            self.response_media_types
        ):
            raise ValueError(
                "response_media_types must be unique"
            )

        unsupported = (
            set(self.response_media_types)
            - _NORMALIZABLE_CONNECTOR_MEDIA_TYPES
        )

        if unsupported:
            raise ValueError(
                "Connector requested media types "
                "outside the sealed Phase-16 "
                "normalizer set: "
                + ",".join(sorted(unsupported))
            )

        return self


class CareerConnectorParseInput(BaseModel):
    """
    Phase-16 evidence projection supplied to a pure
    Career connector parser.

    This object does not itself prove job truth.
    """

    model_config = ConfigDict(frozen=True)

    research_evidence_id: str = Field(
        pattern=(
            r"^research-retrieval-"
            r"[0-9a-f]{24}$"
        )
    )

    content_evidence_id: str = Field(
        pattern=(
            r"^internet-content-"
            r"[0-9a-f]{24}$"
        )
    )

    source_url: str = Field(
        min_length=8,
        max_length=4000,
    )

    media_type: str = Field(
        min_length=3,
        max_length=200,
    )

    normalized_text: str = Field(
        min_length=1,
        max_length=1_000_000,
    )

    normalized_text_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    observed_at: datetime

    phase16_normalized_evidence: Literal[
        True
    ] = True

    metadata_is_job_truth: Literal[
        False
    ] = False

    application_authority_granted: Literal[
        False
    ] = False

    @model_validator(mode="after")
    def validate_parse_input(
        self,
    ) -> CareerConnectorParseInput:
        _require_aware(
            self.observed_at,
            "observed_at",
        )

        _validate_https_url(
            self.source_url,
            "source_url",
        )

        if (
            self.media_type
            not in _NORMALIZABLE_CONNECTOR_MEDIA_TYPES
        ):
            raise ValueError(
                "Connector parse input media type "
                "is outside the sealed Phase-16 "
                "normalizer set"
            )

        actual_hash = hashlib.sha256(
            self.normalized_text.encode("utf-8")
        ).hexdigest()

        if (
            actual_hash
            != self.normalized_text_sha256
        ):
            raise ValueError(
                "normalized_text_sha256 does not "
                "match normalized_text"
            )

        return self


class CareerDiscoveryCandidate(BaseModel):
    """
    Immutable discovery observation.

    Candidate hints are never final Career job truth.
    """

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(
        pattern=(
            r"^career-candidate-"
            r"[0-9a-f]{24}$"
        )
    )

    source_identity_key: str = Field(
        pattern=(
            r"^career-source-key-"
            r"[0-9a-f]{24}$"
        )
    )

    connector_id: str = Field(
        pattern=(
            r"^career-connector-"
            r"[a-z0-9][a-z0-9._-]{1,80}$"
        )
    )

    connector_kind: CareerSourceConnectorKind

    employer_name: str = Field(
        min_length=1,
        max_length=300,
    )

    source_job_id: str = Field(
        min_length=1,
        max_length=500,
    )

    title_hint: str = Field(
        min_length=1,
        max_length=500,
    )

    location_hint: str | None = Field(
        default=None,
        max_length=500,
    )

    detail_url: str = Field(
        min_length=8,
        max_length=4000,
    )

    apply_url_hint: str | None = Field(
        default=None,
        max_length=4000,
    )

    posted_at_hint: datetime | None = None
    source_updated_at_hint: datetime | None = None

    discovery_research_evidence_id: str = Field(
        pattern=(
            r"^research-retrieval-"
            r"[0-9a-f]{24}$"
        )
    )

    discovery_content_evidence_id: str = Field(
        pattern=(
            r"^internet-content-"
            r"[0-9a-f]{24}$"
        )
    )

    discovery_normalized_text_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    observed_at: datetime

    metadata_is_job_truth: Literal[
        False
    ] = False

    freshness_verified: Literal[
        False
    ] = False

    eligible_for_scoring: Literal[
        False
    ] = False

    eligible_for_shortlist: Literal[
        False
    ] = False

    application_authority_granted: Literal[
        False
    ] = False

    @classmethod
    def build(
        cls,
        *,
        connector_id: str,
        connector_kind: CareerSourceConnectorKind,
        employer_name: str,
        source_job_id: str,
        title_hint: str,
        detail_url: str,
        discovery_research_evidence_id: str,
        discovery_content_evidence_id: str,
        discovery_normalized_text_sha256: str,
        observed_at: datetime,
        location_hint: str | None = None,
        apply_url_hint: str | None = None,
        posted_at_hint: datetime | None = None,
        source_updated_at_hint: datetime | None = None,
    ) -> CareerDiscoveryCandidate:
        _require_aware(
            observed_at,
            "observed_at",
        )

        if posted_at_hint is not None:
            _require_aware(
                posted_at_hint,
                "posted_at_hint",
            )

        if source_updated_at_hint is not None:
            _require_aware(
                source_updated_at_hint,
                "source_updated_at_hint",
            )

        connector_id = _normalized_required_text(
            connector_id,
            "connector_id",
        )

        employer_name = _normalized_required_text(
            employer_name,
            "employer_name",
        )

        source_job_id = _normalized_required_text(
            source_job_id,
            "source_job_id",
        )

        title_hint = _normalized_required_text(
            title_hint,
            "title_hint",
        )

        location_hint = _normalized_optional_text(
            location_hint
        )

        detail_url = _validate_https_url(
            detail_url,
            "detail_url",
        )

        if apply_url_hint is not None:
            apply_url_hint = (
                _normalized_optional_text(
                    apply_url_hint
                )
            )

            if apply_url_hint is not None:
                apply_url_hint = _validate_https_url(
                    apply_url_hint,
                    "apply_url_hint",
                )

        identity_payload = {
            "connector_id": connector_id,
            "connector_kind": connector_kind,
            "employer_name": employer_name,
            "source_job_id": source_job_id,
            "detail_url": detail_url,
        }

        source_identity_key = _content_id(
            "career-source-key",
            identity_payload,
        )

        payload = {
            "source_identity_key":
                source_identity_key,
            "connector_id":
                connector_id,
            "connector_kind":
                connector_kind,
            "employer_name":
                employer_name,
            "source_job_id":
                source_job_id,
            "title_hint":
                title_hint,
            "location_hint":
                location_hint,
            "detail_url":
                detail_url,
            "apply_url_hint":
                apply_url_hint,
            "posted_at_hint":
                posted_at_hint,
            "source_updated_at_hint":
                source_updated_at_hint,
            "discovery_research_evidence_id":
                discovery_research_evidence_id,
            "discovery_content_evidence_id":
                discovery_content_evidence_id,
            "discovery_normalized_text_sha256":
                discovery_normalized_text_sha256,
            "observed_at":
                observed_at,
            "metadata_is_job_truth":
                False,
            "freshness_verified":
                False,
            "eligible_for_scoring":
                False,
            "eligible_for_shortlist":
                False,
            "application_authority_granted":
                False,
        }

        return cls(
            candidate_id=_content_id(
                "career-candidate",
                payload,
            ),
            **payload,
        )

    @model_validator(mode="after")
    def validate_candidate(
        self,
    ) -> CareerDiscoveryCandidate:
        for name in (
            "observed_at",
            "posted_at_hint",
            "source_updated_at_hint",
        ):
            value = getattr(self, name)

            if value is not None:
                _require_aware(
                    value,
                    name,
                )

        for name in (
            "connector_id",
            "employer_name",
            "source_job_id",
            "title_hint",
        ):
            value = getattr(self, name)

            if value != value.strip():
                raise ValueError(
                    f"{name} must already be normalized"
                )

        if self.location_hint is not None:
            if (
                self.location_hint
                != self.location_hint.strip()
            ):
                raise ValueError(
                    "location_hint must already "
                    "be normalized"
                )

        _validate_https_url(
            self.detail_url,
            "detail_url",
        )

        if self.apply_url_hint is not None:
            _validate_https_url(
                self.apply_url_hint,
                "apply_url_hint",
            )

        identity_payload = {
            "connector_id":
                self.connector_id,
            "connector_kind":
                self.connector_kind,
            "employer_name":
                self.employer_name,
            "source_job_id":
                self.source_job_id,
            "detail_url":
                self.detail_url,
        }

        expected_source_key = _content_id(
            "career-source-key",
            identity_payload,
        )

        if (
            self.source_identity_key
            != expected_source_key
        ):
            raise ValueError(
                "source_identity_key does not "
                "match canonical source identity"
            )

        payload = self.model_dump(
            mode="python",
            exclude={"candidate_id"},
        )

        expected_candidate_id = _content_id(
            "career-candidate",
            payload,
        )

        if self.candidate_id != expected_candidate_id:
            raise ValueError(
                "candidate_id does not match "
                "canonical candidate content"
            )

        return self


class CareerConnectorResult(BaseModel):
    """
    Immutable output from one pure connector parser run.
    """

    model_config = ConfigDict(frozen=True)

    result_id: str = Field(
        pattern=(
            r"^career-connector-result-"
            r"[0-9a-f]{24}$"
        )
    )

    connector_id: str = Field(
        pattern=(
            r"^career-connector-"
            r"[a-z0-9][a-z0-9._-]{1,80}$"
        )
    )

    research_evidence_id: str = Field(
        pattern=(
            r"^research-retrieval-"
            r"[0-9a-f]{24}$"
        )
    )

    content_evidence_id: str = Field(
        pattern=(
            r"^internet-content-"
            r"[0-9a-f]{24}$"
        )
    )

    source_url: str = Field(
        min_length=8,
        max_length=4000,
    )

    normalized_text_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    observed_at: datetime

    candidates: tuple[
        CareerDiscoveryCandidate,
        ...
    ]

    candidate_count: int = Field(
        ge=0,
        le=10000,
    )

    metadata_is_job_truth: Literal[
        False
    ] = False

    production_truth_mutation_allowed: Literal[
        False
    ] = False

    application_authority_granted: Literal[
        False
    ] = False

    @classmethod
    def build(
        cls,
        *,
        connector_id: str,
        parse_input: CareerConnectorParseInput,
        candidates: tuple[
            CareerDiscoveryCandidate,
            ...
        ],
    ) -> CareerConnectorResult:
        candidate_ids = [
            candidate.candidate_id
            for candidate in candidates
        ]

        payload = {
            "connector_id":
                connector_id,
            "research_evidence_id":
                parse_input.research_evidence_id,
            "content_evidence_id":
                parse_input.content_evidence_id,
            "source_url":
                parse_input.source_url,
            "normalized_text_sha256":
                parse_input.normalized_text_sha256,
            "observed_at":
                parse_input.observed_at,
            "candidate_ids":
                candidate_ids,
            "candidate_count":
                len(candidates),
            "metadata_is_job_truth":
                False,
            "production_truth_mutation_allowed":
                False,
            "application_authority_granted":
                False,
        }

        return cls(
            result_id=_content_id(
                "career-connector-result",
                payload,
            ),
            connector_id=connector_id,
            research_evidence_id=(
                parse_input.research_evidence_id
            ),
            content_evidence_id=(
                parse_input.content_evidence_id
            ),
            source_url=parse_input.source_url,
            normalized_text_sha256=(
                parse_input.normalized_text_sha256
            ),
            observed_at=parse_input.observed_at,
            candidates=candidates,
            candidate_count=len(candidates),
        )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> CareerConnectorResult:
        _require_aware(
            self.observed_at,
            "observed_at",
        )

        _validate_https_url(
            self.source_url,
            "source_url",
        )

        if self.candidate_count != len(
            self.candidates
        ):
            raise ValueError(
                "candidate_count does not match "
                "candidate tuple length"
            )

        candidate_ids: list[str] = []

        for candidate in self.candidates:
            if (
                candidate.connector_id
                != self.connector_id
            ):
                raise ValueError(
                    "Result contains candidate from "
                    "another connector"
                )

            if (
                candidate
                .discovery_research_evidence_id
                != self.research_evidence_id
            ):
                raise ValueError(
                    "Candidate research evidence "
                    "does not match result evidence"
                )

            if (
                candidate
                .discovery_content_evidence_id
                != self.content_evidence_id
            ):
                raise ValueError(
                    "Candidate content evidence "
                    "does not match result evidence"
                )

            if (
                candidate
                .discovery_normalized_text_sha256
                != self.normalized_text_sha256
            ):
                raise ValueError(
                    "Candidate content hash does not "
                    "match result content hash"
                )

            if (
                candidate.observed_at
                != self.observed_at
            ):
                raise ValueError(
                    "Candidate observation timestamp "
                    "does not match result timestamp"
                )

            candidate_ids.append(
                candidate.candidate_id
            )

        payload = {
            "connector_id":
                self.connector_id,
            "research_evidence_id":
                self.research_evidence_id,
            "content_evidence_id":
                self.content_evidence_id,
            "source_url":
                self.source_url,
            "normalized_text_sha256":
                self.normalized_text_sha256,
            "observed_at":
                self.observed_at,
            "candidate_ids":
                candidate_ids,
            "candidate_count":
                self.candidate_count,
            "metadata_is_job_truth":
                False,
            "production_truth_mutation_allowed":
                False,
            "application_authority_granted":
                False,
        }

        expected_result_id = _content_id(
            "career-connector-result",
            payload,
        )

        if self.result_id != expected_result_id:
            raise ValueError(
                "result_id does not match "
                "canonical connector result"
            )

        return self


@runtime_checkable
class CareerConnector(Protocol):
    """
    Pure connector boundary.

    Implementations may build public source URLs and parse
    Phase-16-normalized evidence. They do not perform network
    I/O, database mutation, browser actions, or submission.
    """

    @property
    def descriptor(
        self,
    ) -> CareerConnectorDescriptor:
        ...

    def parse_candidates(
        self,
        parse_input: CareerConnectorParseInput,
    ) -> CareerConnectorResult:
        ...
