from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re
from typing import Any, Protocol

from career.schemas import (
    CareerFitAssessment,
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerVerdict,
    HardExclusionCode,
)


SCORER_VERSION = "phase17c14-deterministic-v1"

ROLE_ALIGNMENT_MAX = 30
SKILLS_ALIGNMENT_MAX = 25
EXPERIENCE_FIT_MAX = 20
GEOGRAPHY_WORK_MODE_MAX = 15
FRESHNESS_OBSERVATION_MAX = 10
MAX_SHORTLIST_RESULTS = 10

DEFAULT_ROLE_FAMILIES = (
    "Junior Cloud Engineer",
    "Junior DevOps Engineer",
    "Cloud Support Engineer",
    "Junior Systems Administrator",
    "Infrastructure Analyst",
    "Cloud Analyst",
    "IT Support",
)

_VERDICT_PRIORITY = {
    "APPLY": 0,
    "CONSIDER": 1,
    "SKIP": 2,
}

_SENIOR_TITLE_TOKENS = {
    "senior",
    "sr",
    "lead",
    "principal",
    "staff",
}

_CANADIAN_NAMES = (
    "canada",
    "ontario",
    "quebec",
    "british columbia",
    "alberta",
    "manitoba",
    "saskatchewan",
    "nova scotia",
    "new brunswick",
    "newfoundland and labrador",
    "prince edward island",
    "yukon",
    "northwest territories",
    "nunavut",
)

_CANADIAN_ABBREVIATIONS = (
    "ON",
    "QC",
    "BC",
    "AB",
    "MB",
    "SK",
    "NS",
    "NB",
    "NL",
    "PE",
    "YT",
    "NT",
    "NU",
)

_NON_CANADIAN_COUNTRIES = (
    "united states",
    "usa",
    "u s a",
    "india",
    "united kingdom",
    "uk",
    "england",
    "germany",
    "france",
    "australia",
    "new zealand",
    "mexico",
)

_EXPERIENCE_KEYS = {
    "minimum_years_experience",
    "minimum_experience_years",
    "min_years_experience",
    "min_experience_years",
    "required_years_experience",
    "required_experience_years",
    "years_experience",
    "experience_years",
}


class CareerScoringIneligible(ValueError):
    """Raised when input is not eligible for Career scoring."""


class FitAssessmentRepository(Protocol):
    def persist_fit_assessment(
        self,
        assessment: CareerFitAssessment,
    ) -> CareerFitAssessment:
        ...


@dataclass(frozen=True)
class CareerScoringProfile:
    version: str
    role_families: tuple[str, ...]
    skills: tuple[str, ...]
    minimum_experience_years: int = 0
    maximum_experience_years: int = 3
    primary_region: str = "Ontario"
    remote_country: str = "Canada"

    def __post_init__(self) -> None:
        if len(self.version.strip()) < 4:
            raise ValueError(
                "profile version must contain at least "
                "four non-space characters"
            )

        if not self.role_families:
            raise ValueError(
                "at least one target role family is required"
            )

        if self.minimum_experience_years < 0:
            raise ValueError(
                "minimum experience cannot be negative"
            )

        if (
            self.maximum_experience_years
            < self.minimum_experience_years
        ):
            raise ValueError(
                "maximum experience cannot be lower "
                "than minimum experience"
            )


@dataclass(frozen=True)
class CareerScoredJob:
    job: CareerJobPosting
    snapshot: CareerJobSnapshot
    assessment: CareerFitAssessment


def _normalize(value: str | None) -> str:
    if not value:
        return ""

    return " ".join(
        re.sub(
            r"[^a-z0-9]+",
            " ",
            value.casefold(),
        ).split()
    )


def _contains_phrase(
    haystack: str,
    needle: str,
) -> bool:
    if not needle:
        return False

    return (
        needle == haystack
        or f" {needle} "
        in f" {haystack} "
    )


