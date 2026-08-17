from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agents.truth_schemas import TaskLedgerRecord
from engineering.engineering_audit_evidence import EngineeringAuditEvidence
from engineering.engineering_audit_repository import PersistedEngineeringAuditRecord

OwnerReviewDecisionValue = Literal["approve", "reject"]


class EngineeringOwnerReviewCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    category: str
    status: str
    detail: str = ""


class EngineeringOwnerReviewPackage(BaseModel):
    """Concise DAP-owned owner-review package for one successful delivery."""

    model_config = ConfigDict(frozen=True)

    review_version: Literal["phase11i.1"] = "phase11i.1"
    review_id: str = Field(min_length=12, max_length=160)
    evidence_id: str
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_task_id: str
    objective: str
    work_order_id: str
    risk_level: Literal["low_non_privileged_workspace"] = "low_non_privileged_workspace"
    changed_files: tuple[str, ...]
    checks: tuple[EngineeringOwnerReviewCheck, ...]
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    delivery_branch: str
    draft_pull_request_number: int = Field(ge=1)
    draft_pull_request_url: str
    evidence_outcome: Literal["succeeded"] = "succeeded"
    owner_action_required: Literal["approve_or_reject"] = "approve_or_reject"
    approval_effect: Literal["record_review_only"] = "record_review_only"
    owner_review_required: Literal[True] = True
    git_write_authority_granted: Literal[False] = False
    merge_authority_granted: Literal[False] = False
    deployment_authority_granted: Literal[False] = False
    guardian_authority_granted: Literal[False] = False
    task_ledger_mutation_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_reviewable_delivery(self) -> EngineeringOwnerReviewPackage:
        if not self.changed_files:
            raise ValueError("owner review package requires changed files")
        if not self.checks:
            raise ValueError("owner review package requires check evidence")
        if any(check.status == "failed" for check in self.checks):
            raise ValueError("owner review package cannot contain failed checks")
        return self

    def canonical_hash(self) -> str:
        return _model_hash(self)


class EngineeringOwnerReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: OwnerReviewDecisionValue
    reason: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_reason(self) -> EngineeringOwnerReviewDecisionRequest:
        normalized = self.reason.strip()
        if self.decision == "reject" and len(normalized) < 2:
            raise ValueError("rejection requires a short owner reason")
        object.__setattr__(self, "reason", normalized)
        return self


class EngineeringOwnerReviewDecision(BaseModel):
    """Immutable owner review decision; intentionally grants no execution authority."""

    model_config = ConfigDict(frozen=True)

    decision_version: Literal["phase11i.1"] = "phase11i.1"
    decision_id: str = Field(min_length=12, max_length=160)
    review_id: str
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_id: str
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_task_id: str
    owner_id: Literal["dipen-owner"] = "dipen-owner"
    decision: OwnerReviewDecisionValue
    reason: str = ""
    review_recorded: Literal[True] = True
    owner_merge_action_still_required: Literal[True] = True
    git_write_performed: Literal[False] = False
    pull_request_merged: Literal[False] = False
    main_merge_performed: Literal[False] = False
    deployment_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    task_ledger_mutated: Literal[False] = False

    def canonical_hash(self) -> str:
        return _model_hash(self)


class EngineeringOwnerReviewView(BaseModel):
    model_config = ConfigDict(frozen=True)

    package: EngineeringOwnerReviewPackage
    decision: EngineeringOwnerReviewDecision | None = None


class EngineeringOwnerReviewListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    reviews: tuple[EngineeringOwnerReviewView, ...]
    review_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    merge_controls_exposed: Literal[False] = False
    deployment_controls_exposed: Literal[False] = False
    guardian_controls_exposed: Literal[False] = False


class EngineeringOwnerReviewService:
    """Build owner-facing review packages and non-executing review decisions."""

    def build_package(
        self,
        *,
        task: TaskLedgerRecord,
        record: PersistedEngineeringAuditRecord,
    ) -> EngineeringOwnerReviewPackage:
        evidence = record.evidence
        self._validate_evidence(task=task, evidence=evidence)
        commit_sha = evidence.commit_sha
        delivery_branch = evidence.delivery_branch
        pr_number = evidence.draft_pull_request_number
        pr_url = evidence.draft_pull_request_url
        if commit_sha is None or delivery_branch is None or pr_number is None or pr_url is None:
            raise ValueError("successful engineering evidence is missing delivery metadata")

        review_seed = "|".join(
            (
                record.evidence_sha256,
                task.task_id,
                commit_sha,
                str(pr_number),
            )
        )
        review_id = "engineering-review-" + hashlib.sha256(
            review_seed.encode("utf-8")
        ).hexdigest()[:24]
        checks = tuple(
            EngineeringOwnerReviewCheck(
                name=check.name,
                category=check.category,
                status=check.status,
                detail=check.detail,
            )
            for check in evidence.checks
        )
        return EngineeringOwnerReviewPackage(
            review_id=review_id,
            evidence_id=evidence.evidence_id,
            evidence_sha256=record.evidence_sha256,
            source_task_id=task.task_id,
            objective=task.objective,
            work_order_id=evidence.work_order_id,
            changed_files=evidence.changed_files,
            checks=checks,
            commit_sha=commit_sha,
            delivery_branch=delivery_branch,
            draft_pull_request_number=pr_number,
            draft_pull_request_url=pr_url,
        )

    def decide(
        self,
        *,
        package: EngineeringOwnerReviewPackage,
        request: EngineeringOwnerReviewDecisionRequest,
    ) -> EngineeringOwnerReviewDecision:
        review_sha256 = package.canonical_hash()
        seed = "|".join(
            (
                review_sha256,
                "dipen-owner",
                request.decision,
                request.reason,
            )
        )
        decision_id = "engineering-review-decision-" + hashlib.sha256(
            seed.encode("utf-8")
        ).hexdigest()[:24]
        return EngineeringOwnerReviewDecision(
            decision_id=decision_id,
            review_id=package.review_id,
            review_sha256=review_sha256,
            evidence_id=package.evidence_id,
            evidence_sha256=package.evidence_sha256,
            source_task_id=package.source_task_id,
            decision=request.decision,
            reason=request.reason,
        )

    @staticmethod
    def _validate_evidence(
        *,
        task: TaskLedgerRecord,
        evidence: EngineeringAuditEvidence,
    ) -> None:
        if evidence.source_task_id != task.task_id:
            raise ValueError("engineering evidence belongs to a different canonical task")
        if task.task_type != "agent" or "engineering-agent" not in task.assigned_agent_ids:
            raise ValueError("owner review requires a canonical engineering-agent task")
        if evidence.outcome != "succeeded":
            raise ValueError("only successful engineering evidence is owner-reviewable")
        if not evidence.draft_pull_request_is_draft:
            raise ValueError("owner review requires a draft pull request")
        if not evidence.owner_review_required:
            raise ValueError("engineering evidence unexpectedly waived owner review")
        if evidence.main_merge_performed or evidence.deployment_performed:
            raise ValueError("already merged/deployed evidence cannot enter Phase 11I review")


def _model_hash(model: BaseModel) -> str:
    encoded = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


engineering_owner_review_service = EngineeringOwnerReviewService()
