from __future__ import annotations

import argparse
import asyncio
import fcntl
import inspect
import json
import re
import sys
import traceback

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from career import automation_runner as core

from career.connectors.ashby import (
    AshbyJobBoardConnector,
)

from career.dashboard import (
    CareerDashboardService,
)

from career.ingestion import (
    CareerVerifiedJobDetail,
)

from career.phase16_retrieval_adapter import (
    CareerPhase16RetrievalAdapter,
)

from career.production_pipeline import (
    run_production_canary,
)

from career.retrieval import (
    CareerRetrievalOrchestrator,
)


DEFAULT_DB = Path(
    "/home/dipen/dap/data/"
    "agent-history/agent-truth.db"
)

DEFAULT_LOCK = Path(
    "/home/dipen/dap/run/"
    "career-ashby.lock"
)


@dataclass(frozen=True)
class AshbyBoardSpec:
    job_board_name: str
    employer_name: str
    enabled: bool = True


def log(
    event: str,
    *parts: object,
) -> None:

    payload = "|".join(
        str(part).replace(
            "\n",
            " ",
        )
        for part in parts
    )

    if payload:
        print(
            f"{event}|{payload}",
            flush=True,
        )
    else:
        print(
            event,
            flush=True,
        )


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def load_boards(
    path: Path,
) -> tuple[AshbyBoardSpec, ...]:

    raw = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(raw, dict):
        raise ValueError(
            "Ashby config root "
            "must be object"
        )

    rows = raw.get("boards")

    if (
        not isinstance(rows, list)
        or not rows
    ):
        raise ValueError(
            "Ashby config requires boards"
        )

    result: list[
        AshbyBoardSpec
    ] = []

    for raw_spec in rows:

        if not isinstance(
            raw_spec,
            dict,
        ):
            raise ValueError(
                "Ashby board entry "
                "must be object"
            )

        spec = AshbyBoardSpec(
            job_board_name=str(
                raw_spec[
                    "job_board_name"
                ]
            ).strip(),
            employer_name=str(
                raw_spec[
                    "employer_name"
                ]
            ).strip(),
            enabled=bool(
                raw_spec.get(
                    "enabled",
                    True,
                )
            ),
        )

        if (
            not spec.job_board_name
            or not spec.employer_name
        ):
            raise ValueError(
                "Ashby board fields "
                "may not be empty"
            )

        if spec.enabled:
            result.append(spec)

    return tuple(result)


def normalized_phrase(
    value: str,
) -> str:

    return " ".join(
        re.sub(
            r"[^a-z0-9]+",
            " ",
            value.casefold(),
        ).split()
    )


def ashby_location_relevant(
    location: str | None,
) -> bool:

    if not location:
        return False

    if core.candidate_location_relevant(
        location
    ):
        return True

    lowered = location.casefold()

    foreign = (
        "united states",
        "usa",
        "u.s.",
        "united kingdom",
        "england",
        "india",
        "germany",
        "france",
        "australia",
        "mexico",
    )

    if any(
        token in lowered
        for token in foreign
    ):
        # Mixed-country locations can still contain
        # Ontario/Canada. Admit only if Canada/Ontario
        # is also explicit.
        if (
            "canada" not in lowered
            and "ontario" not in lowered
        ):
            return False

    if "ontario" in lowered:
        return True

    if any(
        city in lowered
        for city in (
            "toronto",
            "ottawa",
            "mississauga",
            "markham",
            "waterloo",
            "kitchener",
            "hamilton",
            "windsor",
            "london",
            "oakville",
            "burlington",
            "guelph",
            "cambridge",
            "brampton",
        )
    ):
        return True

    if (
        "remote" in lowered
        and "canada" in lowered
    ):
        return True

    if lowered.strip() in {
        "canada",
        "remote canada",
        "remote - canada",
        "canada - remote",
    }:
        return True

    return False


