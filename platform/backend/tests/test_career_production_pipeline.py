from __future__ import annotations

import ast
from contextlib import contextmanager
from datetime import (
    datetime,
    timedelta,
    timezone,
)
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from career.connectors.contracts import (
    CareerDiscoveryCandidate,
)
from career.dashboard import (
    CareerDashboardService,
)
from career.eligibility import (
    CareerEligibilityError,
    classify_verified_freshness,
)
from career.ingestion import (
    CareerVerifiedJobDetail,
)
from career.production_pipeline import (
    CareerProductionCanaryError,
    run_production_canary,
)
from career.repository import (
    CareerRepository,
)
from career.scoring import (
    CareerScoringProfile,
)


OBSERVED = datetime(
    2026,
    8,
    23,
    2,
    0,
    tzinfo=timezone.utc,
)


class TruthRepository:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = path

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(
            self.path
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        try:
            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()


def _sha(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _content_id(
    prefix: str,
    seed: str,
) -> str:
    return (
        prefix
        + "-"
        + _sha(seed)[:24]
    )


def _repository(
    tmp_path: Path,
) -> tuple[
    Path,
    CareerRepository,
]:
    path = (
        tmp_path
        / "career-production.db"
    )

    with sqlite3.connect(
        path
    ) as connection:
        connection.execute(
            """
            CREATE TABLE
            research_retrieval_evidence (
                evidence_id TEXT PRIMARY KEY,
                outcome TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            )
            """
        )

        connection.commit()

    repository = CareerRepository(
        TruthRepository(path)
    )

    return (
        path,
        repository,
    )


def _candidate(
    *,
    seed: str = "one",
) -> CareerDiscoveryCandidate:
    return (
        CareerDiscoveryCandidate.build(
            connector_id=(
                "career-connector-"
                "greenhouse-v1"
            ),
            connector_kind="greenhouse",
            employer_name="Example Corp",
            source_job_id=(
                "REQ-" + seed
            ),
            title_hint=(
                "Junior Cloud Engineer"
            ),
            location_hint=(
                "Ontario, Canada"
            ),
            detail_url=(
                "https://jobs.example.com/"
                "jobs/"
                + seed
            ),
            apply_url_hint=(
                "https://jobs.example.com/"
                "jobs/"
                + seed
                + "/apply"
            ),
            discovery_research_evidence_id=(
                _content_id(
                    "research-retrieval",
                    "discovery-" + seed,
                )
            ),
            discovery_content_evidence_id=(
                _content_id(
                    "internet-content",
                    "discovery-content-"
                    + seed,
                )
            ),
            discovery_normalized_text_sha256=(
                _sha(
                    "discovery-"
                    + seed
                )
            ),
            observed_at=OBSERVED,
        )
    )


def _detail(
    *,
    evidence_id: str,
    seed: str = "one",
    posted_at: datetime | None = None,
    closing_at: datetime | None = None,
) -> CareerVerifiedJobDetail:
    description = (
        "Junior Cloud Engineer role "
        "using AWS Docker Linux Terraform"
    )

    return CareerVerifiedJobDetail(
        research_evidence_id=(
            evidence_id
        ),
        canonical_job_url=(
            "https://jobs.example.com/"
            "jobs/"
            + seed
        ),
        canonical_apply_url=(
            "https://jobs.example.com/"
            "jobs/"
            + seed
            + "/apply"
        ),
        title="Junior Cloud Engineer",
        employer_name="Example Corp",
        description_text=description,
        normalized_text_sha256=(
            _sha(description)
        ),
        observed_at=OBSERVED,
        location_text=(
            "Ontario, Canada"
        ),
        work_mode="HYBRID",
        employment_type="Full-time",
        posted_at=posted_at,
        closing_at=closing_at,
        requirements={
            "minimum_years_experience":
                1,
        },
    )


def _insert_evidence(
    path: Path,
    detail: CareerVerifiedJobDetail,
) -> None:
    payload = json.dumps(
        {
            "normalized_text_sha256":
                detail
                .normalized_text_sha256,

            "final_url":
                detail
                .canonical_job_url,
        },
        sort_keys=True,
    )

    with sqlite3.connect(
        path
    ) as connection:
        connection.execute(
            """
            INSERT INTO
            research_retrieval_evidence (
                evidence_id,
                outcome,
                evidence_json
            )
            VALUES (?, 'succeeded', ?)
            """,
            (
                detail.research_evidence_id,
                payload,
            ),
        )

        connection.commit()


def _profile() -> CareerScoringProfile:
    return CareerScoringProfile(
        version="phase19-test-v1",
        role_families=(
            "Junior Cloud Engineer",
        ),
        skills=(
            "AWS",
            "Docker",
            "Linux",
            "Terraform",
        ),
        minimum_experience_years=0,
        maximum_experience_years=3,
        primary_region="Ontario",
        remote_country="Canada",
    )


def _table_count(
    path: Path,
    table: str,
) -> int:
    with sqlite3.connect(
        path
    ) as connection:
        return int(
            connection.execute(
                f'SELECT COUNT(*) '
                f'FROM "{table}"'
            ).fetchone()[0]
        )


def test_freshness_within_72h() -> None:
    decision = (
        classify_verified_freshness(
            posted_at=(
                OBSERVED
                - timedelta(hours=24)
            ),
            closing_at=None,
            observed_at=OBSERVED,
        )
    )

    assert (
        decision.freshness_state
        == "WITHIN_72H"
    )
    assert (
        decision.lifecycle_state
        == "ACTIVE"
    )
    assert decision.surface_eligible


def test_freshness_older_than_72h() -> None:
    decision = (
        classify_verified_freshness(
            posted_at=(
                OBSERVED
                - timedelta(hours=96)
            ),
            closing_at=None,
            observed_at=OBSERVED,
        )
    )

    assert (
        decision.freshness_state
        == "OLDER_THAN_72H"
    )
    assert (
        decision.lifecycle_state
        == "ACTIVE"
    )
    assert not decision.surface_eligible


def test_missing_posted_at_is_not_surfaceable() -> None:
    decision = (
        classify_verified_freshness(
            posted_at=None,
            closing_at=None,
            observed_at=OBSERVED,
        )
    )

    assert (
        decision.freshness_state
        == "UNKNOWN"
    )
    assert (
        decision.lifecycle_state
        == "ACTIVE"
    )
    assert not decision.surface_eligible


def test_closed_posting_is_expired() -> None:
    decision = (
        classify_verified_freshness(
            posted_at=(
                OBSERVED
                - timedelta(hours=24)
            ),
            closing_at=(
                OBSERVED
                - timedelta(minutes=1)
            ),
            observed_at=OBSERVED,
        )
    )

    assert (
        decision.freshness_state
        == "EXPIRED"
    )
    assert (
        decision.lifecycle_state
        == "EXPIRED"
    )
    assert not decision.surface_eligible


def test_future_posted_at_fails_closed() -> None:
    with pytest.raises(
        CareerEligibilityError,
        match="future posted_at",
    ):
        classify_verified_freshness(
            posted_at=(
                OBSERVED
                + timedelta(minutes=1)
            ),
            closing_at=None,
            observed_at=OBSERVED,
        )


def test_candidate_cap_fails_before_verification_or_write(
    tmp_path: Path,
) -> None:
    path, repository = (
        _repository(tmp_path)
    )

    candidates = tuple(
        _candidate(
            seed=str(index)
        )
        for index in range(4)
    )

    verify_calls = 0

    def verify(candidate, route):
        del candidate
        del route
        nonlocal verify_calls
        verify_calls += 1
        raise AssertionError(
            "verify must not run"
        )

    with pytest.raises(
        CareerProductionCanaryError,
        match="more than three",
    ):
        run_production_canary(
            repository=repository,
            provider_kind="greenhouse",
            provider_target={
                "board": "example",
            },
            discover=lambda route: (
                candidates
            ),
            verify=verify,
            profile=_profile(),
        )

    assert verify_calls == 0

    assert (
        _table_count(
            path,
            "career_job_postings",
        )
        == 0
    )


def test_unknown_provider_fails_before_discovery(
    tmp_path: Path,
) -> None:
    _, repository = (
        _repository(tmp_path)
    )

    discovery_calls = 0

    def discover(route):
        del route
        nonlocal discovery_calls
        discovery_calls += 1
        return ()

    with pytest.raises(
        CareerProductionCanaryError,
        match="provider route failed closed",
    ):
        run_production_canary(
            repository=repository,
            provider_kind="unknown",
            provider_target={
                "target": "example",
            },
            discover=discover,
            verify=lambda candidate, route:
                None,
            profile=_profile(),
        )

    assert discovery_calls == 0


def test_fresh_verified_job_becomes_dashboard_visible(
    tmp_path: Path,
) -> None:
    path, repository = (
        _repository(tmp_path)
    )

    candidate = _candidate()

    evidence_id = _content_id(
        "research-retrieval",
        "fresh-detail",
    )

    detail = _detail(
        evidence_id=evidence_id,
        posted_at=(
            OBSERVED
            - timedelta(hours=24)
        ),
    )

    _insert_evidence(
        path,
        detail,
    )

    result = run_production_canary(
        repository=repository,
        provider_kind="greenhouse",
        provider_target={
            "board": "example",
        },
        discover=lambda route: (
            candidate,
        ),
        verify=lambda item, route: (
            detail
        ),
        profile=_profile(),
        shortlist_limit=3,
    )

    assert result.counts.discovered == 1
    assert result.counts.verified_details == 1
    assert result.counts.ingested == 1

    assert (
        result
        .counts
        .eligible_fresh_active
        == 1
    )

    assert result.counts.scored == 1
    assert result.counts.shortlisted == 1

    eligibility = result.eligibility[0]

    assert (
        eligibility
        .snapshot
        .freshness_state
        == "WITHIN_72H"
    )

    assert (
        eligibility
        .job
        .lifecycle_state
        == "ACTIVE"
    )

    assert (
        eligibility
        .evidence_link
        .evidence_role
        == "FRESHNESS"
    )

    assert (
        _table_count(
            path,
            "career_job_snapshots",
        )
        == 2
    )

    assert (
        _table_count(
            path,
            "career_fit_assessments",
        )
        == 1
    )

    assert (
        _table_count(
            path,
            "career_applications",
        )
        == 0
    )

    assert (
        _table_count(
            path,
            "career_application_events",
        )
        == 0
    )

    dashboard = (
        CareerDashboardService(path)
    )

    listing = dashboard.list_jobs()

    assert listing.total == 1

    assert (
        listing.items[0]
        .freshness_state
        == "WITHIN_72H"
    )

    assert (
        listing.items[0]
        .lifecycle_state
        == "ACTIVE"
    )

    assert (
        listing.items[0].verdict
        == "APPLY"
    )


def test_old_verified_job_is_not_scored_or_surfaceable(
    tmp_path: Path,
) -> None:
    path, repository = (
        _repository(tmp_path)
    )

    candidate = _candidate()

    evidence_id = _content_id(
        "research-retrieval",
        "old-detail",
    )

    detail = _detail(
        evidence_id=evidence_id,
        posted_at=(
            OBSERVED
            - timedelta(hours=96)
        ),
    )

    _insert_evidence(
        path,
        detail,
    )

    result = run_production_canary(
        repository=repository,
        provider_kind="greenhouse",
        provider_target={
            "board": "example",
        },
        discover=lambda route: (
            candidate,
        ),
        verify=lambda item, route: (
            detail
        ),
        profile=_profile(),
    )

    assert (
        result
        .eligibility[0]
        .snapshot
        .freshness_state
        == "OLDER_THAN_72H"
    )

    assert (
        result
        .eligibility[0]
        .job
        .lifecycle_state
        == "ACTIVE"
    )

    assert result.counts.scored == 0
    assert result.counts.shortlisted == 0

    assert (
        _table_count(
            path,
            "career_fit_assessments",
        )
        == 0
    )

    assert (
        CareerDashboardService(
            path
        ).list_jobs().total
        == 0
    )


def test_repeated_identical_canary_has_stable_final_state(
    tmp_path: Path,
) -> None:
    path, repository = (
        _repository(tmp_path)
    )

    candidate = _candidate()

    evidence_id = _content_id(
        "research-retrieval",
        "repeat-detail",
    )

    detail = _detail(
        evidence_id=evidence_id,
        posted_at=(
            OBSERVED
            - timedelta(hours=12)
        ),
    )

    _insert_evidence(
        path,
        detail,
    )

    kwargs = {
        "repository":
            repository,

        "provider_kind":
            "greenhouse",

        "provider_target":
            {
                "board": "example",
            },

        "discover":
            lambda route: (
                candidate,
            ),

        "verify":
            lambda item, route:
                detail,

        "profile":
            _profile(),
    }

    first = run_production_canary(
        **kwargs
    )

    second = run_production_canary(
        **kwargs
    )

    assert (
        first.run_id
        == second.run_id
    )

    assert (
        _table_count(
            path,
            "career_sources",
        )
        == 1
    )

    assert (
        _table_count(
            path,
            "career_job_postings",
        )
        == 1
    )

    assert (
        _table_count(
            path,
            "career_job_snapshots",
        )
        == 2
    )

    assert (
        _table_count(
            path,
            "career_job_evidence_links",
        )
        == 2
    )

    assert (
        _table_count(
            path,
            "career_fit_assessments",
        )
        == 1
    )

    assert (
        CareerDashboardService(
            path
        ).list_jobs().total
        == 1
    )


def test_phase19_modules_have_no_network_application_or_scheduler_authority() -> None:
    backend = (
        Path(__file__).parents[1]
    )

    paths = (
        backend
        / "career"
        / "eligibility.py",

        backend
        / "career"
        / "production_pipeline.py",
    )

    forbidden_imports = {
        "aiohttp",
        "httpx",
        "requests",
        "selenium",
        "playwright",
        "socket",
        "subprocess",
        "systemd",
    }

    forbidden_definitions = {
        "apply",
        "auto_apply",
        "submit",
        "submit_application",
        "send_telegram",
        "schedule",
        "start_scheduler",
    }

    for path in paths:
        source = path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source,
            filename=str(path),
        )

        imported: set[str] = set()

        definitions: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(
                node,
                ast.Import,
            ):
                imported.update(
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
                imported.add(
                    node.module
                )

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                definitions.add(
                    node.name
                )

        assert not (
            imported
            & forbidden_imports
        )

        assert not (
            definitions
            & forbidden_definitions
        )

        assert (
            "career_applications"
            not in source
        )

        assert (
            "career_application_events"
            not in source
        )
