from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engineering.git_delivery_contract import (
    DAP_REPOSITORY_FULL_NAME,
    DELIVERY_BRANCH_PREFIX,
    GitDeliveryPlan,
)
from engineering.local_git_delivery import LocalGitDeliveryResult


class RemoteGitPublicationPlan(BaseModel):
    """DAP-only authority for one exact engineering branch and draft PR."""

    model_config = ConfigDict(frozen=True)

    publication_id: str = Field(min_length=8, max_length=160)
    delivery_id: str
    delivery_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repository_full_name: Literal["dipenkalal/dipen-ai-platform"] = (
        DAP_REPOSITORY_FULL_NAME
    )
    base_branch: str = Field(min_length=2, max_length=180)
    delivery_branch: str = Field(min_length=4, max_length=220)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    local_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    committed_files: tuple[str, ...]
    pull_request_title: str = Field(min_length=4, max_length=240)
    pull_request_body: str = Field(min_length=8, max_length=4000)

    owner_review_required: Literal[True] = True
    dap_remote_branch_push_allowed: Literal[True] = True
    dap_draft_pull_request_allowed: Literal[True] = True
    network_access_required: Literal[True] = True
    dap_managed_github_credentials_required: Literal[True] = True

    github_credentials_exposed_to_codex: Literal[False] = False
    github_credentials_exposed_to_ruflo: Literal[False] = False
    codex_git_authority: Literal[False] = False
    ruflo_git_authority: Literal[False] = False
    force_push_allowed: Literal[False] = False
    protected_branch_update_allowed: Literal[False] = False
    pull_request_auto_merge_allowed: Literal[False] = False
    main_merge_allowed: Literal[False] = False
    tag_allowed: Literal[False] = False
    release_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False

    def canonical_hash(self) -> str:
        return _canonical_hash(self)


class RemoteGitPublicationObservation(BaseModel):
    """Facts returned by the DAP-owned remote publisher."""

    publication_id: str
    publication_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    remote_branch_pushed: bool = False
    remote_branch_reused: bool = False
    remote_commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    draft_pull_request_created: bool = False
    draft_pull_request_reused: bool = False
    pull_request_number: int | None = Field(default=None, ge=1)
    pull_request_is_draft: bool = False
    pull_request_base: str | None = None
    pull_request_head: str | None = None
    force_push_performed: bool = False
    protected_branch_updated: bool = False
    pull_request_auto_merge_enabled: bool = False
    main_merge_performed: bool = False
    tag_created: bool = False
    release_created: bool = False
    deployment_performed: bool = False
    github_credentials_exposed_to_codex: bool = False
    github_credentials_exposed_to_ruflo: bool = False


class RemoteGitPublicationFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=2, max_length=120)
    blocked: bool
    detail: str = Field(min_length=2, max_length=2000)


class RemoteGitPublicationReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    publication_id: str
    publication_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: Literal["succeeded", "rejected"]
    remote_commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    pull_request_number: int | None = Field(default=None, ge=1)
    branch_reused: bool
    draft_pull_request_reused: bool
    findings: tuple[RemoteGitPublicationFinding, ...]
    owner_review_required: Literal[True] = True
    force_push_performed: Literal[False] = False
    main_merge_performed: Literal[False] = False
    deployment_performed: Literal[False] = False
    message: str