def canonical_ashby_location(
    location: str | None,
    *,
    work_mode: str,
) -> str | None:

    if not location:
        return None

    lowered = location.casefold()

    if "ontario" in lowered:
        return location.strip()

    city = core._ontario_city_from_text(
        location
    )

    if city is not None:
        return (
            f"{city}, Ontario, Canada"
        )

    if (
        work_mode == "REMOTE"
        and "canada" in lowered
    ):
        return "Remote (Canada)"

    return location.strip()


async def await_if_needed(
    value,
):
    if inspect.isawaitable(value):
        return await value

    return value


async def build_verified_detail(
    *,
    adapter: CareerPhase16RetrievalAdapter,
    candidate,
    job_board_name: str,
) -> CareerVerifiedJobDetail | None:

    page = await await_if_needed(
        adapter.retrieve_public_url(
            objective=(
                "Verify a DAP Career "
                "candidate from its "
                "canonical public Ashby "
                "posting."
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
            "Ashby canonical evidence "
            "URL mismatch"
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
            "Ashby canonical job "
            "content missing"
        )

    normalized = text.strip()

    title_key = normalized_phrase(
        candidate.title_hint
    )

    body_key = normalized_phrase(
        normalized
    )

    if title_key not in body_key:
        raise RuntimeError(
            "Ashby canonical page does "
            "not contain candidate title"
        )

    work_mode = (
        core.work_mode_from_text(
            normalized,
            candidate.location_hint,
        )
    )

    location = (
        canonical_ashby_location(
            candidate.location_hint,
            work_mode=work_mode,
        )
    )

    if not core.detail_geography_allowed(
        normalized_text=normalized,
        location_hint=location,
        work_mode=work_mode,
    ):
        return None

    experience = (
        core.extract_minimum_experience_years(
            normalized
        )
    )

    requirements: dict[
        str,
        Any,
    ] = {
        "provider": "ashby",
        "job_board_name":
            job_board_name,
        "source_job_id":
            str(
                candidate.source_job_id
            ),
    }

    if experience is not None:
        requirements[
            "minimum_experience_years"
        ] = experience

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
            core.employment_type_from_text(
                normalized
            )
        ),
        posted_at=None,
        closing_at=None,
        salary_text=(
            core.salary_from_text(
                normalized
            )
        ),
        requirements=requirements,
    )


def count_ashby_sources(
    database: Path,
) -> int:

    rows = core.db_read(
        database,
        """
        SELECT COUNT(*) AS n
        FROM career_sources
        WHERE connector_kind='ashby'
        """,
    )

    return int(
        rows[0]["n"]
    )


