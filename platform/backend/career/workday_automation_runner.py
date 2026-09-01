from __future__ import annotations

import argparse
import asyncio
import fcntl
import html
import json
import re
import sqlite3
import sys
import traceback

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


import career.automation_runner as core

from career.connectors.contracts import (
    CareerDiscoveryCandidate,
)

from career.dashboard import (
    CareerDashboardService,
)

from career.phase16_retrieval_adapter import (
    CareerPhase16RetrievalAdapter,
)

from career.production_pipeline import (
    CareerVerifiedJobDetail,
    run_production_canary,
)


DEFAULT_DB = Path(
    "/home/dipen/dap/data/"
    "agent-history/agent-truth.db"
)

DEFAULT_LOCK = Path(
    "/home/dipen/dap/runtime/"
    "career-workday-automation.lock"
)

PAGE_SIZE = 20

MAX_OFFSET = 2000

MAX_PAGES = (
    MAX_OFFSET // PAGE_SIZE
) + 1

CONNECTOR_ID = (
    "career-connector-workday-generic"
)

_SAFE_SEGMENT = re.compile(
    r"^[A-Za-z0-9._~-]+$"
)

# Workday-only discovery supplement.
#
# This does NOT alter the shared Career filter.
# It merely allows relevant platform-engineering
# candidates to reach canonical detail verification.
#
# Final Career eligibility/scoring remains unchanged.
_WORKDAY_EXTRA_TITLE_PATTERNS = (
    r"\bplatform\s+engineer\b",
)


def log(
    *parts: object,
) -> None:

    print(
        "|".join(
            str(part)
            for part in parts
        ),
        flush=True,
    )


def utc_now() -> datetime:

    return datetime.now(
        timezone.utc
    )


def workday_role_relevant(
    title: str,
) -> bool:
    """
    Preserve the global Career title filter and add one
    Workday discovery-only platform-engineer admission.

    This function grants no scoring, shortlist, freshness,
    or application authority.
    """

    if core.candidate_role_relevant(
        title
    ):
        return True

    normalized = re.sub(
        r"[/_-]+",
        " ",
        title,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    return any(
        re.search(
            pattern,
            normalized,
            flags=re.I,
        )
        is not None
        for pattern in (
            _WORKDAY_EXTRA_TITLE_PATTERNS
        )
    )


@dataclass(frozen=True)
class WorkdaySiteSpec:

    host: str
    tenant: str
    site: str
    employer_name: str
    locale: str = "en-US"
    search_text: str = ""
    max_pages: int = 25
    enabled: bool = True

    @property
    def listing_url(
        self,
    ) -> str:

        return (
            f"https://{self.host}"
            f"/wday/cxs/"
            f"{self.tenant}/"
            f"{self.site}/jobs"
        )

    def detail_url(
        self,
        external_path: str,
    ) -> str:

        slug = _external_slug(
            external_path
        )

        return (
            f"https://{self.host}"
            f"/wday/cxs/"
            f"{self.tenant}/"
            f"{self.site}/job/"
            f"{slug}"
        )

    def public_job_url(
        self,
        external_path: str,
    ) -> str:

        slug = _external_slug(
            external_path
        )

        return (
            f"https://{self.host}/"
            f"{self.locale}/"
            f"{self.site}/job/"
            f"{slug}"
        )


@dataclass(frozen=True)
class WorkdayListingPage:

    candidates: tuple[
        CareerDiscoveryCandidate,
        ...
    ]

    total: int
    offset: int


def _require_text(
    value: object,
    *,
    field: str,
) -> str:

    text = str(
        value
    ).strip()

    if not text:
        raise ValueError(
            f"{field} may not be empty"
        )

    return text


def _validate_host(
    value: str,
) -> str:

    host = (
        value.strip()
        .lower()
        .rstrip(".")
    )

    if (
        not host
        or "://" in host
        or "/" in host
        or "@" in host
    ):
        raise ValueError(
            "Workday host must be a "
            "bare hostname"
        )

    if (
        not host.endswith(
            ".myworkdayjobs.com"
        )
        or host
        == "myworkdayjobs.com"
    ):
        raise ValueError(
            "Workday host must be under "
            "*.myworkdayjobs.com"
        )

    return host


def _validate_segment(
    value: str,
    *,
    field: str,
) -> str:

    text = _require_text(
        value,
        field=field,
    )

    if (
        _SAFE_SEGMENT.fullmatch(
            text
        )
        is None
    ):
        raise ValueError(
            f"{field} contains "
            "unsupported characters"
        )

    return text


def _validate_locale(
    value: str,
) -> str:

    locale = _require_text(
        value,
        field="locale",
    )

    if (
        re.fullmatch(
            r"[A-Za-z]{2,3}"
            r"(?:-[A-Za-z]{2,4})?",
            locale,
        )
        is None
    ):
        raise ValueError(
            "Workday locale is invalid"
        )

    return locale


def _external_slug(
    external_path: str,
) -> str:

    path = _require_text(
        external_path,
        field="externalPath",
    )

    parsed = urlsplit(
        path
    )

    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Workday externalPath must "
            "be a relative path"
        )

    if not parsed.path.startswith(
        "/job/"
    ):
        raise ValueError(
            "Workday externalPath must "
            "start with /job/"
        )

    slug = (
        parsed.path
        .rstrip("/")
        .rsplit("/", 1)[-1]
        .strip()
    )

    if not slug:
        raise ValueError(
            "Workday externalPath "
            "contains no job slug"
        )

    return slug


