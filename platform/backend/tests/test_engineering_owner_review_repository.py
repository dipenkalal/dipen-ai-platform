from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.truth_repository import AgentTruthRepository
from engineering.engineering_audit_repository import (
    EngineeringAuditRepository,
    PersistedEngineeringAuditRecord,
)
from engineering.engineering_owner_review import (
    EngineeringOwnerReviewDecisionRequest,
    engineering_owner_review_service,
)
from engineering.engineering_owner_review_repository import (
    EngineeringOwnerReviewConflict,
    EngineeringOwnerReviewRepository,
)
from tests.test_engineering_owner_review import (
    engineering_task,
    successful_evidence,
)


def repositories(tmp_path: Path):
    truth = AgentTruthRepository(tmp_path / "agent-truth.db")
    task = engineering_task()
    truth.upsert_task(task)
    audit = EngineeringAuditRepository(truth)
    evidence = successful_evidence()
    persisted_evidence = audit.persist(evidence)
    review = EngineeringOwnerReviewRepository(truth, audit)
    package = engineering_owner_review_service.build_package(
        task=task,
        record=persisted_evidence,
    )
    return truth, audit, review, package


def test_owner_review_persistence_is_idempotent_and_additive(tmp_path: Path) -> None:
    truth, _audit, review, package = repositories(tmp_path)
    task_before = truth.get_task(package.source_task_id)
    decision = engineering_owner_review_service.decide(
        package=package,
        request=EngineeringOwnerReviewDecisionRequest(
            decision="approve",
            reason="Owner accepts the review package.",
        ),
    )

    first = review.persist(decision)
    replay = review.persist(decision)

    assert replay.decision == first.decision
    assert replay.decision_sha256 == first.decision_sha256
    assert replay.stored_at == first.stored_at
    assert first.task_ledger_mutated is False
    assert first.git_write_performed is False
    assert first.pull_request_merged is False
    assert first.deployment_performed is False
    assert truth.get_task(package.source_task_id) == task_before


def test_conflicting_second_decision_fails_closed(tmp_path: Path) -> None:
    _truth, _audit, review, package = repositories(tmp_path)
    approve = engineering_owner_review_service.decide(
        package=package,
        request=EngineeringOwnerReviewDecisionRequest(decision="approve"),
    )
    reject = engineering_owner_review_service.decide(
        package=package,
        request=EngineeringOwnerReviewDecisionRequest(
            decision="reject",
            reason="Owner rejected the delivery after review.",
        ),
    )
    review.persist(approve)

    with pytest.raises(EngineeringOwnerReviewConflict):
        review.persist(reject)


def test_review_repository_requires_persisted_evidence(tmp_path: Path) -> None:
    truth = AgentTruthRepository(tmp_path / "agent-truth.db")
    task = engineering_task()
    truth.upsert_task(task)
    audit = EngineeringAuditRepository(truth)
    review = EngineeringOwnerReviewRepository(truth, audit)
    evidence = successful_evidence()

    package = engineering_owner_review_service.build_package(
        task=task,
        record=PersistedEngineeringAuditRecord(
            evidence=evidence,
            evidence_sha256=evidence.canonical_hash(),
            stored_at=datetime.now(timezone.utc),
        ),
    )
    decision = engineering_owner_review_service.decide(
        package=package,
        request=EngineeringOwnerReviewDecisionRequest(decision="approve"),
    )

    with pytest.raises(ValueError, match="persisted engineering evidence"):
        review.persist(decision)