async def run(args) -> int:

    boards = load_boards(
        args.config
    )

    profile_config = (
        core.load_config(
            args.profile_config
        )
    )

    profile = (
        core.profile_from_config(
            profile_config
        )
    )

    if args.check_config:

        log(
            "ASHBY_CONFIG",
            "PASS",
        )

        log(
            "BOARDS",
            len(boards),
        )

        log(
            "PROFILE_VERSION",
            profile.version,
        )

        for board in boards:
            log(
                "BOARD",
                board.job_board_name,
                board.employer_name,
            )

        return 0

    DEFAULT_LOCK.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DEFAULT_LOCK.open(
        "w"
    ) as lock_handle:

        try:
            fcntl.flock(
                lock_handle.fileno(),
                fcntl.LOCK_EX
                | fcntl.LOCK_NB,
            )

        except BlockingIOError:
            log(
                "ASHBY_RUN",
                "SKIP_ALREADY_RUNNING",
            )
            return 0

        repository = (
            core.career_repository(
                args.database
            )
        )

        adapter = (
            CareerPhase16RetrievalAdapter()
        )

        orchestrator = (
            CareerRetrievalOrchestrator(
                adapter
            )
        )

        started = utc_now()

        sources_before = (
            count_ashby_sources(
                args.database
            )
        )

        counters = {
            "boards_ok": 0,
            "boards_failed": 0,
            "candidates_seen": 0,
            "normalized_mode": 0,
            "projection_mode": 0,
            "candidates_prefiltered": 0,
            "existing": 0,
            "verified_new": 0,
            "scored_new": 0,
            "apply": 0,
            "consider": 0,
            "skip": 0,
            "geography_skipped": 0,
            "errors": 0,
        }

        log(
            "ASHBY_RUN_START",
            started.isoformat(),
        )

        log(
            "PROVIDER",
            "ashby",
        )

        log(
            "BOARD_COUNT",
            len(boards),
        )

        log(
            "PROFILE_VERSION",
            profile.version,
        )

        log(
            "ASHBY_SOURCES_BEFORE",
            sources_before,
        )

        new_budget = args.max_new

        for spec in boards:

            if new_budget <= 0:
                break

            connector = (
                AshbyJobBoardConnector(
                    job_board_name=(
                        spec.job_board_name
                    ),
                    employer_name=(
                        spec.employer_name
                    ),
                )
            )

            log(
                "BOARD_START",
                spec.job_board_name,
                spec.employer_name,
            )

            try:

                result = (
                    await await_if_needed(
                        orchestrator
                        .retrieve_candidates(
                            connector=connector,
                            objective=(
                                "Discover current "
                                "public Ashby jobs "
                                "for DAP Career."
                            ),
                            source_url=(
                                connector.jobs_url
                            ),
                        )
                    )
                )

                counters[
                    "boards_ok"
                ] += 1

                counters[
                    "candidates_seen"
                ] += (
                    result.candidate_count
                )

                parse_mode = getattr(
                    result,
                    "parser_input_kind",
                    "phase16_normalized_content",
                )

                if (
                    parse_mode
                    == "phase16_structured_json_projection"
                ):
                    counters[
                        "projection_mode"
                    ] += 1
                else:
                    counters[
                        "normalized_mode"
                    ] += 1

                log(
                    "BOARD_DISCOVERED",
                    spec.job_board_name,
                    result.candidate_count,
                )

                log(
                    "ASHBY_PARSE_MODE",
                    spec.job_board_name,
                    parse_mode,
                )

                projection_id = getattr(
                    result,
                    "projection_evidence_id",
                    None,
                )

                if projection_id:
                    log(
                        "ASHBY_PROJECTION",
                        spec.job_board_name,
                        projection_id,
                    )

            except Exception as exc:

                counters[
                    "boards_failed"
                ] += 1

                counters[
                    "errors"
                ] += 1

                log(
                    "BOARD_ERROR",
                    spec.job_board_name,
                    type(exc).__name__,
                    str(exc),
                )

                continue

            for candidate in (
                result.candidates
            ):

                if new_budget <= 0:
                    break

                if not (
                    core.candidate_role_relevant(
                        candidate.title_hint
                    )
                ):
                    continue

                if not (
                    ashby_location_relevant(
                        candidate.location_hint
                    )
                ):
                    continue

                counters[
                    "candidates_prefiltered"
                ] += 1

                existing_before = (
                    core.existing_posting(
                        args.database,
                        employer_name=(
                            candidate.employer_name
                        ),
                        requisition_id=str(
                            candidate.source_job_id
                        ),
                    )
                )

                if existing_before is not None:
                    counters[
                        "existing"
                    ] += 1

                try:

                    detail = (
                        await build_verified_detail(
                            adapter=adapter,
                            candidate=candidate,
                            job_board_name=(
                                spec.job_board_name
                            ),
                        )
                    )

                    if detail is None:

                        counters[
                            "geography_skipped"
                        ] += 1

                        log(
                            "ASHBY_GEOGRAPHY_SKIP",
                            spec.job_board_name,
                            candidate.source_job_id,
                            candidate.title_hint,
                            candidate.location_hint,
                        )

                        continue

                    run_production_canary(
                        repository=repository,
                        provider_kind="ashby",
                        provider_target={
                            "job_board_name":
                                spec.job_board_name,
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

                    posting = (
                        core.existing_posting(
                            args.database,
                            employer_name=(
                                candidate.employer_name
                            ),
                            requisition_id=str(
                                candidate.source_job_id
                            ),
                        )
                    )

                    if posting is None:
                        raise RuntimeError(
                            "Ashby ingestion "
                            "returned without "
                            "persisted posting"
                        )

                    if existing_before is None:
                        counters[
                            "verified_new"
                        ] += 1

                        new_budget -= 1

                    scored = (
                        core.score_persisted_job(
                            database=args.database,
                            repository=repository,
                            posting=posting,
                            profile=profile,
                        )
                    )

                    if scored is not None:

                        assessment = (
                            scored.assessment
                        )

                        counters[
                            "scored_new"
                        ] += 1

                        counters[
                            assessment.verdict.lower()
                        ] += 1

                        log(
                            "ASHBY_SCORE",
                            assessment.fit_score,
                            assessment.verdict,
                            candidate.employer_name,
                            candidate.title_hint,
                            detail.location_text,
                        )

                    else:

                        log(
                            "ASHBY_SCORE",
                            "EXISTING",
                            posting["job_id"],
                            candidate.employer_name,
                            candidate.title_hint,
                        )

                    log(
                        "ASHBY_JOB",
                        candidate.employer_name,
                        candidate.title_hint,
                        detail.location_text,
                        candidate.detail_url,
                    )

                except Exception as exc:

                    counters[
                        "errors"
                    ] += 1

                    log(
                        "ASHBY_CANDIDATE_ERROR",
                        spec.job_board_name,
                        candidate.source_job_id,
                        candidate.title_hint,
                        type(exc).__name__,
                        str(exc),
                    )

                    traceback.print_exc(
                        limit=2,
                        file=sys.stdout,
                    )

        sources_after = (
            count_ashby_sources(
                args.database
            )
        )

        service = (
            CareerDashboardService(
                args.database
            )
        )

        summary = service.summary()

        jobs = service.list_jobs(
            limit=500
        )

        finished = utc_now()

        log(
            "ASHBY_RUN_FINISH",
            finished.isoformat(),
        )

        log(
            "DURATION_SECONDS",
            round(
                (
                    finished
                    - started
                ).total_seconds(),
                3,
            ),
        )

        for key, value in (
            counters.items()
        ):
            log(
                "COUNT",
                key,
                value,
            )

        log(
            "ASHBY_SOURCES_AFTER",
            sources_after,
        )

        log(
            "DASHBOARD",
            "verified_active",
            summary.verified_active_jobs,
        )

        log(
            "DASHBOARD",
            "apply",
            summary.apply_jobs,
        )

        log(
            "DASHBOARD",
            "consider",
            summary.consider_jobs,
        )

        log(
            "DASHBOARD",
            "visible",
            summary.visible_jobs,
        )

        log(
            "DASHBOARD",
            "items",
            jobs.total,
        )

        log(
            "APPLICATION_SUBMISSION",
            "NO",
        )

        log(
            "AUTO_APPLY",
            "NO",
        )

        log(
            "NETWORK_OWNER",
            "PHASE16",
        )

        if (
            counters["boards_ok"]
            == 0
        ):
            log(
                "ASHBY_AUTOMATION",
                "FAILED_NO_BOARDS",
            )
            return 2

        if sources_after < 1:
            log(
                "ASHBY_AUTOMATION",
                "FAILED_NO_PRODUCTION_SOURCE",
            )
            return 3

        log(
            "ASHBY_AUTOMATION",
            "PASS",
        )

        return 0


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--profile-config",
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

    if (
        args.max_new < 1
        or args.max_new > 200
    ):
        raise SystemExit(
            "--max-new must be 1-200"
        )

    return asyncio.run(
        run(args)
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
