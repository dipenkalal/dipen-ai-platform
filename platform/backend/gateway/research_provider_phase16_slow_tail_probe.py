from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import DEFAULT_TRUTH_DATABASE_PATH, AgentTruthRepository
from gateway.internet_transport import BoundedInternetRetriever
from gateway.research_operations_repository import ResearchOperationsRepository
from gateway.research_provider_live_benchmark import MAXIMUM_LIVE_RETRIEVAL_P95_MS
from gateway.research_provider_phase16_validation_corpus import (
    PHASE16_VALIDATION_CORPUS,
    PHASE16_VALIDATION_CORPUS_VERSION,
    Phase16ValidationCorpusCase,
    validate_phase16_validation_corpus,
)
from gateway.research_retrieval_latency_probe_e2 import (
    DetailedLatencyTracingRetriever,
    RetrievalDetailTrace,
    SourceEndToEndTrace,
    build_source_records,
    nearest_rank_percentile,
    summarize_fetch_components,
    summarize_retriever_stages,
)
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from gateway.searxng_search_provider import (
    SEARXNG_PROVIDER_ID,
    SearXNGSearchProviderError,
    SearXNGWebSearchProvider,
)
from gateway.web_search_discovery import (
    WebSearchDiscoveryError,
    WebSearchRetrievalPipeline,
)
from gateway.web_search_provider import WebSearchQuery
from tools.internet_research_tools import InternetResearchRetrieveTool

PHASE16_H1_PROBE_VERSION: Literal["phase16h1.1"] = "phase16h1.1"
PHASE16_H1_REPEAT_COUNT: Literal[3] = 3
PHASE16_H1_TARGET_CASE_IDS: tuple[str, ...] = (
    "p16-usgs-earthquake-magnitude",
    "p16-overlay-filesystems",
    "p16-rfc9293-tcp",
    "p16-dns-over-https",
)
PHASE16_H1_CASE_TIMEOUT_SECONDS = 60.0


class Phase16H1TargetedTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    iteration: int = Field(ge=1, le=3)
    trace: RetrievalDetailTrace


class Phase16H1TargetedSourceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    iteration: int = Field(ge=1, le=3)
    record: SourceEndToEndTrace


class Phase16H1RunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    iteration: int = Field(ge=1, le=3)
    success: bool
    provider_search_duration_ms: float | None = Field(default=None, ge=0)
    total_pipeline_duration_ms: float | None = Field(default=None, ge=0)
    source_record_count: int = Field(ge=0, le=3)
    successful_source_count: int = Field(ge=0, le=3)
    above_target_source_count: int = Field(ge=0, le=3)
    source_p50_ms: float | None = Field(default=None, ge=0)
    source_p95_ms: float | None = Field(default=None, ge=0)
    source_max_ms: float | None = Field(default=None, ge=0)
    error_code: str | None = None


class Phase16H1CaseSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    successful_runs: int = Field(ge=0, le=3)
    source_record_count: int = Field(ge=0, le=9)
    successful_source_count: int = Field(ge=0, le=9)
    above_target_source_count: int = Field(ge=0, le=9)
    source_p50_ms: float | None = Field(default=None, ge=0)
    source_p95_ms: float | None = Field(default=None, ge=0)
    source_max_ms: float | None = Field(default=None, ge=0)
    run_p95_above_target_count: int = Field(ge=0, le=3)


class Phase16H1SlowSourceDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    iteration: int = Field(ge=1, le=3)
    source_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_family: str | None = None
    duration_ms: float = Field(ge=0)
    attempt_count: int = Field(ge=1)
    transient_retry_count: int = Field(ge=0)
    dominant_component: str
    component_durations_ms: dict[str, float]


