from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from gateway.research_operations_repository import ResearchOperationsEvent
from gateway.research_retrieval_repository import PersistedResearchRetrievalRecord
from gateway.research_source_quality import canonical_source_family


class ResearchOperationsEventReadRepository(Protocol):
    def list_recent(self, *, limit: int = 500) -> list[ResearchOperationsEvent]: ...


class ResearchOperationsEvidenceReadRepository(Protocol):
    def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> list[PersistedResearchRetrievalRecord]: ...


class ResearchOperationsThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: Literal["dap-research-reliability-slo-v1"] = (
        "dap-research-reliability-slo-v1"
    )
    minimum_success_rate: float = Field(default=0.80, ge=0, le=1)
    maximum_p95_source_duration_ms: float = Field(default=20_000, ge=0)
    maximum_failure_rate: float = Field(default=0.20, ge=0, le=1)
    maximum_duplicate_content_rate: float = Field(default=0.35, ge=0, le=1)
    minimum_unique_source_family_rate: float = Field(default=0.50, ge=0, le=1)
    factual_correctness_measured: Literal[False] = False


class ResearchErrorCount(BaseModel):
    model_config = ConfigDict(frozen=True)

    error_code: str
    count: int = Field(ge=1)


class ResearchSourceFamilyCount(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_family: str
    count: int = Field(ge=1)


class ResearchDuplicateContentGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    normalized_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_ids: tuple[str, ...] = Field(min_length=2)
    source_families: tuple[str, ...]
    duplicate_count: int = Field(ge=1)


class ResearchProvenanceQuality(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    score: int = Field(ge=0, le=100)
    outcome: str
    citation_present: bool
    content_hash_present: bool
    normalized_hash_present: bool
    source_family: str | None
    prompt_injection_finding_count: int = Field(ge=0)
    score_is_factual_credibility: Literal[False] = False


class ResearchRetentionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: Literal["dap-research-retention-dry-run-v1"] = (
        "dap-research-retention-dry-run-v1"
    )
    default_preserve_all: Literal[True] = True
    duplicate_candidate_after_days: int = Field(default=30, ge=1)
    failed_candidate_after_days: int = Field(default=90, ge=1)
    succeeded_candidate_after_days: int = Field(default=180, ge=1)
    automatic_deletion_enabled: Literal[False] = False
    automatic_archive_enabled: Literal[False] = False
    owner_action_required_for_future_cleanup: Literal[True] = True


class ResearchRetentionCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    classification: Literal[
        "preserve",
        "future-archive-duplicate",
        "future-archive-failed",
        "future-archive-aged-success",
    ]
    reason: str
    age_days: int = Field(ge=0)
    destructive_action_performed: Literal[False] = False


class ResearchRetentionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: Literal["dry_run"] = "dry_run"
    policy: ResearchRetentionPolicy
    total_evidence: int = Field(ge=0)
    preserve_count: int = Field(ge=0)
    future_archive_candidate_count: int = Field(ge=0)
    candidates: tuple[ResearchRetentionCandidate, ...]
    evidence_deleted: Literal[False] = False
    evidence_mutated: Literal[False] = False


class ResearchOperationsSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    window_event_count: int = Field(ge=0)
    evidence_total: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    success_rate: float = Field(ge=0, le=1)
    failure_rate: float = Field(ge=0, le=1)
    unique_source_family_count: int = Field(ge=0)
    unique_source_family_rate: float = Field(ge=0, le=1)
    duplicate_content_group_count: int = Field(ge=0)
    duplicate_content_evidence_count: int = Field(ge=0)
    duplicate_content_rate: float = Field(ge=0, le=1)
    average_source_duration_ms: float | None = Field(default=None, ge=0)
    p50_source_duration_ms: float | None = Field(default=None, ge=0)
    p95_source_duration_ms: float | None = Field(default=None, ge=0)
    retrieval_attempt_count: int = Field(ge=0)
    transient_retry_count: int = Field(ge=0)
    recovered_after_retry_count: int = Field(ge=0)
    prompt_injection_evidence_count: int = Field(ge=0)
    average_provenance_quality_score: float | None = Field(default=None, ge=0, le=100)
    errors: tuple[ResearchErrorCount, ...]
    source_families: tuple[ResearchSourceFamilyCount, ...]
    duplicate_content_groups: tuple[ResearchDuplicateContentGroup, ...]
    provenance_quality: tuple[ResearchProvenanceQuality, ...]
    thresholds: ResearchOperationsThresholds
    meets_current_reliability_thresholds: bool
    reliability_posture: Literal[
        "insufficient-data",
        "within-thresholds",
        "degraded",
    ]
    factual_correctness_measured: Literal[False] = False
    workspace_mode: Literal["read_only"] = "read_only"
    network_authority_granted: Literal[False] = False
    mutation_authority_granted: Literal[False] = False


class ResearchOperationsService:
    def __init__(
        self,
        *,
        evidence_repository: ResearchOperationsEvidenceReadRepository,
        operations_repository: ResearchOperationsEventReadRepository,
        thresholds: ResearchOperationsThresholds | None = None,
        retention_policy: ResearchRetentionPolicy | None = None,
    ) -> None:
        self._evidence_repository = evidence_repository
        self._operations_repository = operations_repository
        self._thresholds = thresholds or ResearchOperationsThresholds()
        self._retention_policy = retention_policy or ResearchRetentionPolicy()

    def summary(
        self,
        *,
        evidence_limit: int = 500,
        event_limit: int = 2000,
    ) -> ResearchOperationsSummary:
        records = self._safe_evidence(evidence_limit)
        events = self._safe_events(event_limit)
        succeeded = sum(record.evidence.outcome == "succeeded" for record in records)
        failed = sum(record.evidence.outcome == "failed" for record in records)
        cancelled = sum(record.evidence.outcome == "cancelled" for record in records)
        total = len(records)
        success_rate = succeeded / total if total else 0.0
        failure_rate = failed / total if total else 0.0

        families = [
            family
            for record in records
            if (family := self._record_source_family(record)) is not None
        ]
        family_counts = Counter(families)
        unique_family_count = len(family_counts)
        unique_family_rate = unique_family_count / len(families) if families else 0.0

        duplicate_groups = self._duplicate_groups(records)
        duplicate_evidence_count = sum(group.duplicate_count for group in duplicate_groups)
        duplicate_rate = duplicate_evidence_count / succeeded if succeeded else 0.0

        retrieval_events = [
            event for event in events if event.event_type == "retrieval-source"
        ]
        durations = [event.duration_ms for event in retrieval_events]
        attempt_count = sum(event.attempt_count for event in retrieval_events)
        retry_count = sum(event.transient_retry_count for event in retrieval_events)
        recovered_count = sum(event.recovered_after_retry for event in retrieval_events)
        errors = Counter(
            event.error_code
            for event in retrieval_events
            if event.outcome == "failed" and event.error_code
        )

        provenance = tuple(self._provenance_quality(record) for record in records)
        provenance_scores = [item.score for item in provenance]
        average_provenance = (
            sum(provenance_scores) / len(provenance_scores)
            if provenance_scores
            else None
        )
        prompt_injection_count = sum(
            bool(record.evidence.prompt_injection_finding_rule_ids) for record in records
        )

        p50 = self._percentile(durations, 0.50)
        p95 = self._percentile(durations, 0.95)
        average_duration = sum(durations) / len(durations) if durations else None
        enough_data = len(retrieval_events) >= 5 and total >= 5
        meets = bool(
            enough_data
            and success_rate >= self._thresholds.minimum_success_rate
            and failure_rate <= self._thresholds.maximum_failure_rate
            and duplicate_rate <= self._thresholds.maximum_duplicate_content_rate
            and unique_family_rate >= self._thresholds.minimum_unique_source_family_rate
            and p95 is not None
            and p95 <= self._thresholds.maximum_p95_source_duration_ms
        )
        posture: Literal["insufficient-data", "within-thresholds", "degraded"]
        if not enough_data:
            posture = "insufficient-data"
        elif meets:
            posture = "within-thresholds"
        else:
            posture = "degraded"

        return ResearchOperationsSummary(
            window_event_count=len(events),
            evidence_total=total,
            succeeded=succeeded,
            failed=failed,
            cancelled=cancelled,
            success_rate=round(success_rate, 4),
            failure_rate=round(failure_rate, 4),
            unique_source_family_count=unique_family_count,
            unique_source_family_rate=round(unique_family_rate, 4),
            duplicate_content_group_count=len(duplicate_groups),
            duplicate_content_evidence_count=duplicate_evidence_count,
            duplicate_content_rate=round(duplicate_rate, 4),
            average_source_duration_ms=(
                round(average_duration, 3) if average_duration is not None else None
            ),
            p50_source_duration_ms=p50,
            p95_source_duration_ms=p95,
            retrieval_attempt_count=attempt_count,
            transient_retry_count=retry_count,
            recovered_after_retry_count=recovered_count,
            prompt_injection_evidence_count=prompt_injection_count,
            average_provenance_quality_score=(
                round(average_provenance, 2)
                if average_provenance is not None
                else None
            ),
            errors=tuple(
                ResearchErrorCount(error_code=code, count=count)
                for code, count in errors.most_common()
            ),
            source_families=tuple(
                ResearchSourceFamilyCount(source_family=family, count=count)
                for family, count in family_counts.most_common()
            ),
            duplicate_content_groups=duplicate_groups,
            provenance_quality=provenance,
            thresholds=self._thresholds,
            meets_current_reliability_thresholds=meets,
            reliability_posture=posture,
        )

    def retention_plan(
        self,
        *,
        now: datetime | None = None,
        evidence_limit: int = 500,
    ) -> ResearchRetentionPlan:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("retention-plan clock must be timezone-aware")
        records = self._safe_evidence(evidence_limit)
        duplicate_ids = {
            evidence_id
            for group in self._duplicate_groups(records)
            for evidence_id in group.evidence_ids[1:]
        }
        candidates: list[ResearchRetentionCandidate] = []
        for record in records:
            age_days = max(0, (current - record.stored_at).days)
            evidence = record.evidence
            classification: Literal[
                "preserve",
                "future-archive-duplicate",
                "future-archive-failed",
                "future-archive-aged-success",
            ] = "preserve"
            reason = "default preserve-all policy"
            if (
                evidence.evidence_id in duplicate_ids
                and age_days >= self._retention_policy.duplicate_candidate_after_days
            ):
                classification = "future-archive-duplicate"
                reason = "duplicate normalized content older than dry-run duplicate horizon"
            elif (
                evidence.outcome == "failed"
                and age_days >= self._retention_policy.failed_candidate_after_days
            ):
                classification = "future-archive-failed"
                reason = "failed retrieval older than dry-run failure horizon"
            elif (
                evidence.outcome == "succeeded"
                and age_days >= self._retention_policy.succeeded_candidate_after_days
            ):
                classification = "future-archive-aged-success"
                reason = "successful evidence older than dry-run success horizon"
            candidates.append(
                ResearchRetentionCandidate(
                    evidence_id=evidence.evidence_id,
                    classification=classification,
                    reason=reason,
                    age_days=age_days,
                )
            )

        preserve_count = sum(item.classification == "preserve" for item in candidates)
        return ResearchRetentionPlan(
            policy=self._retention_policy,
            total_evidence=len(candidates),
            preserve_count=preserve_count,
            future_archive_candidate_count=len(candidates) - preserve_count,
            candidates=tuple(candidates),
        )

    def _safe_evidence(self, limit: int) -> list[PersistedResearchRetrievalRecord]:
        try:
            return self._evidence_repository.list_recent(limit=limit)
        except sqlite3.OperationalError as exc:
            if "no such table: research_retrieval_evidence" in str(exc).lower():
                return []
            raise

    def _safe_events(self, limit: int) -> list[ResearchOperationsEvent]:
        try:
            return self._operations_repository.list_recent(limit=limit)
        except sqlite3.OperationalError as exc:
            if "no such table: research_operations_events" in str(exc).lower():
                return []
            raise

    @staticmethod
    def _record_source_family(
        record: PersistedResearchRetrievalRecord,
    ) -> str | None:
        url = record.evidence.final_url or record.evidence.requested_url
        try:
            return canonical_source_family(url)
        except ValueError:
            return None

    def _duplicate_groups(
        self,
        records: list[PersistedResearchRetrievalRecord],
    ) -> tuple[ResearchDuplicateContentGroup, ...]:
        groups: dict[str, list[PersistedResearchRetrievalRecord]] = defaultdict(list)
        for record in records:
            digest = record.evidence.normalized_text_sha256
            if record.evidence.outcome == "succeeded" and digest:
                groups[digest].append(record)

        results: list[ResearchDuplicateContentGroup] = []
        for digest, matches in groups.items():
            if len(matches) < 2:
                continue
            ordered = sorted(matches, key=lambda item: (item.stored_at, item.evidence.evidence_id))
            families = tuple(
                sorted(
                    {
                        family
                        for match in ordered
                        if (family := self._record_source_family(match)) is not None
                    }
                )
            )
            results.append(
                ResearchDuplicateContentGroup(
                    normalized_text_sha256=digest,
                    evidence_ids=tuple(match.evidence.evidence_id for match in ordered),
                    source_families=families,
                    duplicate_count=len(ordered) - 1,
                )
            )
        return tuple(sorted(results, key=lambda item: item.normalized_text_sha256))

    def _provenance_quality(
        self,
        record: PersistedResearchRetrievalRecord,
    ) -> ResearchProvenanceQuality:
        evidence = record.evidence
        score = 0
        if evidence.outcome == "succeeded":
            score += 35
        if evidence.citation is not None:
            score += 25
        if evidence.final_url:
            score += 10
        if evidence.source_body_sha256:
            score += 10
        if evidence.normalized_text_sha256:
            score += 10
        if not evidence.prompt_injection_finding_rule_ids:
            score += 10
        return ResearchProvenanceQuality(
            evidence_id=evidence.evidence_id,
            score=min(100, score),
            outcome=evidence.outcome,
            citation_present=evidence.citation is not None,
            content_hash_present=evidence.source_body_sha256 is not None,
            normalized_hash_present=evidence.normalized_text_sha256 is not None,
            source_family=self._record_source_family(record),
            prompt_injection_finding_count=len(
                evidence.prompt_injection_finding_rule_ids
            ),
        )

    @staticmethod
    def _percentile(values: list[float], quantile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
        return round(ordered[index], 3)
