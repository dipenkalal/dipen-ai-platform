from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_repository import DEFAULT_TRUTH_DATABASE_PATH, AgentTruthRepository
from gateway.internet_destination_policy import (
    InternetDestinationDecision,
    InternetDestinationIntent,
    InternetDestinationPolicy,
    InternetDestinationPreflightDecision,
    InternetDestinationRequest,
)
from gateway.internet_transport import (
    BoundedInternetRetriever,
    InternetDNSResolution,
    InternetRetrievalResult,
    InternetTransportError,
    PinnedHTTPSFetcher,
    SystemInternetDNSResolver,
)
from gateway.research_operations_repository import ResearchOperationsRepository
from gateway.research_provider_corpus import (
    PHASE15_CORPUS_VERSION,
    PHASE15_PROVIDER_CORPUS,
    validate_phase15_provider_corpus,
)
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from gateway.research_source_quality import canonical_source_family
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

PHASE16_RETRIEVAL_LATENCY_VERSION: Literal["phase16e1.1"] = "phase16e1.1"
PHASE16_RETRIEVAL_CASE_TIMEOUT_SECONDS = 60.0

TimerProvider = Any


class _TimingAccumulator:
    def __init__(self) -> None:
        self.preflight_ms = 0.0
        self.dns_ms = 0.0
        self.admission_ms = 0.0
        self.fetch_ms = 0.0
        self.preflight_count = 0
        self.dns_count = 0
        self.admission_count = 0
        self.fetch_count = 0


class _TimedPolicy:
    def __init__(
        self,
        delegate: InternetDestinationPolicy,
        accumulator: _TimingAccumulator,
        timer: TimerProvider,
    ) -> None:
        self._delegate = delegate
        self._accumulator = accumulator
        self._timer = timer

    def preflight(
        self,
        intent: InternetDestinationIntent,
    ) -> InternetDestinationPreflightDecision:
        started = self._timer()
        try:
            return self._delegate.preflight(intent)
        finally:
            self._accumulator.preflight_ms += _elapsed_ms(self._timer, started)
            self._accumulator.preflight_count += 1

    def evaluate(self, request: InternetDestinationRequest) -> InternetDestinationDecision:
        started = self._timer()
        try:
            return self._delegate.evaluate(request)
        finally:
            self._accumulator.admission_ms += _elapsed_ms(self._timer, started)
            self._accumulator.admission_count += 1


class _TimedResolver:
    def __init__(
        self,
        delegate: SystemInternetDNSResolver,
        accumulator: _TimingAccumulator,
        timer: TimerProvider,
    ) -> None:
        self._delegate = delegate
        self._accumulator = accumulator
        self._timer = timer

    async def resolve(self, preflight: Any) -> InternetDNSResolution:
        started = self._timer()
        try:
            return await self._delegate.resolve(preflight)
        finally:
            self._accumulator.dns_ms += _elapsed_ms(self._timer, started)
            self._accumulator.dns_count += 1


class _TimedFetcher:
    def __init__(
        self,
        delegate: PinnedHTTPSFetcher,
        accumulator: _TimingAccumulator,
        timer: TimerProvider,
    ) -> None:
        self._delegate = delegate
        self._accumulator = accumulator
        self._timer = timer

    async def fetch(self, admission: Any) -> Any:
        started = self._timer()
        try:
            return await self._delegate.fetch(admission)
        finally:
            self._accumulator.fetch_ms += _elapsed_ms(self._timer, started)
            self._accumulator.fetch_count += 1


class RetrievalStageTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_family: str | None = None
    success: bool
    error_code: str | None = None
    total_ms: float = Field(ge=0)
    preflight_ms: float = Field(ge=0)
    dns_ms: float = Field(ge=0)
    admission_ms: float = Field(ge=0)
    fetch_ms: float = Field(ge=0)
    uninstrumented_overhead_ms: float = Field(ge=0)
    preflight_count: int = Field(ge=0)
    dns_count: int = Field(ge=0)
    admission_count: int = Field(ge=0)
    fetch_count: int = Field(ge=0)
    redirect_hop_count: int = Field(ge=0, le=4)


