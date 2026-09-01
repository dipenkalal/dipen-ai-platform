from __future__ import annotations

import argparse
import asyncio
import fcntl
import inspect
import json
import re
import sqlite3
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.truth_repository import AgentTruthRepository
from career.connectors.greenhouse import GreenhouseJobBoardConnector
from career.ingestion import CareerVerifiedJobDetail
from career.phase16_retrieval_adapter import CareerPhase16RetrievalAdapter
from career.production_pipeline import (
    CareerScoringProfile,
    run_production_canary,
)
from career.repository import CareerRepository
from career.retrieval import CareerRetrievalOrchestrator
from career.scoring import persist_scored_job, score_verified_job


DEFAULT_DB = Path(
    "/home/dipen/dap/data/agent-history/agent-truth.db"
)

DEFAULT_LOCK = Path(
    "/home/dipen/dap/run/career-automation.lock"
)

TARGET_TITLE_PATTERNS = (
    r"\bdevops\b",
    r"\bdevsecops\b",
    r"\bcloud\s+(?:support\s+)?engineer\b",
    r"\bcloud\s+analyst\b",
    r"\binfrastructure\s+(?:engineer|analyst)\b",
    r"\bsystems?\s+administrator\b",
    r"\bsysadmin\b",
    r"\btechnical\s+support\b",
    r"\bsupport\s+engineer\b",
    r"\bsupport\s+analyst\b",
    r"\bcustomer\s+support\s+engineer\b",
    r"\btechnical\s+solutions?\s+engineer\b",
    r"\bcloud\s+support\s+specialist\b",
    r"\bcloud\s+operations\s+(?:analyst|engineer)\b",
    r"\bit\s+support\s+specialist\b",
    r"\b(?:service|help)\s+desk\s+analyst\b",
    r"\bdesktop\s+support\s+technician\b",
    r"\bnoc\s+analyst\b",
    r"\b(?:cloud|azure|linux)\s+administrator\b",
    r"\b(?:junior\s+)?systems?\s+engineer\b",
)

LOCATION_HINTS = (
    "canada",
    "ontario",
    "toronto",
    "kitchener",
    "waterloo",
    "ottawa",
    "mississauga",
    "markham",
    "oakville",
    "burlington",
    "hamilton",
    "london",
    "windsor",
    "remote",
)


ONTARIO_CITY_CANONICAL = {
    "toronto": "Toronto",
    "kitchener": "Kitchener",
    "waterloo": "Waterloo",
    "ottawa": "Ottawa",
    "mississauga": "Mississauga",
    "markham": "Markham",
    "oakville": "Oakville",
    "burlington": "Burlington",
    "hamilton": "Hamilton",
    "london": "London",
    "windsor": "Windsor",
    "guelph": "Guelph",
    "cambridge": "Cambridge",
    "brampton": "Brampton",
    "vaughan": "Vaughan",
    "richmond hill": "Richmond Hill",
}

FOREIGN_LOCATION_TOKENS = (
    "united states",
    "usa",
    "u.s.",
    "united kingdom",
    "uk",
    "england",
    "india",
    "germany",
    "france",
    "australia",
    "mexico",
)


@dataclass(frozen=True)
class BoardSpec:
    board_token: str
    employer_name: str
    enabled: bool = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def log(event: str, *parts: object) -> None:
    payload = "|".join(
        str(part).replace("\n", " ")
        for part in parts
    )

    if payload:
        print(f"{event}|{payload}", flush=True)
    else:
        print(event, flush=True)


def load_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise ValueError("configuration root must be an object")

    boards = raw.get("boards")

    if not isinstance(boards, list) or not boards:
        raise ValueError("configuration requires boards")

    return raw


def board_specs(config: dict[str, Any]) -> tuple[BoardSpec, ...]:
    result: list[BoardSpec] = []

    for raw in config["boards"]:
        if not isinstance(raw, dict):
            raise ValueError("board entry must be an object")

        spec = BoardSpec(
            board_token=str(raw["board_token"]).strip(),
            employer_name=str(raw["employer_name"]).strip(),
            enabled=bool(raw.get("enabled", True)),
        )

        if not spec.board_token or not spec.employer_name:
            raise ValueError("board fields may not be empty")

        result.append(spec)

    return tuple(result)