def _flatten_requirements(
    value: Any,
) -> str:
    if isinstance(value, Mapping):
        parts: list[str] = []

        for key in sorted(
            value,
            key=lambda item: str(item),
        ):
            parts.append(str(key))
            parts.append(
                _flatten_requirements(
                    value[key]
                )
            )

        return " ".join(parts)

    if isinstance(
        value,
        (list, tuple),
    ):
        return " ".join(
            _flatten_requirements(item)
            for item in value
        )

    if value is None:
        return ""

    return str(value)


def _combined_text(
    snapshot: CareerJobSnapshot,
) -> str:
    return _normalize(
        " ".join(
            (
                snapshot.title,
                snapshot.description_text,
                snapshot.employment_type or "",
                snapshot.salary_text or "",
                _flatten_requirements(
                    snapshot.requirements
                ),
            )
        )
    )


def _role_alignment(
    *,
    title: str,
    profile: CareerScoringProfile,
) -> tuple[int, str]:
    normalized_title = _normalize(title)

    best_overlap = 0.0

    for role in profile.role_families:
        normalized_role = _normalize(role)

        if _contains_phrase(
            normalized_title,
            normalized_role,
        ):
            return (
                ROLE_ALIGNMENT_MAX,
                "ROLE_ALIGNMENT_FULL",
            )

        role_tokens = set(
            normalized_role.split()
        )

        if not role_tokens:
            continue

        title_tokens = set(
            normalized_title.split()
        )

        overlap = (
            len(
                role_tokens
                & title_tokens
            )
            / len(role_tokens)
        )

        best_overlap = max(
            best_overlap,
            overlap,
        )

    points = int(
        ROLE_ALIGNMENT_MAX
        * best_overlap
    )

    return (
        points,
        (
            "ROLE_ALIGNMENT_PARTIAL"
            if points
            else "ROLE_ALIGNMENT_NONE"
        ),
    )


def _skills_alignment(
    *,
    snapshot: CareerJobSnapshot,
    profile: CareerScoringProfile,
) -> tuple[int, str]:
    skills = tuple(
        dict.fromkeys(
            normalized
            for normalized in (
                _normalize(skill)
                for skill in profile.skills
            )
            if normalized
        )
    )

    if not skills:
        return (
            0,
            "SKILLS_PROFILE_EMPTY",
        )

    text = _combined_text(
        snapshot
    )

    matched = sum(
        1
        for skill in skills
        if _contains_phrase(
            text,
            skill,
        )
    )

    points = (
        SKILLS_ALIGNMENT_MAX
        * matched
        // len(skills)
    )

    return (
        points,
        (
            "SKILLS_MATCH_"
            f"{matched}_OF_{len(skills)}"
        ),
    )


def _numeric_years(
    value: Any,
) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(
        value,
        (int, float),
    ):
        number = float(value)

        if number >= 0:
            return number

    return None


def _explicit_experience_values(
    value: Any,
) -> list[float]:
    values: list[float] = []

    if not isinstance(
        value,
        Mapping,
    ):
        return values

    for key, item in value.items():
        normalized_key = (
            _normalize(str(key))
            .replace(" ", "_")
        )

        if normalized_key in _EXPERIENCE_KEYS:
            years = _numeric_years(
                item
            )

            if years is not None:
                values.append(years)

        if isinstance(
            item,
            Mapping,
        ):
            values.extend(
                _explicit_experience_values(
                    item
                )
            )

    return values


def _experience_fit(
    *,
    snapshot: CareerJobSnapshot,
    profile: CareerScoringProfile,
) -> tuple[int, str]:
    values = _explicit_experience_values(
        snapshot.requirements
    )

    if not values:
        return (
            0,
            "EXPERIENCE_REQUIREMENT_UNKNOWN",
        )

    required_years = max(
        values
    )

    if (
        profile.minimum_experience_years
        <= required_years
        <= profile.maximum_experience_years
    ):
        return (
            EXPERIENCE_FIT_MAX,
            "EXPERIENCE_WITHIN_TARGET_BAND",
        )

    return (
        0,
        "EXPERIENCE_OUTSIDE_TARGET_BAND",
    )


