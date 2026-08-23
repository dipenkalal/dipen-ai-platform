from __future__ import annotations

import ast
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest

from career.schemas import (
    CareerFitAssessment,
    CareerJobEvidenceLink,
    CareerJobPosting,
    CareerJobSnapshot,
)
from career.scoring import (
    EXPERIENCE_FIT_MAX,
    FRESHNESS_OBSERVATION_MAX,
    GEOGRAPHY_WORK_MODE_MAX,
    MAX_SHORTLIST_RESULTS,
    ROLE_ALIGNMENT_MAX,
    SCORER_VERSION,
    SKILLS_ALIGNMENT_MAX,
    CareerScoredJob,
    CareerScoringIneligible,
    CareerScoringProfile,
    build_shortlist,
    persist_scored_job,
    score_verified_job,
    verdict_for_score,
)


NOW = datetime(
    2026,
    8,
    22,
    18,
    0,
    tzinfo=timezone.utc,
)

BASE_DESCRIPTION = (
    "Hands-on Python AWS Terraform Docker "
    "Kubernetes cloud infrastructure work."
)

PROFILE = CareerScoringProfile(
    version="profile-v1",
    role_families=(
        "Junior Cloud Engineer",
        "Junior DevOps Engineer",
        "Cloud Support Engineer",
        "Junior Systems Administrator",
        "Infrastructure Analyst",
        "Cloud Analyst",
        "IT Support",
    ),
    skills=(
        "Python",
        "AWS",
        "Terraform",
        "Docker",
        "Kubernetes",
    ),
)


def _fixture(
    *,
    suffix: str = "1",
    title: str = "Junior DevOps Engineer",
    description: str = BASE_DESCRIPTION,
    location: str | None = (
        "Toronto, Ontario, Canada"
    ),
    work_mode: str | None = "REMOTE",
    employment_type: str | None = "Full-time",
    salary_text: str | None = None,
    requirements: dict[str, object] | None = None,
    freshness_state: str = "WITHIN_72H",
    lifecycle_state: str = "ACTIVE",
    verification_state: str = "VERIFIED",
    closing_at: datetime | None = None,
) -> tuple[
    CareerJobPosting,
    CareerJobSnapshot,
    CareerJobEvidenceLink,
]:
    job_id = (
        "career-job-test-"
        + suffix
    )

    posted_at = None

    if freshness_state == "WITHIN_72H":
        posted_at = (
            NOW
            - timedelta(hours=1)
        )

    elif freshness_state == "OLDER_THAN_72H":
        posted_at = (
            NOW
            - timedelta(days=5)
        )

    snapshot = CareerJobSnapshot.build(
        job_id=job_id,
        source_id="career-source-test",
        title=title,
        employer_name="Example Employer",
        description_text=description,
        freshness_state=freshness_state,
        normalized_text_sha256=(
            "b" * 64
        ),
        observed_at=NOW,
        location_text=location,
        work_mode=work_mode,
        employment_type=employment_type,
        posted_at=posted_at,
        closing_at=closing_at,
        salary_text=salary_text,
        requirements=(
            requirements
            if requirements is not None
            else {
                "min_experience_years": 2,
            }
        ),
    )

    job = CareerJobPosting(
        job_id=job_id,
        employer_name="Example Employer",
        requisition_id=(
            "REQ-" + suffix
        ),
        canonical_job_url=(
            "https://example.com/jobs/"
            + suffix
        ),
        canonical_apply_url=(
            "https://example.com/jobs/"
            + suffix
            + "/apply"
        ),
        current_snapshot_id=(
            snapshot.snapshot_id
        ),
        verification_state=(
            verification_state
        ),
        lifecycle_state=lifecycle_state,
        first_seen_at=NOW,
        last_seen_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )

    evidence = (
        CareerJobEvidenceLink.build(
            job_id=job.job_id,
            snapshot_id=(
                snapshot.snapshot_id
            ),
            research_evidence_id=(
                "research-retrieval-"
                + "a" * 24
            ),
            evidence_role="JOB_DETAIL",
            linked_at=NOW,
        )
    )

    return (
        job,
        snapshot,
        evidence,
    )


def _score(
    **kwargs: object,
) -> CareerScoredJob:
    (
        job,
        snapshot,
        evidence,
    ) = _fixture(
        **kwargs
    )

    return score_verified_job(
        job=job,
        snapshot=snapshot,
        evidence_link=evidence,
        profile=PROFILE,
    )