def candidate_role_relevant(title: str) -> bool:
    return any(
        re.search(pattern, title, flags=re.I)
        for pattern in TARGET_TITLE_PATTERNS
    )


def _ontario_city_from_text(
    value: str | None,
) -> str | None:
    if not value:
        return None

    lowered = value.casefold()

    for token, canonical in (
        ONTARIO_CITY_CANONICAL.items()
    ):
        if token in lowered:
            return canonical

    return None


def candidate_location_relevant(
    location: str | None,
) -> bool:
    if not location:
        return False

    lowered = location.casefold().strip()

    if any(
        token in lowered
        for token in FOREIGN_LOCATION_TOKENS
    ):
        return False

    if (
        "ontario" in lowered
        or _ontario_city_from_text(location)
        is not None
    ):
        return True

    # Generic Canada / Remote entries are permitted
    # only to reach canonical evidence verification.
    # detail_geography_allowed() makes the final
    # evidence-based decision.
    if lowered in {
        "canada",
        "remote",
        "remote canada",
        "remote (canada)",
        "canada - remote",
    }:
        return True

    if (
        "remote" in lowered
        and "canada" in lowered
    ):
        return True

    return False


def db_read(path: Path, sql: str, args: tuple = ()):
    con = sqlite3.connect(
        f"file:{path}?mode=ro",
        uri=True,
    )

    con.row_factory = sqlite3.Row

    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def existing_posting(
    path: Path,
    *,
    employer_name: str,
    requisition_id: str,
):
    rows = db_read(
        path,
        """
        SELECT *
        FROM career_job_postings
        WHERE employer_name=?
          AND requisition_id=?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (employer_name, requisition_id),
    )

    return dict(rows[0]) if rows else None


def latest_evidence_link(path: Path, job_id: str):
    rows = db_read(
        path,
        """
        SELECT *
        FROM career_job_evidence_links
        WHERE job_id=?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (job_id,),
    )

    return dict(rows[0]) if rows else None


def assessment_exists(
    path: Path,
    *,
    job_id: str,
    snapshot_id: str,
    profile_version: str,
) -> bool:
    rows = db_read(
        path,
        """
        SELECT COUNT(*) AS n
        FROM career_fit_assessments
        WHERE job_id=?
          AND snapshot_id=?
          AND profile_version=?
        """,
        (job_id, snapshot_id, profile_version),
    )

    return int(rows[0]["n"]) > 0


def invoke_getter(
    repository: CareerRepository,
    method_name: str,
    known: dict[str, Any],
):
    method = getattr(repository, method_name)
    sig = inspect.signature(method)

    kwargs: dict[str, Any] = {}

    for name, parameter in sig.parameters.items():
        if name in known:
            kwargs[name] = known[name]
        elif parameter.default is inspect.Parameter.empty:
            raise RuntimeError(
                f"{method_name} requires unresolved field {name}"
            )

    value = method(**kwargs)

    if value is None:
        raise RuntimeError(
            f"{method_name} returned no object"
        )

    return value


def profile_from_config(
    config: dict[str, Any],
) -> CareerScoringProfile:
    raw = config["profile"]

    return CareerScoringProfile(
        version=str(raw["version"]),
        role_families=tuple(raw["role_families"]),
        skills=tuple(raw["skills"]),
        minimum_experience_years=int(
            raw.get("minimum_experience_years", 0)
        ),
        maximum_experience_years=int(
            raw.get("maximum_experience_years", 3)
        ),
        primary_region=str(
            raw.get("primary_region", "Ontario")
        ),
        remote_country=str(
            raw.get("remote_country", "Canada")
        ),
    )


def career_repository(path: Path) -> CareerRepository:
    return CareerRepository(
        AgentTruthRepository(database_path=path),
        initialize=False,
    )


def score_persisted_job(
    *,
    database: Path,
    repository: CareerRepository,
    posting: dict[str, Any],
    profile: CareerScoringProfile,
):
    job_id = str(posting["job_id"])
    snapshot_id = str(posting["current_snapshot_id"])

    if assessment_exists(
        database,
        job_id=job_id,
        snapshot_id=snapshot_id,
        profile_version=profile.version,
    ):
        return None

    link = latest_evidence_link(database, job_id)

    if link is None:
        raise RuntimeError(
            f"missing evidence link for {job_id}"
        )

    known = dict(posting)
    known.update(link)
    known["job_id"] = job_id
    known["snapshot_id"] = snapshot_id

    job = invoke_getter(
        repository,
        "get_job",
        known,
    )

    snapshot = invoke_getter(
        repository,
        "get_snapshot",
        known,
    )

    evidence_link = invoke_getter(
        repository,
        "get_evidence_link",
        known,
    )

    scored = score_verified_job(
        job=job,
        snapshot=snapshot,
        evidence_link=evidence_link,
        profile=profile,
    )

    persist_scored_job(repository, scored)

    return scored