class RemoteGitPublicationService:
    """Promote a verified local commit into exact DAP-owned remote authority."""

    def prepare(
        self,
        *,
        delivery_plan: GitDeliveryPlan,
        local_result: LocalGitDeliveryResult,
    ) -> RemoteGitPublicationPlan:
        self._validate_local_delivery(
            delivery_plan=delivery_plan,
            local_result=local_result,
        )
        publication_id = self._publication_id(
            delivery_plan_sha256=delivery_plan.canonical_hash(),
            local_commit_sha=local_result.commit_sha,
            repository_full_name=delivery_plan.repository_full_name,
            base_branch=delivery_plan.base_branch,
            delivery_branch=delivery_plan.delivery_branch,
        )
        title = f"Engineering delivery: {delivery_plan.delivery_branch.removeprefix(DELIVERY_BRANCH_PREFIX)}"
        body = (
            "DAP Engineering Agent delivery prepared for owner review.\n\n"
            f"Delivery ID: `{delivery_plan.delivery_id}`\n"
            f"Source commit: `{delivery_plan.source_commit}`\n"
            f"Engineering commit: `{local_result.commit_sha}`\n"
            "\nThis pull request must remain draft until owner review. "
            "Automatic merge and deployment are not authorized."
        )
        return RemoteGitPublicationPlan(
            publication_id=publication_id,
            delivery_id=delivery_plan.delivery_id,
            delivery_plan_sha256=delivery_plan.canonical_hash(),
            base_branch=delivery_plan.base_branch,
            delivery_branch=delivery_plan.delivery_branch,
            source_commit=delivery_plan.source_commit,
            local_commit_sha=local_result.commit_sha,
            committed_files=local_result.receipt.committed_files,
            pull_request_title=title,
            pull_request_body=body,
        )

    def validate_observation(
        self,
        *,
        plan: RemoteGitPublicationPlan,
        observation: RemoteGitPublicationObservation,
    ) -> RemoteGitPublicationReceipt:
        findings: list[RemoteGitPublicationFinding] = []
        if observation.publication_id != plan.publication_id:
            findings.append(self._finding("publication-id-mismatch", "Remote observation belongs to another publication plan."))
        if observation.publication_plan_sha256 != plan.canonical_hash():
            findings.append(self._finding("publication-hash-mismatch", "Remote observation does not match the publication plan hash."))

        if observation.remote_branch_pushed == observation.remote_branch_reused:
            findings.append(self._finding("remote-branch-outcome", "Exactly one of branch push or exact branch reuse must be observed."))
        if observation.remote_commit_sha != plan.local_commit_sha:
            findings.append(self._finding("remote-commit-mismatch", "Remote engineering branch does not point at the exact local delivery commit."))

        if observation.draft_pull_request_created == observation.draft_pull_request_reused:
            findings.append(self._finding("draft-pr-outcome", "Exactly one of draft PR creation or exact draft PR reuse must be observed."))
        if observation.pull_request_number is None:
            findings.append(self._finding("draft-pr-missing", "DAP remote publication requires a draft pull request."))
        if not observation.pull_request_is_draft:
            findings.append(self._finding("pr-not-draft", "Engineering pull request must remain draft."))
        if observation.pull_request_base != plan.base_branch:
            findings.append(self._finding("pr-base-mismatch", "Draft pull request base branch changed."))
        if observation.pull_request_head != plan.delivery_branch:
            findings.append(self._finding("pr-head-mismatch", "Draft pull request head branch changed."))

        prohibited = {
            "force-push": observation.force_push_performed,
            "protected-branch-update": observation.protected_branch_updated,
            "auto-merge": observation.pull_request_auto_merge_enabled,
            "main-merge": observation.main_merge_performed,
            "tag-created": observation.tag_created,
            "release-created": observation.release_created,
            "deployment": observation.deployment_performed,
            "credentials-to-codex": observation.github_credentials_exposed_to_codex,
            "credentials-to-ruflo": observation.github_credentials_exposed_to_ruflo,
        }
        for rule_id, observed in prohibited.items():
            if observed:
                findings.append(self._finding(rule_id, f"Remote publication observed prohibited action: {rule_id}."))

        blocked = any(finding.blocked for finding in findings)
        return RemoteGitPublicationReceipt(
            publication_id=plan.publication_id,
            publication_plan_sha256=plan.canonical_hash(),
            disposition="rejected" if blocked else "succeeded",
            remote_commit_sha=observation.remote_commit_sha,
            pull_request_number=observation.pull_request_number,
            branch_reused=observation.remote_branch_reused,
            draft_pull_request_reused=observation.draft_pull_request_reused,
            findings=tuple(findings),
            message=(
                "DAP engineering branch and draft PR passed remote publication validation."
                if not blocked
                else "Remote engineering publication failed the DAP delivery boundary."
            ),
        )

    @staticmethod
    def _validate_local_delivery(
        *,
        delivery_plan: GitDeliveryPlan,
        local_result: LocalGitDeliveryResult,
    ) -> None:
        if delivery_plan.repository_full_name != DAP_REPOSITORY_FULL_NAME:
            raise ValueError("remote publication repository changed")
        if not delivery_plan.delivery_branch.startswith(DELIVERY_BRANCH_PREFIX):
            raise ValueError("remote publication requires a DAP engineering branch")
        if delivery_plan.base_branch in {"main", "master"}:
            raise ValueError("remote publication cannot target a protected base branch")
        if local_result.receipt.disposition != "succeeded":
            raise ValueError("remote publication requires a successful local delivery receipt")
        if local_result.receipt.delivery_id != delivery_plan.delivery_id:
            raise ValueError("local delivery receipt belongs to another delivery plan")
        if local_result.receipt.delivery_plan_sha256 != delivery_plan.canonical_hash():
            raise ValueError("local delivery receipt does not match delivery plan hash")
        if local_result.source_commit != delivery_plan.source_commit:
            raise ValueError("local delivery source commit changed")
        if local_result.delivery_branch != delivery_plan.delivery_branch:
            raise ValueError("local delivery branch changed")
        if local_result.receipt.commit_sha != local_result.commit_sha:
            raise ValueError("local delivery commit receipt changed")
        if local_result.receipt.committed_files != delivery_plan.changed_files:
            raise ValueError("local delivery file set changed")
        if local_result.remote_count != 0:
            raise ValueError("remote publication requires the network-free local delivery result")

        forbidden_local_authority = {
            "delivery-branch-push": delivery_plan.delivery_branch_push_allowed,
            "draft-pr": delivery_plan.draft_pull_request_allowed,
            "codex-git": delivery_plan.codex_git_authority,
            "ruflo-git": delivery_plan.ruflo_git_authority,
            "force-push": delivery_plan.force_push_allowed,
            "main-merge": delivery_plan.main_merge_allowed,
            "tag": delivery_plan.tag_allowed,
            "release": delivery_plan.release_allowed,
            "deployment": delivery_plan.deployment_allowed,
        }
        enabled = [name for name, value in forbidden_local_authority.items() if value]
        if enabled:
            raise ValueError(
                "remote publication refuses a local delivery plan with remote authority: "
                + ", ".join(enabled)
            )

    @staticmethod
    def _publication_id(**payload: str) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "git-publication-" + hashlib.sha256(encoded).hexdigest()[:24]

    @staticmethod
    def _finding(rule_id: str, detail: str) -> RemoteGitPublicationFinding:
        return RemoteGitPublicationFinding(rule_id=rule_id, blocked=True, detail=detail)


def _canonical_hash(model: BaseModel) -> str:
    encoded = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


remote_git_publication_service = RemoteGitPublicationService()