def _manual_entry(
    *,
    suffix: str,
    score: float,
    verdict: str,
    observed_minutes: int = 0,
    employer: str = "Example Employer",
    title: str | None = None,
    location: str = (
        "Toronto, Ontario, Canada"
    ),
) -> CareerScoredJob:
    observed_at = (
        NOW
        + timedelta(
            minutes=observed_minutes
        )
    )

    job_id = (
        "career-job-shortlist-"
        + suffix
    )

    snapshot = CareerJobSnapshot.build(
        job_id=job_id,
        source_id="career-source-test",
        title=(
            title
            or f"Cloud Engineer {suffix}"
        ),
        employer_name=employer,
        description_text=(
            "Verified job description."
        ),
        freshness_state="UNKNOWN",
        normalized_text_sha256=(
            "c" * 64
        ),
        observed_at=observed_at,
        location_text=location,
        work_mode="REMOTE",
        requirements={},
    )

    job = CareerJobPosting(
        job_id=job_id,
        employer_name=employer,
        requisition_id=(
            "REQ-S-" + suffix
        ),
        canonical_job_url=(
            "https://example.com/shortlist/"
            + suffix
        ),
        canonical_apply_url=None,
        current_snapshot_id=(
            snapshot.snapshot_id
        ),
        verification_state="VERIFIED",
        lifecycle_state="ACTIVE",
        first_seen_at=observed_at,
        last_seen_at=observed_at,
        created_at=observed_at,
        updated_at=observed_at,
    )

    assessment = (
        CareerFitAssessment.build(
            job_id=job.job_id,
            snapshot_id=(
                snapshot.snapshot_id
            ),
            profile_version=(
                PROFILE.version
            ),
            scorer_version=(
                SCORER_VERSION
            ),
            fit_score=score,
            verdict=verdict,
            assessed_at=observed_at,
            hard_exclusion_codes=[],
            score_breakdown={
                "total": score,
            },
            explanation={
                "reason_codes": [
                    "TEST_ENTRY",
                ],
            },
        )
    )

    return CareerScoredJob(
        job=job,
        snapshot=snapshot,
        assessment=assessment,
    )


class _MemoryAssessmentRepository:
    def __init__(self) -> None:
        self._values: dict[
            tuple[str, str, str],
            CareerFitAssessment,
        ] = {}

    def persist_fit_assessment(
        self,
        assessment: CareerFitAssessment,
    ) -> CareerFitAssessment:
        key = (
            assessment.snapshot_id,
            assessment.profile_version,
            assessment.scorer_version,
        )

        existing = self._values.get(
            key
        )

        if existing is not None:
            assert existing == assessment
            return existing

        self._values[key] = assessment

        return assessment


def test_location_out_of_scope_schema_literal_is_accepted() -> None:
    scored = _score(
        suffix="location-schema",
        location=(
            "New York, NY, United States"
        ),
        work_mode="ONSITE",
    )

    assert (
        "LOCATION_OUT_OF_SCOPE"
        in scored.assessment.hard_exclusion_codes
    )


def test_candidate_only_input_is_ineligible() -> None:
    (
        _,
        snapshot,
        evidence,
    ) = _fixture(
        suffix="candidate-only"
    )

    with pytest.raises(
        CareerScoringIneligible,
    ):
        score_verified_job(
            job={
                "candidate_metadata_only": True,
            },
            snapshot=snapshot,
            evidence_link=evidence,
            profile=PROFILE,
        )


def test_unverified_job_is_ineligible() -> None:
    (
        job,
        snapshot,
        evidence,
    ) = _fixture(
        suffix="unverified",
        verification_state="DISCOVERED",
    )

    with pytest.raises(
        CareerScoringIneligible,
        match="VERIFIED",
    ):
        score_verified_job(
            job=job,
            snapshot=snapshot,
            evidence_link=evidence,
            profile=PROFILE,
        )


def test_current_snapshot_is_required() -> None:
    (
        job,
        snapshot,
        evidence,
    ) = _fixture(
        suffix="snapshot"
    )

    job = job.model_copy(
        update={
            "current_snapshot_id":
                None,
        }
    )

    with pytest.raises(
        CareerScoringIneligible,
        match="current snapshot",
    ):
        score_verified_job(
            job=job,
            snapshot=snapshot,
            evidence_link=evidence,
            profile=PROFILE,
        )


