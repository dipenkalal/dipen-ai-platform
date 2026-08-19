from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gateway.research_operations import ResearchOperationsSummary
from gateway.research_provider_health import ResearchProviderHealth
from gateway.research_provider_live_benchmark import (
    DEFAULT_LIVE_REPORT_PATH,
    Phase15LiveBenchmarkReport,
    Phase15LiveThresholds,
)

PROVIDER_READINESS_POLICY_ID = "dap-phase15-provider-readiness-view-v1"


class Phase15LoadedLiveReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    report: Phase15LiveBenchmarkReport | None
    status: Literal["missing", "valid", "invalid"]
    error_code: str | None = None


class ResearchProviderReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str = PROVIDER_READINESS_POLICY_ID
    state: Literal["insufficient-data", "healthy", "degraded", "unavailable"]
    reason_codes: tuple[str, ...]
    provider_id: Literal["searxng-local-v1"] = "searxng-local-v1"
    provider_health_healthy: bool
    operations_reliability_posture: Literal[
        "insufficient-data",
        "within-thresholds",
        "degraded",
    ]
    live_corpus_status: Literal["missing", "valid", "invalid"]
    live_corpus_version: str | None = None
    live_report_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    query_coverage_rate: float | None = Field(default=None, ge=0, le=1)
    no_candidate_rate: float | None = Field(default=None, ge=0, le=1)
    selected_unique_source_family_rate: float | None = Field(default=None, ge=0, le=1)
    duplicate_content_rate: float | None = Field(default=None, ge=0, le=1)
    retrieval_source_p95_ms: float | None = Field(default=None, ge=0)
    live_recommended_posture: Literal[
        "manual-research-production-ready",
        "manual-research-experimental-only",
        "manual-research-provider-degraded",
    ] | None = None
    thresholds: Phase15LiveThresholds
    smart_routing_research_activated: Literal[False] = False
    network_authority_granted: Literal[False] = False
    mutation_authority_granted: Literal[False] = False
    service_control_authority_granted: Literal[False] = False
    provider_reconfiguration_authority_granted: Literal[False] = False
    owner_approval_required_for_future_authority_expansion: Literal[True] = True


def load_phase15_live_report(
    path: Path = DEFAULT_LIVE_REPORT_PATH,
) -> Phase15LoadedLiveReport:
    if not path.is_file():
        return Phase15LoadedLiveReport(report=None, status="missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("live report root must be an object")
        stated_hash = raw.get("report_sha256")
        if not isinstance(stated_hash, str):
            raise ValueError("live report SHA-256 is missing")
        canonical_payload = dict(raw)
        canonical_payload.pop("report_sha256", None)
        canonical = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual_hash != stated_hash:
            raise ValueError("live report SHA-256 mismatch")
        report = Phase15LiveBenchmarkReport.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return Phase15LoadedLiveReport(
            report=None,
            status="invalid",
            error_code=f"phase15-live-report-invalid:{type(exc).__name__}",
        )
    return Phase15LoadedLiveReport(report=report, status="valid")


def assess_phase15_provider_readiness(
    *,
    operations: ResearchOperationsSummary,
    health: ResearchProviderHealth,
    loaded_report: Phase15LoadedLiveReport,
) -> ResearchProviderReadiness:
    report = loaded_report.report
    thresholds = report.thresholds if report is not None else Phase15LiveThresholds()
    reasons: list[str] = []

    if not health.healthy:
        reasons.append("provider-health-failed")
    if operations.reliability_posture == "degraded":
        reasons.append("operations-reliability-degraded")
    elif operations.reliability_posture == "insufficient-data":
        reasons.append("operations-data-insufficient")

    if loaded_report.status == "missing":
        reasons.append("phase15-live-corpus-pending")
    elif loaded_report.status == "invalid":
        reasons.append("phase15-live-corpus-report-invalid")
    elif report is not None:
        if report.success_rate < thresholds.minimum_success_rate:
            reasons.append("query-coverage-below-target")
        if report.no_candidate_rate > thresholds.maximum_no_candidate_rate:
            reasons.append("no-candidate-rate-above-target")
        if (
            report.selected_unique_source_family_rate
            < thresholds.minimum_unique_source_family_rate
        ):
            reasons.append("source-family-diversity-below-target")
        if report.duplicate_content_rate > thresholds.maximum_duplicate_content_rate:
            reasons.append("duplicate-content-rate-above-target")
        if (
            report.retrieval_source_p95_ms is None
            or report.retrieval_source_p95_ms > thresholds.maximum_retrieval_p95_ms
        ):
            reasons.append("retrieval-p95-above-target")

    if not health.healthy:
        state: Literal["insufficient-data", "healthy", "degraded", "unavailable"] = (
            "unavailable"
        )
    elif report is None:
        state = "insufficient-data"
    elif report.meets_phase15_targets:
        state = "healthy"
    else:
        state = "degraded"

    return ResearchProviderReadiness(
        state=state,
        reason_codes=tuple(reasons),
        provider_health_healthy=health.healthy,
        operations_reliability_posture=operations.reliability_posture,
        live_corpus_status=loaded_report.status,
        live_corpus_version=report.corpus_version if report is not None else None,
        live_report_sha256=report.report_sha256 if report is not None else None,
        query_coverage_rate=report.success_rate if report is not None else None,
        no_candidate_rate=report.no_candidate_rate if report is not None else None,
        selected_unique_source_family_rate=(
            report.selected_unique_source_family_rate if report is not None else None
        ),
        duplicate_content_rate=(
            report.duplicate_content_rate if report is not None else None
        ),
        retrieval_source_p95_ms=(
            report.retrieval_source_p95_ms if report is not None else None
        ),
        live_recommended_posture=(
            report.recommended_posture if report is not None else None
        ),
        thresholds=thresholds,
    )
