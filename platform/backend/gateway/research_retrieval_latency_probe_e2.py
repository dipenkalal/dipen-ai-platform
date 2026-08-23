from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import time
from collections.abc import Callable
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
    ConnectionFactory,
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
from gateway.research_provider_live_benchmark import MAXIMUM_LIVE_RETRIEVAL_P95_MS
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
from tools.internet_research_tools import (
    TRANSIENT_RETRY_BACKOFF_SECONDS,
    InternetResearchRetrieveTool,
)

PHASE16_RETRIEVAL_LATENCY_E2_VERSION: Literal["phase16e2.1"] = "phase16e2.1"
PHASE16_RETRIEVAL_CASE_TIMEOUT_SECONDS = 60.0

TimerProvider = Callable[[], float]


class _TimingAccumulator:
    def __init__(self) -> None:
        self.preflight_ms = 0.0
        self.dns_ms = 0.0
        self.admission_ms = 0.0
        self.fetch_ms = 0.0
        self.connect_tls_ms = 0.0
        self.request_write_ms = 0.0
        self.response_header_ms = 0.0
        self.response_body_ms = 0.0
        self.close_wait_ms = 0.0
        self.preflight_count = 0
        self.dns_count = 0
        self.admission_count = 0
        self.fetch_count = 0
        self.connection_attempt_count = 0
        self.request_drain_count = 0
        self.response_header_read_count = 0
        self.response_body_read_count = 0
        self.close_wait_count = 0


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


class _TimedReader:
    def __init__(
        self,
        delegate: asyncio.StreamReader,
        accumulator: _TimingAccumulator,
        timer: TimerProvider,
    ) -> None:
        self._delegate = delegate
        self._accumulator = accumulator
        self._timer = timer
        self._header_complete = False

    async def readuntil(self, separator: bytes = b"\n") -> bytes:
        started = self._timer()
        try:
            return await self._delegate.readuntil(separator)
        finally:
            elapsed = _elapsed_ms(self._timer, started)
            if not self._header_complete and separator == b"\r\n\r\n":
                self._accumulator.response_header_ms += elapsed
                self._accumulator.response_header_read_count += 1
                self._header_complete = True
            else:
                self._accumulator.response_body_ms += elapsed
                self._accumulator.response_body_read_count += 1

    async def readexactly(self, size: int) -> bytes:
        started = self._timer()
        try:
            return await self._delegate.readexactly(size)
        finally:
            self._accumulator.response_body_ms += _elapsed_ms(self._timer, started)
            self._accumulator.response_body_read_count += 1

    async def read(self, size: int = -1) -> bytes:
        started = self._timer()
        try:
            return await self._delegate.read(size)
        finally:
            self._accumulator.response_body_ms += _elapsed_ms(self._timer, started)
            self._accumulator.response_body_read_count += 1

    async def readline(self) -> bytes:
        started = self._timer()
        try:
            return await self._delegate.readline()
        finally:
            self._accumulator.response_body_ms += _elapsed_ms(self._timer, started)
            self._accumulator.response_body_read_count += 1


class _TimedWriter:
    def __init__(
        self,
        delegate: Any,
        accumulator: _TimingAccumulator,
        timer: TimerProvider,
    ) -> None:
        self._delegate = delegate
        self._accumulator = accumulator
        self._timer = timer

    def write(self, data: bytes) -> None:
        self._delegate.write(data)

    async def drain(self) -> None:
        started = self._timer()
        try:
            await self._delegate.drain()
        finally:
            self._accumulator.request_write_ms += _elapsed_ms(self._timer, started)
            self._accumulator.request_drain_count += 1

    def close(self) -> None:
        self._delegate.close()

    async def wait_closed(self) -> None:
        started = self._timer()
        try:
            await self._delegate.wait_closed()
        finally:
            self._accumulator.close_wait_ms += _elapsed_ms(self._timer, started)
            self._accumulator.close_wait_count += 1


class _TimedConnectionFactory:
    def __init__(
        self,
        accumulator: _TimingAccumulator,
        timer: TimerProvider,
    ) -> None:
        self._accumulator = accumulator
        self._timer = timer

    async def __call__(self, *args: Any, **kwargs: Any) -> tuple[Any, Any]:
        started = self._timer()
        try:
            reader, writer = await asyncio.open_connection(*args, **kwargs)
        finally:
            self._accumulator.connect_tls_ms += _elapsed_ms(self._timer, started)
            self._accumulator.connection_attempt_count += 1
        return (
            _TimedReader(reader, self._accumulator, self._timer),
            _TimedWriter(writer, self._accumulator, self._timer),
        )