def test_evidence_link_is_required() -> None:
    (
        job,
        snapshot,
        _,
    ) = _fixture(
        suffix="evidence"
    )

    with pytest.raises(
        CareerScoringIneligible,
        match="evidence link",
    ):
        score_verified_job(
            job=job,
            snapshot=snapshot,
            evidence_link=None,
            profile=PROFILE,
        )


def test_evidence_link_must_bind_current_snapshot() -> None:
    (
        job,
        snapshot,
        _,
    ) = _fixture(
        suffix="evidence-bind"
    )

    bad = CareerJobEvidenceLink.build(
        job_id=job.job_id,
        snapshot_id=(
            "career-snapshot-"
            + "f" * 24
        ),
        research_evidence_id=(
            "research-retrieval-"
            + "b" * 24
        ),
        evidence_role="JOB_DETAIL",
        linked_at=NOW,
    )

    with pytest.raises(
        CareerScoringIneligible,
        match="does not bind",
    ):
        score_verified_job(
            job=job,
            snapshot=snapshot,
            evidence_link=bad,
            profile=PROFILE,
        )


def test_score_component_maxima_total_exactly_100() -> None:
    assert (
        ROLE_ALIGNMENT_MAX
        + SKILLS_ALIGNMENT_MAX
        + EXPERIENCE_FIT_MAX
        + GEOGRAPHY_WORK_MODE_MAX
        + FRESHNESS_OBSERVATION_MAX
    ) == 100


def test_fully_aligned_job_scores_100_and_apply() -> None:
    scored = _score(
        suffix="full"
    )

    assert (
        scored.assessment.fit_score
        == 100
    )

    assert (
        scored.assessment.verdict
        == "APPLY"
    )

    assert scored.assessment.score_breakdown == {
        "role_alignment": 30,
        "skills_alignment": 25,
        "experience_fit": 20,
        "geography_work_mode": 15,
        "freshness_observation": 10,
        "total": 100,
    }


def test_same_inputs_produce_same_assessment_identity() -> None:
    (
        job,
        snapshot,
        evidence,
    ) = _fixture(
        suffix="deterministic"
    )

    first = score_verified_job(
        job=job,
        snapshot=snapshot,
        evidence_link=evidence,
        profile=PROFILE,
    )

    second = score_verified_job(
        job=job,
        snapshot=snapshot,
        evidence_link=evidence,
        profile=PROFILE,
    )

    assert (
        first.assessment
        == second.assessment
    )

    assert (
        first.assessment.assessment_id
        == second.assessment.assessment_id
    )


def test_apply_threshold_is_80_through_100() -> None:
    assert verdict_for_score(
        100
    ) == "APPLY"

    assert verdict_for_score(
        80
    ) == "APPLY"


def test_consider_threshold_is_60_through_79() -> None:
    assert verdict_for_score(
        79
    ) == "CONSIDER"

    assert verdict_for_score(
        60
    ) == "CONSIDER"


def test_skip_threshold_is_0_through_59() -> None:
    assert verdict_for_score(
        59
    ) == "SKIP"

    assert verdict_for_score(
        0
    ) == "SKIP"


def test_hard_exclusion_overrides_perfect_numeric_score() -> None:
    scored = _score(
        suffix="senior",
        title=(
            "Senior Junior DevOps Engineer"
        ),
    )

    assert (
        scored.assessment.fit_score
        == 100
    )

    assert (
        scored.assessment.verdict
        == "SKIP"
    )

    assert (
        "SENIORITY_OUT_OF_SCOPE"
        in scored.assessment.hard_exclusion_codes
    )


def test_french_required_is_hard_exclusion() -> None:
    scored = _score(
        suffix="french",
        description=(
            BASE_DESCRIPTION
            + " French required."
        ),
    )

    assert (
        "FRENCH_REQUIRED"
        in scored.assessment.hard_exclusion_codes
    )

    assert (
        scored.assessment.verdict
        == "SKIP"
    )


def test_unpaid_role_is_hard_exclusion() -> None:
    scored = _score(
        suffix="unpaid",
        employment_type=(
            "Unpaid internship"
        ),
    )

    assert (
        "UNPAID"
        in scored.assessment.hard_exclusion_codes
    )

    assert (
        scored.assessment.verdict
        == "SKIP"
    )


