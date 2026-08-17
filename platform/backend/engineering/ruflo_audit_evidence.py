from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engineering.ruflo_adapter_contract import (
    RufloAdapterReceipt,
    RufloArtifactPin,
    RufloPolicyFinding,
)
from engineering.ruflo_executive_handoff import RufloExecutiveHandoff


class RufloAuditEvidence(BaseModel):
    """Immutable DAP-owned provenance for one Ruflo candidate evaluation."""

    model_config = ConfigDict(frozen=True)

    evidence_version: Literal["phase10d.4"] = "phase10d.4"
    evidence_id: str = Field(min_length=8, max_length=160)

    source_execution_id: str
    source_delegation_id: str
    source_parent_task_id: str
    source_task_id: str
    source_task_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_handoff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    request_id: str
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_artifact: RufloArtifactPin

    source_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_disposition: Literal["accepted", "rejected"]
    candidate_artifact_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    upstream_valid: bool
    dap_policy_findings: list[RufloPolicyFinding] = Field(default_factory=list)

    canonical_task_created: Literal[False] = False
    owner_approval_created: Literal[False] = False
    execution_authority_transferred: Literal[False] = False
    initializer_invoked: Literal[False] = False
    codex_cli_invoked: Literal[False] = False
    mcp_registered: Literal[False] = False
    plugin_installed: Literal[False] = False
    upstream_config_written: Literal[False] = False
    execution_started: Literal[False] = False
    evidence_persisted: Literal[False] = False

    message: str = Field(min_length=4, max_length=2000)

    @model_validator(mode="after")
    def enforce_evidence_consistency(self) -> RufloAuditEvidence:
        blocked = [
            finding.rule_id
            for finding in self.dap_policy_findings
            if finding.blocked
        ]

        if self.candidate_disposition == "accepted":
            if not self.upstream_valid:
                raise ValueError("accepted audit evidence requires upstream validation")
            if self.candidate_artifact_sha256 is None:
                raise ValueError("accepted audit evidence requires a candidate hash")
            if blocked:
                raise ValueError(
                    "accepted audit evidence cannot contain blocked DAP findings: "
                    + ", ".join(blocked)
                )

        if self.candidate_disposition == "rejected" and not self.dap_policy_findings:
            raise ValueError("rejected audit evidence requires DAP policy findings")

        return self

    def canonical_hash(self) -> str:
        return _hash_payload(self.model_dump(mode="json"))


class RufloAuditEvidenceService:
    """Bind DAP task/admission handoff evidence to a Ruflo bridge receipt.

    This service is pure: it writes no database rows, starts no process, and grants
    no authority. Persistence belongs to the later Phase 10F audit integration.
    """

    def build(
        self,
        *,
        handoff: RufloExecutiveHandoff,
        receipt: RufloAdapterReceipt,
    ) -> RufloAuditEvidence:
        self._validate_chain(handoff=handoff, receipt=receipt)

        handoff_sha256 = _hash_model(handoff)
        receipt_sha256 = _hash_model(receipt)
        evidence_id = self._evidence_id(
            handoff_sha256=handoff_sha256,
            receipt_sha256=receipt_sha256,
        )

        return RufloAuditEvidence(
            evidence_id=evidence_id,
            source_execution_id=handoff.source_execution_id,
            source_delegation_id=handoff.source_delegation_id,
            source_parent_task_id=handoff.source_parent_task_id,
            source_task_id=handoff.source_task_id,
            source_task_sha256=handoff.source_task_sha256,
            source_admission_sha256=handoff.source_admission_sha256,
            source_handoff_sha256=handoff_sha256,
            request_id=handoff.request.request_id,
            request_sha256=handoff.request.canonical_hash(),
            adapter_artifact=handoff.request.artifact_pin,
            source_receipt_sha256=receipt_sha256,
            candidate_disposition=receipt.disposition,
            candidate_artifact_sha256=receipt.artifact_sha256,
            upstream_valid=receipt.upstream_valid,
            dap_policy_findings=list(receipt.dap_policy_findings),
            message=(
                "DAP bound canonical task/admission provenance, the bounded Ruflo "
                "handoff, exact adapter identity, candidate result, and explicit "
                "no-execution evidence. Persistence has not started."
            ),
        )

    @staticmethod
    def _validate_chain(
        *,
        handoff: RufloExecutiveHandoff,
        receipt: RufloAdapterReceipt,
    ) -> None:
        if handoff.request.request_id != receipt.request_id:
            raise ValueError("Ruflo receipt belongs to a different handoff request")
        if handoff.request.canonical_hash() != receipt.request_hash:
            raise ValueError("Ruflo receipt request hash does not match the handoff")
        if handoff.request.artifact_pin != receipt.artifact_pin:
            raise ValueError("Ruflo receipt artifact identity does not match the handoff")

        handoff_authority = {
            "canonical_task_created": handoff.canonical_task_created,
            "owner_approval_created": handoff.owner_approval_created,
            "execution_authority_transferred": handoff.execution_authority_transferred,
        }
        enabled_handoff = [
            name for name, value in handoff_authority.items() if value
        ]
        if enabled_handoff:
            raise ValueError(
                "Ruflo handoff contains prohibited authority transfer: "
                + ", ".join(enabled_handoff)
            )

        receipt_side_effects = {
            "initializer_invoked": receipt.initializer_invoked,
            "codex_cli_invoked": receipt.codex_cli_invoked,
            "mcp_registered": receipt.mcp_registered,
            "plugin_installed": receipt.plugin_installed,
            "upstream_config_written": receipt.upstream_config_written,
            "execution_started": receipt.execution_started,
        }
        enabled_receipt = [
            name for name, value in receipt_side_effects.items() if value
        ]
        if enabled_receipt:
            raise ValueError(
                "Ruflo receipt contains prohibited execution side effects: "
                + ", ".join(enabled_receipt)
            )

        blocked = [
            finding.rule_id
            for finding in receipt.dap_policy_findings
            if finding.blocked
        ]
        if receipt.disposition == "accepted":
            if receipt.artifact_sha256 is None:
                raise ValueError("accepted Ruflo receipt is missing candidate hash")
            if not receipt.upstream_valid:
                raise ValueError("accepted Ruflo receipt lacks upstream validation")
            if blocked:
                raise ValueError(
                    "accepted Ruflo receipt contains blocked DAP findings: "
                    + ", ".join(blocked)
                )
        elif not receipt.dap_policy_findings:
            raise ValueError("rejected Ruflo receipt lacks DAP policy findings")

    @staticmethod
    def _evidence_id(*, handoff_sha256: str, receipt_sha256: str) -> str:
        digest = hashlib.sha256(
            f"{handoff_sha256}|{receipt_sha256}".encode("utf-8")
        ).hexdigest()[:24]
        return f"ruflo-audit-{digest}"


def _hash_model(model: BaseModel) -> str:
    return _hash_payload(model.model_dump(mode="json"))


def _hash_payload(payload: object) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


ruflo_audit_evidence_service = RufloAuditEvidenceService()