def _has_abbreviation(
    text: str,
    abbreviations: tuple[str, ...],
) -> bool:
    if not text:
        return False

    pattern = (
        r"(?:^|[\s,()/\-])(?:"
        + "|".join(
            re.escape(item)
            for item in abbreviations
        )
        + r")(?:$|[\s,()/\-])"
    )

    return (
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        is not None
    )


def _is_canadian_location(
    location: str | None,
) -> bool:
    normalized = _normalize(
        location
    )

    if any(
        _contains_phrase(
            normalized,
            name,
        )
        for name in _CANADIAN_NAMES
    ):
        return True

    return _has_abbreviation(
        location or "",
        _CANADIAN_ABBREVIATIONS,
    )


def _is_ontario_location(
    location: str | None,
) -> bool:
    normalized = _normalize(
        location
    )

    return (
        _contains_phrase(
            normalized,
            "ontario",
        )
        or _has_abbreviation(
            location or "",
            ("ON",),
        )
    )


def _is_explicitly_outside_canada(
    location: str | None,
) -> bool:
    if not location:
        return False

    if _is_canadian_location(
        location
    ):
        return False

    normalized = _normalize(
        location
    )

    return any(
        _contains_phrase(
            normalized,
            country,
        )
        for country in _NON_CANADIAN_COUNTRIES
    )


def _geography_score(
    snapshot: CareerJobSnapshot,
) -> tuple[int, str]:
    if _is_ontario_location(
        snapshot.location_text
    ):
        return (
            GEOGRAPHY_WORK_MODE_MAX,
            "GEOGRAPHY_ONTARIO",
        )

    if (
        snapshot.work_mode == "REMOTE"
        and _is_canadian_location(
            snapshot.location_text
        )
    ):
        return (
            GEOGRAPHY_WORK_MODE_MAX,
            "GEOGRAPHY_REMOTE_CANADA",
        )

    if not snapshot.location_text:
        return (
            0,
            "GEOGRAPHY_LOCATION_MISSING",
        )

    return (
        0,
        "GEOGRAPHY_NOT_PREFERRED",
    )


def _freshness_score(
    snapshot: CareerJobSnapshot,
) -> tuple[int, str]:
    if (
        snapshot.freshness_state
        == "WITHIN_72H"
    ):
        return (
            FRESHNESS_OBSERVATION_MAX,
            "FRESHNESS_WITHIN_72H",
        )

    if (
        snapshot.freshness_state
        == "UNKNOWN"
    ):
        return (
            0,
            "FRESHNESS_UNKNOWN",
        )

    if (
        snapshot.freshness_state
        == "EXPIRED"
    ):
        return (
            0,
            "FRESHNESS_EXPIRED",
        )

    return (
        0,
        "FRESHNESS_OLDER_THAN_72H",
    )


def _seniority_excluded(
    title: str,
) -> bool:
    return bool(
        set(
            _normalize(
                title
            ).split()
        )
        & _SENIOR_TITLE_TOKENS
    )


def _french_required(
    snapshot: CareerJobSnapshot,
) -> bool:
    text = _combined_text(
        snapshot
    )

    if (
        "bilingual" in text
        and "french" in text
    ):
        return True

    patterns = (
        r"\bfrench required\b",
        r"\brequired french\b",
        r"\bmust\b.*\bfrench\b",
        r"\bmandatory\b.*\bfrench\b",
        r"\bfluent in french\b",
    )

    return any(
        re.search(
            pattern,
            text,
        )
        is not None
        for pattern in patterns
    )


def _unpaid(
    snapshot: CareerJobSnapshot,
) -> bool:
    text = _combined_text(
        snapshot
    )

    return (
        re.search(
            r"\bunpaid\b|\bvolunteer\b",
            text,
        )
        is not None
    )


def _clearance_required(
    snapshot: CareerJobSnapshot,
) -> bool:
    text = _combined_text(
        snapshot
    )

    patterns = (
        r"\bsecurity clearance required\b",
        r"\bsecret clearance\b",
        r"\btop secret\b",
        r"\breliability status required\b",
    )

    return any(
        re.search(
            pattern,
            text,
        )
        is not None
        for pattern in patterns
    )