def test_clearance_requirement_is_hard_exclusion() -> None:
    scored = _score(
        suffix="clearance",
        description=(
            BASE_DESCRIPTION
            + " Security clearance required."
        ),
    )

    assert (
        "CLEARANCE_INELIGIBLE"
        in scored.assessment.hard_exclusion_codes
    )

    assert (
        scored.assessment.verdict
        == "SKIP"
    )


def test_expired_or_closed_is_hard_exclusion() -> None:
    scored = _score(
        suffix="expired",
        lifecycle_state="CLOSED",
    )

    assert (
        "EXPIRED_OR_CLOSED"
        in scored.assessment.hard_exclusion_codes
    )

    assert (
        scored.assessment.verdict
        == "SKIP"
    )


def test_outside_canada_uses_location_code_not_agency_code() -> None:
    scored = _score(
        suffix="outside",
        location=(
            "New York, NY, United States"
        ),
        work_mode="ONSITE",
    )

    assert (
        scored.assessment.hard_exclusion_codes
        == [
            "LOCATION_OUT_OF_SCOPE",
        ]
    )

    assert (
        "AGENCY_DUPLICATE"
        not in scored.assessment.hard_exclusion_codes
    )

    assert (
        scored.assessment.verdict
        == "SKIP"
    )


def test_missing_optional_data_gets_no_invented_points() -> None:
    (
        job,
        snapshot,
        evidence,
    ) = _fixture(
        suffix="missing",
        title="Unknown Technician",
        description="General duties.",
        location=None,
        work_mode=None,
        requirements={},
        freshness_state="UNKNOWN",
    )

    profile = CareerScoringProfile(
        version="profile-missing",
        role_families=(
            "Junior DevOps Engineer",
        ),
        skills=(
            "Terraform",
            "Kubernetes",
        ),
    )

    scored = score_verified_job(
        job=job,
        snapshot=snapshot,
        evidence_link=evidence,
        profile=profile,
    )

    assert (
        scored.assessment.fit_score
        == 0
    )

    assert scored.assessment.score_breakdown == {
        "role_alignment": 0,
        "skills_alignment": 0,
        "experience_fit": 0,
        "geography_work_mode": 0,
        "freshness_observation": 0,
        "total": 0,
    }


def test_unknown_freshness_gets_zero_freshness_points() -> None:
    scored = _score(
        suffix="fresh-unknown",
        freshness_state="UNKNOWN",
    )

    assert (
        scored.assessment.score_breakdown[
            "freshness_observation"
        ]
        == 0
    )


def test_experience_points_require_explicit_compatible_data() -> None:
    unknown = _score(
        suffix="exp-unknown",
        requirements={},
    )

    compatible = _score(
        suffix="exp-compatible",
        requirements={
            "min_experience_years": 3,
        },
    )

    outside = _score(
        suffix="exp-outside",
        requirements={
            "min_experience_years": 5,
        },
    )

    assert (
        unknown.assessment.score_breakdown[
            "experience_fit"
        ]
        == 0
    )

    assert (
        compatible.assessment.score_breakdown[
            "experience_fit"
        ]
        == 20
    )

    assert (
        outside.assessment.score_breakdown[
            "experience_fit"
        ]
        == 0
    )


def test_scoring_does_not_mutate_job_or_snapshot_truth() -> None:
    (
        job,
        snapshot,
        evidence,
    ) = _fixture(
        suffix="immutability"
    )

    before_job = job.model_dump(
        mode="python"
    )

    before_snapshot = (
        snapshot.model_dump(
            mode="python"
        )
    )

    score_verified_job(
        job=job,
        snapshot=snapshot,
        evidence_link=evidence,
        profile=PROFILE,
    )

    assert (
        job.model_dump(
            mode="python"
        )
        == before_job
    )

    assert (
        snapshot.model_dump(
            mode="python"
        )
        == before_snapshot
    )


def test_reason_codes_and_hard_exclusion_codes_are_persistable() -> None:
    scored = _score(
        suffix="reasons"
    )

    assert (
        scored.assessment.explanation[
            "reason_codes"
        ]
    )

    assert (
        scored.assessment.explanation[
            "hard_exclusion_codes"
        ]
        == []
    )

    assert (
        scored.assessment.scorer_version
        == SCORER_VERSION
    )

    assert (
        scored.assessment.profile_version
        == PROFILE.version
    )


