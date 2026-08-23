from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from career.dashboard import (
    CareerDashboardService,
)


def _create_database(
    path: Path,
) -> None:
    connection = sqlite3.connect(path)

    connection.executescript(
        """
        CREATE TABLE career_job_postings (
            job_id TEXT PRIMARY KEY,
            employer_name TEXT NOT NULL,
            canonical_job_url TEXT NOT NULL,
            canonical_apply_url TEXT,
            current_snapshot_id TEXT,
            verification_state TEXT NOT NULL,
            lifecycle_state TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );

        CREATE TABLE career_job_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            title TEXT NOT NULL,
            employer_name TEXT NOT NULL,
            location_text TEXT,
            work_mode TEXT,
            employment_type TEXT,
            salary_text TEXT,
            posted_at TEXT,
            closing_at TEXT,
            freshness_state TEXT NOT NULL,
            observed_at TEXT NOT NULL
        );

        CREATE TABLE career_fit_assessments (
            assessment_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            snapshot_id TEXT NOT NULL,
            fit_score REAL NOT NULL,
            verdict TEXT NOT NULL,
            hard_exclusion_codes_json TEXT NOT NULL,
            score_breakdown_json TEXT NOT NULL,
            explanation_json TEXT NOT NULL,
            assessed_at TEXT NOT NULL
        );

        CREATE TABLE career_applications (
            application_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    jobs = [
        (
            "career-job-apply",
            "Example Apply Inc",
            "https://example.com/job/apply",
            "https://example.com/job/apply/form",
            "career-snapshot-apply",
            "VERIFIED",
            "ACTIVE",
            "2026-08-23T00:00:00+00:00",
        ),
        (
            "career-job-consider",
            "Example Consider Inc",
            "https://example.com/job/consider",
            None,
            "career-snapshot-consider",
            "VERIFIED",
            "ACTIVE",
            "2026-08-23T00:00:00+00:00",
        ),
        (
            "career-job-skip",
            "Example Skip Inc",
            "https://example.com/job/skip",
            None,
            "career-snapshot-skip",
            "VERIFIED",
            "ACTIVE",
            "2026-08-23T00:00:00+00:00",
        ),
        (
            "career-job-unverified",
            "Example Unknown Inc",
            "https://example.com/job/unverified",
            None,
            "career-snapshot-unverified",
            "DISCOVERED",
            "ACTIVE",
            "2026-08-23T00:00:00+00:00",
        ),
    ]

    connection.executemany(
        """
        INSERT INTO career_job_postings (
            job_id,
            employer_name,
            canonical_job_url,
            canonical_apply_url,
            current_snapshot_id,
            verification_state,
            lifecycle_state,
            last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        jobs,
    )

    for suffix, employer in (
        ("apply", "Example Apply Inc"),
        ("consider", "Example Consider Inc"),
        ("skip", "Example Skip Inc"),
        ("unverified", "Example Unknown Inc"),
    ):
        connection.execute(
            """
            INSERT INTO career_job_snapshots (
                snapshot_id,
                job_id,
                title,
                employer_name,
                location_text,
                work_mode,
                employment_type,
                salary_text,
                posted_at,
                closing_at,
                freshness_state,
                observed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"career-snapshot-{suffix}",
                f"career-job-{suffix}",
                f"{suffix.title()} Cloud Engineer",
                employer,
                "Ontario, Canada",
                "HYBRID",
                "FULL_TIME",
                None,
                "2026-08-22T12:00:00+00:00",
                None,
                "WITHIN_72H",
                "2026-08-22T12:30:00+00:00",
            ),
        )

    assessments = (
        (
            "assessment-apply",
            "career-job-apply",
            "career-snapshot-apply",
            91.0,
            "APPLY",
        ),
        (
            "assessment-consider",
            "career-job-consider",
            "career-snapshot-consider",
            72.0,
            "CONSIDER",
        ),
        (
            "assessment-skip",
            "career-job-skip",
            "career-snapshot-skip",
            30.0,
            "SKIP",
        ),
        (
            "assessment-unverified",
            "career-job-unverified",
            "career-snapshot-unverified",
            88.0,
            "APPLY",
        ),
    )

    for (
        assessment_id,
        job_id,
        snapshot_id,
        score,
        verdict,
    ) in assessments:
        connection.execute(
            """
            INSERT INTO career_fit_assessments (
                assessment_id,
                job_id,
                snapshot_id,
                fit_score,
                verdict,
                hard_exclusion_codes_json,
                score_breakdown_json,
                explanation_json,
                assessed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_id,
                job_id,
                snapshot_id,
                score,
                verdict,
                json.dumps([]),
                json.dumps(
                    {
                        "role_alignment": score,
                    }
                ),
                json.dumps(
                    {
                        "summary":
                            f"{verdict} test explanation"
                    }
                ),
                "2026-08-22T13:00:00+00:00",
            ),
        )

    connection.execute(
        """
        INSERT INTO career_applications (
            application_id,
            job_id,
            state,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "application-1",
            "career-job-apply",
            "SHORTLISTED",
            "2026-08-22T14:00:00+00:00",
        ),
    )

    connection.commit()
    connection.close()


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "career-dashboard.db"
    _create_database(path)
    return path


def test_dashboard_returns_verified_apply_and_consider_only(
    database_path: Path,
) -> None:
    service = CareerDashboardService(
        database_path
    )

    result = service.list_jobs()

    assert result.total == 2

    assert [
        item.verdict
        for item in result.items
    ] == [
        "APPLY",
        "CONSIDER",
    ]

    assert {
        item.job_id
        for item in result.items
    } == {
        "career-job-apply",
        "career-job-consider",
    }


def test_apply_url_prefers_canonical_apply_url(
    database_path: Path,
) -> None:
    service = CareerDashboardService(
        database_path
    )

    result = service.list_jobs()

    apply_job = result.items[0]

    assert (
        apply_job.manual_apply_url
        == "https://example.com/job/apply/form"
    )


def test_job_url_is_manual_apply_fallback(
    database_path: Path,
) -> None:
    service = CareerDashboardService(
        database_path
    )

    result = service.list_jobs()

    consider_job = result.items[1]

    assert (
        consider_job.manual_apply_url
        == "https://example.com/job/consider"
    )


def test_summary_counts_read_only_dashboard_scope(
    database_path: Path,
) -> None:
    service = CareerDashboardService(
        database_path
    )

    summary = service.summary()

    assert summary.verified_active_jobs == 3
    assert summary.apply_jobs == 1
    assert summary.consider_jobs == 1
    assert summary.visible_jobs == 2
    assert summary.application_records == 1

    assert (
        summary.production_database_write_enabled
        is False
    )
    assert (
        summary.application_submission_enabled
        is False
    )
    assert summary.auto_apply_enabled is False


def test_invalid_limit_fails_closed(
    database_path: Path,
) -> None:
    service = CareerDashboardService(
        database_path
    )

    with pytest.raises(ValueError):
        service.list_jobs(
            limit=0
        )


def test_missing_database_fails_closed(
    tmp_path: Path,
) -> None:
    service = CareerDashboardService(
        tmp_path / "missing.db"
    )

    with pytest.raises(FileNotFoundError):
        service.list_jobs()


def test_read_only_connection_rejects_write(
    database_path: Path,
) -> None:
    service = CareerDashboardService(
        database_path
    )

    with service._connection() as connection:
        with pytest.raises(
            sqlite3.OperationalError
        ):
            connection.execute(
                """
                INSERT INTO career_applications (
                    application_id,
                    job_id,
                    state,
                    updated_at
                )
                VALUES (
                    'forbidden',
                    'career-job-apply',
                    'SHORTLISTED',
                    '2026-08-23T00:00:00+00:00'
                )
                """
            )


def test_dashboard_source_contains_no_write_queries() -> None:
    import career.dashboard as dashboard

    source = Path(
        dashboard.__file__
    ).read_text(
        encoding="utf-8"
    ).upper()

    for forbidden in (
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "CREATE TABLE",
        "DROP TABLE",
        "ALTER TABLE",
    ):
        assert forbidden not in source


def test_dashboard_has_no_truth_repository_import_side_effect() -> None:
    import career.dashboard as dashboard

    source = Path(
        dashboard.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "agents.truth_repository"
        not in source
    )