def _validate_spec(
    spec: WorkdaySiteSpec,
) -> WorkdaySiteSpec:

    host = _validate_host(
        spec.host
    )

    tenant = _validate_segment(
        spec.tenant,
        field="tenant",
    )

    site = _validate_segment(
        spec.site,
        field="site",
    )

    employer = _require_text(
        spec.employer_name,
        field="employer_name",
    )

    locale = _validate_locale(
        spec.locale
    )

    search_text = (
        spec.search_text.strip()
    )

    if len(search_text) > 120:
        raise ValueError(
            "Workday search_text "
            "must be <=120 characters"
        )

    if (
        spec.max_pages < 1
        or spec.max_pages > MAX_PAGES
    ):
        raise ValueError(
            "Workday max_pages "
            f"must be 1-{MAX_PAGES}"
        )

    host_tenant = (
        host.split(
            ".",
            1,
        )[0]
    )

    if (
        host_tenant.casefold()
        != tenant.casefold()
    ):
        raise ValueError(
            "Workday tenant must match "
            "the first host label"
        )

    return WorkdaySiteSpec(
        host=host,
        tenant=tenant,
        site=site,
        employer_name=employer,
        locale=locale,
        search_text=search_text,
        max_pages=spec.max_pages,
        enabled=spec.enabled,
    )


def load_sites(
    path: Path,
) -> tuple[
    WorkdaySiteSpec,
    ...
]:

    raw = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(
            "Workday config root "
            "must be object"
        )

    rows = raw.get(
        "sites"
    )

    if (
        not isinstance(
            rows,
            list,
        )
        or not rows
    ):
        raise ValueError(
            "Workday config requires sites"
        )

    result: list[
        WorkdaySiteSpec
    ] = []

    for raw_spec in rows:

        if not isinstance(
            raw_spec,
            dict,
        ):
            raise ValueError(
                "Workday site entry "
                "must be object"
            )

        spec = _validate_spec(
            WorkdaySiteSpec(
                host=str(
                    raw_spec[
                        "host"
                    ]
                ),
                tenant=str(
                    raw_spec[
                        "tenant"
                    ]
                ),
                site=str(
                    raw_spec[
                        "site"
                    ]
                ),
                employer_name=str(
                    raw_spec[
                        "employer_name"
                    ]
                ),
                locale=str(
                    raw_spec.get(
                        "locale",
                        "en-US",
                    )
                ),
                search_text=str(
                    raw_spec.get(
                        "search_text",
                        "",
                    )
                ),
                max_pages=int(
                    raw_spec.get(
                        "max_pages",
                        25,
                    )
                ),
                enabled=bool(
                    raw_spec.get(
                        "enabled",
                        True,
                    )
                ),
            )
        )

        if spec.enabled:
            result.append(
                spec
            )

    if not result:
        raise ValueError(
            "Workday config has no "
            "enabled sites"
        )

    return tuple(
        result
    )


