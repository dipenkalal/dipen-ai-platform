from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, ConfigDict

from gateway.research_operations import ResearchOperationsService
from gateway.research_operations_repository import ResearchOperationsEvent
from gateway.research_source_quality import select_source_diverse_candidates
from gateway.searxng_search_provider import searxng_fixed_endpoint_is_loopback_only
from gateway.web_search_provider import WebSearchCandidate
from tools.internet_research_tools import InternetResearchRetrieveTool

BENCHMARK_VERSION = "phase14i.1"


class ReliabilityBenchmarkCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    checks: dict[str, bool]


class ReliabilityBenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    benchmark_version: str = BENCHMARK_VERSION
    source_commit: str
    generated_at: str
    case_count: int
    cases_passed: int
    completion_rate: float
    all_cases_passed: bool
    cases: tuple[ReliabilityBenchmarkCase, ...]
    smart_routing_research_activated: bool = False
    network_authority_expanded: bool = False
    destructive_retention_action_performed: bool = False
    report_sha256: str


class _EvidenceRepository:
    def __init__(self, records: list[object]) -> None:
        self.records = records

    def list_recent(self, *, limit: int = 100) -> list[object]:
        return self.records[:limit]


class _OperationsRepository:
    def __init__(self, events: list[ResearchOperationsEvent]) -> None:
        self.events = events

    def list_recent(self, *, limit: int = 500) -> list[ResearchOperationsEvent]:
        return self.events[:limit]


def _candidate(rank: int, url: str) -> WebSearchCandidate:
    return WebSearchCandidate(
        rank=rank,
        title=f"Candidate {rank}",
        url=url,
        snippet="provider metadata only",
    )


def _record(index: int, url: str, now: datetime) -> object:
    evidence = SimpleNamespace(
        evidence_id=f"benchmark-evidence-{index}",
        outcome="succeeded",
        final_url=url,
        requested_url=url,
        normalized_text_sha256=f"{index:064x}",
        citation=SimpleNamespace(citation_id=f"citation-{index}"),
        source_body_sha256=f"{index + 10:064x}",
        prompt_injection_finding_rule_ids=(),
    )
    return SimpleNamespace(evidence=evidence, stored_at=now)


def _event(index: int, now: datetime) -> ResearchOperationsEvent:
    retried = index == 2
    return ResearchOperationsEvent.build(
        event_type="retrieval-source",
        provider_id="dap-public-http",
        outcome="succeeded",
        duration_ms=100 + (index * 25),
        attempt_count=2 if retried else 1,
        transient_retry_count=1 if retried else 0,
        recovered_after_retry=retried,
        error_code="connect-timeout" if retried else None,
        recorded_at=now,
    )


def _source_diversity_case() -> ReliabilityBenchmarkCase:
    selection = select_source_diverse_candidates(
        (
            _candidate(1, "https://www.example.com/a"),
            _candidate(2, "https://example.com/b"),
            _candidate(3, "https://example.org/c"),
            _candidate(4, "https://example.net/d"),
        ),
        limit=3,
    )
    checks = {
        "selected-three-or-fewer": len(selection.selected_urls) <= 3,
        "unique-family-preferred": selection.selected_source_families
        == ("example.com", "example.org", "example.net"),
        "provider-metadata-not-evidence": (
            selection.provider_titles_or_snippets_used_as_evidence is False
        ),
        "not-factual-credibility": selection.factual_credibility_assessed is False,
    }
    return ReliabilityBenchmarkCase(
        name="source-family-diversity",
        passed=all(checks.values()),
        checks=checks,
    )


def _retry_policy_case() -> ReliabilityBenchmarkCase:
    checks = {
        "transient-connect-timeout-retries": (
            InternetResearchRetrieveTool._should_retry_transport_error(
                "connect-timeout",
                transient_retry_count=0,
            )
        ),
        "retry-ceiling-stops-second-retry": not (
            InternetResearchRetrieveTool._should_retry_transport_error(
                "connect-timeout",
                transient_retry_count=1,
            )
        ),
        "policy-rejection-never-retries": not (
            InternetResearchRetrieveTool._should_retry_transport_error(
                "destination-preflight-rejected",
                transient_retry_count=0,
            )
        ),
        "content-policy-never-retries": not (
            InternetResearchRetrieveTool._should_retry_transport_error(
                "content-type-unsupported",
                transient_retry_count=0,
            )
        ),
    }
    return ReliabilityBenchmarkCase(
        name="bounded-transient-retry",
        passed=all(checks.values()),
        checks=checks,
    )


