from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from gateway.research_operations import ResearchOperationsService
from gateway.research_operations_repository import ResearchOperationsEvent


class EvidenceRepository:
    def __init__(self, records: list[object]) -> None:
        self.records = records

    def list_recent(self, *, limit: int = 100) -> list[object]:
        return self.records[:limit]


class OperationsRepository:
    def __init__(self, events: list[ResearchOperationsEvent]) -> None:
        self.events = events

    def list_recent(self, *, limit: int = 500) -> list[ResearchOperationsEvent]:
        return self.events[:limit]


def _record(
    evidence_id: str,
    *,
    outcome: str,
    url: str,
    digest: str | None,
    stored_at: datetime,
    injection: tuple[str, ...] = (),
) -> object:
    succeeded = outcome == "succeeded"
    citation = SimpleNamespace(citation_id="citation") if succeeded else None
    evidence = SimpleNamespace(
        evidence_id=evidence_id,
        outcome=outcome,
        final_url=url if succeeded else None,
        requested_url=url,
        normalized_text_sha256=digest,
        citation=citation,
        source_body_sha256=("a" * 64 if succeeded else None),
        prompt_injection_finding_rule_ids=injection,
    )
    return SimpleNamespace(evidence=evidence, stored_at=stored_at)


def _event(
    *,
    outcome: str,
    duration_ms: float,
    attempts: int = 1,
    retries: int = 0,
    recovered: bool = False,
    error_code: str | None = None,
) -> ResearchOperationsEvent:
    return ResearchOperationsEvent.build(
        event_type="retrieval-source",
        provider_id="dap-public-http",
        outcome=outcome,  # type: ignore[arg-type]
        duration_ms=duration_ms,
        attempt_count=attempts,
        transient_retry_count=retries,
        recovered_after_retry=recovered,
        error_code=error_code,
        recorded_at=datetime(2026, 8, 18, 23, 45, tzinfo=timezone.utc),
    )


def test_summary_surfaces_duplicates_families_latency_and_recovery() -> None:
    now = datetime(2026, 8, 18, 23, 50, tzinfo=timezone.utc)
    records = [
        _record(
            "evidence-1",
            outcome="succeeded",
            url="https://www.example.com/a",
            digest="1" * 64,
            stored_at=now,
        ),
        _record(
            "evidence-2",
            outcome="succeeded",
            url="https://example.org/b",
            digest="1" * 64,
            stored_at=now,
        ),
        _record(
            "evidence-3",
            outcome="succeeded",
            url="https://example.net/c",
            digest="2" * 64,
            stored_at=now,
        ),
        _record(
            "evidence-4",
            outcome="failed",
            url="https://127.0.0.1/blocked-safety-probe",
            digest=None,
            stored_at=now,
        ),
        _record(
            "evidence-5",
            outcome="succeeded",
            url="https://docs.example.edu/e",
            digest="3" * 64,
            stored_at=now,
            injection=("remote-instruction",),
        ),
    ]
    events = [
        _event(outcome="succeeded", duration_ms=100),
        _event(
            outcome="succeeded",
            duration_ms=200,
            attempts=2,
            retries=1,
            recovered=True,
            error_code="connect-timeout",
        ),
        _event(outcome="succeeded", duration_ms=300),
        _event(outcome="failed", duration_ms=400, error_code="content-type-unsupported"),
        _event(outcome="succeeded", duration_ms=500),
    ]
    service = ResearchOperationsService(
        evidence_repository=EvidenceRepository(records),  # type: ignore[arg-type]
        operations_repository=OperationsRepository(events),
    )

    summary = service.summary()

    assert summary.evidence_total == 5
    assert summary.succeeded == 4
    assert summary.failed == 1
    assert summary.success_rate == 0.8
    assert summary.unique_source_family_count == 4
    assert summary.unique_source_family_rate == 1.0
    assert {item.source_family for item in summary.source_families} == {
        "example.com",
        "example.org",
        "example.net",
        "docs.example.edu",
    }
    assert all(item.source_family != "127.0.0.1" for item in summary.source_families)
    failed_provenance = next(
        item for item in summary.provenance_quality if item.evidence_id == "evidence-4"
    )
    assert failed_provenance.source_family is None
    assert summary.duplicate_content_group_count == 1
    assert summary.duplicate_content_evidence_count == 1
    assert summary.retrieval_attempt_count == 6
    assert summary.transient_retry_count == 1
    assert summary.recovered_after_retry_count == 1
    assert summary.p50_source_duration_ms == 300
    assert summary.p95_source_duration_ms == 500
    assert summary.prompt_injection_evidence_count == 1
    assert summary.factual_correctness_measured is False
    assert summary.workspace_mode == "read_only"
    assert summary.network_authority_granted is False
    assert summary.mutation_authority_granted is False


def test_retention_plan_is_dry_run_and_never_deletes() -> None:
    now = datetime(2026, 8, 18, 23, 55, tzinfo=timezone.utc)
    records = [
        _record(
            "evidence-a",
            outcome="succeeded",
            url="https://example.com/a",
            digest="a" * 64,
            stored_at=now - timedelta(days=45),
        ),
        _record(
            "evidence-b",
            outcome="succeeded",
            url="https://example.org/b",
            digest="a" * 64,
            stored_at=now - timedelta(days=40),
        ),
        _record(
            "evidence-c",
            outcome="failed",
            url="https://example.net/c",
            digest=None,
            stored_at=now - timedelta(days=120),
        ),
    ]
    service = ResearchOperationsService(
        evidence_repository=EvidenceRepository(records),  # type: ignore[arg-type]
        operations_repository=OperationsRepository([]),
    )

    plan = service.retention_plan(now=now)

    assert plan.mode == "dry_run"
    assert plan.evidence_deleted is False
    assert plan.evidence_mutated is False
    assert plan.policy.automatic_deletion_enabled is False
    assert plan.policy.automatic_archive_enabled is False
    assert plan.policy.owner_action_required_for_future_cleanup is True
    classifications = {
        item.evidence_id: item.classification for item in plan.candidates
    }
    assert classifications["evidence-a"] == "preserve"
    assert classifications["evidence-b"] == "future-archive-duplicate"
    assert classifications["evidence-c"] == "future-archive-failed"
    assert all(item.destructive_action_performed is False for item in plan.candidates)
