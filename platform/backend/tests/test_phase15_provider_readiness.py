from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from gateway.research_operations import (
    ResearchOperationsSummary,
    ResearchOperationsThresholds,
)
from gateway.research_provider_health import ResearchProviderHealth
from gateway.research_provider_live_benchmark import (
    Phase15LiveBenchmarkReport,
    Phase15LiveThresholds,
)
from gateway.research_provider_readiness import (
    Phase15LoadedLiveReport,
    assess_phase15_provider_readiness,
    load_phase15_live_report,
)


def _summary(posture: str = "within-thresholds") -> ResearchOperationsSummary:
    return ResearchOperationsSummary.model_validate(
        {
            "window_event_count": 5,
            "evidence_total": 5,
            "succeeded": 5,
            "failed": 0,
            "cancelled": 0,
            "success_rate": 1.0,
            "failure_rate": 0.0,
            "unique_source_family_count": 5,
            "unique_source_family_rate": 1.0,
            "duplicate_content_group_count": 0,
            "duplicate_content_evidence_count": 0,
            "duplicate_content_rate": 0.0,
            "average_source_duration_ms": 100.0,
            "p50_source_duration_ms": 100.0,
            "p95_source_duration_ms": 100.0,
            "retrieval_attempt_count": 5,
            "transient_retry_count": 0,
            "recovered_after_retry_count": 0,
            "prompt_injection_evidence_count": 0,
            "average_provenance_quality_score": 100.0,
            "errors": [],
            "source_families": [],
            "duplicate_content_groups": [],
            "provenance_quality": [],
            "thresholds": ResearchOperationsThresholds().model_dump(mode="json"),
            "meets_current_reliability_thresholds": posture == "within-thresholds",
            "reliability_posture": posture,
        }
    )


def _health(healthy: bool = True) -> ResearchProviderHealth:
    return ResearchProviderHealth(
        healthy=healthy,
        status_code=200 if healthy else None,
        latency_ms=2.0,
        error_code=None if healthy else "searxng-health-unavailable",
        checked_at=datetime(2026, 8, 19, 2, 0, tzinfo=timezone.utc),
    )


def _report(*, meets: bool = True) -> Phase15LiveBenchmarkReport:
    thresholds = Phase15LiveThresholds()
    payload = {
        "benchmark_version": "phase15i.1",
        "corpus_version": "phase15-provider-corpus-v1",
        "source_commit": "a" * 40,
        "provider_id": "searxng-local-v1",
        "case_count": 30,
        "success_count": 30 if meets else 24,
        "success_rate": 1.0 if meets else 0.8,
        "no_candidate_count": 0 if meets else 6,
        "no_candidate_rate": 0.0 if meets else 0.2,
        "fallback_case_count": 2,
        "selected_source_count": 90,
        "selected_unique_source_family_rate": 1.0 if meets else 0.5,
        "successful_source_count": 90 if meets else 60,
        "duplicate_content_count": 0 if meets else 30,
        "duplicate_content_rate": 0.0 if meets else 0.5,
        "provider_search_p50_ms": 10.0,
        "provider_search_p95_ms": 20.0,
        "retrieval_source_p50_ms": 100.0,
        "retrieval_source_p95_ms": 500.0 if meets else 2500.0,
        "pipeline_p95_ms": 900.0 if meets else 5000.0,
        "thresholds": thresholds.model_dump(mode="json"),
        "meets_phase15_targets": meets,
        "recommended_posture": (
            "manual-research-production-ready"
            if meets
            else "manual-research-provider-degraded"
        ),
        "cases": [],
        "truth_database_scope": "isolated-benchmark",
        "production_task_truth_mutation_performed": False,
        "production_research_evidence_mutation_performed": False,
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
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return Phase15LiveBenchmarkReport(**payload, report_sha256=digest)


def test_missing_live_report_yields_insufficient_data_without_authority(tmp_path: Path) -> None:
    loaded = load_phase15_live_report(tmp_path / "missing.json")
    readiness = assess_phase15_provider_readiness(
        operations=_summary(),
        health=_health(),
        loaded_report=loaded,
    )

    assert loaded.status == "missing"
    assert readiness.state == "insufficient-data"
    assert "phase15-live-corpus-pending" in readiness.reason_codes
    assert readiness.query_coverage_rate is None
    assert readiness.smart_routing_research_activated is False
    assert readiness.network_authority_granted is False
    assert readiness.mutation_authority_granted is False
    assert readiness.service_control_authority_granted is False
    assert readiness.provider_reconfiguration_authority_granted is False


def test_valid_hashed_live_report_can_reach_healthy_readiness(tmp_path: Path) -> None:
    report = _report(meets=True)
    path = tmp_path / "report.json"
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")

    loaded = load_phase15_live_report(path)
    readiness = assess_phase15_provider_readiness(
        operations=_summary(),
        health=_health(),
        loaded_report=loaded,
    )

    assert loaded.status == "valid"
    assert loaded.report == report
    assert readiness.state == "healthy"
    assert readiness.reason_codes == ()
    assert readiness.query_coverage_rate == 1.0
    assert readiness.no_candidate_rate == 0.0
    assert readiness.selected_unique_source_family_rate == 1.0
    assert readiness.duplicate_content_rate == 0.0
    assert readiness.retrieval_source_p95_ms == 500.0
    assert readiness.live_recommended_posture == "manual-research-production-ready"


def test_degraded_report_and_failed_health_are_owner_visible_not_auto_remediated() -> None:
    report = _report(meets=False)
    readiness = assess_phase15_provider_readiness(
        operations=_summary(posture="degraded"),
        health=_health(healthy=False),
        loaded_report=Phase15LoadedLiveReport(report=report, status="valid"),
    )

    assert readiness.state == "unavailable"
    assert "provider-health-failed" in readiness.reason_codes
    assert "operations-reliability-degraded" in readiness.reason_codes
    assert "query-coverage-below-target" in readiness.reason_codes
    assert "no-candidate-rate-above-target" in readiness.reason_codes
    assert "source-family-diversity-below-target" in readiness.reason_codes
    assert "duplicate-content-rate-above-target" in readiness.reason_codes
    assert "retrieval-p95-above-target" in readiness.reason_codes
    assert readiness.service_control_authority_granted is False
    assert readiness.owner_approval_required_for_future_authority_expansion is True


def test_tampered_live_report_is_rejected(tmp_path: Path) -> None:
    report = _report(meets=True)
    payload = report.model_dump(mode="json")
    payload["success_rate"] = 0.1
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_phase15_live_report(path)

    assert loaded.status == "invalid"
    assert loaded.report is None
    assert loaded.error_code is not None
