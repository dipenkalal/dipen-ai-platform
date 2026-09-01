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
from career.connectors.smartrecruiters import (
    SmartRecruitersPostingConnector,
)
from career.dashboard import CareerDashboardService
from career.ingestion import CareerVerifiedJobDetail
from career.phase16_retrieval_adapter import (
    CareerPhase16RetrievalAdapter,
)
from career.production_pipeline import (
    run_production_canary,
)
from career.retrieval import CareerRetrievalOrchestrator


DEFAULT_DB = Path(
    "/home/dipen/dap/data/agent-history/"
    "agent-truth.db"
)

DEFAULT_LOCK = Path(
    "/home/dipen/dap/run/"
    "career-smartrecruiters.lock"
)


@dataclass(frozen=True)
class CompanySpec:
    company_identifier: str
    employer_name: str
    enabled: bool = True


def log(event: str, *parts: object) -> None:
    payload = "|".join(
        str(part).replace("\n", " ")
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


def load_companies(
    path: Path,
) -> tuple[CompanySpec, ...]:
    raw = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(raw, dict):
        raise ValueError(
            "SmartRecruiters config root "
            "must be an object"
        )

    rows = raw.get("companies")

    if (
        not isinstance(rows, list)
        or not rows
    ):
        raise ValueError(
            "SmartRecruiters config requires "
            "companies"
        )

    result: list[CompanySpec] = []

    for raw_spec in rows:
        if not isinstance(
            raw_spec,
            dict,
        ):
            raise ValueError(
                "company entry must be object"
            )

        spec = CompanySpec(
            company_identifier=str(
                raw_spec[
                    "company_identifier"
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
            not spec.company_identifier
            or not spec.employer_name
        ):
            raise ValueError(
                "SmartRecruiters company "
                "fields may not be empty"
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


def smart_location_relevant(
    location: str | None,
) -> bool:
    if not location:
        return False

    if core.candidate_location_relevant(
        location
    ):
        return True

    lowered = location.casefold()

    if any(
        token in lowered
        for token in (
            "united states",
            "usa",
            "united kingdom",
            "england",
            "india",
            "germany",
            "france",
            "australia",
            "mexico",
        )
    ):
        return False

    # SmartRecruiters commonly emits:
    # Toronto, ON, CA (Remote)
    # Ottawa, ON, CA
    # CA (Remote)
    if re.search(
        r"(?:^|[,\s])ON(?:[,\s]|$)",
        location,
        flags=re.I,
    ):
        return True

    if (
        "remote" in lowered
        and re.search(
            r"(?:^|[,\s])CA(?:[,\s()]|$)",
            location,
            flags=re.I,
        )
    ):
        return True

    return False


def canonical_location_hint(
    location: str | None,
    *,
    work_mode: str,
) -> str | None:
    if not location:
        return None

    city = core._ontario_city_from_text(
        location
    )

    if city is not None:
        return (
            f"{city}, Ontario, Canada"
        )

    if re.search(
        r"(?:^|[,\s])ON(?:[,\s]|$)",
        location,
        flags=re.I,
    ):
        cleaned = re.sub(
            r"(?:^|,\s*)ON(?=,|\s|$)",
            ", Ontario",
            location,
            flags=re.I,
        )

        cleaned = re.sub(
            r"(?:^|,\s*)CA(?=\s*\(Remote\)|,|\s|$)",
            ", Canada",
            cleaned,
            flags=re.I,
        )

        return (
            cleaned
            .replace(
                " (Remote)",
                "",
            )
            .strip(" ,")
        )

    if (
        work_mode == "REMOTE"
        and re.search(
            r"(?:^|[,\s])CA(?:[,\s()]|$)",
            location,
            flags=re.I,
        )
    ):
        return "Remote (Canada)"

    return location.strip()


async def await_if_needed(
    value,
):
    if inspect.isawaitable(
        value
    ):
        return await value

    return value


async def build_verified_detail(
    *,
    adapter: CareerPhase16RetrievalAdapter,
    candidate,
    company_identifier: str,
) -> CareerVerifiedJobDetail | None:

    page = await await_if_needed(
        adapter.retrieve_public_url(
            objective=(
                "Verify a DAP Career candidate "
                "from its canonical public "
                "SmartRecruiters posting."
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
            "SmartRecruiters canonical "
            "evidence URL mismatch: "
            f"{candidate.detail_url!r} != "
            f"{evidence.final_url!r}"
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
            "SmartRecruiters canonical "
            "evidence content missing"
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
            "canonical SmartRecruiters "
            "page does not contain title"
        )

    work_mode = (
        core.work_mode_from_text(
            normalized,
            candidate.location_hint,
        )
    )

    location = (
        canonical_location_hint(
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
        "provider":
            "smartrecruiters",

        "company_identifier":
            company_identifier,

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


async def run(
    args,
) -> int:

    company_specs = load_companies(
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
            "SMART_CONFIG",
            "PASS",
        )

        log(
            "COMPANIES",
            len(company_specs),
        )

        log(
            "PROFILE_VERSION",
            profile.version,
        )

        for spec in company_specs:
            log(
                "COMPANY",
                spec.company_identifier,
                spec.employer_name,
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
                "SMART_RUN",
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

        counters = {
            "companies_ok": 0,
            "companies_failed": 0,
            "candidates_seen": 0,
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
            "SMART_RUN_START",
            started.isoformat(),
        )

        log(
            "PROVIDER",
            "smartrecruiters",
        )

        log(
            "COMPANY_COUNT",
            len(company_specs),
        )

        log(
            "PROFILE_VERSION",
            profile.version,
        )

        new_budget = args.max_new

        for spec in company_specs:

            if new_budget <= 0:
                break

            log(
                "COMPANY_START",
                spec.company_identifier,
                spec.employer_name,
            )

            connector = (
                SmartRecruitersPostingConnector(
                    company_identifier=(
                        spec.company_identifier
                    ),
                    employer_name=(
                        spec.employer_name
                    ),
                )
            )

            try:
                result = (
                    await await_if_needed(
                        orchestrator
                        .retrieve_candidates(
                            connector=connector,
                            objective=(
                                "Discover current "
                                "public SmartRecruiters "
                                "jobs for DAP Career."
                            ),
                            source_url=(
                                connector.jobs_url
                            ),
                        )
                    )
                )

                counters[
                    "companies_ok"
                ] += 1

                counters[
                    "candidates_seen"
                ] += (
                    result.candidate_count
                )

                log(
                    "COMPANY_DISCOVERED",
                    spec.company_identifier,
                    result.candidate_count,
                )

            except Exception as exc:

                counters[
                    "companies_failed"
                ] += 1

                counters[
                    "errors"
                ] += 1

                log(
                    "COMPANY_ERROR",
                    spec.company_identifier,
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
                    smart_location_relevant(
                        candidate.location_hint
                    )
                ):
                    continue

                counters[
                    "candidates_prefiltered"
                ] += 1

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

                if posting is not None:
                    counters[
                        "existing"
                    ] += 1

                try:
                    detail = (
                        await build_verified_detail(
                            adapter=adapter,
                            candidate=candidate,
                            company_identifier=(
                                spec
                                .company_identifier
                            ),
                        )
                    )

                    if detail is None:
                        counters[
                            "geography_skipped"
                        ] += 1

                        log(
                            "SMART_GEOGRAPHY_SKIP",
                            spec.company_identifier,
                            candidate.source_job_id,
                            candidate.title_hint,
                            candidate.location_hint,
                        )

                        continue

                    run_production_canary(
                        repository=repository,
                        provider_kind=(
                            "smartrecruiters"
                        ),
                        provider_target={
                            "company_identifier":
                                spec
                                .company_identifier,
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
                                candidate
                                .employer_name
                            ),
                            requisition_id=str(
                                candidate
                                .source_job_id
                            ),
                        )
                    )

                    if posting is None:
                        raise RuntimeError(
                            "SmartRecruiters "
                            "ingestion returned "
                            "without posting"
                        )

                    if not (
                        core.assessment_exists(
                            args.database,
                            job_id=(
                                posting["job_id"]
                            ),
                            snapshot_id=(
                                posting[
                                    "current_snapshot_id"
                                ]
                            ),
                            profile_version=(
                                profile.version
                            ),
                        )
                    ):
                        scored = (
                            core.score_persisted_job(
                                database=(
                                    args.database
                                ),
                                repository=repository,
                                posting=posting,
                                profile=profile,
                            )
                        )
                    else:
                        scored = None

                    if posting is not None and (
                        not core.assessment_exists(
                            args.database,
                            job_id=(
                                posting["job_id"]
                            ),
                            snapshot_id=(
                                posting[
                                    "current_snapshot_id"
                                ]
                            ),
                            profile_version=(
                                profile.version
                            ),
                        )
                    ):
                        raise RuntimeError(
                            "SmartRecruiters job "
                            "remained unscored"
                        )

                    if scored is not None:
                        assessment = (
                            scored.assessment
                        )

                        counters[
                            "scored_new"
                        ] += 1

                        counters[
                            assessment
                            .verdict
                            .lower()
                        ] += 1

                        log(
                            "SMART_SCORE",
                            assessment.fit_score,
                            assessment.verdict,
                            candidate.employer_name,
                            candidate.title_hint,
                            detail.location_text,
                        )

                    if (
                        posting is not None
                        and not (
                            core.existing_posting(
                                args.database,
                                employer_name=(
                                    candidate
                                    .employer_name
                                ),
                                requisition_id=str(
                                    candidate
                                    .source_job_id
                                ),
                            )
                            is None
                        )
                    ):
                        if (
                            candidate.source_job_id
                            and posting
                        ):
                            pass

                    if counters[
                        "existing"
                    ] == 0 or (
                        posting["first_seen_at"]
                        == posting["created_at"]
                    ):
                        pass

                    if posting is not None:
                        # Count only truly new persisted
                        # rows through first-observation
                        # equality against this run is not
                        # reliable enough for authority.
                        # The before/after DB report below
                        # is canonical.
                        pass

                    if (
                        candidate.source_job_id
                        and detail
                    ):
                        log(
                            "SMART_JOB",
                            candidate.employer_name,
                            candidate.title_hint,
                            detail.location_text,
                            candidate.detail_url,
                        )

                    if posting is not None:
                        new_budget -= (
                            0
                            if core.existing_posting(
                                args.database,
                                employer_name=(
                                    candidate
                                    .employer_name
                                ),
                                requisition_id=str(
                                    candidate
                                    .source_job_id
                                ),
                            )
                            is None
                            else 1
                        )

                except Exception as exc:

                    counters[
                        "errors"
                    ] += 1

                    log(
                        "SMART_CANDIDATE_ERROR",
                        spec.company_identifier,
                        candidate.source_job_id,
                        candidate.title_hint,
                        type(exc).__name__,
                        str(exc),
                    )

                    traceback.print_exc(
                        limit=2,
                        file=sys.stdout,
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
            "SMART_RUN_FINISH",
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
            counters["companies_ok"]
            == 0
        ):
            log(
                "SMART_AUTOMATION",
                "FAILED_NO_COMPANIES",
            )
            return 2

        log(
            "SMART_AUTOMATION",
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