async def await_if_needed(value):
    if inspect.isawaitable(value):
        return await value

    return value


def salary_from_text(text: str) -> str | None:
    match = re.search(
        r"\$[\d,]+(?:\.\d+)?"
        r"\s*(?:-|–|—|to)\s*"
        r"\$[\d,]+(?:\.\d+)?"
        r"(?:\s*(?:CAD|CA\$))?",
        text,
        flags=re.I,
    )

    return match.group(0) if match else None


def employment_type_from_text(
    text: str,
) -> str | None:
    lower = text.lower()

    if (
        "full-time" in lower
        or "full time" in lower
    ):
        return "Full-time"

    if (
        "part-time" in lower
        or "part time" in lower
    ):
        return "Part-time"

    if "contract" in lower:
        return "Contract"

    return None


def work_mode_from_text(
    text: str,
    location: str | None,
) -> str:
    lower = (
        text
        + " "
        + (location or "")
    ).lower()

    if "hybrid" in lower:
        return "HYBRID"

    if "remote" in lower:
        return "REMOTE"

    if location:
        return "ONSITE"

    return "UNKNOWN"


def extract_minimum_experience_years(
    text: str,
) -> int | None:
    """
    Conservative extraction from verified canonical
    job-page evidence.

    Only phrases explicitly tied to 'experience'
    contribute to the Career requirements projection.
    """

    patterns = (
        (
            r"\b(?:minimum(?:\s+of)?|at\s+least)"
            r"\s+(\d{1,2})\+?\s+years?"
            r"(?:\s+of)?"
            r"(?:\s+[A-Za-z][A-Za-z0-9/+.-]*){0,7}"
            r"\s+experience\b"
        ),
        (
            r"\b(\d{1,2})"
            r"\s*(?:-|–|—|to)\s*\d{1,2}"
            r"\s+years?"
            r"(?:\s+of)?"
            r"(?:\s+[A-Za-z][A-Za-z0-9/+.-]*){0,7}"
            r"\s+experience\b"
        ),
        (
            r"\b(\d{1,2})\+?"
            r"\s+years?"
            r"(?:\s+of)?"
            r"(?:\s+[A-Za-z][A-Za-z0-9/+.-]*){0,6}"
            r"\s+experience\b"
        ),
    )

    values: list[int] = []

    for pattern in patterns:
        for match in re.finditer(
            pattern,
            text,
            flags=re.I,
        ):
            years = int(match.group(1))

            if 0 <= years <= 15:
                values.append(years)

    if not values:
        return None

    # Conservative: if several explicit minimum
    # requirements exist, use the largest.
    return max(values)


def normalize_verified_location(
    location: str | None,
    *,
    work_mode: str,
) -> str | None:
    if not location:
        return None

    lowered = location.casefold().strip()

    city = _ontario_city_from_text(
        location
    )

    if city is not None:
        return (
            f"{city}, Ontario, Canada"
        )

    if "ontario" in lowered:
        return location.strip()

    if (
        work_mode == "REMOTE"
        and (
            lowered == "canada"
            or (
                "remote" in lowered
                and "canada" in lowered
            )
        )
    ):
        return "Remote (Canada)"

    return location.strip()


def detail_geography_allowed(
    *,
    normalized_text: str,
    location_hint: str | None,
    work_mode: str,
) -> bool:
    location = (
        location_hint or ""
    ).casefold().strip()

    body = normalized_text.casefold()

    if any(
        token in location
        for token in FOREIGN_LOCATION_TOKENS
    ):
        return False

    if (
        "ontario" in location
        or _ontario_city_from_text(
            location_hint
        )
        is not None
    ):
        return True

    if work_mode == "REMOTE":
        if "canada" in location:
            return True

        if location == "remote":
            return "canada" in body

        if location == "canada":
            return True

    return False


