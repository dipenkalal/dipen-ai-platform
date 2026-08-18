from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engineering.codex_execution_contract import (
    CodexExecutionReceipt,
    CodexExecutionTicket,
)
from engineering.codex_runner import CodexRunResult
from engineering.engineering_agent_service import EngineeringWorkOrder
from engineering.guardian_execution_admission import EngineeringGuardianAdmission

DAP_REPOSITORY_FULL_NAME: Literal["dipenkalal/dipen-ai-platform"] = "dipenkalal/dipen-ai-platform"
PROTECTED_BASE_BRANCHES = frozenset({"main", "master"})
DELIVERY_BRANCH_PREFIX = "engineering/"


class GitDeliveryPlan(BaseModel):
    """Immutable DAP authority for one post-Codex Git delivery attempt."""

    model_config = ConfigDict(frozen=True)

    delivery_id: str = Field(min_length=8, max_length=160)
    repository_full_name: Literal["dipenkalal/dipen-ai-platform"] = DAP_REPOSITORY_FULL_NAME
    base_branch: str = Field(min_length=2, max_length=180)
    delivery_branch: str = Field(min_length=4, max_length=220)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    work_order_id: str
    work_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ticket_id: str
    ticket_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    guardian_admission_id: str
    guardian_admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    changed_files: tuple[str, ...]
    commit_message: str = Field(min_length=4, max_length=240)
    owner_review_required: Literal[True] = True
    commit_allowed: Literal[True] = True
    delivery_branch_push_allowed: Literal[False] = False
    draft_pull_request_allowed: Literal[False] = False
    github_credentials_exposed_to_codex: Literal[False] = False
    codex_git_authority: Literal[False] = False
    ruflo_git_authority: Literal[False] = False
    force_push_allowed: Literal[False] = False
    main_merge_allowed: Literal[False] = False
    tag_allowed: Literal[False] = False
    release_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False

    def canonical_hash(self) -> str:
        return _canonical_hash(self)


class GitDeliveryObservation(BaseModel):
    """Facts observed after a DAP-owned delivery implementation runs."""

    plan_id: str
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    commit_created: bool = False
    commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    committed_files: tuple[str, ...] = ()
    local_branch_created: bool = False
    remote_branch_pushed: bool = False
    draft_pull_request_created: bool = False
    pull_request_number: int | None = Field(default=None, ge=1)
    force_push_performed: bool = False
    main_merge_performed: bool = False
    tag_created: bool = False
    release_created: bool = False
    deployment_performed: bool = False


class GitDeliveryFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=2, max_length=120)
    blocked: bool
    detail: str = Field(min_length=2, max_length=2000)


class GitDeliveryReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    delivery_id: str
    delivery_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: Literal["succeeded", "rejected"]
    commit_created: bool
    commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    committed_files: tuple[str, ...]
    findings: tuple[GitDeliveryFinding, ...]
    remote_branch_pushed: Literal[False] = False
    draft_pull_request_created: Literal[False] = False
    main_merge_performed: Literal[False] = False
    deployment_performed: Literal[False] = False
    owner_review_required: Literal[True] = True
    message: str


