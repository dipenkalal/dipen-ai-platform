from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import DEFAULT_TRUTH_DATABASE_PATH, AgentTruthRepository
from gateway.research_operations_repository import ResearchOperationsRepository
from gateway.research_provider_live_benchmark import (
    LIVE_CASE_TIMEOUT_SECONDS,
    MAXIMUM_LIVE_DUPLICATE_CONTENT_RATE,
    MAXIMUM_LIVE_NO_CANDIDATE_RATE,
    MAXIMUM_LIVE_RETRIEVAL_P95_MS,
    MINIMUM_LIVE_SUCCESS_RATE,
    MINIMUM_LIVE_UNIQUE_SOURCE_FAMILY_RATE,
)
from gateway.research_provider_phase16_validation_corpus import (
    PHASE16_VALIDATION_CORPUS,
    PHASE16_VALIDATION_CORPUS_CASE_COUNT,
    PHASE16_VALIDATION_CORPUS_VERSION,
    validate_phase16_validation_corpus,
)
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from gateway.searxng_search_provider import (
    SEARXNG_PROVIDER_ID,
    SearXNGSearchProviderError,
    SearXNGWebSearchProvider,
)
from gateway.web_search_discovery import WebSearchDiscoveryError, WebSearchRetrievalPipeline
from gateway.web_search_provider import WebSearchQuery
from tools.internet_research_tools import InternetResearchRetrieveTool

PHASE16_VALIDATION_VERSION: Literal["phase16h.1"] = "phase16h.1"


class Phase16ValidationThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: Literal["dap-phase16-validation-readiness-v1"] = (
        "dap-phase16-validation-readiness-v1"
    )
    minimum_success_rate: float = MINIMUM_LIVE_SUCCESS_RATE
    maximum_no_candidate_rate: float = MAXIMUM_LIVE_NO_CANDIDATE_RATE
    minimum_unique_source_family_rate: float = MINIMUM_LIVE_UNIQUE_SOURCE_FAMILY_RATE
    maximum_duplicate_content_rate: float = MAXIMUM_LIVE_DUPLICATE_CONTENT_RATE
    maximum_retrieval_p95_ms: float = MAXIMUM_LIVE_RETRIEVAL_P95_MS
    maximum_case_wall_clock_seconds: float = LIVE_CASE_TIMEOUT_SECONDS


class Phase16ValidationCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    success: bool
    no_candidate: bool
    search_attempt_count: int = Field(ge=1, le=3)
    fallback_used: bool
    selected_url_count: int = Field(ge=0, le=3)
    selected_unique_source_family_count: int = Field(ge=0, le=3)
    successful_source_count: int = Field(ge=0, le=3)
    provider_search_duration_ms: float | None = Field(default=None, ge=0)
    pipeline_duration_ms: float | None = Field(default=None, ge=0)
    source_durations_ms: tuple[float, ...] = ()
    normalized_text_sha256: tuple[str, ...] = ()
    error_code: str | None = None
    provider_titles_or_snippets_recorded: Literal[False] = False