async def build_verified_detail(
    *,
    adapter: CareerPhase16RetrievalAdapter,
    candidate,
    board_token: str,
) -> CareerVerifiedJobDetail | None:
    page = await await_if_needed(
        adapter.retrieve_public_url(
            objective=(
                "Verify a DAP Career candidate from its "
                "canonical public Greenhouse posting."
            ),
            url=candidate.detail_url,
        )
    )

    evidence = page.retrieval_evidence
    content = page.content_evidence

    if (
        evidence.final_url
        != candidate.detail_url
    ):
        raise RuntimeError(
            "canonical job evidence URL mismatch"
        )

    text = getattr(
        content,
        "normalized_text",
        None,
    )

    sha = getattr(
        content,
        "normalized_text_sha256",
        None,
    )

    if (
        not isinstance(text, str)
        or not text.strip()
        or not sha
    ):
        raise RuntimeError(
            "canonical job evidence content missing"
        )

    normalized = text.strip()

    if (
        candidate.title_hint.lower()
        not in normalized.lower()
    ):
        raise RuntimeError(
            "canonical page does not contain "
            "candidate title"
        )

    work_mode = work_mode_from_text(
        normalized,
        candidate.location_hint,
    )

    if not detail_geography_allowed(
        normalized_text=normalized,
        location_hint=candidate.location_hint,
        work_mode=work_mode,
    ):
        return None

    location = normalize_verified_location(
        candidate.location_hint,
        work_mode=work_mode,
    )

    experience_years = (
        extract_minimum_experience_years(
            normalized
        )
    )

    requirements: dict[str, Any] = {
        "provider": "greenhouse",
        "board": board_token,
        "source_job_id": str(
            candidate.source_job_id
        ),
    }

    if experience_years is not None:
        requirements[
            "minimum_experience_years"
        ] = experience_years

    return CareerVerifiedJobDetail(
        research_evidence_id=(
            evidence.evidence_id
        ),
        canonical_job_url=(
            candidate.detail_url
        ),
        canonical_apply_url=(
            candidate.apply_url_hint
            or candidate.detail_url
        ),
        title=candidate.title_hint,
        employer_name=(
            candidate.employer_name
        ),
        description_text=normalized,
        normalized_text_sha256=sha,
        observed_at=evidence.observed_at,
        location_text=location,
        work_mode=work_mode,
        employment_type=(
            employment_type_from_text(
                normalized
            )
        ),
        posted_at=None,
        closing_at=None,
        salary_text=salary_from_text(
            normalized
        ),
        requirements=requirements,
    )


def dashboard_counts(path: Path) -> dict[str, int]:
    rows = db_read(
        path,
        """
        WITH latest_fit AS (
            SELECT f.*
            FROM career_fit_assessments AS f
            JOIN (
                SELECT job_id, MAX(rowid) AS max_rowid
                FROM career_fit_assessments
                GROUP BY job_id
            ) AS x
              ON x.max_rowid = f.rowid
        )
        SELECT
            SUM(
                CASE
                    WHEN j.verification_state='VERIFIED'
                     AND j.lifecycle_state='ACTIVE'
                    THEN 1 ELSE 0
                END
            ) AS verified_active,
            SUM(
                CASE WHEN f.verdict='APPLY'
                THEN 1 ELSE 0 END
            ) AS apply_count,
            SUM(
                CASE WHEN f.verdict='CONSIDER'
                THEN 1 ELSE 0 END
            ) AS consider_count,
            SUM(
                CASE WHEN f.verdict IN ('APPLY','CONSIDER')
                THEN 1 ELSE 0 END
            ) AS visible_count
        FROM career_job_postings AS j
        LEFT JOIN latest_fit AS f
          ON f.job_id=j.job_id
        """,
    )

    row = dict(rows[0])

    return {
        key: int(value or 0)
        for key, value in row.items()
    }