def test_fit_assessment_persistence_is_idempotent() -> None:
    scored = _score(
        suffix="persist"
    )

    repository = (
        _MemoryAssessmentRepository()
    )

    first = persist_scored_job(
        repository,
        scored,
    )

    second = persist_scored_job(
        repository,
        scored,
    )

    assert (
        first.assessment
        == second.assessment
    )

    assert len(
        repository._values
    ) == 1


def test_shortlist_contains_at_most_ten_jobs() -> None:
    entries = [
        _manual_entry(
            suffix=str(index),
            score=float(
                100 - index
            ),
            verdict="APPLY",
            title=(
                "Cloud Engineer "
                + str(index)
            ),
        )
        for index in range(12)
    ]

    shortlist = build_shortlist(
        entries
    )

    assert (
        len(shortlist)
        == MAX_SHORTLIST_RESULTS
        == 10
    )


def test_shortlist_excludes_skip_entries() -> None:
    shortlist = build_shortlist(
        (
            _manual_entry(
                suffix="skip",
                score=100,
                verdict="SKIP",
            ),
            _manual_entry(
                suffix="apply",
                score=80,
                verdict="APPLY",
            ),
        )
    )

    assert len(shortlist) == 1

    assert (
        shortlist[0].assessment.verdict
        == "APPLY"
    )


def test_shortlist_order_is_deterministic() -> None:
    entries = (
        _manual_entry(
            suffix="consider",
            score=99,
            verdict="CONSIDER",
        ),
        _manual_entry(
            suffix="apply-low-old",
            score=80,
            verdict="APPLY",
            observed_minutes=0,
        ),
        _manual_entry(
            suffix="apply-low-new",
            score=80,
            verdict="APPLY",
            observed_minutes=1,
        ),
        _manual_entry(
            suffix="apply-high",
            score=90,
            verdict="APPLY",
        ),
    )

    shortlist = build_shortlist(
        entries
    )

    assert [
        item.job.job_id
        for item in shortlist
    ] == [
        "career-job-shortlist-apply-high",
        "career-job-shortlist-apply-low-new",
        "career-job-shortlist-apply-low-old",
        "career-job-shortlist-consider",
    ]


def test_shortlist_final_tie_break_is_job_id_ascending() -> None:
    entries = (
        _manual_entry(
            suffix="b",
            score=80,
            verdict="APPLY",
            title="Cloud Engineer B",
        ),
        _manual_entry(
            suffix="a",
            score=80,
            verdict="APPLY",
            title="Cloud Engineer A",
        ),
    )

    shortlist = build_shortlist(
        entries
    )

    assert [
        item.job.job_id
        for item in shortlist
    ] == [
        "career-job-shortlist-a",
        "career-job-shortlist-b",
    ]


def test_duplicate_logical_jobs_collapse_to_best_entry() -> None:
    lower = _manual_entry(
        suffix="duplicate-low",
        score=70,
        verdict="CONSIDER",
        employer="Same Employer",
        title="Junior Cloud Engineer",
        location=(
            "Toronto, Ontario, Canada"
        ),
    )

    higher = _manual_entry(
        suffix="duplicate-high",
        score=90,
        verdict="APPLY",
        employer="Same Employer",
        title="Junior Cloud Engineer",
        location=(
            "Toronto, Ontario, Canada"
        ),
    )

    shortlist = build_shortlist(
        (
            lower,
            higher,
        )
    )

    assert len(shortlist) == 1

    assert (
        shortlist[0].job.job_id
        == "career-job-shortlist-duplicate-high"
    )


def test_scoring_layer_has_no_network_or_application_authority() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "scoring.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    imports: set[str] = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            imports.update(
                alias.name
                for alias in node.names
            )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imports.add(
                node.module
            )

    forbidden = {
        "aiohttp",
        "http.client",
        "httpx",
        "paramiko",
        "playwright",
        "requests",
        "selenium",
        "socket",
        "urllib.request",
    }

    bad = {
        imported
        for imported in imports
        for prefix in forbidden
        if (
            imported == prefix
            or imported.startswith(
                prefix + "."
            )
        )
    }

    assert bad == set()

    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    assert {
        "apply",
        "auto_apply",
        "send_application",
        "submit",
        "submit_application",
    } & names == set()

    assert (
        "DAP_AGENT_TRUTH_DB"
        not in source
    )

    assert (
        "agent-truth.db"
        not in source
    )