class GitDeliveryService:
    """Derive local-commit-only Git authority from a fully validated run chain."""

    def prepare(
        self,
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
        run_result: CodexRunResult,
        base_branch: str,
    ) -> GitDeliveryPlan:
        base = self._validate_base_branch(base_branch)
        self._validate_chain(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=guardian_admission,
            run_result=run_result,
        )
        receipt_sha256 = self._execution_receipt_hash(run_result.receipt)
        delivery_branch = self._delivery_branch(
            task_id=work_order.source_task_id,
            receipt_sha256=receipt_sha256,
        )
        delivery_id = self._delivery_id(
            work_order_sha256=work_order.canonical_hash(),
            ticket_sha256=ticket.canonical_hash(),
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            receipt_sha256=receipt_sha256,
            source_commit=run_result.source_commit,
            base_branch=base,
            delivery_branch=delivery_branch,
        )

        return GitDeliveryPlan(
            delivery_id=delivery_id,
            base_branch=base,
            delivery_branch=delivery_branch,
            source_commit=run_result.source_commit,
            work_order_id=work_order.work_order_id,
            work_order_sha256=work_order.canonical_hash(),
            ticket_id=ticket.ticket_id,
            ticket_sha256=ticket.canonical_hash(),
            guardian_admission_id=guardian_admission.admission_id,
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            execution_receipt_sha256=receipt_sha256,
            changed_files=run_result.receipt.changed_files,
            commit_message=f"engineering: deliver {work_order.source_task_id}",
        )

    def validate_observation(
        self,
        *,
        plan: GitDeliveryPlan,
        observation: GitDeliveryObservation,
    ) -> GitDeliveryReceipt:
        findings: list[GitDeliveryFinding] = []
        if observation.plan_id != plan.delivery_id:
            findings.append(self._finding("plan-id-mismatch", "Delivery observation belongs to another plan."))
        if observation.plan_sha256 != plan.canonical_hash():
            findings.append(self._finding("plan-hash-mismatch", "Delivery observation does not match the DAP plan hash."))
        if tuple(sorted(observation.committed_files)) != tuple(sorted(plan.changed_files)):
            findings.append(self._finding("committed-files-mismatch", "Git commit files differ from the DAP delivery allowlist."))
        if not observation.commit_created or observation.commit_sha is None:
            findings.append(self._finding("commit-missing", "DAP delivery did not create the required local commit."))
        if not observation.local_branch_created:
            findings.append(self._finding("branch-missing", "DAP delivery did not create its isolated local branch."))

        prohibited = {
            "remote-branch-push": observation.remote_branch_pushed,
            "draft-pr-created": observation.draft_pull_request_created,
            "force-push": observation.force_push_performed,
            "main-merge": observation.main_merge_performed,
            "tag-created": observation.tag_created,
            "release-created": observation.release_created,
            "deployment": observation.deployment_performed,
        }
        for rule_id, observed in prohibited.items():
            if observed:
                findings.append(self._finding(rule_id, f"11E.2 local delivery observed prohibited action: {rule_id}."))

        blocked = any(finding.blocked for finding in findings)
        return GitDeliveryReceipt(
            delivery_id=plan.delivery_id,
            delivery_plan_sha256=plan.canonical_hash(),
            disposition="rejected" if blocked else "succeeded",
            commit_created=observation.commit_created,
            commit_sha=observation.commit_sha,
            committed_files=observation.committed_files,
            findings=tuple(findings),
            message=(
                "Local Git delivery passed; remote publication remains separately disabled."
                if not blocked
                else "Local Git delivery failed the DAP post-delivery boundary."
            ),
        )

    @staticmethod
    def _validate_chain(
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
        run_result: CodexRunResult,
    ) -> None:
        work_hash = work_order.canonical_hash()
        ticket_hash = ticket.canonical_hash()
        admission_hash = guardian_admission.canonical_hash()
        receipt = run_result.receipt

        if ticket.work_order_id != work_order.work_order_id or ticket.work_order_sha256 != work_hash:
            raise ValueError("Git delivery ticket is not bound to this work order")
        if guardian_admission.work_order_id != work_order.work_order_id or guardian_admission.work_order_sha256 != work_hash:
            raise ValueError("Git delivery Guardian admission is not bound to this work order")
        if guardian_admission.ticket_id != ticket.ticket_id or guardian_admission.ticket_sha256 != ticket_hash:
            raise ValueError("Git delivery Guardian admission is not bound to this ticket")
        if run_result.guardian_admission_id != guardian_admission.admission_id or run_result.guardian_admission_sha256 != admission_hash:
            raise ValueError("Git delivery run result is not bound to this Guardian admission")
        if receipt.ticket_id != ticket.ticket_id or receipt.ticket_sha256 != ticket_hash:
            raise ValueError("Git delivery execution receipt is not bound to this ticket")
        if receipt.work_order_id != work_order.work_order_id:
            raise ValueError("Git delivery execution receipt belongs to another work order")
        if receipt.disposition != "succeeded" or not receipt.delivery_allowed or receipt.exit_code != 0:
            raise ValueError("Codex execution is not eligible for Git delivery")
        if receipt.findings:
            raise ValueError("Codex execution receipt contains findings and cannot be delivered")
        if not receipt.changed_files:
            raise ValueError("Git delivery requires at least one changed file")
        if set(receipt.changed_files) - set(work_order.allowed_paths):
            raise ValueError("Git delivery contains files outside the Engineering Agent allowlist")
        if (
            receipt.git_commit_created
            or receipt.pull_request_created
            or receipt.main_merge_performed
            or receipt.deployment_performed
        ):
            raise ValueError("Codex execution already performed prohibited Git or deployment actions")
        if (
            guardian_admission.guardian_service_contacted
            or guardian_admission.root_authorization_granted
            or guardian_admission.guardian_broker_contact_allowed
        ):
            raise ValueError("Git delivery cannot inherit Guardian/root authority")

    @staticmethod
    def _validate_base_branch(value: str) -> str:
        branch = value.strip()
        if not branch or branch in PROTECTED_BASE_BRANCHES:
            raise ValueError("Git delivery base branch must be a non-main development branch")
        if branch.startswith(("refs/", "-")) or any(
            token in branch for token in ("..", " ", "~", "^", ":", "?", "*", "[", "\\")
        ):
            raise ValueError("Git delivery base branch is not a safe Git branch name")
        return branch

    @staticmethod
    def _delivery_branch(*, task_id: str, receipt_sha256: str) -> str:
        safe_task = re.sub(r"[^A-Za-z0-9._-]+", "-", task_id).strip(".-")
        if not safe_task:
            safe_task = "task"
        safe_task = safe_task[:80]
        return f"{DELIVERY_BRANCH_PREFIX}{safe_task}-{receipt_sha256[:12]}"

    @staticmethod
    def _delivery_id(**payload: str) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "git-delivery-" + hashlib.sha256(encoded).hexdigest()[:24]

    @staticmethod
    def _execution_receipt_hash(receipt: CodexExecutionReceipt) -> str:
        return _canonical_hash(receipt)

    @staticmethod
    def _finding(rule_id: str, detail: str) -> GitDeliveryFinding:
        return GitDeliveryFinding(rule_id=rule_id, blocked=True, detail=detail)


def _canonical_hash(model: BaseModel) -> str:
    encoded = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


git_delivery_service = GitDeliveryService()