def _expired_or_closed(
    *,
    job: CareerJobPosting,
    snapshot: CareerJobSnapshot,
) -> bool:
    if job.lifecycle_state in {
        "CLOSED",
        "EXPIRED",
        "REMOVED",
    }:
        return True

    if (
        snapshot.freshness_state
        == "EXPIRED"
    ):
        return True

    return (
        snapshot.closing_at
        is not None
        and snapshot.closing_at
        <= snapshot.observed_at
    )


def _hard_exclusions(
    *,
    job: CareerJobPosting,
    snapshot: CareerJobSnapshot,
) -> list[HardExclusionCode]:
    codes: list[
        HardExclusionCode
    ] = []

    if _seniority_excluded(
        snapshot.title
    ):
        codes.append(
            "SENIORITY_OUT_OF_SCOPE"
        )

    if _french_required(
        snapshot
    ):
        codes.append(
            "FRENCH_REQUIRED"
        )

    if _unpaid(
        snapshot
    ):
        codes.append(
            "UNPAID"
        )

    if _clearance_required(
        snapshot
    ):
        codes.append(
            "CLEARANCE_INELIGIBLE"
        )

    if _expired_or_closed(
        job=job,
        snapshot=snapshot,
    ):
        codes.append(
            "EXPIRED_OR_CLOSED"
        )

    if _is_explicitly_outside_canada(
        snapshot.location_text
    ):
        codes.append(
            "LOCATION_OUT_OF_SCOPE"
        )

    return codes


def verdict_for_score(
    score: float,
    *,
    hard_exclusion_codes: Iterable[
        HardExclusionCode
    ] = (),
) -> CareerVerdict:
    if score < 0 or score > 100:
        raise ValueError(
            "score must be within 0-100"
        )

    if tuple(
        hard_exclusion_codes
    ):
        return "SKIP"

    if score >= 80:
        return "APPLY"

    if score >= 60:
        return "CONSIDER"

    return "SKIP"


def _require_verified_inputs(
    *,
    job: object,
    snapshot: object,
    evidence_link: object,
) -> tuple[
    CareerJobPosting,
    CareerJobSnapshot,
    CareerJobEvidenceLink,
]:
    if not isinstance(
        job,
        CareerJobPosting,
    ):
        raise CareerScoringIneligible(
            "Career scoring requires a persisted "
            "CareerJobPosting."
        )

    if not isinstance(
        snapshot,
        CareerJobSnapshot,
    ):
        raise CareerScoringIneligible(
            "Career scoring requires a persisted "
            "CareerJobSnapshot."
        )

    if not isinstance(
        evidence_link,
        CareerJobEvidenceLink,
    ):
        raise CareerScoringIneligible(
            "Career scoring requires an evidence link."
        )

    if (
        job.verification_state
        != "VERIFIED"
    ):
        raise CareerScoringIneligible(
            "Only VERIFIED jobs are eligible "
            "for scoring."
        )

    if (
        job.current_snapshot_id
        is None
        or job.current_snapshot_id
        != snapshot.snapshot_id
    ):
        raise CareerScoringIneligible(
            "Scoring requires the job's current snapshot."
        )

    if snapshot.job_id != job.job_id:
        raise CareerScoringIneligible(
            "Snapshot job identity does not match job."
        )

    if (
        evidence_link.job_id
        != job.job_id
        or evidence_link.snapshot_id
        != snapshot.snapshot_id
    ):
        raise CareerScoringIneligible(
            "Evidence link does not bind the "
            "current job snapshot."
        )

    return (
        job,
        snapshot,
        evidence_link,
    )