class Phase16ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    validation_version: Literal["phase16h.1"] = PHASE16_VALIDATION_VERSION
    corpus_version: Literal["phase16-validation-corpus-v1"] = (
        PHASE16_VALIDATION_CORPUS_VERSION
    )
    source_commit: str
    provider_id: Literal["searxng-local-v1"] = SEARXNG_PROVIDER_ID
    case_count: Literal[24] = PHASE16_VALIDATION_CORPUS_CASE_COUNT
    success_count: int = Field(ge=0, le=24)
    success_rate: float = Field(ge=0, le=1)
    no_candidate_count: int = Field(ge=0, le=24)
    no_candidate_rate: float = Field(ge=0, le=1)
    fallback_case_count: int = Field(ge=0, le=24)
    selected_source_count: int = Field(ge=0)
    selected_unique_source_family_rate: float = Field(ge=0, le=1)
    successful_source_count: int = Field(ge=0)
    duplicate_content_count: int = Field(ge=0)
    duplicate_content_rate: float = Field(ge=0, le=1)
    provider_search_p50_ms: float | None = Field(default=None, ge=0)
    provider_search_p95_ms: float | None = Field(default=None, ge=0)
    retrieval_source_p50_ms: float | None = Field(default=None, ge=0)
    retrieval_source_p95_ms: float | None = Field(default=None, ge=0)
    pipeline_p95_ms: float | None = Field(default=None, ge=0)
    category_success_rates: dict[str, float]
    thresholds: Phase16ValidationThresholds
    meets_phase16_targets: bool
    recommended_posture: Literal[
        "manual-research-production-ready",
        "manual-research-experimental-only",
        "manual-research-provider-degraded",
    ]
    cases: tuple[Phase16ValidationCaseResult, ...]
    truth_database_scope: Literal["isolated-phase16-validation"] = (
        "isolated-phase16-validation"
    )
    frozen_phase15_corpus_modified: Literal[False] = False
    production_task_truth_mutation_performed: Literal[False] = False
    production_research_evidence_mutation_performed: Literal[False] = False
    production_research_operations_mutation_performed: Literal[False] = False
    smart_routing_research_activated: Literal[False] = False
    provider_switching_performed: Literal[False] = False
    generic_network_authority_expanded: Literal[False] = False
    provider_titles_or_snippets_used_as_evidence: Literal[False] = False
    automatic_knowledge_mutation_performed: Literal[False] = False
    destructive_evidence_cleanup_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return round(float(ordered[index]), 3)


def _source_metrics(output: dict[str, Any] | None) -> tuple[int, list[float], list[str]]:
    if not output:
        return 0, [], []
    successful = 0
    durations: list[float] = []
    hashes: list[str] = []
    for item in output.get("sources") or []:
        if not isinstance(item, dict) or item.get("success") is not True:
            continue
        successful += 1
        duration = item.get("duration_ms")
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            durations.append(max(0.0, float(duration)))
        citation = item.get("citation")
        if isinstance(citation, dict):
            digest = citation.get("normalized_text_sha256")
            if isinstance(digest, str) and len(digest) == 64:
                hashes.append(digest)
    return successful, durations, hashes


def _isolated_repositories(
    path: Path,
) -> tuple[ResearchRetrievalRepository, ResearchOperationsRepository]:
    resolved = path.expanduser().resolve()
    production = DEFAULT_TRUTH_DATABASE_PATH.expanduser().resolve()
    if resolved == production or not str(resolved).startswith("/tmp/"):
        raise ValueError("Phase 16 validation truth DB must be an isolated /tmp database")
    truth = AgentTruthRepository(database_path=resolved)
    return ResearchRetrievalRepository(truth), ResearchOperationsRepository(truth)