class Phase16H1Report(BaseModel):
    model_config = ConfigDict(frozen=True)

    probe_version: Literal["phase16h1.1"] = PHASE16_H1_PROBE_VERSION
    corpus_version: Literal["phase16-validation-corpus-v1"] = (
        "phase16-validation-corpus-v1"
    )
    source_commit: str
    provider_id: Literal["searxng-local-v1"] = SEARXNG_PROVIDER_ID
    target_case_ids: tuple[str, ...]
    repeat_count: Literal[3] = PHASE16_H1_REPEAT_COUNT
    run_count: Literal[12] = 12
    successful_run_count: int = Field(ge=0, le=12)
    source_record_count: int = Field(ge=0, le=36)
    successful_source_record_count: int = Field(ge=0, le=36)
    above_target_source_count: int = Field(ge=0, le=36)
    run_p95_above_target_count: int = Field(ge=0, le=12)
    successful_source_p50_ms: float | None = Field(default=None, ge=0)
    successful_source_p95_ms: float | None = Field(default=None, ge=0)
    successful_source_max_ms: float | None = Field(default=None, ge=0)
    frozen_retrieval_source_target_ms: float = MAXIMUM_LIVE_RETRIEVAL_P95_MS
    retriever_stage_p50_ms: dict[str, float]
    retriever_stage_p95_ms: dict[str, float]
    fetch_component_p50_ms: dict[str, float]
    fetch_component_p95_ms: dict[str, float]
    dominant_fetch_component_by_p95: str
    case_summaries: tuple[Phase16H1CaseSummary, ...]
    runs: tuple[Phase16H1RunResult, ...]
    slow_sources: tuple[Phase16H1SlowSourceDiagnostic, ...]
    traces: tuple[Phase16H1TargetedTrace, ...]
    source_records: tuple[Phase16H1TargetedSourceRecord, ...]
    truth_database_scope: Literal["isolated-phase16-h1-diagnostic"] = (
        "isolated-phase16-h1-diagnostic"
    )
    target_corpus_modified: Literal[False] = False
    provider_configuration_mutated: Literal[False] = False
    transport_behavior_mutated: Literal[False] = False
    transport_timeout_mutated: Literal[False] = False
    retry_policy_mutated: Literal[False] = False
    concurrency_policy_mutated: Literal[False] = False
    production_task_truth_mutation_performed: Literal[False] = False
    production_research_evidence_mutation_performed: Literal[False] = False
    production_research_operations_mutation_performed: Literal[False] = False
    smart_routing_research_activated: Literal[False] = False
    provider_switching_performed: Literal[False] = False
    generic_network_authority_expanded: Literal[False] = False
    provider_titles_or_snippets_recorded: Literal[False] = False
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
        raise ValueError("Phase 16H.1 truth DB must be an isolated /tmp database")
    truth = AgentTruthRepository(database_path=resolved)
    return ResearchRetrievalRepository(truth), ResearchOperationsRepository(truth)


def _target_cases() -> tuple[Phase16ValidationCorpusCase, ...]:
    validate_phase16_validation_corpus()
    by_id = {case.case_id: case for case in PHASE16_VALIDATION_CORPUS}
    missing = [case_id for case_id in PHASE16_H1_TARGET_CASE_IDS if case_id not in by_id]
    if missing:
        raise ValueError(f"Phase 16H.1 target cases missing: {missing}")
    return tuple(by_id[case_id] for case_id in PHASE16_H1_TARGET_CASE_IDS)


def _max_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(max(values), 3)


def _component_totals(
    traces: list[RetrievalDetailTrace],
    record: SourceEndToEndTrace,
) -> dict[str, float]:
    matching = [
        trace for trace in traces if trace.source_key_sha256 == record.source_key_sha256
    ]
    components = {
        "dns": sum(trace.dns_ms for trace in matching),
        "connect-tls": sum(trace.connect_tls_ms for trace in matching),
        "request-write": sum(trace.request_write_ms for trace in matching),
        "response-header": sum(trace.response_header_ms for trace in matching),
        "response-body": sum(trace.response_body_ms for trace in matching),
        "close-wait": sum(trace.close_wait_ms for trace in matching),
        "fetch-uninstrumented": sum(
            trace.fetch_uninstrumented_ms for trace in matching
        ),
        "retriever-uninstrumented": sum(
            trace.retriever_uninstrumented_ms for trace in matching
        ),
        "retry-backoff": record.retry_backoff_ms,
        "tool-overhead": record.tool_overhead_excluding_backoff_ms,
    }
    return {name: round(float(value), 3) for name, value in components.items()}


