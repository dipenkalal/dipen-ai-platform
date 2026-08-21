from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import DEFAULT_TRUTH_DATABASE_PATH, AgentTruthRepository
from gateway.research_operations_repository import ResearchOperationsRepository
from gateway.research_provider_corpus import (
    PHASE15_CORPUS_VERSION,
    PHASE15_PROVIDER_CORPUS,
    validate_phase15_provider_corpus,
)
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from gateway.searxng_search_provider import (
    SEARXNG_PROVIDER_ID,
    SearXNGSearchProviderError,
    SearXNGWebSearchProvider,
)
from gateway.web_search_discovery import (
    WebSearchAttemptDiagnostic,
    WebSearchDiscoveryError,
    WebSearchRetrievalPipeline,
)
from gateway.web_search_provider import WebSearchQuery
from tools.internet_research_tools import InternetResearchRetrieveTool

PHASE16_DIAGNOSTIC_VERSION: Literal["phase16a.1"] = "phase16a.1"
PHASE16_CASE_TIMEOUT_SECONDS = 60.0

FailureClass = Literal[
    "provider-zero-results",
    "dap-filtered-zero",
    "provider-transport-error",
    "retrieval-failed",
    "benchmark-case-timeout",
    "unclassified-no-candidate",
    "success",
]


class Phase16AttemptDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0, le=3)
    provider_result_count: int | None = Field(default=None, ge=0)
    considered_result_count: int | None = Field(default=None, ge=0)
    invalid_candidate_count: int | None = Field(default=None, ge=0)
    policy_rejected_candidate_count: int | None = Field(default=None, ge=0)
    provider_zero_results: bool | None = None
    admissible_candidate_zero_after_filtering: bool | None = None
    outcome: Literal["selected", "no-candidate"]
    provider_titles_recorded: Literal[False] = False
    provider_snippets_recorded: Literal[False] = False


class Phase16CaseDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    query: str
    failure_class: FailureClass
    success: bool
    search_attempt_count: int = Field(ge=1, le=3)
    fallback_used: bool
    attempts: tuple[Phase16AttemptDiagnostic, ...] = ()
    selected_url_count: int = Field(ge=0, le=3)
    successful_source_count: int = Field(ge=0, le=3)
    provider_search_duration_ms: float | None = Field(default=None, ge=0)
    retrieval_duration_ms: float | None = Field(default=None, ge=0)
    total_pipeline_duration_ms: float | None = Field(default=None, ge=0)
    source_durations_ms: tuple[float, ...] = ()
    error_code: str | None = None
    provider_titles_or_snippets_recorded: Literal[False] = False


class Phase16DiagnosticReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    diagnostic_version: Literal["phase16a.1"] = PHASE16_DIAGNOSTIC_VERSION
    corpus_version: str = PHASE15_CORPUS_VERSION
    source_commit: str
    provider_id: Literal["searxng-local-v1"] = SEARXNG_PROVIDER_ID
    case_count: int = Field(ge=30)
    failure_class_counts: dict[str, int]
    category_failure_counts: dict[str, dict[str, int]]
    cases: tuple[Phase16CaseDiagnostic, ...]
    truth_database_scope: Literal["isolated-diagnostic"] = "isolated-diagnostic"
    provider_configuration_mutated: Literal[False] = False
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


def _isolated_repositories(
    path: Path,
) -> tuple[ResearchRetrievalRepository, ResearchOperationsRepository]:
    resolved = path.expanduser().resolve()
    production = DEFAULT_TRUTH_DATABASE_PATH.expanduser().resolve()
    if resolved == production or not str(resolved).startswith("/tmp/"):
        raise ValueError("Phase 16 diagnostic truth DB must be an isolated /tmp database")
    truth = AgentTruthRepository(database_path=resolved)
    return ResearchRetrievalRepository(truth), ResearchOperationsRepository(truth)


def _attempt_from_mapping(item: dict[str, Any]) -> Phase16AttemptDiagnostic:
    return Phase16AttemptDiagnostic(
        query=str(item.get("query") or ""),
        candidate_count=max(0, int(item.get("candidate_count") or 0)),
        selected_count=max(0, min(3, int(item.get("selected_count") or 0))),
        provider_result_count=_optional_nonnegative_int(item.get("provider_result_count")),
        considered_result_count=_optional_nonnegative_int(
            item.get("considered_result_count")
        ),
        invalid_candidate_count=_optional_nonnegative_int(
            item.get("invalid_candidate_count")
        ),
        policy_rejected_candidate_count=_optional_nonnegative_int(
            item.get("policy_rejected_candidate_count")
        ),
        provider_zero_results=_optional_bool(item.get("provider_zero_results")),
        admissible_candidate_zero_after_filtering=_optional_bool(
            item.get("admissible_candidate_zero_after_filtering")
        ),
        outcome="selected" if item.get("outcome") == "selected" else "no-candidate",
    )


def _attempt_from_model(item: WebSearchAttemptDiagnostic) -> Phase16AttemptDiagnostic:
    return Phase16AttemptDiagnostic(
        query=item.query,
        candidate_count=item.candidate_count,
        selected_count=item.selected_count,
        provider_result_count=item.provider_result_count,
        considered_result_count=item.considered_result_count,
        invalid_candidate_count=item.invalid_candidate_count,
        policy_rejected_candidate_count=item.policy_rejected_candidate_count,
        provider_zero_results=item.provider_zero_results,
        admissible_candidate_zero_after_filtering=(
            item.admissible_candidate_zero_after_filtering
        ),
        outcome=item.outcome,
    )


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(0, value)


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def classify_no_candidate_attempts(
    attempts: tuple[Phase16AttemptDiagnostic, ...],
) -> FailureClass:
    if attempts and all(item.provider_zero_results is True for item in attempts):
        return "provider-zero-results"
    if any(
        item.admissible_candidate_zero_after_filtering is True
        or (
            (item.provider_result_count or 0) > 0
            and item.selected_count == 0
            and (
                (item.invalid_candidate_count or 0)
                + (item.policy_rejected_candidate_count or 0)
            )
            > 0
        )
        for item in attempts
    ):
        return "dap-filtered-zero"
    return "unclassified-no-candidate"