class _TimedFetcher:
    def __init__(
        self,
        accumulator: _TimingAccumulator,
        timer: TimerProvider,
    ) -> None:
        connection_factory = _TimedConnectionFactory(accumulator, timer)
        self._delegate = PinnedHTTPSFetcher(
            connection_factory=cast(ConnectionFactory, connection_factory)
        )
        self._accumulator = accumulator
        self._timer = timer

    async def fetch(self, admission: Any) -> Any:
        started = self._timer()
        try:
            return await self._delegate.fetch(admission)
        finally:
            self._accumulator.fetch_ms += _elapsed_ms(self._timer, started)
            self._accumulator.fetch_count += 1


class RetrievalDetailTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_family: str | None = None
    success: bool
    error_code: str | None = None
    total_ms: float = Field(ge=0)
    preflight_ms: float = Field(ge=0)
    dns_ms: float = Field(ge=0)
    admission_ms: float = Field(ge=0)
    fetch_ms: float = Field(ge=0)
    connect_tls_ms: float = Field(ge=0)
    request_write_ms: float = Field(ge=0)
    response_header_ms: float = Field(ge=0)
    response_body_ms: float = Field(ge=0)
    close_wait_ms: float = Field(ge=0)
    fetch_uninstrumented_ms: float = Field(ge=0)
    retriever_uninstrumented_ms: float = Field(ge=0)
    preflight_count: int = Field(ge=0)
    dns_count: int = Field(ge=0)
    admission_count: int = Field(ge=0)
    fetch_count: int = Field(ge=0)
    connection_attempt_count: int = Field(ge=0)
    request_drain_count: int = Field(ge=0)
    response_header_read_count: int = Field(ge=0)
    response_body_read_count: int = Field(ge=0)
    close_wait_count: int = Field(ge=0)
    redirect_hop_count: int = Field(ge=0, le=4)


class DetailedLatencyTracingRetriever:
    """Diagnostic-only detailed wrapper around the sealed production retriever."""

    def __init__(self, *, timer_provider: TimerProvider | None = None) -> None:
        self._timer = timer_provider or time.perf_counter
        self.records: list[RetrievalDetailTrace] = []

    async def retrieve(
        self,
        url: str,
        *,
        method: Literal["GET", "HEAD"] = "GET",
    ) -> InternetRetrievalResult:
        accumulator = _TimingAccumulator()
        policy = _TimedPolicy(InternetDestinationPolicy(), accumulator, self._timer)
        resolver = _TimedResolver(SystemInternetDNSResolver(), accumulator, self._timer)
        fetcher = _TimedFetcher(accumulator, self._timer)
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
            fetch_components = (
                accumulator.connect_tls_ms
                + accumulator.request_write_ms
                + accumulator.response_header_ms
                + accumulator.response_body_ms
                + accumulator.close_wait_ms
            )
            retriever_components = (
                accumulator.preflight_ms
                + accumulator.dns_ms
                + accumulator.admission_ms
                + accumulator.fetch_ms
            )
            self.records.append(
                RetrievalDetailTrace(
                    source_key_sha256=_source_key(url),
                    source_family=_safe_source_family(url),
                    success=result is not None,
                    error_code=error_code,
                    total_ms=total_ms,
                    preflight_ms=round(accumulator.preflight_ms, 3),
                    dns_ms=round(accumulator.dns_ms, 3),
                    admission_ms=round(accumulator.admission_ms, 3),
                    fetch_ms=round(accumulator.fetch_ms, 3),
                    connect_tls_ms=round(accumulator.connect_tls_ms, 3),
                    request_write_ms=round(accumulator.request_write_ms, 3),
                    response_header_ms=round(accumulator.response_header_ms, 3),
                    response_body_ms=round(accumulator.response_body_ms, 3),
                    close_wait_ms=round(accumulator.close_wait_ms, 3),
                    fetch_uninstrumented_ms=round(
                        max(0.0, accumulator.fetch_ms - fetch_components), 3
                    ),
                    retriever_uninstrumented_ms=round(
                        max(0.0, total_ms - retriever_components), 3
                    ),
                    preflight_count=accumulator.preflight_count,
                    dns_count=accumulator.dns_count,
                    admission_count=accumulator.admission_count,
                    fetch_count=accumulator.fetch_count,
                    connection_attempt_count=accumulator.connection_attempt_count,
                    request_drain_count=accumulator.request_drain_count,
                    response_header_read_count=accumulator.response_header_read_count,
                    response_body_read_count=accumulator.response_body_read_count,
                    close_wait_count=accumulator.close_wait_count,
                    redirect_hop_count=(
                        len(result.hops) if result is not None else accumulator.fetch_count
                    ),
                )
            )


class SourceEndToEndTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_family: str | None = None
    success: bool
    duration_ms: float = Field(ge=0)
    attempt_count: int = Field(ge=1)
    transient_retry_count: int = Field(ge=0)
    recovered_after_retry: bool
    retry_trigger_error_code: str | None = None
    retriever_trace_count: int = Field(ge=0)
    retriever_total_ms: float = Field(ge=0)
    retry_backoff_ms: float = Field(ge=0)
    tool_overhead_excluding_backoff_ms: float = Field(ge=0)


class Phase16E2LatencyCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    success: bool
    provider_search_duration_ms: float | None = Field(default=None, ge=0)
    retrieval_duration_ms: float | None = Field(default=None, ge=0)
    total_pipeline_duration_ms: float | None = Field(default=None, ge=0)
    successful_source_count: int = Field(ge=0, le=3)
    source_record_count: int = Field(ge=0, le=3)
    retrieval_attempt_trace_count: int = Field(ge=0)


class Phase16E2LatencyReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    probe_version: Literal["phase16e2.1"] = PHASE16_RETRIEVAL_LATENCY_E2_VERSION
    corpus_version: str = PHASE15_CORPUS_VERSION
    source_commit: str
    provider_id: Literal["searxng-local-v1"] = SEARXNG_PROVIDER_ID
    case_count: int = Field(ge=30)
    successful_case_count: int = Field(ge=0)
    retrieval_trace_count: int = Field(ge=0)
    successful_retrieval_trace_count: int = Field(ge=0)
    source_record_count: int = Field(ge=0)
    successful_source_record_count: int = Field(ge=0)
    retrying_source_count: int = Field(ge=0)
    retry_backoff_total_ms: float = Field(ge=0)
    retriever_stage_p50_ms: dict[str, float]
    retriever_stage_p95_ms: dict[str, float]
    fetch_component_p50_ms: dict[str, float]
    fetch_component_p95_ms: dict[str, float]
    dominant_fetch_component_by_p95: str
    frozen_retrieval_source_p50_ms: float | None = Field(default=None, ge=0)
    frozen_retrieval_source_p95_ms: float | None = Field(default=None, ge=0)
    frozen_retrieval_source_target_ms: float = MAXIMUM_LIVE_RETRIEVAL_P95_MS
    meets_frozen_retrieval_source_target: bool
    tool_overhead_excluding_backoff_p95_ms: float | None = Field(default=None, ge=0)
    case_retrieval_p95_ms: float | None = Field(default=None, ge=0)
    cases: tuple[Phase16E2LatencyCase, ...]
    traces: tuple[RetrievalDetailTrace, ...]
    source_records: tuple[SourceEndToEndTrace, ...]
    truth_database_scope: Literal["isolated-diagnostic"] = "isolated-diagnostic"
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
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _elapsed_ms(timer: TimerProvider, started: float) -> float:
    return round(max(0.0, (float(timer()) - float(started)) * 1000.0), 3)


def _source_key(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def _safe_source_family(url: str) -> str | None:
    try:
        return canonical_source_family(url)
    except ValueError:
        return None


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(float(ordered[0]), 3)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return round(float(ordered[lower]), 3)
    weight = index - lower
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * weight
    return round(float(value), 3)


def nearest_rank_percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return round(float(ordered[index]), 3)


def summarize_retriever_stages(
    traces: list[RetrievalDetailTrace],
) -> tuple[dict[str, float], dict[str, float]]:
    successful = [trace for trace in traces if trace.success]
    stages = {
        "preflight": [trace.preflight_ms for trace in successful],
        "dns": [trace.dns_ms for trace in successful],
        "admission": [trace.admission_ms for trace in successful],
        "fetch": [trace.fetch_ms for trace in successful],
        "retriever-uninstrumented": [
            trace.retriever_uninstrumented_ms for trace in successful
        ],
        "total": [trace.total_ms for trace in successful],
    }
    return (
        {name: percentile(values, 0.50) for name, values in stages.items()},
        {name: percentile(values, 0.95) for name, values in stages.items()},
    )


def summarize_fetch_components(
    traces: list[RetrievalDetailTrace],
) -> tuple[dict[str, float], dict[str, float], str]:
    successful = [trace for trace in traces if trace.success]
    components = {
        "connect-tls": [trace.connect_tls_ms for trace in successful],
        "request-write": [trace.request_write_ms for trace in successful],
        "response-header": [trace.response_header_ms for trace in successful],
        "response-body": [trace.response_body_ms for trace in successful],
        "close-wait": [trace.close_wait_ms for trace in successful],
        "fetch-uninstrumented": [
            trace.fetch_uninstrumented_ms for trace in successful
        ],
    }
    p50 = {name: percentile(values, 0.50) for name, values in components.items()}
    p95 = {name: percentile(values, 0.95) for name, values in components.items()}
    dominant = max(components, key=lambda name: p95[name])
    return p50, p95, dominant


def _isolated_repositories(
    path: Path,
) -> tuple[ResearchRetrievalRepository, ResearchOperationsRepository]:
    resolved = path.expanduser().resolve()
    production = DEFAULT_TRUTH_DATABASE_PATH.expanduser().resolve()
    if resolved == production or not str(resolved).startswith("/tmp/"):
        raise ValueError("Phase 16E.2 latency probe truth DB must be an isolated /tmp database")
    truth = AgentTruthRepository(database_path=resolved)
    return ResearchRetrievalRepository(truth), ResearchOperationsRepository(truth)


def _nonnegative_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, float(value))