class LatencyTracingRetriever:
    """Diagnostic-only wrapper around the sealed production retriever."""

    def __init__(self, *, timer_provider: TimerProvider | None = None) -> None:
        self._timer = timer_provider or time.perf_counter
        self.records: list[RetrievalStageTrace] = []

    async def retrieve(
        self,
        url: str,
        *,
        method: Literal["GET", "HEAD"] = "GET",
    ) -> InternetRetrievalResult:
        accumulator = _TimingAccumulator()
        policy = _TimedPolicy(InternetDestinationPolicy(), accumulator, self._timer)
        resolver = _TimedResolver(SystemInternetDNSResolver(), accumulator, self._timer)
        fetcher = _TimedFetcher(PinnedHTTPSFetcher(), accumulator, self._timer)
        delegate = BoundedInternetRetriever(
            policy=cast(InternetDestinationPolicy, policy),
            resolver=cast(SystemInternetDNSResolver, resolver),
            fetcher=cast(PinnedHTTPSFetcher, fetcher),
        )
        started = self._timer()
        result: InternetRetrievalResult | None = None
        error_code: str | None = None
        try:
            result = await delegate.retrieve(url, method=method)
            return result
        except InternetTransportError as exc:
            error_code = exc.code
            raise
        finally:
            total_ms = _elapsed_ms(self._timer, started)
            instrumented = (
                accumulator.preflight_ms
                + accumulator.dns_ms
                + accumulator.admission_ms
                + accumulator.fetch_ms
            )
            self.records.append(
                RetrievalStageTrace(
                    source_family=_safe_source_family(url),
                    success=result is not None,
                    error_code=error_code,
                    total_ms=total_ms,
                    preflight_ms=round(accumulator.preflight_ms, 3),
                    dns_ms=round(accumulator.dns_ms, 3),
                    admission_ms=round(accumulator.admission_ms, 3),
                    fetch_ms=round(accumulator.fetch_ms, 3),
                    uninstrumented_overhead_ms=round(
                        max(0.0, total_ms - instrumented),
                        3,
                    ),
                    preflight_count=accumulator.preflight_count,
                    dns_count=accumulator.dns_count,
                    admission_count=accumulator.admission_count,
                    fetch_count=accumulator.fetch_count,
                    redirect_hop_count=(
                        len(result.hops) if result is not None else accumulator.fetch_count
                    ),
                )
            )


class Phase16LatencyCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    success: bool
    provider_search_duration_ms: float | None = Field(default=None, ge=0)
    retrieval_duration_ms: float | None = Field(default=None, ge=0)
    total_pipeline_duration_ms: float | None = Field(default=None, ge=0)
    successful_source_count: int = Field(ge=0, le=3)
    retrieval_attempt_trace_count: int = Field(ge=0)


class Phase16RetrievalLatencyReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    probe_version: Literal["phase16e1.1"] = PHASE16_RETRIEVAL_LATENCY_VERSION
    corpus_version: str = PHASE15_CORPUS_VERSION
    source_commit: str
    provider_id: Literal["searxng-local-v1"] = SEARXNG_PROVIDER_ID
    case_count: int = Field(ge=30)
    successful_case_count: int = Field(ge=0)
    retrieval_trace_count: int = Field(ge=0)
    successful_retrieval_trace_count: int = Field(ge=0)
    over_1500ms_successful_trace_count: int = Field(ge=0)
    stage_p50_ms: dict[str, float]
    stage_p95_ms: dict[str, float]
    dominant_stage_by_p95: str
    fetch_share_p50: float = Field(ge=0, le=1)
    cases: tuple[Phase16LatencyCase, ...]
    traces: tuple[RetrievalStageTrace, ...]
    truth_database_scope: Literal["isolated-diagnostic"] = "isolated-diagnostic"
    provider_configuration_mutated: Literal[False] = False
    transport_behavior_mutated: Literal[False] = False
    transport_timeout_mutated: Literal[False] = False
    retry_policy_mutated: Literal[False] = False
    production_task_truth_mutation_performed: Literal[False] = False
    production_research_evidence_mutation_performed: Literal[False] = False
    production_research_operations_mutation_performed: Literal[False] = False
    smart_routing_research_activated: Literal[False] = False
    provider_switching_performed: Literal[False] = False
    generic_network_authority_expanded: Literal[False] = False
    provider_titles_or_snippets_recorded: Literal[False] = False
    automatic_knowledge_mutation_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _elapsed_ms(timer: TimerProvider, started: float) -> float:
    return round(max(0.0, (float(timer()) - float(started)) * 1000.0), 3)