def parse_listing_bundle(
    *,
    bundle,
    spec: WorkdaySiteSpec,
    offset: int,
) -> WorkdayListingPage:

    if (
        offset < 0
        or offset > MAX_OFFSET
        or offset % PAGE_SIZE != 0
    ):
        raise ValueError(
            "Workday listing offset "
            "is outside the sealed boundary"
        )

    evidence = (
        bundle.retrieval_evidence
    )

    content = (
        bundle.content_evidence
    )

    if evidence.method != "POST":
        raise ValueError(
            "Workday discovery requires "
            "POST Phase16 evidence"
        )

    if (
        evidence.request_body_sha256
        is None
    ):
        raise ValueError(
            "Workday discovery evidence "
            "is missing body binding"
        )

    if (
        content.media_type
        != "application/json"
    ):
        raise ValueError(
            "Workday discovery requires "
            "application/json"
        )

    payload = json.loads(
        content.normalized_text
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Workday listing root "
            "must be object"
        )

    total = payload.get(
        "total"
    )

    jobs = payload.get(
        "jobPostings"
    )

    if (
        not isinstance(
            total,
            int,
        )
        or total < 0
    ):
        raise ValueError(
            "Workday listing total "
            "is invalid"
        )

    if not isinstance(
        jobs,
        list,
    ):
        raise ValueError(
            "Workday listing jobPostings "
            "must be list"
        )

    candidates: list[
        CareerDiscoveryCandidate
    ] = []

    for item in jobs:

        if not isinstance(
            item,
            dict,
        ):
            continue

        title = str(
            item.get(
                "title",
                "",
            )
        ).strip()

        external_path = str(
            item.get(
                "externalPath",
                "",
            )
        ).strip()

        if (
            not title
            or not external_path
        ):
            continue

        slug = _external_slug(
            external_path
        )

        location_raw = (
            item.get(
                "locationsText"
            )
            or item.get(
                "location"
            )
        )

        location = (
            str(
                location_raw
            ).strip()
            if location_raw
            is not None
            else None
        )

        if location == "":
            location = None

        candidate = (
            CareerDiscoveryCandidate.build(
                connector_id=(
                    CONNECTOR_ID
                ),
                connector_kind=(
                    "generic_employer"
                ),
                employer_name=(
                    spec.employer_name
                ),
                source_job_id=slug,
                title_hint=title,
                location_hint=(
                    location
                ),
                detail_url=(
                    spec.detail_url(
                        external_path
                    )
                ),
                apply_url_hint=(
                    spec.public_job_url(
                        external_path
                    )
                ),
                discovery_research_evidence_id=(
                    evidence.evidence_id
                ),
                discovery_content_evidence_id=(
                    content.evidence_id
                ),
                discovery_normalized_text_sha256=(
                    content
                    .normalized_text_sha256
                ),
                observed_at=(
                    evidence.observed_at
                ),
            )
        )

        candidates.append(
            candidate
        )

    return WorkdayListingPage(
        candidates=tuple(
            candidates
        ),
        total=total,
        offset=offset,
    )