def build_source_records(
    output: dict[str, Any] | None,
    traces: list[RetrievalDetailTrace],
) -> list[SourceEndToEndTrace]:
    if not output:
        return []
    grouped: dict[str, list[RetrievalDetailTrace]] = {}
    for trace in traces:
        grouped.setdefault(trace.source_key_sha256, []).append(trace)

    records: list[SourceEndToEndTrace] = []
    for item in output.get("sources") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        source_key = _source_key(url)
        matching = grouped.get(source_key, [])
        duration_ms = _nonnegative_float(item.get("duration_ms"))
        attempt_count = max(1, int(item.get("attempt_count") or 1))
        retry_count = max(0, int(item.get("transient_retry_count") or 0))
        retry_backoff_ms = round(
            retry_count * TRANSIENT_RETRY_BACKOFF_SECONDS * 1000.0,
            3,
        )
        retriever_total_ms = round(sum(trace.total_ms for trace in matching), 3)
        records.append(
            SourceEndToEndTrace(
                source_key_sha256=source_key,
                source_family=_safe_source_family(url),
                success=item.get("success") is True,
                duration_ms=round(duration_ms, 3),
                attempt_count=attempt_count,
                transient_retry_count=retry_count,
                recovered_after_retry=item.get("recovered_after_retry") is True,
                retry_trigger_error_code=(
                    str(item.get("retry_trigger_error_code"))
                    if item.get("retry_trigger_error_code")
                    else None
                ),
                retriever_trace_count=len(matching),
                retriever_total_ms=retriever_total_ms,
                retry_backoff_ms=retry_backoff_ms,
                tool_overhead_excluding_backoff_ms=round(
                    max(0.0, duration_ms - retriever_total_ms - retry_backoff_ms),
                    3,
                ),
            )
        )
    return records