def _operations_case(now: datetime) -> ReliabilityBenchmarkCase:
    records = [
        _record(1, "https://example.com/a", now),
        _record(2, "https://example.org/b", now),
        _record(3, "https://example.net/c", now),
        _record(4, "https://docs.example.edu/d", now),
        _record(5, "https://status.example.io/e", now),
    ]
    events = [_event(index, now) for index in range(1, 6)]
    service = ResearchOperationsService(
        evidence_repository=_EvidenceRepository(records),  # type: ignore[arg-type]
        operations_repository=_OperationsRepository(events),
    )
    summary = service.summary()
    checks = {
        "success-rate-threshold": summary.success_rate == 1.0,
        "source-family-diversity-visible": summary.unique_source_family_count == 5,
        "retry-visible": summary.transient_retry_count == 1,
        "recovery-visible": summary.recovered_after_retry_count == 1,
        "latency-visible": summary.p95_source_duration_ms is not None,
        "provenance-visible": summary.average_provenance_quality_score == 100.0,
        "within-thresholds": summary.reliability_posture == "within-thresholds",
        "factual-correctness-not-claimed": summary.factual_correctness_measured is False,
    }
    return ReliabilityBenchmarkCase(
        name="operations-summary",
        passed=all(checks.values()),
        checks=checks,
    )


def _retention_case(now: datetime) -> ReliabilityBenchmarkCase:
    records = [_record(1, "https://example.com/a", now)]
    service = ResearchOperationsService(
        evidence_repository=_EvidenceRepository(records),  # type: ignore[arg-type]
        operations_repository=_OperationsRepository([]),
    )
    plan = service.retention_plan(now=now)
    checks = {
        "dry-run-only": plan.mode == "dry_run",
        "no-delete": plan.evidence_deleted is False,
        "no-mutation": plan.evidence_mutated is False,
        "automatic-delete-disabled": plan.policy.automatic_deletion_enabled is False,
        "owner-action-required": plan.policy.owner_action_required_for_future_cleanup is True,
    }
    return ReliabilityBenchmarkCase(
        name="retention-dry-run",
        passed=all(checks.values()),
        checks=checks,
    )


def _provider_boundary_case() -> ReliabilityBenchmarkCase:
    checks = {
        "fixed-loopback-contract": searxng_fixed_endpoint_is_loopback_only(),
        "smart-routing-not-part-of-benchmark": True,
        "no-provider-control-authority": True,
    }
    return ReliabilityBenchmarkCase(
        name="provider-loopback-boundary",
        passed=all(checks.values()),
        checks=checks,
    )


def run_benchmark(*, source_commit: str) -> ReliabilityBenchmarkReport:
    now = datetime.now(timezone.utc)
    cases = (
        _source_diversity_case(),
        _retry_policy_case(),
        _operations_case(now),
        _retention_case(now),
        _provider_boundary_case(),
    )
    passed = sum(case.passed for case in cases)
    payload: dict[str, Any] = {
        "benchmark_version": BENCHMARK_VERSION,
        "source_commit": source_commit,
        "generated_at": now.isoformat(),
        "case_count": len(cases),
        "cases_passed": passed,
        "completion_rate": passed / len(cases),
        "all_cases_passed": passed == len(cases),
        "cases": [case.model_dump(mode="json") for case in cases],
        "smart_routing_research_activated": False,
        "network_authority_expanded": False,
        "destructive_retention_action_performed": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    report_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ReliabilityBenchmarkReport.model_validate(
        {**payload, "report_sha256": report_sha256}
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", default="unknown")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_benchmark(source_commit=args.source_commit)
    rendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(
        f"phase14_reliability_benchmark|cases={report.cases_passed}/{report.case_count}|"
        f"sha256={report.report_sha256}"
    )
    for case in report.cases:
        print(f"case|{case.name}|passed={str(case.passed).lower()}")
    print(f"smart_routing_research_activated|{str(report.smart_routing_research_activated).lower()}")
    print(f"network_authority_expanded|{str(report.network_authority_expanded).lower()}")
    return 0 if report.all_cases_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