def score_verified_job(
    *,
    job: object,
    snapshot: object,
    evidence_link: object,
    profile: CareerScoringProfile,
) -> CareerScoredJob:
    (
        verified_job,
        current_snapshot,
        _,
    ) = _require_verified_inputs(
        job=job,
        snapshot=snapshot,
        evidence_link=evidence_link,
    )

    (
        role_points,
        role_reason,
    ) = _role_alignment(
        title=current_snapshot.title,
        profile=profile,
    )

    (
        skills_points,
        skills_reason,
    ) = _skills_alignment(
        snapshot=current_snapshot,
        profile=profile,
    )

    (
        experience_points,
        experience_reason,
    ) = _experience_fit(
        snapshot=current_snapshot,
        profile=profile,
    )

    (
        geography_points,
        geography_reason,
    ) = _geography_score(
        current_snapshot
    )

    (
        freshness_points,
        freshness_reason,
    ) = _freshness_score(
        current_snapshot
    )

    breakdown = {
        "role_alignment":
            role_points,

        "skills_alignment":
            skills_points,

        "experience_fit":
            experience_points,

        "geography_work_mode":
            geography_points,

        "freshness_observation":
            freshness_points,
    }

    total = sum(
        breakdown.values()
    )

    hard_exclusions = _hard_exclusions(
        job=verified_job,
        snapshot=current_snapshot,
    )

    verdict = verdict_for_score(
        float(total),
        hard_exclusion_codes=(
            hard_exclusions
        ),
    )

    reason_codes = [
        role_reason,
        skills_reason,
        experience_reason,
        geography_reason,
        freshness_reason,
    ]

    reason_codes.extend(
        f"HARD_EXCLUSION_{code}"
        for code in hard_exclusions
    )

    assessment = CareerFitAssessment.build(
        job_id=verified_job.job_id,
        snapshot_id=current_snapshot.snapshot_id,
        profile_version=profile.version,
        scorer_version=SCORER_VERSION,
        fit_score=float(total),
        verdict=verdict,
        assessed_at=current_snapshot.observed_at,
        hard_exclusion_codes=(
            hard_exclusions
        ),
        score_breakdown={
            **breakdown,
            "total": total,
        },
        explanation={
            "reason_codes":
                reason_codes,

            "hard_exclusion_codes":
                list(
                    hard_exclusions
                ),

            "verified_input":
                True,

            "policy":
                SCORER_VERSION,
        },
    )

    return CareerScoredJob(
        job=verified_job,
        snapshot=current_snapshot,
        assessment=assessment,
    )


def persist_scored_job(
    repository: FitAssessmentRepository,
    scored_job: CareerScoredJob,
) -> CareerScoredJob:
    stored = (
        repository.persist_fit_assessment(
            scored_job.assessment
        )
    )

    return CareerScoredJob(
        job=scored_job.job,
        snapshot=scored_job.snapshot,
        assessment=stored,
    )


def _logical_job_key(
    item: CareerScoredJob,
) -> tuple[str, str, str]:
    return (
        _normalize(
            item.job.employer_name
        ),
        _normalize(
            item.snapshot.title
        ),
        _normalize(
            item.snapshot.location_text
        ),
    )


def _shortlist_sort_key(
    item: CareerScoredJob,
) -> tuple[
    int,
    float,
    float,
    str,
]:
    return (
        _VERDICT_PRIORITY[
            item.assessment.verdict
        ],
        -float(
            item.assessment.fit_score
        ),
        -item.snapshot.observed_at.timestamp(),
        item.job.job_id,
    )


def build_shortlist(
    items: Iterable[
        CareerScoredJob
    ],
    *,
    limit: int = MAX_SHORTLIST_RESULTS,
) -> tuple[
    CareerScoredJob,
    ...,
]:
    if (
        limit < 1
        or limit > MAX_SHORTLIST_RESULTS
    ):
        raise ValueError(
            "shortlist limit must be within 1-10"
        )

    ranked = sorted(
        (
            item
            for item in items
            if item.assessment.verdict
            in {
                "APPLY",
                "CONSIDER",
            }
        ),
        key=_shortlist_sort_key,
    )

    selected: list[
        CareerScoredJob
    ] = []

    seen: set[
        tuple[str, str, str]
    ] = set()

    for item in ranked:
        logical_key = _logical_job_key(
            item
        )

        if logical_key in seen:
            continue

        seen.add(
            logical_key
        )

        selected.append(
            item
        )

        if len(selected) == limit:
            break

    return tuple(
        selected
    )