def _slow_source_diagnostic(
    *,
    case_id: str,
    category: str,
    iteration: int,
    record: SourceEndToEndTrace,
    traces: list[RetrievalDetailTrace],
) -> Phase16H1SlowSourceDiagnostic:
    components = _component_totals(traces, record)
    dominant = max(components, key=lambda name: components[name])
    return Phase16H1SlowSourceDiagnostic(
        case_id=case_id,
        category=category,
        iteration=iteration,
        source_key_sha256=record.source_key_sha256,
        source_family=record.source_family,
        duration_ms=record.duration_ms,
        attempt_count=record.attempt_count,
        transient_retry_count=record.transient_retry_count,
        dominant_component=dominant,
        component_durations_ms=components,
    )


def _case_summaries(
    runs: list[Phase16H1RunResult],
    records: list[Phase16H1TargetedSourceRecord],
) -> tuple[Phase16H1CaseSummary, ...]:
    summaries: list[Phase16H1CaseSummary] = []
    for case in _target_cases():
        case_runs = [item for item in runs if item.case_id == case.case_id]
        case_records = [
            item.record for item in records if item.case_id == case.case_id
        ]
        successful_records = [item for item in case_records if item.success]
        durations = [item.duration_ms for item in successful_records]
        summaries.append(
            Phase16H1CaseSummary(
                case_id=case.case_id,
                category=case.category,
                successful_runs=sum(item.success for item in case_runs),
                source_record_count=len(case_records),
                successful_source_count=len(successful_records),
                above_target_source_count=sum(
                    item.duration_ms > MAXIMUM_LIVE_RETRIEVAL_P95_MS
                    for item in successful_records
                ),
                source_p50_ms=nearest_rank_percentile(durations, 0.50),
                source_p95_ms=nearest_rank_percentile(durations, 0.95),
                source_max_ms=_max_or_none(durations),
                run_p95_above_target_count=sum(
                    item.source_p95_ms is not None
                    and item.source_p95_ms > MAXIMUM_LIVE_RETRIEVAL_P95_MS
                    for item in case_runs
                ),
            )
        )
    return tuple(summaries)