def _successful_source_metrics(output: dict[str, Any] | None) -> tuple[int, tuple[float, ...]]:
    if not output:
        return 0, ()
    successful = 0
    durations: list[float] = []
    for item in output.get("sources") or []:
        if not isinstance(item, dict) or item.get("success") is not True:
            continue
        successful += 1
        duration = item.get("duration_ms")
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            durations.append(round(max(0.0, float(duration)), 3))
    return successful, tuple(durations)


async def run_phase16_diagnostic(
    *,
    source_commit: str,
    truth_db: Path,
) -> Phase16DiagnosticReport:
    validate_phase15_provider_corpus()
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

    cases: list[Phase16CaseDiagnostic] = []

    for case in PHASE15_PROVIDER_CORPUS:
        try:
            async with asyncio.timeout(PHASE16_CASE_TIMEOUT_SECONDS):
                result = await pipeline.run(
                    objective=case.objective,
                    query=WebSearchQuery(query=case.query, count=5),
                )
        except TimeoutError:
            cases.append(
                Phase16CaseDiagnostic(
                    case_id=case.case_id,
                    category=case.category,
                    query=case.query,
                    failure_class="benchmark-case-timeout",
                    success=False,
                    search_attempt_count=1,
                    fallback_used=False,
                    selected_url_count=0,
                    successful_source_count=0,
                    error_code="benchmark-case-timeout",
                )
            )
            continue
        except WebSearchDiscoveryError as exc:
            raw_attempts = exc.diagnostics.get("attempts")
            attempt_values = (
                tuple(
                    _attempt_from_mapping(item)
                    for item in raw_attempts
                    if isinstance(item, dict)
                )
                if isinstance(raw_attempts, list)
                else ()
            )
            attempt_count = max(
                1,
                min(3, int(exc.diagnostics.get("search_attempt_count") or 1)),
            )
            cases.append(
                Phase16CaseDiagnostic(
                    case_id=case.case_id,
                    category=case.category,
                    query=case.query,
                    failure_class=classify_no_candidate_attempts(attempt_values),
                    success=False,
                    search_attempt_count=attempt_count,
                    fallback_used=attempt_count > 1,
                    attempts=attempt_values,
                    selected_url_count=0,
                    successful_source_count=0,
                    error_code=exc.code,
                )
            )
            continue
        except SearXNGSearchProviderError as exc:
            cases.append(
                Phase16CaseDiagnostic(
                    case_id=case.case_id,
                    category=case.category,
                    query=case.query,
                    failure_class="provider-transport-error",
                    success=False,
                    search_attempt_count=1,
                    fallback_used=False,
                    selected_url_count=0,
                    successful_source_count=0,
                    error_code=exc.code,
                )
            )
            continue

        successful_sources, source_durations = _successful_source_metrics(
            result.retrieval_output
        )
        success = result.retrieval_success and successful_sources > 0
        cases.append(
            Phase16CaseDiagnostic(
                case_id=case.case_id,
                category=case.category,
                query=case.query,
                failure_class="success" if success else "retrieval-failed",
                success=success,
                search_attempt_count=result.search_attempt_count,
                fallback_used=result.fallback_used,
                attempts=tuple(
                    _attempt_from_model(item) for item in result.search_attempts
                ),
                selected_url_count=len(result.selected_urls),
                successful_source_count=successful_sources,
                provider_search_duration_ms=result.provider_search_duration_ms,
                retrieval_duration_ms=result.retrieval_duration_ms,
                total_pipeline_duration_ms=result.total_pipeline_duration_ms,
                source_durations_ms=source_durations,
                error_code=None if success else "retrieval-failed",
            )
        )

    failure_counts = Counter(item.failure_class for item in cases)
    category_counts: dict[str, Counter[str]] = {}
    for item in cases:
        category_counts.setdefault(item.category, Counter())[item.failure_class] += 1

    payload: dict[str, Any] = {
        "diagnostic_version": PHASE16_DIAGNOSTIC_VERSION,
        "corpus_version": PHASE15_CORPUS_VERSION,
        "source_commit": source_commit,
        "provider_id": SEARXNG_PROVIDER_ID,
        "case_count": len(cases),
        "failure_class_counts": dict(sorted(failure_counts.items())),
        "category_failure_counts": {
            category: dict(sorted(counts.items()))
            for category, counts in sorted(category_counts.items())
        },
        "cases": [item.model_dump(mode="json") for item in cases],
        "truth_database_scope": "isolated-diagnostic",
        "provider_configuration_mutated": False,
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
    return Phase16DiagnosticReport(**payload)


def write_phase16_diagnostic(report: Phase16DiagnosticReport, path: Path) -> None:
    resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


async def _async_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--truth-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = await run_phase16_diagnostic(
        source_commit=args.source_commit,
        truth_db=args.truth_db,
    )
    write_phase16_diagnostic(report, args.output)
    print(f"phase16_diagnostic_version|{report.diagnostic_version}")
    print(f"phase16_case_count|{report.case_count}")
    for failure_class, count in sorted(report.failure_class_counts.items()):
        print(f"phase16_failure_class|{failure_class}|{count}")
    print(f"phase16_report_sha256|{report.report_sha256}")
    print("PHASE16_FAILURE_TAXONOMY|PASS")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
