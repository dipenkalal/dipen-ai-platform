from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from engineering.engineering_agent_service import EngineeringWorkOrder

CodexSandboxMode = Literal["workspace-write"]
CodexApprovalPolicy = Literal["on-request"]
CodexExecutionDisposition = Literal["succeeded", "failed", "rejected"]


class EngineeringExecutionLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    timeout_seconds: int = Field(default=600, ge=30, le=1800)
    max_changed_files: int = Field(default=20, ge=1, le=40)
    max_output_bytes: int = Field(default=1_048_576, ge=4096, le=4_194_304)


class CodexExecutionTicket(BaseModel):
    """DAP-owned authority for one bounded Codex workspace execution."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str = Field(min_length=8, max_length=160)
    work_order_id: str
    work_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_id: str = Field(min_length=4, max_length=160)
    allowed_paths: tuple[str, ...]
    sandbox_mode: CodexSandboxMode = "workspace-write"
    approval_policy: CodexApprovalPolicy = "on-request"
    limits: EngineeringExecutionLimits = Field(
        default_factory=EngineeringExecutionLimits
    )
    workspace_file_write_allowed: Literal[True] = True
    codex_execution_allowed: Literal[True] = True
    shell_execution_inside_sandbox_allowed: Literal[True] = True
    network_access_allowed: Literal[False] = False
    privileged_access_allowed: Literal[False] = False
    git_metadata_write_allowed: Literal[False] = False
    external_repository_write_allowed: Literal[False] = False
    guardian_access_allowed: Literal[False] = False
    production_secret_access_allowed: Literal[False] = False
    main_merge_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    owner_review_required: Literal[True] = True

    def canonical_hash(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class CodexRunnerObservation(BaseModel):
    """Observable facts returned by the executor harness after one run."""

    exit_code: int
    changed_files: list[str] = Field(default_factory=list, max_length=100)
    output_bytes: int = Field(ge=0)
    subprocess_spawned: bool = False
    network_attempted: bool = False
    privileged_access_attempted: bool = False
    git_metadata_modified: bool = False
    external_repository_modified: bool = False
    guardian_access_attempted: bool = False
    production_secret_access_attempted: bool = False

    @field_validator("changed_files")
    @classmethod
    def normalize_changed_files(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("changed file paths must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("changed file paths must be unique")
        return normalized


class CodexExecutionFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=2, max_length=120)
    blocked: bool
    detail: str = Field(min_length=2, max_length=2000)


class CodexExecutionReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: str
    ticket_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    work_order_id: str
    disposition: CodexExecutionDisposition
    exit_code: int
    changed_files: tuple[str, ...]
    findings: tuple[CodexExecutionFinding, ...]
    execution_started: bool
    delivery_allowed: bool
    owner_review_required: Literal[True] = True
    git_commit_created: Literal[False] = False
    pull_request_created: Literal[False] = False
    main_merge_performed: Literal[False] = False
    deployment_performed: Literal[False] = False
    message: str


class EngineeringExecutionPolicy:
    """Promote a no-execution work order into a narrow workspace ticket."""

    def issue_ticket(
        self,
        *,
        work_order: EngineeringWorkOrder,
        workspace_id: str,
        limits: EngineeringExecutionLimits | None = None,
    ) -> CodexExecutionTicket:
        self._validate_work_order(work_order)
        work_order_sha256 = work_order.canonical_hash()
        ticket_id = self._ticket_id(
            work_order_sha256=work_order_sha256,
            workspace_id=workspace_id,
        )
        return CodexExecutionTicket(
            ticket_id=ticket_id,
            work_order_id=work_order.work_order_id,
            work_order_sha256=work_order_sha256,
            workspace_id=workspace_id,
            allowed_paths=work_order.allowed_paths,
            limits=limits or EngineeringExecutionLimits(),
        )

    @staticmethod
    def _validate_work_order(work_order: EngineeringWorkOrder) -> None:
        if not work_order.validation_only or not work_order.owner_review_required:
            raise ValueError("engineering work order lost its Phase 11B safety boundary")

        authority_flags = {
            "execution_authority_granted": work_order.execution_authority_granted,
            "repository_mutation_allowed": work_order.repository_mutation_allowed,
            "git_write_allowed": work_order.git_write_allowed,
            "codex_execution_allowed": work_order.codex_execution_allowed,
            "network_access_allowed": work_order.network_access_allowed,
            "privileged_access_allowed": work_order.privileged_access_allowed,
            "main_merge_allowed": work_order.main_merge_allowed,
            "deployment_allowed": work_order.deployment_allowed,
        }
        enabled = [name for name, value in authority_flags.items() if value]
        if enabled:
            raise ValueError(
                "engineering work order contains unexpected pre-existing authority: "
                + ", ".join(enabled)
            )

    @staticmethod
    def _ticket_id(*, work_order_sha256: str, workspace_id: str) -> str:
        digest = hashlib.sha256(
            f"{work_order_sha256}|{workspace_id}".encode()
        ).hexdigest()[:24]
        return f"codex-ticket-{digest}"


class CodexExecutionValidator:
    """Fail closed on any observed escape from a DAP-issued execution ticket."""

    def evaluate(
        self,
        *,
        ticket: CodexExecutionTicket,
        observation: CodexRunnerObservation,
    ) -> CodexExecutionReceipt:
        findings: list[CodexExecutionFinding] = []
        allowed_paths = set(ticket.allowed_paths)
        changed_paths = set(observation.changed_files)
        outside_scope = sorted(changed_paths - allowed_paths)

        if outside_scope:
            findings.append(
                CodexExecutionFinding(
                    rule_id="changed-files-outside-scope",
                    blocked=True,
                    detail=(
                        "Codex changed repository paths outside the DAP ticket: "
                        + ", ".join(outside_scope)
                    ),
                )
            )

        if len(observation.changed_files) > ticket.limits.max_changed_files:
            findings.append(
                CodexExecutionFinding(
                    rule_id="changed-file-limit",
                    blocked=True,
                    detail="Codex exceeded the DAP changed-file limit.",
                )
            )

        if observation.output_bytes > ticket.limits.max_output_bytes:
            findings.append(
                CodexExecutionFinding(
                    rule_id="output-limit",
                    blocked=True,
                    detail="Codex exceeded the DAP captured-output limit.",
                )
            )

        prohibited_observations = {
            "network-attempt": observation.network_attempted,
            "privileged-access-attempt": observation.privileged_access_attempted,
            "git-metadata-modified": observation.git_metadata_modified,
            "external-repository-modified": observation.external_repository_modified,
            "guardian-access-attempt": observation.guardian_access_attempted,
            "production-secret-access-attempt": (
                observation.production_secret_access_attempted
            ),
        }
        for rule_id, observed in prohibited_observations.items():
            if observed:
                findings.append(
                    CodexExecutionFinding(
                        rule_id=rule_id,
                        blocked=True,
                        detail=f"Executor observation violated ticket rule: {rule_id}",
                    )
                )

        blocked = any(finding.blocked for finding in findings)
        if blocked:
            disposition: CodexExecutionDisposition = "rejected"
        elif observation.exit_code != 0:
            disposition = "failed"
        else:
            disposition = "succeeded"

        delivery_allowed = disposition == "succeeded"
        return CodexExecutionReceipt(
            ticket_id=ticket.ticket_id,
            ticket_sha256=ticket.canonical_hash(),
            work_order_id=ticket.work_order_id,
            disposition=disposition,
            exit_code=observation.exit_code,
            changed_files=tuple(observation.changed_files),
            findings=tuple(findings),
            execution_started=observation.subprocess_spawned,
            delivery_allowed=delivery_allowed,
            message=(
                "Controlled Codex observation passed the DAP execution boundary."
                if disposition == "succeeded"
                else "Controlled Codex observation is not eligible for Git delivery."
            ),
        )


engineering_execution_policy = EngineeringExecutionPolicy()
codex_execution_validator = CodexExecutionValidator()