def _safe_source_family(url: str) -> str | None:
    try:
        return canonical_source_family(url)
    except ValueError:
        return None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    index = (len(ordered) - 1) * p
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return round(ordered[lower], 3)
    fraction = index - lower
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
    return round(value, 3)


def summarize_stage_timings(
    traces: list[RetrievalStageTrace],
) -> tuple[dict[str, float], dict[str, float], str, float, int]:
    successful = [trace for trace in traces if trace.success]
    stages = {
        "preflight": [trace.preflight_ms for trace in successful],
        "dns": [trace.dns_ms for trace in successful],
        "admission": [trace.admission_ms for trace in successful],
        "fetch": [trace.fetch_ms for trace in successful],
        "uninstrumented-overhead": [
            trace.uninstrumented_overhead_ms for trace in successful
        ],
        "total": [trace.total_ms for trace in successful],
    }
    p50 = {name: percentile(values, 0.50) for name, values in stages.items()}
    p95 = {name: percentile(values, 0.95) for name, values in stages.items()}
    candidate_stages = (
        "preflight",
        "dns",
        "admission",
        "fetch",
        "uninstrumented-overhead",
    )
    dominant = max(candidate_stages, key=lambda name: p95[name])
    fetch_shares = [
        min(1.0, max(0.0, trace.fetch_ms / trace.total_ms))
        for trace in successful
        if trace.total_ms > 0
    ]
    fetch_share_p50 = percentile(fetch_shares, 0.50)
    over_1500 = sum(trace.total_ms > 1500.0 for trace in successful)
    return p50, p95, dominant, fetch_share_p50, over_1500


def _isolated_repositories(
    path: Path,
) -> tuple[ResearchRetrievalRepository, ResearchOperationsRepository]:
    resolved = path.expanduser().resolve()
    production = DEFAULT_TRUTH_DATABASE_PATH.expanduser().resolve()
    if resolved == production or not str(resolved).startswith("/tmp/"):
        raise ValueError("Phase 16E latency probe truth DB must be an isolated /tmp database")
    truth = AgentTruthRepository(database_path=resolved)
    return ResearchRetrievalRepository(truth), ResearchOperationsRepository(truth)


def _successful_source_count(output: dict[str, Any] | None) -> int:
    if not output:
        return 0
    return sum(
        isinstance(item, dict) and item.get("success") is True
        for item in (output.get("sources") or [])
    )