async def run_phase16e2_latency_probe(
    *,
    source_commit: str,
    truth_db: Path,
) -> Phase16E2LatencyReport:
    validate_phase15_provider_corpus()
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

    cases: list[Phase16E2LatencyCase] = []
    source_records: list[SourceEndToEndTrace] = []

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
                Phase16E2LatencyCase(
                    case_id=case.case_id,
                    category=case.category,
                    success=False,
                    successful_source_count=0,
                    source_record_count=0,
                    retrieval_attempt_trace_count=len(tracer.records) - trace_start,
                )
            )
            continue

        case_traces = tracer.records[trace_start:]
        case_source_records = build_source_records(result.retrieval_output, case_traces)
        source_records.extend(case_source_records)
        successful_sources = sum(record.success for record in case_source_records)
        cases.append(
            Phase16E2LatencyCase(
                case_id=case.case_id,
                category=case.category,
                success=result.retrieval_success and successful_sources > 0,
                provider_search_duration_ms=result.provider_search_duration_ms,
                retrieval_duration_ms=result.retrieval_duration_ms,
                total_pipeline_duration_ms=result.total_pipeline_duration_ms,
                successful_source_count=successful_sources,
                source_record_count=len(case_source_records),
                retrieval_attempt_trace_count=len(case_traces),
            )
        )

    retriever_p50, retriever_p95 = summarize_retriever_stages(tracer.records)
    fetch_p50, fetch_p95, dominant_fetch = summarize_fetch_components(tracer.records)
    successful_source_records = [record for record in source_records if record.success]
    source_durations = [record.duration_ms for record in successful_source_records]
    source_p50 = nearest_rank_percentile(source_durations, 0.50)
    source_p95 = nearest_rank_percentile(source_durations, 0.95)
    tool_overheads = [
        record.tool_overhead_excluding_backoff_ms for record in successful_source_records
    ]
    case_retrievals = [
        case.retrieval_duration_ms
        for case in cases
        if case.success and case.retrieval_duration_ms is not None
    ]
    meets_target = bool(
        source_p95 is not None and source_p95 <= MAXIMUM_LIVE_RETRIEVAL_P95_MS
    )

    payload: dict[str, Any] = {
        "probe_version": PHASE16_RETRIEVAL_LATENCY_E2_VERSION,
        "corpus_version": PHASE15_CORPUS_VERSION,
        "source_commit": source_commit,
        "provider_id": SEARXNG_PROVIDER_ID,
        "case_count": len(cases),
        "successful_case_count": sum(case.success for case in cases),
        "retrieval_trace_count": len(tracer.records),
        "successful_retrieval_trace_count": sum(trace.success for trace in tracer.records),
        "source_record_count": len(source_records),
        "successful_source_record_count": len(successful_source_records),
        "retrying_source_count": sum(
            record.transient_retry_count > 0 for record in source_records
        ),
        "retry_backoff_total_ms": round(
            sum(record.retry_backoff_ms for record in source_records), 3
        ),
        "retriever_stage_p50_ms": retriever_p50,
        "retriever_stage_p95_ms": retriever_p95,
        "fetch_component_p50_ms": fetch_p50,
        "fetch_component_p95_ms": fetch_p95,
        "dominant_fetch_component_by_p95": dominant_fetch,
        "frozen_retrieval_source_p50_ms": source_p50,
        "frozen_retrieval_source_p95_ms": source_p95,
        "frozen_retrieval_source_target_ms": MAXIMUM_LIVE_RETRIEVAL_P95_MS,
        "meets_frozen_retrieval_source_target": meets_target,
        "tool_overhead_excluding_backoff_p95_ms": nearest_rank_percentile(
            tool_overheads, 0.95
        ),
        "case_retrieval_p95_ms": nearest_rank_percentile(case_retrievals, 0.95),
        "cases": [case.model_dump(mode="json") for case in cases],
        "traces": [trace.model_dump(mode="json") for trace in tracer.records],
        "source_records": [record.model_dump(mode="json") for record in source_records],
        "truth_database_scope": "isolated-diagnostic",
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
        "guardian_contacted": False,
        "privileged_host_action_performed": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Phase16E2LatencyReport(**payload)


def write_phase16e2_latency_report(
    report: Phase16E2LatencyReport,
    path: Path,
) -> None:
    resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


async def _async_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--truth-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = await run_phase16e2_latency_probe(
        source_commit=args.source_commit,
        truth_db=args.truth_db,
    )
    write_phase16e2_latency_report(report, args.output)

    print(f"phase16e2_probe_version|{report.probe_version}")
    print(f"phase16e2_case_count|{report.case_count}")
    print(f"phase16e2_successful_cases|{report.successful_case_count}")
    print(f"phase16e2_retrieval_trace_count|{report.retrieval_trace_count}")
    print(f"phase16e2_source_record_count|{report.source_record_count}")
    for stage, value in sorted(report.retriever_stage_p95_ms.items()):
        print(f"phase16e2_retriever_p95_ms|{stage}|{value:.3f}")
    for component, value in sorted(report.fetch_component_p95_ms.items()):
        print(f"phase16e2_fetch_component_p95_ms|{component}|{value:.3f}")
    print(
        "phase16e2_dominant_fetch_component|"
        f"{report.dominant_fetch_component_by_p95}"
    )
    print(
        "phase16e2_frozen_retrieval_source_p95_ms|"
        f"{report.frozen_retrieval_source_p95_ms}"
    )
    print(
        "phase16e2_frozen_retrieval_source_target|"
        + ("PASS" if report.meets_frozen_retrieval_source_target else "FAIL")
    )
    print(f"phase16e2_retrying_source_count|{report.retrying_source_count}")
    print(f"phase16e2_retry_backoff_total_ms|{report.retry_backoff_total_ms:.3f}")
    print(f"phase16e2_report_sha256|{report.report_sha256}")
    print("PHASE16_RETRIEVAL_LATENCY_E2_PROBE|PASS")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