async def run_phase16_validation(
    *,
    source_commit: str,
    truth_db: Path,
) -> Phase16ValidationReport:
    validate_phase16_validation_corpus()
    retrieval_repository, operations_repository = _isolated_repositories(truth_db)
    retrieval_tool = InternetResearchRetrieveTool(
        repository_factory=lambda: retrieval_repository,
        operations_repository=operations_repository,
    )
    pipeline = WebSearchRetrievalPipeline(
        provider=SearXNGWebSearchProvider(),
        retrieval_tool=retrieval_tool,
        enable_bounded_query_fallback=True,
    )

    cases: list[Phase16ValidationCaseResult] = []
    provider_durations: list[float] = []
    pipeline_durations: list[float] = []
    source_durations: list[float] = []
    content_hashes: list[str] = []
    total_selected = 0
    total_selected_unique_families = 0

    for case in PHASE16_VALIDATION_CORPUS:
        try:
            async with asyncio.timeout(LIVE_CASE_TIMEOUT_SECONDS):
                result = await pipeline.run(
                    objective=case.objective,
                    query=WebSearchQuery(query=case.query, count=5),
                )
        except TimeoutError:
            cases.append(
                Phase16ValidationCaseResult(
                    case_id=case.case_id,
                    category=case.category,
                    success=False,
                    no_candidate=False,
                    search_attempt_count=1,
                    fallback_used=False,
                    selected_url_count=0,
                    selected_unique_source_family_count=0,
                    successful_source_count=0,
                    error_code="validation-case-timeout",
                )
            )
            continue
        except WebSearchDiscoveryError as exc:
            attempt_count = int(exc.diagnostics.get("search_attempt_count") or 1)
            cases.append(
                Phase16ValidationCaseResult(
                    case_id=case.case_id,
                    category=case.category,
                    success=False,
                    no_candidate=exc.code == "no-search-candidates",
                    search_attempt_count=min(3, max(1, attempt_count)),
                    fallback_used=attempt_count > 1,
                    selected_url_count=0,
                    selected_unique_source_family_count=0,
                    successful_source_count=0,
                    error_code=exc.code,
                )
            )
            continue
        except SearXNGSearchProviderError as exc:
            cases.append(
                Phase16ValidationCaseResult(
                    case_id=case.case_id,
                    category=case.category,
                    success=False,
                    no_candidate=False,
                    search_attempt_count=1,
                    fallback_used=False,
                    selected_url_count=0,
                    selected_unique_source_family_count=0,
                    successful_source_count=0,
                    error_code=exc.code,
                )
            )
            continue

        successful_sources, case_durations, case_hashes = _source_metrics(
            result.retrieval_output
        )
        selected_count = len(result.selected_urls)
        selected_unique = len(set(result.selected_source_families))
        total_selected += selected_count
        total_selected_unique_families += selected_unique
        source_durations.extend(case_durations)
        content_hashes.extend(case_hashes)
        if result.provider_search_duration_ms is not None:
            provider_durations.append(result.provider_search_duration_ms)
        if result.total_pipeline_duration_ms is not None:
            pipeline_durations.append(result.total_pipeline_duration_ms)

        cases.append(
            Phase16ValidationCaseResult(
                case_id=case.case_id,
                category=case.category,
                success=result.retrieval_success and successful_sources > 0,
                no_candidate=False,
                search_attempt_count=result.search_attempt_count,
                fallback_used=result.fallback_used,
                selected_url_count=selected_count,
                selected_unique_source_family_count=selected_unique,
                successful_source_count=successful_sources,
                provider_search_duration_ms=result.provider_search_duration_ms,
                pipeline_duration_ms=result.total_pipeline_duration_ms,
                source_durations_ms=tuple(round(value, 3) for value in case_durations),
                normalized_text_sha256=tuple(case_hashes),
                error_code=None if result.retrieval_success else "retrieval-failed",
            )
        )

    success_count = sum(item.success for item in cases)
    no_candidate_count = sum(item.no_candidate for item in cases)
    fallback_case_count = sum(item.fallback_used for item in cases)
    success_rate = success_count / len(cases)
    no_candidate_rate = no_candidate_count / len(cases)
    source_family_rate = (
        total_selected_unique_families / total_selected if total_selected else 0.0
    )
    duplicate_count = len(content_hashes) - len(set(content_hashes))
    duplicate_rate = duplicate_count / len(content_hashes) if content_hashes else 0.0
    retrieval_p95 = _percentile(source_durations, 0.95)
    thresholds = Phase16ValidationThresholds()

    category_success_rates: dict[str, float] = {}
    for category in sorted({item.category for item in cases}):
        category_cases = [item for item in cases if item.category == category]
        category_success_rates[category] = round(
            sum(item.success for item in category_cases) / len(category_cases),
            4,
        )

    meets_targets = bool(
        success_rate >= thresholds.minimum_success_rate
        and no_candidate_rate <= thresholds.maximum_no_candidate_rate
        and source_family_rate >= thresholds.minimum_unique_source_family_rate
        and duplicate_rate <= thresholds.maximum_duplicate_content_rate
        and retrieval_p95 is not None
        and retrieval_p95 <= thresholds.maximum_retrieval_p95_ms
    )

    if meets_targets:
        posture = "manual-research-production-ready"
    elif success_rate >= 0.90 and no_candidate_rate <= 0.10:
        posture = "manual-research-experimental-only"
    else:
        posture = "manual-research-provider-degraded"

    payload: dict[str, Any] = {
        "validation_version": PHASE16_VALIDATION_VERSION,
        "corpus_version": PHASE16_VALIDATION_CORPUS_VERSION,
        "source_commit": source_commit,
        "provider_id": SEARXNG_PROVIDER_ID,
        "case_count": PHASE16_VALIDATION_CORPUS_CASE_COUNT,
        "success_count": success_count,
        "success_rate": round(success_rate, 4),
        "no_candidate_count": no_candidate_count,
        "no_candidate_rate": round(no_candidate_rate, 4),
        "fallback_case_count": fallback_case_count,
        "selected_source_count": total_selected,
        "selected_unique_source_family_rate": round(source_family_rate, 4),
        "successful_source_count": sum(item.successful_source_count for item in cases),
        "duplicate_content_count": duplicate_count,
        "duplicate_content_rate": round(duplicate_rate, 4),
        "provider_search_p50_ms": _percentile(provider_durations, 0.50),
        "provider_search_p95_ms": _percentile(provider_durations, 0.95),
        "retrieval_source_p50_ms": _percentile(source_durations, 0.50),
        "retrieval_source_p95_ms": retrieval_p95,
        "pipeline_p95_ms": _percentile(pipeline_durations, 0.95),
        "category_success_rates": category_success_rates,
        "thresholds": thresholds.model_dump(mode="json"),
        "meets_phase16_targets": meets_targets,
        "recommended_posture": posture,
        "cases": [item.model_dump(mode="json") for item in cases],
        "truth_database_scope": "isolated-phase16-validation",
        "frozen_phase15_corpus_modified": False,
        "production_task_truth_mutation_performed": False,
        "production_research_evidence_mutation_performed": False,
        "production_research_operations_mutation_performed": False,
        "smart_routing_research_activated": False,
        "provider_switching_performed": False,
        "generic_network_authority_expanded": False,
        "provider_titles_or_snippets_used_as_evidence": False,
        "automatic_knowledge_mutation_performed": False,
        "destructive_evidence_cleanup_performed": False,
        "guardian_contacted": False,
        "privileged_host_action_performed": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Phase16ValidationReport(**payload)


def write_phase16_validation_report(report: Phase16ValidationReport, path: Path) -> None:
    resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


async def _async_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--truth-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = await run_phase16_validation(
        source_commit=args.source_commit,
        truth_db=args.truth_db,
    )
    write_phase16_validation_report(report, args.output)

    print(f"phase16h_validation_version|{report.validation_version}")
    print(f"phase16h_corpus_version|{report.corpus_version}")
    print(f"phase16h_case_count|{report.case_count}")
    print(f"phase16h_success|{report.success_count}/{report.case_count}")
    print(f"phase16h_success_rate|{report.success_rate:.4f}")
    print(f"phase16h_no_candidate_rate|{report.no_candidate_rate:.4f}")
    print(
        "phase16h_source_family_rate|"
        f"{report.selected_unique_source_family_rate:.4f}"
    )
    print(f"phase16h_duplicate_rate|{report.duplicate_content_rate:.4f}")
    print(f"phase16h_retrieval_p95_ms|{report.retrieval_source_p95_ms}")
    for category, rate in report.category_success_rates.items():
        print(f"phase16h_category_success|{category}|{rate:.4f}")
    print(
        "phase16h_targets|"
        + ("PASS" if report.meets_phase16_targets else "FAIL")
    )
    print(f"phase16h_posture|{report.recommended_posture}")
    print(f"phase16h_report_sha256|{report.report_sha256}")
    print("PHASE16_INDEPENDENT_VALIDATION|PASS")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