async def run(args) -> int:
    config = load_config(args.config)
    specs = tuple(
        spec
        for spec in board_specs(config)
        if spec.enabled
    )

    profile = profile_from_config(config)

    if args.check_config:
        log("CONFIG", "PASS")
        log("BOARDS", len(specs))
        log("PROFILE_VERSION", profile.version)

        for spec in specs:
            log(
                "BOARD",
                spec.board_token,
                spec.employer_name,
            )

        return 0

    DEFAULT_LOCK.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DEFAULT_LOCK.open("w") as lock_handle:
        try:
            fcntl.flock(
                lock_handle.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            log("RUN", "SKIP_ALREADY_RUNNING")
            return 0

        repository = career_repository(args.database)
        adapter = CareerPhase16RetrievalAdapter()
        orchestrator = CareerRetrievalOrchestrator(adapter)

        started = utc_now()

        log("RUN_START", started.isoformat())
        log("DATABASE", args.database)
        log("PROFILE_VERSION", profile.version)
        log("BOARD_COUNT", len(specs))
        log("MAX_NEW", args.max_new)

        counters = {
            "boards_ok": 0,
            "boards_failed": 0,
            "candidates_seen": 0,
            "candidates_prefiltered": 0,
            "existing": 0,
            "verified_new": 0,
            "scored_new": 0,
            "apply": 0,
            "consider": 0,
            "skip": 0,
            "errors": 0,
        }

        # Ensure every existing VERIFIED/ACTIVE job has the
        # current automation scoring profile.
        existing_rows = db_read(
            args.database,
            """
            SELECT *
            FROM career_job_postings
            WHERE verification_state='VERIFIED'
              AND lifecycle_state='ACTIVE'
            ORDER BY rowid
            """,
        )

        for raw in existing_rows:
            posting = dict(raw)

            try:
                scored = score_persisted_job(
                    database=args.database,
                    repository=repository,
                    posting=posting,
                    profile=profile,
                )

                if scored is not None:
                    verdict = scored.assessment.verdict

                    counters["scored_new"] += 1
                    counters[verdict.lower()] += 1

                    log(
                        "RESCORE",
                        posting["job_id"],
                        scored.assessment.fit_score,
                        verdict,
                    )
            except Exception as exc:
                counters["errors"] += 1
                log(
                    "RESCORE_ERROR",
                    posting.get("job_id"),
                    type(exc).__name__,
                    str(exc),
                )

        new_budget = args.max_new

        for spec in specs:
            if new_budget <= 0:
                break

            log(
                "BOARD_START",
                spec.board_token,
                spec.employer_name,
            )

            try:
                connector = GreenhouseJobBoardConnector(
                    board_token=spec.board_token,
                    employer_name=spec.employer_name,
                )

                result = await await_if_needed(
                    orchestrator.retrieve_candidates(
                        connector=connector,
                        objective=(
                            "Discover current public Greenhouse "
                            "jobs for DAP Career automation."
                        ),
                        source_url=connector.jobs_url,
                    )
                )

                counters["boards_ok"] += 1
                counters["candidates_seen"] += (
                    result.candidate_count
                )

                log(
                    "BOARD_DISCOVERED",
                    spec.board_token,
                    result.candidate_count,
                )

            except Exception as exc:
                counters["boards_failed"] += 1
                counters["errors"] += 1

                log(
                    "BOARD_ERROR",
                    spec.board_token,
                    type(exc).__name__,
                    str(exc),
                )

                continue

            for candidate in result.candidates:
                if new_budget <= 0:
                    break

                if not candidate_role_relevant(
                    candidate.title_hint
                ):
                    continue

                if not candidate_location_relevant(
                    candidate.location_hint
                ):
                    continue

                counters["candidates_prefiltered"] += 1

                posting = existing_posting(
                    args.database,
                    employer_name=candidate.employer_name,
                    requisition_id=str(
                        candidate.source_job_id
                    ),
                )

                if posting is not None:
                    counters["existing"] += 1

                    try:
                        detail = (
                            await build_verified_detail(
                                adapter=adapter,
                                candidate=candidate,
                                board_token=(
                                    spec.board_token
                                ),
                            )
                        )

                        if detail is None:
                            log(
                                "EXISTING_GEOGRAPHY_SKIP",
                                spec.board_token,
                                candidate.source_job_id,
                                candidate.title_hint,
                                candidate.location_hint,
                            )
                            continue

                        run_production_canary(
                            repository=repository,
                            provider_kind="greenhouse",
                            provider_target={
                                "board":
                                    spec.board_token,
                            },
                            discover=(
                                lambda route,
                                c=candidate: (c,)
                            ),
                            verify=(
                                lambda item,
                                route,
                                d=detail: d
                            ),
                            profile=profile,
                            shortlist_limit=1,
                        )

                        posting = existing_posting(
                            args.database,
                            employer_name=(
                                candidate.employer_name
                            ),
                            requisition_id=str(
                                candidate.source_job_id
                            ),
                        )

                        if posting is None:
                            raise RuntimeError(
                                "existing Career posting "
                                "disappeared after refresh"
                            )

                        scored = score_persisted_job(
                            database=args.database,
                            repository=repository,
                            posting=posting,
                            profile=profile,
                        )

                        if scored is not None:
                            verdict = (
                                scored.assessment.verdict
                            )

                            counters[
                                "scored_new"
                            ] += 1

                            counters[
                                verdict.lower()
                            ] += 1

                            log(
                                "REFRESH_SCORE",
                                posting["job_id"],
                                scored.assessment.fit_score,
                                verdict,
                            )

                    except Exception as exc:
                        counters["errors"] += 1

                        log(
                            "EXISTING_REFRESH_ERROR",
                            candidate.source_job_id,
                            type(exc).__name__,
                            str(exc),
                        )

                    continue

                try:
                    detail = await build_verified_detail(
                        adapter=adapter,
                        candidate=candidate,
                        board_token=spec.board_token,
                    )

                    if detail is None:
                        log(
                            "GEOGRAPHY_SKIP",
                            spec.board_token,
                            candidate.source_job_id,
                            candidate.title_hint,
                            candidate.location_hint,
                        )
                        continue

                    run_production_canary(
                        repository=repository,
                        provider_kind="greenhouse",
                        provider_target={
                            "board": spec.board_token,
                        },
                        discover=lambda route, c=candidate: (c,),
                        verify=lambda item, route, d=detail: d,
                        profile=profile,
                        shortlist_limit=1,
                    )

                    posting = existing_posting(
                        args.database,
                        employer_name=candidate.employer_name,
                        requisition_id=str(
                            candidate.source_job_id
                        ),
                    )

                    if posting is None:
                        raise RuntimeError(
                            "Career ingestion returned without "
                            "a persisted posting"
                        )

                    counters["verified_new"] += 1
                    new_budget -= 1

                    scored = score_persisted_job(
                        database=args.database,
                        repository=repository,
                        posting=posting,
                        profile=profile,
                    )

                    if scored is None:
                        raise RuntimeError(
                            "new posting was not scored"
                        )

                    assessment = scored.assessment

                    counters["scored_new"] += 1
                    counters[
                        assessment.verdict.lower()
                    ] += 1

                    log(
                        "NEW_JOB",
                        assessment.verdict,
                        assessment.fit_score,
                        candidate.employer_name,
                        candidate.title_hint,
                        candidate.location_hint,
                        candidate.detail_url,
                    )

                except Exception as exc:
                    counters["errors"] += 1

                    log(
                        "CANDIDATE_ERROR",
                        spec.board_token,
                        candidate.source_job_id,
                        candidate.title_hint,
                        type(exc).__name__,
                        str(exc),
                    )

                    traceback.print_exc(
                        limit=2,
                        file=sys.stdout,
                    )

        dashboard = dashboard_counts(args.database)

        finished = utc_now()

        log("RUN_FINISH", finished.isoformat())
        log(
            "DURATION_SECONDS",
            round(
                (finished - started).total_seconds(),
                3,
            ),
        )

        for key, value in counters.items():
            log(
                "COUNT",
                key,
                value,
            )

        for key, value in dashboard.items():
            log(
                "DASHBOARD",
                key,
                value,
            )

        log("APPLICATION_SUBMISSION", "NO")
        log("AUTO_APPLY", "NO")
        log("TELEGRAM_SEND", "NO")
        log("NETWORK_OWNER", "PHASE16")

        if counters["boards_ok"] == 0:
            log("CAREER_AUTOMATION", "FAILED_NO_BOARDS")
            return 2

        log("CAREER_AUTOMATION", "PASS")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DB,
    )

    parser.add_argument(
        "--max-new",
        type=int,
        default=60,
    )

    parser.add_argument(
        "--check-config",
        action="store_true",
    )

    args = parser.parse_args()

    if args.max_new < 1 or args.max_new > 200:
        raise SystemExit(
            "--max-new must be between 1 and 200"
        )

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
