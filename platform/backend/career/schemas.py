from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


CareerSourceKind = Literal[
    "official_structured_ats",
    "official_employer_career",
    "discovery_web",
    "third_party_discovery",
]

CareerConnectorKind = Literal[
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "workday",
    "generic_employer",
    "discovery",
]

CareerSourceState = Literal[
    "active",
    "degraded",
    "needs_review",
    "disabled",
]

CareerVerificationState = Literal[
    "DISCOVERED",
    "RETRIEVED",
    "VERIFIED",
    "FRESHNESS_UNVERIFIED",
    "EXPIRED",
    "REJECTED_SOURCE",
    "RETRIEVAL_FAILED",
]

CareerLifecycleState = Literal[
    "ACTIVE",
    "CLOSED",
    "EXPIRED",
    "REMOVED",
    "UNKNOWN",
]

CareerWorkMode = Literal[
    "REMOTE",
    "HYBRID",
    "ONSITE",
    "UNKNOWN",
]

CareerFreshnessState = Literal[
    "WITHIN_72H",
    "OLDER_THAN_72H",
    "UNKNOWN",
    "EXPIRED",
]

CareerEvidenceRole = Literal[
    "JOB_DETAIL",
    "LISTING",
    "FRESHNESS",
    "CLOSURE",
]

CareerVerdict = Literal[
    "APPLY",
    "CONSIDER",
    "SKIP",
]

HardExclusionCode = Literal[
    "SENIORITY_OUT_OF_SCOPE",
    "FRENCH_REQUIRED",
    "UNPAID",
    "EXPIRED_OR_CLOSED",
    "CLEARANCE_INELIGIBLE",
    "AGENCY_DUPLICATE",
]

CareerApplicationState = Literal[
    "SHORTLISTED",
    "PREPARING",
    "READY_FOR_REVIEW",
    "OWNER_APPROVED",
    "APPLIED_CONFIRMED",
    "INTERVIEW",
    "REJECTED",
    "WITHDRAWN",
    "OFFER",
    "CLOSED",
]

CareerAppliedConfirmationKind = Literal[
    "OWNER_MANUAL",
    "FUTURE_BROKER_EVIDENCE",
]

CareerApplicationActorKind = Literal[
    "OWNER",
    "DETERMINISTIC_SYSTEM",
]


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _canonical_hash(payload: object) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )
    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _content_id(
    prefix: str,
    payload: object,
) -> str:
    return f"{prefix}-{_canonical_hash(payload)[:24]}"


def _text_sha256(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _require_aware(
    value: datetime | None,
    field_name: str,
) -> None:
    if value is None:
        return

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )


class CareerSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str = Field(
        pattern=r"^career-source-[A-Za-z0-9._:-]+$"
    )
    display_name: str = Field(
        min_length=1,
        max_length=300,
    )
    employer_name: str = Field(
        min_length=1,
        max_length=300,
    )
    source_kind: CareerSourceKind
    connector_kind: CareerConnectorKind
    trust_tier: int = Field(ge=0, le=3)
    canonical_base_url: str = Field(
        min_length=8,
        max_length=4000,
    )
    state: CareerSourceState = "active"
    last_verified_at: datetime | None = None
    last_error_code: str | None = Field(
        default=None,
        max_length=200,
    )
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_source(self) -> CareerSource:
        _require_aware(
            self.last_verified_at,
            "last_verified_at",
        )
        _require_aware(
            self.created_at,
            "created_at",
        )
        _require_aware(
            self.updated_at,
            "updated_at",
        )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot precede created_at"
            )

        return self


class CareerJobPosting(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str = Field(
        pattern=r"^career-job-[A-Za-z0-9._:-]+$"
    )
    employer_name: str = Field(
        min_length=1,
        max_length=300,
    )
    requisition_id: str | None = Field(
        default=None,
        max_length=300,
    )
    canonical_job_url: str = Field(
        min_length=8,
        max_length=4000,
    )
    canonical_apply_url: str | None = Field(
        default=None,
        max_length=4000,
    )
    current_snapshot_id: str | None = Field(
        default=None,
        pattern=r"^career-snapshot-[0-9a-f]{24}$",
    )
    verification_state: CareerVerificationState
    lifecycle_state: CareerLifecycleState
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_job(self) -> CareerJobPosting:
        for name in (
            "first_seen_at",
            "last_seen_at",
            "created_at",
            "updated_at",
        ):
            _require_aware(
                getattr(self, name),
                name,
            )

        if self.last_seen_at < self.first_seen_at:
            raise ValueError(
                "last_seen_at cannot precede first_seen_at"
            )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot precede created_at"
            )

        return self


class CareerJobSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str = Field(
        pattern=r"^career-snapshot-[0-9a-f]{24}$"
    )
    job_id: str = Field(
        pattern=r"^career-job-[A-Za-z0-9._:-]+$"
    )
    source_id: str = Field(
        pattern=r"^career-source-[A-Za-z0-9._:-]+$"
    )
    title: str = Field(
        min_length=1,
        max_length=500,
    )
    employer_name: str = Field(
        min_length=1,
        max_length=300,
    )
    location_text: str | None = Field(
        default=None,
        max_length=500,
    )
    work_mode: CareerWorkMode | None = None
    employment_type: str | None = Field(
        default=None,
        max_length=200,
    )
    description_text: str = Field(min_length=1)
    description_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    posted_at: datetime | None = None
    closing_at: datetime | None = None
    freshness_state: CareerFreshnessState
    salary_text: str | None = None
    requirements: dict[str, Any] = Field(
        default_factory=dict
    )
    normalized_text_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    observed_at: datetime

    @classmethod
    def build(
        cls,
        *,
        job_id: str,
        source_id: str,
        title: str,
        employer_name: str,
        description_text: str,
        freshness_state: CareerFreshnessState,
        normalized_text_sha256: str,
        observed_at: datetime,
        location_text: str | None = None,
        work_mode: CareerWorkMode | None = None,
        employment_type: str | None = None,
        posted_at: datetime | None = None,
        closing_at: datetime | None = None,
        salary_text: str | None = None,
        requirements: dict[str, Any] | None = None,
    ) -> CareerJobSnapshot:
        payload: dict[str, Any] = {
            "job_id": job_id,
            "source_id": source_id,
            "title": title,
            "employer_name": employer_name,
            "location_text": location_text,
            "work_mode": work_mode,
            "employment_type": employment_type,
            "description_text": description_text,
            "description_sha256": _text_sha256(
                description_text
            ),
            "posted_at": posted_at,
            "closing_at": closing_at,
            "freshness_state": freshness_state,
            "salary_text": salary_text,
            "requirements": requirements or {},
            "normalized_text_sha256": (
                normalized_text_sha256
            ),
            "observed_at": observed_at,
        }

        return cls(
            snapshot_id=_content_id(
                "career-snapshot",
                payload,
            ),
            **payload,
        )

    @model_validator(mode="after")
    def validate_snapshot(
        self,
    ) -> CareerJobSnapshot:
        for name in (
            "posted_at",
            "closing_at",
            "observed_at",
        ):
            _require_aware(
                getattr(self, name),
                name,
            )

        if (
            self.description_sha256
            != _text_sha256(self.description_text)
        ):
            raise ValueError(
                "description_sha256 does not match "
                "description_text"
            )

        if (
            self.posted_at is None
            and self.freshness_state
            in {
                "WITHIN_72H",
                "OLDER_THAN_72H",
            }
        ):
            raise ValueError(
                "dated freshness state requires "
                "an evidenced posted_at"
            )

        payload = self.model_dump(
            mode="python",
            exclude={"snapshot_id"},
        )

        expected_id = _content_id(
            "career-snapshot",
            payload,
        )

        if self.snapshot_id != expected_id:
            raise ValueError(
                "snapshot_id does not match "
                "canonical snapshot content"
            )

        return self


class CareerJobEvidenceLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    link_id: str = Field(
        pattern=r"^career-evidence-link-[0-9a-f]{24}$"
    )
    job_id: str = Field(
        pattern=r"^career-job-[A-Za-z0-9._:-]+$"
    )
    snapshot_id: str = Field(
        pattern=r"^career-snapshot-[0-9a-f]{24}$"
    )
    research_evidence_id: str = Field(
        pattern=r"^research-retrieval-[0-9a-f]{24}$"
    )
    evidence_role: CareerEvidenceRole
    linked_at: datetime

    @classmethod
    def build(
        cls,
        *,
        job_id: str,
        snapshot_id: str,
        research_evidence_id: str,
        evidence_role: CareerEvidenceRole,
        linked_at: datetime,
    ) -> CareerJobEvidenceLink:
        payload = {
            "job_id": job_id,
            "snapshot_id": snapshot_id,
            "research_evidence_id": (
                research_evidence_id
            ),
            "evidence_role": evidence_role,
            "linked_at": linked_at,
        }

        return cls(
            link_id=_content_id(
                "career-evidence-link",
                payload,
            ),
            **payload,
        )

    @model_validator(mode="after")
    def validate_link(
        self,
    ) -> CareerJobEvidenceLink:
        _require_aware(
            self.linked_at,
            "linked_at",
        )

        payload = self.model_dump(
            mode="python",
            exclude={"link_id"},
        )

        if self.link_id != _content_id(
            "career-evidence-link",
            payload,
        ):
            raise ValueError(
                "link_id does not match canonical "
                "evidence-link content"
            )

        return self


class CareerFitAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    assessment_id: str = Field(
        pattern=r"^career-assessment-[0-9a-f]{24}$"
    )
    job_id: str = Field(
        pattern=r"^career-job-[A-Za-z0-9._:-]+$"
    )
    snapshot_id: str = Field(
        pattern=r"^career-snapshot-[0-9a-f]{24}$"
    )
    profile_version: str = Field(
        min_length=4,
        max_length=128,
    )
    scorer_version: str = Field(
        min_length=1,
        max_length=128,
    )
    fit_score: float = Field(ge=0.0, le=100.0)
    verdict: CareerVerdict
    hard_exclusion_codes: list[
        HardExclusionCode
    ] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(
        default_factory=dict
    )
    explanation: dict[str, Any] = Field(
        default_factory=dict
    )
    assessed_at: datetime

    @classmethod
    def build(
        cls,
        *,
        job_id: str,
        snapshot_id: str,
        profile_version: str,
        scorer_version: str,
        fit_score: float,
        verdict: CareerVerdict,
        assessed_at: datetime,
        hard_exclusion_codes: list[
            HardExclusionCode
        ] | None = None,
        score_breakdown: dict[
            str,
            Any,
        ] | None = None,
        explanation: dict[
            str,
            Any,
        ] | None = None,
    ) -> CareerFitAssessment:
        payload: dict[str, Any] = {
            "job_id": job_id,
            "snapshot_id": snapshot_id,
            "profile_version": profile_version,
            "scorer_version": scorer_version,
            "fit_score": float(fit_score),
            "verdict": verdict,
            "hard_exclusion_codes": (
                hard_exclusion_codes or []
            ),
            "score_breakdown": (
                score_breakdown or {}
            ),
            "explanation": explanation or {},
            "assessed_at": assessed_at,
        }

        return cls(
            assessment_id=_content_id(
                "career-assessment",
                payload,
            ),
            **payload,
        )

    @model_validator(mode="after")
    def validate_assessment(
        self,
    ) -> CareerFitAssessment:
        _require_aware(
            self.assessed_at,
            "assessed_at",
        )

        if (
            self.hard_exclusion_codes
            and self.verdict != "SKIP"
        ):
            raise ValueError(
                "hard exclusions require SKIP verdict"
            )

        payload = self.model_dump(
            mode="python",
            exclude={"assessment_id"},
        )

        if self.assessment_id != _content_id(
            "career-assessment",
            payload,
        ):
            raise ValueError(
                "assessment_id does not match "
                "canonical assessment content"
            )

        return self


class CareerApplication(BaseModel):
    model_config = ConfigDict(frozen=True)

    application_id: str = Field(
        pattern=r"^career-application-[A-Za-z0-9._:-]+$"
    )
    job_id: str = Field(
        pattern=r"^career-job-[A-Za-z0-9._:-]+$"
    )
    state: CareerApplicationState
    owner_approved_at: datetime | None = None
    applied_confirmed_at: datetime | None = None
    applied_confirmation_kind: (
        CareerAppliedConfirmationKind | None
    ) = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_application(
        self,
    ) -> CareerApplication:
        for name in (
            "owner_approved_at",
            "applied_confirmed_at",
            "created_at",
            "updated_at",
        ):
            _require_aware(
                getattr(self, name),
                name,
            )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot precede created_at"
            )

        if (
            self.state == "OWNER_APPROVED"
            and self.owner_approved_at is None
        ):
            raise ValueError(
                "OWNER_APPROVED requires "
                "owner_approved_at"
            )

        confirmation_values = (
            self.applied_confirmed_at,
            self.applied_confirmation_kind,
        )

        if (
            confirmation_values[0] is None
        ) != (
            confirmation_values[1] is None
        ):
            raise ValueError(
                "application confirmation timestamp "
                "and kind must be supplied together"
            )

        if (
            self.state == "APPLIED_CONFIRMED"
            and self.applied_confirmed_at is None
        ):
            raise ValueError(
                "APPLIED_CONFIRMED requires explicit "
                "external confirmation"
            )

        return self


class CareerApplicationEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(
        pattern=r"^career-app-event-[0-9a-f]{24}$"
    )
    application_id: str = Field(
        pattern=r"^career-application-[A-Za-z0-9._:-]+$"
    )
    from_state: CareerApplicationState | None = None
    to_state: CareerApplicationState
    actor_kind: CareerApplicationActorKind
    actor_id: str = Field(
        min_length=1,
        max_length=200,
    )
    reason: str = Field(
        min_length=1,
        max_length=4000,
    )
    evidence_id: str | None = Field(
        default=None,
        max_length=300,
    )
    occurred_at: datetime

    @classmethod
    def build(
        cls,
        *,
        application_id: str,
        from_state: CareerApplicationState | None,
        to_state: CareerApplicationState,
        actor_kind: CareerApplicationActorKind,
        actor_id: str,
        reason: str,
        occurred_at: datetime,
        evidence_id: str | None = None,
    ) -> CareerApplicationEvent:
        payload = {
            "application_id": application_id,
            "from_state": from_state,
            "to_state": to_state,
            "actor_kind": actor_kind,
            "actor_id": actor_id,
            "reason": reason,
            "evidence_id": evidence_id,
            "occurred_at": occurred_at,
        }

        return cls(
            event_id=_content_id(
                "career-app-event",
                payload,
            ),
            **payload,
        )

    @model_validator(mode="after")
    def validate_event(
        self,
    ) -> CareerApplicationEvent:
        _require_aware(
            self.occurred_at,
            "occurred_at",
        )

        payload = self.model_dump(
            mode="python",
            exclude={"event_id"},
        )

        if self.event_id != _content_id(
            "career-app-event",
            payload,
        ):
            raise ValueError(
                "event_id does not match canonical "
                "application-event content"
            )

        return self