async def run_phase16_retrieval_latency_probe(
    *,
    source_commit: str,
    truth_db: Path,
) -> Phase16RetrievalLatencyReport:
    validate_phase15_provider_corpus()
    retrieval_repository, operations_repository = _isolated_repositories(truth_db)
    tracer = LatencyTracingRetriever()
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

    cases: list[Phase16LatencyCase] = []
    for case in PHASE15_PROVIDER_CORPUS:
        trace_start = len(tracer.records)
        try:
            async with asyncio.timeout(PHASE16_RETRIEVAL_CASE_TIMEOUT_SECONDS):
                result = await pipeline.run(
                    objective=case.objective,
                    query=WebSearchQuery(query=case.query, count=5),
                )
        except (TimeoutError, WebSearchDiscoveryError, SearXNGSearchProviderError):
            cases.append(
                Phase16LatencyCase(
                    case_id=case.case_id,
                    category=case.category,
                    success=False,
                    successful_source_count=0,
                    retrieval_attempt_trace_count=len(tracer.records) - trace_start,
                )
            )
            continue

        successful_sources = _successful_source_count(result.retrieval_output)
        cases.append(
            Phase16LatencyCase(
                case_id=case.case_id,
                category=case.category,
                success=result.retrieval_success and successful_sources > 0,
                provider_search_duration_ms=result.provider_search_duration_ms,
                retrieval_duration_ms=result.retrieval_duration_ms,
                total_pipeline_duration_ms=result.total_pipeline_duration_ms,
                successful_source_count=successful_sources,
                retrieval_attempt_trace_count=len(tracer.records) - trace_start,
            )
        )

    p50, p95, dominant, fetch_share_p50, over_1500 = summarize_stage_timings(
        tracer.records
    )
    payload: dict[str, Any] = {
        "probe_version": PHASE16_RETRIEVAL_LATENCY_VERSION,
        "corpus_version": PHASE15_CORPUS_VERSION,
        "source_commit": source_commit,
        "provider_id": SEARXNG_PROVIDER_ID,
        "case_count": len(cases),
        "successful_case_count": sum(case.success for case in cases),
        "retrieval_trace_count": len(tracer.records),
        "successful_retrieval_trace_count": sum(trace.success for trace in tracer.records),
        "over_1500ms_successful_trace_count": over_1500,
        "stage_p50_ms": p50,
        "stage_p95_ms": p95,
        "dominant_stage_by_p95": dominant,
        "fetch_share_p50": fetch_share_p50,
        "cases": [case.model_dump(mode="json") for case in cases],
        "traces": [trace.model_dump(mode="json") for trace in tracer.records],
        "truth_database_scope": "isolated-diagnostic",
        "provider_configuration_mutated": False,
        "transport_behavior_mutated": False,
        "transport_timeout_mutated": False,
        "retry_policy_mutated": False,
        "production_task_truth_mutation_performed": False,
        "production_research_evidence_mutation_performed": False,
        "production_research_operations_mutation_performed": False,
        "smart_routing_research_activated": False,
        "provider_switching_performed": False,
        "generic_network_authority_expanded": False,
        "provider_titles_or_snippets_recorded": False,
        "automatic_knowledge_mutation_performed": False,
        "guardian_contacted": False,
        "privileged_host_action_performed": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Phase16RetrievalLatencyReport(**payload)


def write_report(report: Phase16RetrievalLatencyReport, path: Path) -> None:
    resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


async def _async_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--truth-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = await run_phase16_retrieval_latency_probe(
        source_commit=args.source_commit,
        truth_db=args.truth_db,
    )
    write_report(report, args.output)
    print(f"phase16_latency_probe_version|{report.probe_version}")
    print(f"phase16_latency_case_count|{report.case_count}")
    print(f"phase16_latency_successful_cases|{report.successful_case_count}")
    print(f"phase16_latency_trace_count|{report.retrieval_trace_count}")
    for stage, value in sorted(report.stage_p50_ms.items()):
        print(f"phase16_latency_stage_p50_ms|{stage}|{value:.3f}")
    for stage, value in sorted(report.stage_p95_ms.items()):
        print(f"phase16_latency_stage_p95_ms|{stage}|{value:.3f}")
    print(f"phase16_latency_dominant_stage|{report.dominant_stage_by_p95}")
    print(f"phase16_latency_fetch_share_p50|{report.fetch_share_p50:.3f}")
    print(
        "phase16_latency_over_1500ms_successful_trace_count|"
        f"{report.over_1500ms_successful_trace_count}"
    )
    print(f"phase16_latency_report_sha256|{report.report_sha256}")
    print("PHASE16_RETRIEVAL_LATENCY_PROBE|PASS")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
