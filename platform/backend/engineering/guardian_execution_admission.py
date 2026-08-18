from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engineering.codex_execution_contract import CodexExecutionTicket
from engineering.engineering_agent_service import EngineeringWorkOrder

GuardianRiskClass = Literal["non_privileged_workspace"]


class EngineeringGuardianAdmission(BaseModel):
    """DAP-owned proof that one Codex run stays below Guardian privilege."""

    model_config = ConfigDict(frozen=True)

    admission_id: str = Field(min_length=8, max_length=160)
    work_order_id: str
    work_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ticket_id: str
    ticket_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    risk_class: GuardianRiskClass = "non_privileged_workspace"

    codex_execution_admitted: Literal[True] = True
    execution_may_proceed: Literal[True] = True
    guardian_service_contact_required: Literal[False] = False
    guardian_service_contacted: Literal[False] = False
    guardian_broker_contact_allowed: Literal[False] = False
    root_authorization_required: Literal[False] = False
    root_authorization_granted: Literal[False] = False

    network_access_allowed: Literal[False] = False
    privileged_access_allowed: Literal[False] = False
    git_metadata_write_allowed: Literal[False] = False
    external_repository_write_allowed: Literal[False] = False
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
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


class EngineeringGuardianAdmissionService:
    """Admit only non-privileged Engineering Agent workspace execution.

    Phase 11 does not request Guardian privilege on behalf of Codex. Any ticket
    that needs network, root, Guardian, Git metadata, external repository,
    secret, merge, or deployment authority is rejected instead of escalated.
    """

    def admit(
        self,
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
    ) -> EngineeringGuardianAdmission:
        self._validate_binding(work_order=work_order, ticket=ticket)
        self._validate_non_privileged_ticket(ticket)

        work_order_sha256 = work_order.canonical_hash()
        ticket_sha256 = ticket.canonical_hash()
        admission_id = self._admission_id(
            work_order_sha256=work_order_sha256,
            ticket_sha256=ticket_sha256,
        )
        return EngineeringGuardianAdmission(
            admission_id=admission_id,
            work_order_id=work_order.work_order_id,
            work_order_sha256=work_order_sha256,
            ticket_id=ticket.ticket_id,
            ticket_sha256=ticket_sha256,
        )

    @staticmethod
    def _validate_binding(
        *,
        work_order: EngineeringWorkOrder,
        ticket: CodexExecutionTicket,
    ) -> None:
        if ticket.work_order_id != work_order.work_order_id:
            raise ValueError("Guardian admission ticket belongs to another work order")
        if ticket.work_order_sha256 != work_order.canonical_hash():
            raise ValueError("Guardian admission ticket does not match work-order hash")
        if ticket.allowed_paths != work_order.allowed_paths:
            raise ValueError("Guardian admission ticket path scope changed")
        if not work_order.owner_review_required:
            raise ValueError("Guardian admission requires owner review")

    @staticmethod
    def _validate_non_privileged_ticket(ticket: CodexExecutionTicket) -> None:
        if ticket.sandbox_mode != "workspace-write":
            raise ValueError("Guardian admission requires workspace-write sandbox")
        if ticket.approval_policy != "on-request":
            raise ValueError("Guardian admission requires on-request approvals")
        if not ticket.workspace_file_write_allowed or not ticket.codex_execution_allowed:
            raise ValueError("Guardian admission requires a valid Codex workspace ticket")
        if not ticket.shell_execution_inside_sandbox_allowed:
            raise ValueError("Guardian admission requires sandbox-local shell execution")

        prohibited = {
            "network": ticket.network_access_allowed,
            "privileged": ticket.privileged_access_allowed,
            "git-metadata": ticket.git_metadata_write_allowed,
            "external-repository": ticket.external_repository_write_allowed,
            "guardian": ticket.guardian_access_allowed,
            "production-secret": ticket.production_secret_access_allowed,
            "main-merge": ticket.main_merge_allowed,
            "deployment": ticket.deployment_allowed,
        }
        enabled = [name for name, value in prohibited.items() if value]
        if enabled:
            raise ValueError(
                "Engineering execution crossed the non-privileged Guardian boundary: "
                + ", ".join(enabled)
            )
        if not ticket.owner_review_required:
            raise ValueError("Guardian admission requires owner review")

    @staticmethod
    def _admission_id(*, work_order_sha256: str, ticket_sha256: str) -> str:
        digest = hashlib.sha256(
            f"{work_order_sha256}|{ticket_sha256}|phase11d".encode()
        ).hexdigest()[:24]
        return f"guardian-admission-{digest}"


engineering_guardian_admission_service = EngineeringGuardianAdmissionService()
