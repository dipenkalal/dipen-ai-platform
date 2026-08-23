from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_TRUTH_DATABASE_PATH = (
    Path.home()
    / "dap"
    / "data"
    / "agent-history"
    / "agent-truth.db"
)


def get_truth_database_path() -> Path:
    configured_path = os.getenv(
        "DAP_AGENT_TRUTH_DB"
    )

    if configured_path:
        return Path(
            configured_path
        ).expanduser()

    return DEFAULT_TRUTH_DATABASE_PATH


class CareerDashboardJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str
    snapshot_id: str
    assessment_id: str

    title: str
    employer_name: str

    location_text: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    salary_text: str | None = None

    posted_at: str | None = None
    closing_at: str | None = None
    observed_at: str
    last_seen_at: str

    freshness_state: str
    verification_state: str
    lifecycle_state: str

    fit_score: float = Field(ge=0, le=100)
    verdict: str

    hard_exclusion_codes: list[str]
    score_breakdown: dict[str, Any]
    explanation: Any

    canonical_job_url: str
    canonical_apply_url: str | None = None
    manual_apply_url: str

    application_id: str | None = None
    application_state: str | None = None


class CareerDashboardListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: int
    items: tuple[CareerDashboardJob, ...]


class CareerDashboardSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    verified_active_jobs: int
    apply_jobs: int
    consider_jobs: int
    visible_jobs: int
    application_records: int

    production_database_write_enabled: bool = False
    application_submission_enabled: bool = False
    auto_apply_enabled: bool = False