async def run_phase16h1_probe(
    *,
    source_commit: str,
    truth_db: Path,
) -> Phase16H1Report:
    retrieval_repository, operations_repository = _isolated_repositories(truth_db)
    tracer = DetailedLatencyTracingRetriever()
    retrieval_tool = InternetResearchRetrieveTool(
        retriever=cast(BoundedInternetRetriever, tracer),
        repository_factory=lambda: retrieval_repository,
        operations_repository=operations_repository,
    )
    pipeline = WebSearchRetrievalPipeline(
        provider=SearXNGWebSearchProvider(),
        retrieval_tool=retrieval_tool,
        enable_bounded_query_fallback=True,
    )

    runs: list[Phase16H1RunResult] = []
    targeted_traces: list[Phase16H1TargetedTrace] = []
    targeted_records: list[Phase16H1TargetedSourceRecord] = []
    slow_sources: list[Phase16H1SlowSourceDiagnostic] = []

    for case in _target_cases():
        for iteration in range(1, PHASE16_H1_REPEAT_COUNT + 1):
            trace_start = len(tracer.records)
            error_code: str | None = None
            try:
                async with asyncio.timeout(PHASE16_H1_CASE_TIMEOUT_SECONDS):
                    result = await pipeline.run(
                        objective=case.objective,
                        query=WebSearchQuery(query=case.query, count=5),
                    )
            except TimeoutError:
                error_code = "h1-case-timeout"
                result = None
            except WebSearchDiscoveryError as exc:
                error_code = exc.code
                result = None
            except SearXNGSearchProviderError as exc:
                error_code = exc.code
                result = None

            case_traces = tracer.records[trace_start:]
            for trace in case_traces:
                targeted_traces.append(
                    Phase16H1TargetedTrace(
                        case_id=case.case_id,
                        category=case.category,
                        iteration=iteration,
                        trace=trace,
                    )
                )

            if result is None:
                runs.append(
                    Phase16H1RunResult(
                        case_id=case.case_id,
                        category=case.category,
                        iteration=iteration,
                        success=False,
                        source_record_count=0,
                        successful_source_count=0,
                        above_target_source_count=0,
                        error_code=error_code,
                    )
                )
                continue

            source_records = build_source_records(result.retrieval_output, case_traces)
            successful_records = [record for record in source_records if record.success]
            durations = [record.duration_ms for record in successful_records]

            for record in source_records:
                targeted_records.append(
                    Phase16H1TargetedSourceRecord(
                        case_id=case.case_id,
                        category=case.category,
                        iteration=iteration,
                        record=record,
                    )
                )
                if record.success and record.duration_ms > MAXIMUM_LIVE_RETRIEVAL_P95_MS:
                    slow_sources.append(
                        _slow_source_diagnostic(
                            case_id=case.case_id,
                            category=case.category,
                            iteration=iteration,
                            record=record,
                            traces=case_traces,
                        )
                    )

            runs.append(
                Phase16H1RunResult(
                    case_id=case.case_id,
                    category=case.category,
                    iteration=iteration,
                    success=result.retrieval_success and bool(successful_records),
                    provider_search_duration_ms=result.provider_search_duration_ms,
                    total_pipeline_duration_ms=result.total_pipeline_duration_ms,
                    source_record_count=len(source_records),
                    successful_source_count=len(successful_records),
                    above_target_source_count=sum(
                        record.duration_ms > MAXIMUM_LIVE_RETRIEVAL_P95_MS
                        for record in successful_records
                    ),
                    source_p50_ms=nearest_rank_percentile(durations, 0.50),
                    source_p95_ms=nearest_rank_percentile(durations, 0.95),
                    source_max_ms=_max_or_none(durations),
                    error_code=None if result.retrieval_success else "retrieval-failed",
                )
            )

    all_traces = [item.trace for item in targeted_traces]
    all_records = [item.record for item in targeted_records]
    successful_records = [item for item in all_records if item.success]
    successful_durations = [item.duration_ms for item in successful_records]

    retriever_p50, retriever_p95 = summarize_retriever_stages(all_traces)
    fetch_p50, fetch_p95, dominant_fetch = summarize_fetch_components(all_traces)

    payload: dict[str, Any] = {
        "probe_version": PHASE16_H1_PROBE_VERSION,
        "corpus_version": PHASE16_VALIDATION_CORPUS_VERSION,
        "source_commit": source_commit,
        "provider_id": SEARXNG_PROVIDER_ID,
        "target_case_ids": PHASE16_H1_TARGET_CASE_IDS,
        "repeat_count": PHASE16_H1_REPEAT_COUNT,
        "run_count": len(runs),
        "successful_run_count": sum(item.success for item in runs),
        "source_record_count": len(all_records),
        "successful_source_record_count": len(successful_records),
        "above_target_source_count": sum(
            item.duration_ms > MAXIMUM_LIVE_RETRIEVAL_P95_MS
            for item in successful_records
        ),
        "run_p95_above_target_count": sum(
            item.source_p95_ms is not None
            and item.source_p95_ms > MAXIMUM_LIVE_RETRIEVAL_P95_MS
            for item in runs
        ),
        "successful_source_p50_ms": nearest_rank_percentile(
            successful_durations, 0.50
        ),
        "successful_source_p95_ms": nearest_rank_percentile(
            successful_durations, 0.95
        ),
        "successful_source_max_ms": _max_or_none(successful_durations),
        "frozen_retrieval_source_target_ms": MAXIMUM_LIVE_RETRIEVAL_P95_MS,
        "retriever_stage_p50_ms": retriever_p50,
        "retriever_stage_p95_ms": retriever_p95,
        "fetch_component_p50_ms": fetch_p50,
        "fetch_component_p95_ms": fetch_p95,
        "dominant_fetch_component_by_p95": dominant_fetch,
        "case_summaries": [
            item.model_dump(mode="json") for item in _case_summaries(runs, targeted_records)
        ],
        "runs": [item.model_dump(mode="json") for item in runs],
        "slow_sources": [item.model_dump(mode="json") for item in slow_sources],
        "traces": [item.model_dump(mode="json") for item in targeted_traces],
        "source_records": [
            item.model_dump(mode="json") for item in targeted_records
        ],
        "truth_database_scope": "isolated-phase16-h1-diagnostic",
        "target_corpus_modified": False,
        "provider_configuration_mutated": False,
        "transport_behavior_mutated": False,
        "transport_timeout_mutated": False,
        "retry_policy_mutated": False,
        "concurrency_policy_mutated": False,
        "production_task_truth_mutation_performed": False,
        "production_research_evidence_mutation_performed": False,
        "production_research_operations_mutation_performed": False,
        "smart_routing_research_activated": False,
        "provider_switching_performed": False,
        "generic_network_authority_expanded": False,
        "provider_titles_or_snippets_recorded": False,
        "automatic_knowledge_mutation_performed": False,
        "destructive_evidence_cleanup_performed": False,
        "guardian_contacted": False,
        "privileged_host_action_performed": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Phase16H1Report(**payload)


def write_phase16h1_report(report: Phase16H1Report, path: Path) -> None:
    resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


async def _async_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--truth-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = await run_phase16h1_probe(
        source_commit=args.source_commit,
        truth_db=args.truth_db,
    )
    write_phase16h1_report(report, args.output)

    print(f"phase16h1_probe_version|{report.probe_version}")
    print(f"phase16h1_target_case_count|{len(report.target_case_ids)}")
    print(f"phase16h1_repeat_count|{report.repeat_count}")
    print(f"phase16h1_run_count|{report.run_count}")
    print(f"phase16h1_successful_runs|{report.successful_run_count}")
    print(f"phase16h1_source_record_count|{report.source_record_count}")
    print(
        "phase16h1_successful_source_record_count|"
        f"{report.successful_source_record_count}"
    )
    print(f"phase16h1_above_target_source_count|{report.above_target_source_count}")
    print(f"phase16h1_run_p95_above_target_count|{report.run_p95_above_target_count}")
    print(f"phase16h1_source_p50_ms|{report.successful_source_p50_ms}")
    print(f"phase16h1_source_p95_ms|{report.successful_source_p95_ms}")
    print(f"phase16h1_source_max_ms|{report.successful_source_max_ms}")
    print(f"phase16h1_dominant_fetch_component|{report.dominant_fetch_component_by_p95}")
    for summary in report.case_summaries:
        print(
            "phase16h1_case|"
            f"{summary.case_id}|runs={summary.successful_runs}/3|"
            f"sources={summary.successful_source_count}|"
            f"above_target={summary.above_target_source_count}|"
            f"run_p95_above_target={summary.run_p95_above_target_count}|"
            f"p95_ms={summary.source_p95_ms}|max_ms={summary.source_max_ms}"
        )
    for slow in report.slow_sources:
        print(
            "phase16h1_slow_source|"
            f"{slow.case_id}|iteration={slow.iteration}|"
            f"family={slow.source_family}|duration_ms={slow.duration_ms}|"
            f"dominant={slow.dominant_component}|"
            f"retries={slow.transient_retry_count}"
        )
    print(f"phase16h1_report_sha256|{report.report_sha256}")
    print("PHASE16_H1_SLOW_TAIL_PROBE|PASS")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
