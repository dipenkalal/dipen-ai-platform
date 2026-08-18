from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engineering.codex_execution_contract import CodexExecutionTicket
from engineering.codex_runner import CODEX_CLI_VERSION, CodexRunResult
from engineering.engineering_agent_service import EngineeringWorkOrder
from engineering.engineering_diff_evidence import EngineeringDiffEvidence
from engineering.git_delivery_contract import GitDeliveryPlan
from engineering.guardian_execution_admission import EngineeringGuardianAdmission
from engineering.local_git_delivery import LocalGitDeliveryResult
from engineering.remote_git_publication import RemoteGitPublicationPlan
from engineering.remote_git_publisher import RemoteGitPublisherResult

EngineeringOutcome = Literal["succeeded", "failed", "rejected", "cancelled"]
EngineeringCheckStatus = Literal["passed", "failed", "skipped"]
EngineeringTerminalStage = Literal[
    "codex_execution",
    "git_delivery",
    "remote_publication",
    "post_publication_checks",
]


class EngineeringCheckResult(BaseModel):
    """DAP-observed result for one deterministic engineering check."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=2, max_length=160)
    category: Literal["lint", "typecheck", "compile", "test", "ci", "policy"]
    status: EngineeringCheckStatus
    source: str = Field(min_length=2, max_length=240)
    detail: str = Field(default="", max_length=2000)


class EngineeringPolicyDecision(BaseModel):
    """One policy fact attributable to DAP, Guardian, or owner policy."""

    model_config = ConfigDict(frozen=True)

    policy_id: str = Field(min_length=2, max_length=160)
    authority: Literal["dap", "guardian", "owner"]
    decision: Literal["allow", "deny", "require"]
    detail: str = Field(min_length=2, max_length=2000)


class EngineeringAuditEvidence(BaseModel):
    """Immutable Phase 11 evidence for one terminal engineering attempt."""

    model_config = ConfigDict(frozen=True)

    evidence_version: Literal["phase11f.1"] = "phase11f.1"
    evidence_id: str = Field(min_length=12, max_length=160)

    source_execution_id: str
    source_delegation_id: str
    source_parent_task_id: str
    source_task_id: str
    source_task_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    work_order_id: str
    work_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ticket_id: str
    ticket_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    guardian_admission_id: str
    guardian_admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    guardian_risk_class: Literal["non_privileged_workspace"]

    executor_runtime_identity: str = Field(min_length=4, max_length=160)
    command_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    allowed_paths: tuple[str, ...]
    admitted_actions: tuple[str, ...]
    policy_decisions: tuple[EngineeringPolicyDecision, ...]

    execution_receipt_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    execution_disposition: Literal["not_started", "succeeded", "failed", "rejected"]
    execution_exit_code: int | None = None
    execution_findings: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()

    diff_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    checks: tuple[EngineeringCheckResult, ...] = ()

    delivery_id: str | None = None
    delivery_plan_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    delivery_receipt_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")

    publication_id: str | None = None
    publication_plan_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    publication_receipt_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    delivery_branch: str | None = None
    remote_commit_sha: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{40}$",
    )
    draft_pull_request_number: int | None = Field(default=None, ge=1)
    draft_pull_request_url: str | None = None
    draft_pull_request_is_draft: bool = False

    outcome: EngineeringOutcome
    terminal_stage: EngineeringTerminalStage | None = None
    failure_information: str | None = Field(default=None, max_length=4000)
    cancellation_information: str | None = Field(default=None, max_length=4000)

    owner_review_required: Literal[True] = True
    github_credentials_exposed_to_codex: Literal[False] = False
    github_credentials_exposed_to_ruflo: Literal[False] = False
    codex_git_authority: Literal[False] = False
    ruflo_git_authority: Literal[False] = False
    force_push_performed: Literal[False] = False
    protected_branch_updated: Literal[False] = False
    pull_request_auto_merge_enabled: Literal[False] = False
    main_merge_performed: Literal[False] = False
    tag_created: Literal[False] = False
    release_created: Literal[False] = False
    deployment_performed: Literal[False] = False
    task_ledger_mutated: Literal[False] = False

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> EngineeringAuditEvidence:
        if not self.allowed_paths:
            raise ValueError("engineering audit evidence requires allowed paths")
        if not self.admitted_actions:
            raise ValueError("engineering audit evidence requires admitted actions")
        if not self.policy_decisions:
            raise ValueError("engineering audit evidence requires policy decisions")

        if self.outcome == "succeeded":
            required = {
                "command_sha256": self.command_sha256,
                "execution_receipt_sha256": self.execution_receipt_sha256,
                "diff_sha256": self.diff_sha256,
                "delivery_id": self.delivery_id,
                "delivery_plan_sha256": self.delivery_plan_sha256,
                "delivery_receipt_sha256": self.delivery_receipt_sha256,
                "commit_sha": self.commit_sha,
                "publication_id": self.publication_id,
                "publication_plan_sha256": self.publication_plan_sha256,
                "publication_receipt_sha256": self.publication_receipt_sha256,
                "delivery_branch": self.delivery_branch,
                "remote_commit_sha": self.remote_commit_sha,
                "draft_pull_request_number": self.draft_pull_request_number,
                "draft_pull_request_url": self.draft_pull_request_url,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise ValueError(
                    "successful engineering evidence is incomplete: "
                    + ", ".join(missing)
                )
            if self.execution_disposition != "succeeded":
                raise ValueError("successful engineering evidence requires successful execution")
            if not self.changed_files:
                raise ValueError("successful engineering evidence requires changed files")
            if not self.checks or not any(check.status == "passed" for check in self.checks):
                raise ValueError("successful engineering evidence requires passed checks")
            if any(check.status == "failed" for check in self.checks):
                raise ValueError("successful engineering evidence cannot contain failed checks")
            if not self.draft_pull_request_is_draft:
                raise ValueError("successful engineering evidence requires a draft PR")
            if self.failure_information or self.cancellation_information:
                raise ValueError("successful engineering evidence cannot contain terminal errors")
        elif self.outcome in {"failed", "rejected"}:
            if not self.terminal_stage or not self.failure_information:
                raise ValueError("failed engineering evidence requires stage and failure detail")
            if self.cancellation_information:
                raise ValueError("failed engineering evidence cannot contain cancellation detail")
        elif self.outcome == "cancelled":
            if not self.terminal_stage or not self.cancellation_information:
                raise ValueError(
                    "cancelled engineering evidence requires stage and cancellation detail"
                )
            if self.failure_information:
                raise ValueError("cancelled engineering evidence cannot contain failure detail")
        return self

    def canonical_hash(self) -> str:
        return _model_hash(self)


class EngineeringAuditEvidenceService:
    """Build attributable DAP evidence from already-bounded Phase 11 artifacts."""

    def build_success(
        self,
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
        run_result: CodexRunResult,
        delivery_plan: GitDeliveryPlan,
        local_result: LocalGitDeliveryResult,
        diff_evidence: EngineeringDiffEvidence,
        publication_plan: RemoteGitPublicationPlan,
        publisher_result: RemoteGitPublisherResult,
        checks: tuple[EngineeringCheckResult, ...],
    ) -> EngineeringAuditEvidence:
        self._validate_execution_chain(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=guardian_admission,
            run_result=run_result,
        )
        self._validate_delivery_chain(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=guardian_admission,
            run_result=run_result,
            delivery_plan=delivery_plan,
            local_result=local_result,
            diff_evidence=diff_evidence,
        )
        self._validate_publication_chain(
            delivery_plan=delivery_plan,
            local_result=local_result,
            publication_plan=publication_plan,
            publisher_result=publisher_result,
        )
        if not checks or any(check.status == "failed" for check in checks):
            raise ValueError("successful engineering evidence requires non-failing checks")

        execution_receipt_sha256 = _model_hash(run_result.receipt)
        delivery_receipt_sha256 = _model_hash(local_result.receipt)
        publication_receipt_sha256 = _model_hash(publisher_result.receipt)
        evidence_id = self._evidence_id(
            work_order_sha256=work_order.canonical_hash(),
            ticket_sha256=ticket.canonical_hash(),
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            execution_receipt_sha256=execution_receipt_sha256,
            delivery_receipt_sha256=delivery_receipt_sha256,
            publication_receipt_sha256=publication_receipt_sha256,
            outcome="succeeded",
        )

        return EngineeringAuditEvidence(
            evidence_id=evidence_id,
            source_execution_id=work_order.source_execution_id,
            source_delegation_id=work_order.source_delegation_id,
            source_parent_task_id=work_order.source_parent_task_id,
            source_task_id=work_order.source_task_id,
            source_task_sha256=work_order.source_task_sha256,
            source_admission_sha256=work_order.source_admission_sha256,
            work_order_id=work_order.work_order_id,
            work_order_sha256=work_order.canonical_hash(),
            ticket_id=ticket.ticket_id,
            ticket_sha256=ticket.canonical_hash(),
            guardian_admission_id=guardian_admission.admission_id,
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            guardian_risk_class=guardian_admission.risk_class,
            executor_runtime_identity=CODEX_CLI_VERSION,
            command_sha256=run_result.command_sha256,
            allowed_paths=work_order.allowed_paths,
            admitted_actions=(
                "codex.workspace_execute",
                "git.local_commit",
                "git.remote_engineering_branch_create",
                "github.draft_pull_request_create",
            ),
            policy_decisions=self._success_policy_decisions(),
            execution_receipt_sha256=execution_receipt_sha256,
            execution_disposition=run_result.receipt.disposition,
            execution_exit_code=run_result.receipt.exit_code,
            execution_findings=tuple(
                finding.rule_id for finding in run_result.receipt.findings
            ),
            changed_files=run_result.receipt.changed_files,
            diff_sha256=diff_evidence.diff_sha256,
            checks=checks,
            delivery_id=delivery_plan.delivery_id,
            delivery_plan_sha256=delivery_plan.canonical_hash(),
            delivery_receipt_sha256=delivery_receipt_sha256,
            commit_sha=local_result.commit_sha,
            publication_id=publication_plan.publication_id,
            publication_plan_sha256=publication_plan.canonical_hash(),
            publication_receipt_sha256=publication_receipt_sha256,
            delivery_branch=publication_plan.delivery_branch,
            remote_commit_sha=publisher_result.remote_commit_sha,
            draft_pull_request_number=publisher_result.pull_request_number,
            draft_pull_request_url=publisher_result.pull_request_url,
            draft_pull_request_is_draft=True,
            outcome="succeeded",
        )

    def build_execution_failure(
        self,
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
        run_result: CodexRunResult,
        failure_information: str,
        checks: tuple[EngineeringCheckResult, ...] = (),
    ) -> EngineeringAuditEvidence:
        self._validate_execution_chain(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=guardian_admission,
            run_result=run_result,
            require_success=False,
        )
        if run_result.receipt.disposition == "succeeded":
            raise ValueError("execution-failure evidence cannot wrap a successful receipt")
        outcome: Literal["failed", "rejected"] = (
            "rejected" if run_result.receipt.disposition == "rejected" else "failed"
        )
        receipt_sha256 = _model_hash(run_result.receipt)
        evidence_id = self._evidence_id(
            work_order_sha256=work_order.canonical_hash(),
            ticket_sha256=ticket.canonical_hash(),
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            execution_receipt_sha256=receipt_sha256,
            delivery_receipt_sha256="",
            publication_receipt_sha256="",
            outcome=outcome,
        )
        return EngineeringAuditEvidence(
            evidence_id=evidence_id,
            source_execution_id=work_order.source_execution_id,
            source_delegation_id=work_order.source_delegation_id,
            source_parent_task_id=work_order.source_parent_task_id,
            source_task_id=work_order.source_task_id,
            source_task_sha256=work_order.source_task_sha256,
            source_admission_sha256=work_order.source_admission_sha256,
            work_order_id=work_order.work_order_id,
            work_order_sha256=work_order.canonical_hash(),
            ticket_id=ticket.ticket_id,
            ticket_sha256=ticket.canonical_hash(),
            guardian_admission_id=guardian_admission.admission_id,
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            guardian_risk_class=guardian_admission.risk_class,
            executor_runtime_identity=CODEX_CLI_VERSION,
            command_sha256=run_result.command_sha256,
            allowed_paths=work_order.allowed_paths,
            admitted_actions=("codex.workspace_execute",),
            policy_decisions=self._execution_policy_decisions(),
            execution_receipt_sha256=receipt_sha256,
            execution_disposition=run_result.receipt.disposition,
            execution_exit_code=run_result.receipt.exit_code,
            execution_findings=tuple(
                finding.rule_id for finding in run_result.receipt.findings
            ),
            changed_files=run_result.receipt.changed_files,
            checks=checks,
            outcome=outcome,
            terminal_stage="codex_execution",
            failure_information=failure_information.strip(),
        )

    def build_cancelled_before_execution(
        self,
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
        cancellation_information: str,
    ) -> EngineeringAuditEvidence:
        self._validate_ticket_and_admission(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=guardian_admission,
        )
        evidence_id = self._evidence_id(
            work_order_sha256=work_order.canonical_hash(),
            ticket_sha256=ticket.canonical_hash(),
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            execution_receipt_sha256="",
            delivery_receipt_sha256="",
            publication_receipt_sha256="",
            outcome="cancelled",
        )
        return EngineeringAuditEvidence(
            evidence_id=evidence_id,
            source_execution_id=work_order.source_execution_id,
            source_delegation_id=work_order.source_delegation_id,
            source_parent_task_id=work_order.source_parent_task_id,
            source_task_id=work_order.source_task_id,
            source_task_sha256=work_order.source_task_sha256,
            source_admission_sha256=work_order.source_admission_sha256,
            work_order_id=work_order.work_order_id,
            work_order_sha256=work_order.canonical_hash(),
            ticket_id=ticket.ticket_id,
            ticket_sha256=ticket.canonical_hash(),
            guardian_admission_id=guardian_admission.admission_id,
            guardian_admission_sha256=guardian_admission.canonical_hash(),
            guardian_risk_class=guardian_admission.risk_class,
            executor_runtime_identity=CODEX_CLI_VERSION,
            allowed_paths=work_order.allowed_paths,
            admitted_actions=("codex.workspace_execute",),
            policy_decisions=self._execution_policy_decisions(),
            execution_disposition="not_started",
            outcome="cancelled",
            terminal_stage="codex_execution",
            cancellation_information=cancellation_information.strip(),
        )

    @staticmethod
    def _validate_ticket_and_admission(
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
    ) -> None:
        work_hash = work_order.canonical_hash()
        ticket_hash = ticket.canonical_hash()
        if ticket.work_order_id != work_order.work_order_id:
            raise ValueError("audit ticket belongs to another work order")
        if ticket.work_order_sha256 != work_hash:
            raise ValueError("audit ticket work-order hash changed")
        if ticket.allowed_paths != work_order.allowed_paths:
            raise ValueError("audit ticket allowed paths changed")
        if guardian_admission.work_order_id != work_order.work_order_id:
            raise ValueError("audit Guardian admission belongs to another work order")
        if guardian_admission.work_order_sha256 != work_hash:
            raise ValueError("audit Guardian work-order hash changed")
        if guardian_admission.ticket_id != ticket.ticket_id:
            raise ValueError("audit Guardian admission belongs to another ticket")
        if guardian_admission.ticket_sha256 != ticket_hash:
            raise ValueError("audit Guardian ticket hash changed")
        if guardian_admission.guardian_service_contacted:
            raise ValueError("Phase 11 audit refuses unexpected Guardian service contact")
        if guardian_admission.root_authorization_granted:
            raise ValueError("Phase 11 audit refuses unexpected root authorization")

    @classmethod
    def _validate_execution_chain(
        cls,
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
        run_result: CodexRunResult,
        require_success: bool = True,
    ) -> None:
        cls._validate_ticket_and_admission(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=guardian_admission,
        )
        if run_result.receipt.ticket_id != ticket.ticket_id:
            raise ValueError("audit execution receipt belongs to another ticket")
        if run_result.receipt.ticket_sha256 != ticket.canonical_hash():
            raise ValueError("audit execution receipt ticket hash changed")
        if run_result.receipt.work_order_id != work_order.work_order_id:
            raise ValueError("audit execution receipt belongs to another work order")
        if run_result.guardian_admission_id != guardian_admission.admission_id:
            raise ValueError("audit run result Guardian admission changed")
        if run_result.guardian_admission_sha256 != guardian_admission.canonical_hash():
            raise ValueError("audit run result Guardian admission hash changed")
        if require_success and (
            run_result.receipt.disposition != "succeeded"
            or not run_result.receipt.delivery_allowed
        ):
            raise ValueError("successful engineering audit requires delivery-eligible execution")

    @staticmethod
    def _validate_delivery_chain(
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
        guardian_admission: EngineeringGuardianAdmission,
        run_result: CodexRunResult,
        delivery_plan: GitDeliveryPlan,
        local_result: LocalGitDeliveryResult,
        diff_evidence: EngineeringDiffEvidence,
    ) -> None:
        if delivery_plan.work_order_id != work_order.work_order_id:
            raise ValueError("audit delivery plan belongs to another work order")
        if delivery_plan.work_order_sha256 != work_order.canonical_hash():
            raise ValueError("audit delivery work-order hash changed")
        if delivery_plan.ticket_id != ticket.ticket_id:
            raise ValueError("audit delivery plan belongs to another ticket")
        if delivery_plan.ticket_sha256 != ticket.canonical_hash():
            raise ValueError("audit delivery ticket hash changed")
        if delivery_plan.guardian_admission_id != guardian_admission.admission_id:
            raise ValueError("audit delivery Guardian admission changed")
        if delivery_plan.guardian_admission_sha256 != guardian_admission.canonical_hash():
            raise ValueError("audit delivery Guardian hash changed")
        if delivery_plan.execution_receipt_sha256 != _model_hash(run_result.receipt):
            raise ValueError("audit delivery execution receipt hash changed")
        if local_result.receipt.delivery_id != delivery_plan.delivery_id:
            raise ValueError("audit local delivery receipt belongs to another plan")
        if local_result.receipt.delivery_plan_sha256 != delivery_plan.canonical_hash():
            raise ValueError("audit local delivery plan hash changed")
        if local_result.receipt.disposition != "succeeded":
            raise ValueError("audit requires successful local Git delivery")
        if local_result.commit_sha != local_result.receipt.commit_sha:
            raise ValueError("audit local delivery commit receipt changed")
        if local_result.receipt.committed_files != run_result.receipt.changed_files:
            raise ValueError("audit local delivery file set changed")
        if diff_evidence.commit_sha != local_result.commit_sha:
            raise ValueError("audit diff evidence commit changed")
        if diff_evidence.parent_sha != local_result.source_commit:
            raise ValueError("audit diff evidence parent changed")
        if diff_evidence.changed_files != tuple(sorted(local_result.receipt.committed_files)):
            raise ValueError("audit diff evidence file set changed")

    @staticmethod
    def _validate_publication_chain(
        *,
        delivery_plan: GitDeliveryPlan,
        local_result: LocalGitDeliveryResult,
        publication_plan: RemoteGitPublicationPlan,
        publisher_result: RemoteGitPublisherResult,
    ) -> None:
        if publication_plan.delivery_id != delivery_plan.delivery_id:
            raise ValueError("audit publication plan belongs to another delivery")
        if publication_plan.delivery_plan_sha256 != delivery_plan.canonical_hash():
            raise ValueError("audit publication delivery plan hash changed")
        if publication_plan.local_commit_sha != local_result.commit_sha:
            raise ValueError("audit publication local commit changed")
        if publication_plan.committed_files != local_result.receipt.committed_files:
            raise ValueError("audit publication committed files changed")
        if publisher_result.publication_id != publication_plan.publication_id:
            raise ValueError("audit publisher result belongs to another publication")
        if publisher_result.publication_plan_sha256 != publication_plan.canonical_hash():
            raise ValueError("audit publisher result plan hash changed")
        if publisher_result.receipt.disposition != "succeeded":
            raise ValueError("audit requires successful remote publication")
        if publisher_result.remote_commit_sha != local_result.commit_sha:
            raise ValueError("audit remote commit differs from local delivery commit")
        if publisher_result.receipt.pull_request_number != publisher_result.pull_request_number:
            raise ValueError("audit publisher pull request receipt changed")
        prohibited = {
            "credentials-to-codex": publisher_result.github_credentials_exposed_to_codex,
            "credentials-to-ruflo": publisher_result.github_credentials_exposed_to_ruflo,
            "force-push": publisher_result.force_push_performed,
            "main-merge": publisher_result.main_merge_performed,
            "deployment": publisher_result.deployment_performed,
        }
        enabled = [name for name, value in prohibited.items() if value]
        if enabled:
            raise ValueError(
                "audit publisher result contains prohibited authority: "
                + ", ".join(enabled)
            )

    @staticmethod
    def _execution_policy_decisions() -> tuple[EngineeringPolicyDecision, ...]:
        return (
            EngineeringPolicyDecision(
                policy_id="guardian-non-privileged-workspace",
                authority="guardian",
                decision="allow",
                detail="DAP admitted one non-privileged workspace execution.",
            ),
            EngineeringPolicyDecision(
                policy_id="network-access",
                authority="dap",
                decision="deny",
                detail="Engineering execution has no network authority.",
            ),
            EngineeringPolicyDecision(
                policy_id="privileged-access",
                authority="guardian",
                decision="deny",
                detail="Engineering execution has no root or privileged host authority.",
            ),
            EngineeringPolicyDecision(
                policy_id="owner-review",
                authority="owner",
                decision="require",
                detail="Any delivered engineering result requires owner review.",
            ),
        )

    @classmethod
    def _success_policy_decisions(cls) -> tuple[EngineeringPolicyDecision, ...]:
        return (
            *cls._execution_policy_decisions(),
            EngineeringPolicyDecision(
                policy_id="local-git-commit",
                authority="dap",
                decision="allow",
                detail="DAP admitted one bounded local Git commit.",
            ),
            EngineeringPolicyDecision(
                policy_id="remote-engineering-branch",
                authority="dap",
                decision="allow",
                detail="DAP admitted creation or exact reuse of one engineering branch.",
            ),
            EngineeringPolicyDecision(
                policy_id="draft-pull-request",
                authority="dap",
                decision="allow",
                detail="DAP admitted one exact draft pull request for owner review.",
            ),
            EngineeringPolicyDecision(
                policy_id="merge-release-deploy",
                authority="owner",
                decision="deny",
                detail="Automatic merge, tag, release, and deployment remain prohibited.",
            ),
        )

    @staticmethod
    def _evidence_id(
        *,
        work_order_sha256: str,
        ticket_sha256: str,
        guardian_admission_sha256: str,
        execution_receipt_sha256: str,
        delivery_receipt_sha256: str,
        publication_receipt_sha256: str,
        outcome: EngineeringOutcome,
    ) -> str:
        payload = {
            "work_order_sha256": work_order_sha256,
            "ticket_sha256": ticket_sha256,
            "guardian_admission_sha256": guardian_admission_sha256,
            "execution_receipt_sha256": execution_receipt_sha256,
            "delivery_receipt_sha256": delivery_receipt_sha256,
            "publication_receipt_sha256": publication_receipt_sha256,
            "outcome": outcome,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]
        return f"engineering-audit-{digest}"


def _model_hash(model: BaseModel) -> str:
    encoded = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


engineering_audit_evidence_service = EngineeringAuditEvidenceService()