class CareerDashboardService:
    def __init__(
        self,
        database_path: Path | None = None,
    ) -> None:
        self.database_path = (
            database_path
            if database_path is not None
            else get_truth_database_path()
        )

    @contextmanager
    def _connection(
        self,
    ) -> Iterator[sqlite3.Connection]:
        resolved = self.database_path.expanduser().resolve()

        if not resolved.exists():
            raise FileNotFoundError(
                f"Career truth database does not exist: {resolved}"
            )

        connection = sqlite3.connect(
            f"file:{resolved}?mode=ro",
            uri=True,
            timeout=10.0,
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute(
                "PRAGMA query_only = ON"
            )
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _decode_json(
        value: str,
        *,
        expected: type,
        label: str,
    ) -> Any:
        decoded = json.loads(value)

        if not isinstance(decoded, expected):
            raise ValueError(
                f"{label} has unexpected JSON shape"
            )

        return decoded

    def list_jobs(
        self,
        *,
        limit: int = 100,
    ) -> CareerDashboardListResponse:
        if limit < 1 or limit > 500:
            raise ValueError(
                "Career dashboard limit must be 1 through 500"
            )

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    j.job_id,
                    j.canonical_job_url,
                    j.canonical_apply_url,
                    j.verification_state,
                    j.lifecycle_state,
                    j.last_seen_at,

                    s.snapshot_id,
                    s.title,
                    s.employer_name,
                    s.location_text,
                    s.work_mode,
                    s.employment_type,
                    s.salary_text,
                    s.posted_at,
                    s.closing_at,
                    s.freshness_state,
                    s.observed_at,

                    f.assessment_id,
                    f.fit_score,
                    f.verdict,
                    f.hard_exclusion_codes_json,
                    f.score_breakdown_json,
                    f.explanation_json,

                    a.application_id,
                    a.state AS application_state

                FROM career_job_postings AS j

                JOIN career_job_snapshots AS s
                  ON s.snapshot_id = j.current_snapshot_id

                JOIN career_fit_assessments AS f
                  ON f.assessment_id = (
                      SELECT f2.assessment_id
                      FROM career_fit_assessments AS f2
                      WHERE f2.snapshot_id = s.snapshot_id
                      ORDER BY
                          f2.assessed_at DESC,
                          f2.assessment_id DESC
                      LIMIT 1
                  )

                LEFT JOIN career_applications AS a
                  ON a.application_id = (
                      SELECT a2.application_id
                      FROM career_applications AS a2
                      WHERE a2.job_id = j.job_id
                      ORDER BY
                          a2.updated_at DESC,
                          a2.application_id DESC
                      LIMIT 1
                  )

                WHERE j.verification_state = 'VERIFIED'
                  AND j.lifecycle_state = 'ACTIVE'
                  AND f.verdict IN ('APPLY', 'CONSIDER')

                ORDER BY
                    CASE f.verdict
                        WHEN 'APPLY' THEN 0
                        ELSE 1
                    END,
                    f.fit_score DESC,
                    s.posted_at DESC,
                    j.job_id ASC

                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        items: list[CareerDashboardJob] = []

        for row in rows:
            apply_url = (
                row["canonical_apply_url"]
                or row["canonical_job_url"]
            )

            items.append(
                CareerDashboardJob(
                    job_id=row["job_id"],
                    snapshot_id=row["snapshot_id"],
                    assessment_id=row["assessment_id"],
                    title=row["title"],
                    employer_name=row["employer_name"],
                    location_text=row["location_text"],
                    work_mode=row["work_mode"],
                    employment_type=row["employment_type"],
                    salary_text=row["salary_text"],
                    posted_at=row["posted_at"],
                    closing_at=row["closing_at"],
                    observed_at=row["observed_at"],
                    last_seen_at=row["last_seen_at"],
                    freshness_state=row["freshness_state"],
                    verification_state=row["verification_state"],
                    lifecycle_state=row["lifecycle_state"],
                    fit_score=float(row["fit_score"]),
                    verdict=row["verdict"],
                    hard_exclusion_codes=self._decode_json(
                        row["hard_exclusion_codes_json"],
                        expected=list,
                        label="hard exclusion codes",
                    ),
                    score_breakdown=self._decode_json(
                        row["score_breakdown_json"],
                        expected=dict,
                        label="score breakdown",
                    ),
                    explanation=json.loads(
                        row["explanation_json"]
                    ),
                    canonical_job_url=row[
                        "canonical_job_url"
                    ],
                    canonical_apply_url=row[
                        "canonical_apply_url"
                    ],
                    manual_apply_url=apply_url,
                    application_id=row[
                        "application_id"
                    ],
                    application_state=row[
                        "application_state"
                    ],
                )
            )

        return CareerDashboardListResponse(
            total=len(items),
            items=tuple(items),
        )

    def summary(
        self,
    ) -> CareerDashboardSummary:
        with self._connection() as connection:
            verified_row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM career_job_postings
                WHERE verification_state = 'VERIFIED'
                  AND lifecycle_state = 'ACTIVE'
                  AND current_snapshot_id IS NOT NULL
                """
            ).fetchone()

            verdict_rows = connection.execute(
                """
                SELECT
                    f.verdict,
                    COUNT(*) AS count

                FROM career_job_postings AS j

                JOIN career_job_snapshots AS s
                  ON s.snapshot_id = j.current_snapshot_id

                JOIN career_fit_assessments AS f
                  ON f.assessment_id = (
                      SELECT f2.assessment_id
                      FROM career_fit_assessments AS f2
                      WHERE f2.snapshot_id = s.snapshot_id
                      ORDER BY
                          f2.assessed_at DESC,
                          f2.assessment_id DESC
                      LIMIT 1
                  )

                WHERE j.verification_state = 'VERIFIED'
                  AND j.lifecycle_state = 'ACTIVE'
                  AND f.verdict IN ('APPLY', 'CONSIDER')

                GROUP BY f.verdict
                """
            ).fetchall()

            application_row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM career_applications
                """
            ).fetchone()

        verdict_counts = {
            str(row["verdict"]): int(row["count"])
            for row in verdict_rows
        }

        apply_jobs = verdict_counts.get(
            "APPLY",
            0,
        )
        consider_jobs = verdict_counts.get(
            "CONSIDER",
            0,
        )

        return CareerDashboardSummary(
            verified_active_jobs=int(
                verified_row["count"]
                if verified_row is not None
                else 0
            ),
            apply_jobs=apply_jobs,
            consider_jobs=consider_jobs,
            visible_jobs=(
                apply_jobs
                + consider_jobs
            ),
            application_records=int(
                application_row["count"]
                if application_row is not None
                else 0
            ),
        )


career_dashboard_service = CareerDashboardService()