def _description_text(
    value: object,
) -> str:

    raw = str(
        value or ""
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        raw,
    )

    text = html.unescape(
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if not text:
        raise ValueError(
            "Workday detail description "
            "is empty"
        )

    return text


def _optional_text(
    value: object,
) -> str | None:

    if value is None:
        return None

    text = str(
        value
    ).strip()

    return (
        text
        if text
        else None
    )


def _infer_work_mode(
    *,
    location: str | None,
    description: str,
) -> str | None:

    blob = (
        f"{location or ''} "
        f"{description}"
    ).casefold()

    if "hybrid" in blob:
        return "HYBRID"

    if "remote" in blob:
        return "REMOTE"

    return None


async def build_verified_detail(
    *,
    adapter:
        CareerPhase16RetrievalAdapter,
    candidate:
        CareerDiscoveryCandidate,
) -> CareerVerifiedJobDetail | None:

    bundle = (
        await adapter.retrieve_public_url(
            objective=(
                "Verify one public Workday "
                "job detail through Phase16."
            ),
            url=(
                candidate.detail_url
            ),
        )
    )

    if (
        bundle.retrieval_evidence
        .method
        != "GET"
    ):
        raise ValueError(
            "Workday detail verification "
            "must use GET"
        )

    payload = json.loads(
        bundle.content_evidence
        .normalized_text
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Workday detail root "
            "must be object"
        )

    info = payload.get(
        "jobPostingInfo"
    )

    if not isinstance(
        info,
        dict,
    ):
        raise ValueError(
            "Workday detail requires "
            "jobPostingInfo"
        )

    title = _require_text(
        info.get(
            "title",
            "",
        ),
        field="jobPostingInfo.title",
    )

    location = _optional_text(
        info.get(
            "location"
        )
    )

    description = _description_text(
        info.get(
            "jobDescription"
        )
    )

    canonical_apply_url = _optional_text(
        info.get(
            "externalUrl"
        )
    )

    if canonical_apply_url is not None:

        parsed_apply = urlsplit(
            canonical_apply_url
        )

        parsed_detail = urlsplit(
            candidate.detail_url
        )

        if (
            parsed_apply.scheme.lower()
            != "https"
            or parsed_apply.hostname
            is None
            or parsed_apply.username
            is not None
            or parsed_apply.password
            is not None
        ):
            raise ValueError(
                "Workday externalUrl must use "
                "credential-free HTTPS"
            )

        try:
            apply_port = (
                parsed_apply.port
            )
        except ValueError as exc:
            raise ValueError(
                "Workday externalUrl contains "
                "an invalid port"
            ) from exc

        if apply_port not in {
            None,
            443,
        }:
            raise ValueError(
                "Workday externalUrl permits "
                "only HTTPS port 443"
            )

        if (
            parsed_detail.hostname
            is None
            or parsed_apply.hostname
            .casefold()
            != parsed_detail.hostname
            .casefold()
        ):
            raise ValueError(
                "Workday externalUrl host does not "
                "match verified detail host"
            )

    if not (
        workday_role_relevant(
            title
        )
    ):
        return None

    if not (
        core.candidate_location_relevant(
            location
        )
    ):
        return None

    requirements: dict[
        str,
        Any,
    ] = {}

    for source_key, target_key in (
        (
            "jobReqId",
            "job_req_id",
        ),
        (
            "postedOn",
            "posted_on",
        ),
        (
            "startDate",
            "start_date",
        ),
    ):
        value = _optional_text(
            info.get(
                source_key
            )
        )

        if value is not None:
            requirements[
                target_key
            ] = value

    return CareerVerifiedJobDetail(
        research_evidence_id=(
            bundle.retrieval_evidence
            .evidence_id
        ),
        canonical_job_url=(
            candidate.detail_url
        ),
        canonical_apply_url=(
            canonical_apply_url
        ),
        title=title,
        employer_name=(
            candidate.employer_name
        ),
        description_text=(
            description
        ),
        normalized_text_sha256=(
            bundle.content_evidence
            .normalized_text_sha256
        ),
        observed_at=(
            bundle.retrieval_evidence
            .observed_at
        ),
        location_text=location,
        work_mode=(
            _infer_work_mode(
                location=location,
                description=description,
            )
        ),
        employment_type=(
            _optional_text(
                info.get(
                    "timeType"
                )
            )
        ),
        posted_at=None,
        closing_at=None,
        salary_text=None,
        requirements=requirements,
    )


def count_workday_sources(
    database: Path,
) -> int:

    db = sqlite3.connect(
        f"file:{database}?mode=ro",
        uri=True,
    )

    try:
        db.execute(
            "PRAGMA query_only=ON"
        )

        row = db.execute(
            """
            SELECT COUNT(*)
            FROM career_sources
            WHERE lower(canonical_base_url)
                  LIKE 'https://%.myworkdayjobs.com'
            """
        ).fetchone()

        return int(
            row[0]
        )

    finally:
        db.close()


async def run(
    args,
) -> int:

    sites = load_sites(
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
            "WORKDAY_CONFIG",
            "PASS",
        )

        log(
            "SITES",
            len(sites),
        )

        log(
            "PROFILE_VERSION",
            profile.version,
        )

        for spec in sites:

            log(
                "SITE",
                spec.host,
                spec.tenant,
                spec.site,
                spec.employer_name,
                spec.search_text
                or "<EMPTY>",
                spec.max_pages,
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
                "WORKDAY_RUN",
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

        started = (
            utc_now()
        )

        sources_before = (
            count_workday_sources(
                args.database
            )
        )

        counters = {
            "sites_ok": 0,
            "sites_failed": 0,
            "listing_pages": 0,
            "candidates_seen": 0,
            "candidates_prefiltered": 0,
            "shared_role_match": 0,
            "workday_role_supplement": 0,
            "existing": 0,
            "verified_new": 0,
            "scored_new": 0,
            "apply": 0,
            "consider": 0,
            "skip": 0,
            "detail_filtered": 0,
            "errors": 0,
        }

        log(
            "WORKDAY_RUN_START",
            started.isoformat(),
        )

        log(
            "PROVIDER",
            "workday",
        )

        log(
            "ROUTE",
            "GENERIC_PHASE16_FALLBACK",
        )

        log(
            "NETWORK_OWNER",
            "PHASE16",
        )

        log(
            "SITE_COUNT",
            len(sites),
        )

        log(
            "PROFILE_VERSION",
            profile.version,
        )

        log(
            "WORKDAY_SOURCES_BEFORE",
            sources_before,
        )

        new_budget = (
            args.max_new
        )

        for spec in sites:

            if new_budget <= 0:
                break

            log(
                "SITE_START",
                spec.host,
                spec.site,
                spec.employer_name,
            )

            discovered: list[
                CareerDiscoveryCandidate
            ] = []

            seen: set[
                tuple[str, str]
            ] = set()

            try:

                for page_index in range(
                    spec.max_pages
                ):

                    offset = (
                        page_index
                        * PAGE_SIZE
                    )

                    if offset > MAX_OFFSET:
                        break

                    bundle = (
                        await adapter
                        .retrieve_workday_cxs_jobs(
                            objective=(
                                "Discover current "
                                "public Workday jobs "
                                "for DAP Career."
                            ),
                            url=(
                                spec.listing_url
                            ),
                            offset=offset,
                            search_text=(
                                spec.search_text
                            ),
                        )
                    )

                    page = (
                        parse_listing_bundle(
                            bundle=bundle,
                            spec=spec,
                            offset=offset,
                        )
                    )

                    counters[
                        "listing_pages"
                    ] += 1

                    log(
                        "WORKDAY_PAGE",
                        spec.host,
                        offset,
                        len(
                            page.candidates
                        ),
                        page.total,
                    )

                    for candidate in (
                        page.candidates
                    ):

                        identity = (
                            candidate
                            .source_job_id,
                            candidate
                            .detail_url,
                        )

                        if identity in seen:
                            continue

                        seen.add(
                            identity
                        )

                        discovered.append(
                            candidate
                        )

                    if (
                        not page.candidates
                        or offset
                        + PAGE_SIZE
                        >= page.total
                    ):
                        break

                counters[
                    "sites_ok"
                ] += 1

                counters[
                    "candidates_seen"
                ] += len(
                    discovered
                )

                log(
                    "SITE_DISCOVERED",
                    spec.host,
                    len(discovered),
                )

            except Exception as exc:

                counters[
                    "sites_failed"
                ] += 1

                counters[
                    "errors"
                ] += 1

                log(
                    "SITE_ERROR",
                    spec.host,
                    type(exc).__name__,
                    str(exc),
                )

                traceback.print_exc(
                    limit=2,
                    file=sys.stdout,
                )

                continue

            for candidate in (
                discovered
            ):

                if new_budget <= 0:
                    break

                shared_match = (
                    core.candidate_role_relevant(
                        candidate.title_hint
                    )
                )

                workday_match = (
                    workday_role_relevant(
                        candidate.title_hint
                    )
                )

                if not workday_match:
                    continue

                if shared_match:
                    counters[
                        "shared_role_match"
                    ] += 1
                else:
                    counters[
                        "workday_role_supplement"
                    ] += 1

                    log(
                        "WORKDAY_ROLE_SUPPLEMENT",
                        candidate
                        .employer_name,
                        candidate
                        .title_hint,
                    )

                if not (
                    core.candidate_location_relevant(
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
                            candidate
                            .employer_name
                        ),
                        requisition_id=str(
                            candidate
                            .source_job_id
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
                        )
                    )

                    if detail is None:

                        counters[
                            "detail_filtered"
                        ] += 1

                        log(
                            "WORKDAY_DETAIL_SKIP",
                            spec.host,
                            candidate
                            .source_job_id,
                            candidate
                            .title_hint,
                            candidate
                            .location_hint,
                        )

                        continue

                    run_production_canary(
                        repository=repository,
                        provider_kind="workday",
                        provider_target={
                            "host":
                                spec.host,
                            "tenant":
                                spec.tenant,
                            "site":
                                spec.site,
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
                            "Workday ingestion "
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
                            database=(
                                args.database
                            ),
                            repository=(
                                repository
                            ),
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

                        verdict = (
                            assessment.verdict
                            .lower()
                        )

                        if verdict in counters:
                            counters[
                                verdict
                            ] += 1

                        log(
                            "WORKDAY_SCORE",
                            assessment
                            .fit_score,
                            assessment
                            .verdict,
                            candidate
                            .employer_name,
                            detail.title,
                            detail
                            .location_text,
                        )

                    else:

                        log(
                            "WORKDAY_SCORE",
                            "EXISTING",
                            posting["job_id"],
                            candidate
                            .employer_name,
                            detail.title,
                        )

                    log(
                        "WORKDAY_JOB",
                        candidate
                        .employer_name,
                        detail.title,
                        detail.location_text,
                        detail
                        .canonical_apply_url,
                    )

                except Exception as exc:

                    counters[
                        "errors"
                    ] += 1

                    log(
                        "WORKDAY_CANDIDATE_ERROR",
                        spec.host,
                        candidate
                        .source_job_id,
                        candidate
                        .title_hint,
                        type(exc).__name__,
                        str(exc),
                    )

                    traceback.print_exc(
                        limit=2,
                        file=sys.stdout,
                    )

        sources_after = (
            count_workday_sources(
                args.database
            )
        )

        dashboard = (
            CareerDashboardService(
                args.database
            )
        )

        summary = (
            dashboard.summary()
        )

        jobs = (
            dashboard.list_jobs(
                limit=500
            )
        )

        finished = (
            utc_now()
        )

        log(
            "WORKDAY_RUN_FINISH",
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
            "WORKDAY_SOURCES_AFTER",
            sources_after,
        )

        log(
            "DASHBOARD",
            "verified_active",
            summary
            .verified_active_jobs,
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
            "TELEGRAM_SEND",
            "NO",
        )

        if (
            counters["sites_ok"]
            == 0
        ):

            log(
                "WORKDAY_AUTOMATION",
                "FAILED_NO_SITES",
            )

            return 2

        if sources_after < 1:

            log(
                "WORKDAY_AUTOMATION",
                "FAILED_NO_PRODUCTION_SOURCE",
            )

            return 3

        log(
            "WORKDAY_AUTOMATION",
            "PASS",
        )

        return 0


def main() -> int:

    parser = (
        argparse.ArgumentParser()
    )

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
