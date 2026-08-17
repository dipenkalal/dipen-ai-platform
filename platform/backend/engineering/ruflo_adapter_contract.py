from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator

RUFLO_CODEX_PACKAGE = "@claude-flow/codex"
RUFLO_CODEX_PACKAGE_VERSION = "3.0.2"
RUFLO_CODEX_CLI_SHA256 = (
    "1df00b5aa26c6d76b354bbf2d80042c9c91e83b877c7bacc22f96ee098bea096"
)

AdapterDisposition = Literal["accepted", "rejected"]
AdapterCapability = Literal["generate_agents", "validate_agents"]


class RufloArtifactPin(BaseModel):
    package_name: Literal["@claude-flow/codex"] = RUFLO_CODEX_PACKAGE
    package_version: Literal["3.0.2"] = RUFLO_CODEX_PACKAGE_VERSION
    cli_sha256: Literal[
        "1df00b5aa26c6d76b354bbf2d80042c9c91e83b877c7bacc22f96ee098bea096"
    ] = RUFLO_CODEX_CLI_SHA256


class EngineeringTaskEnvelope(BaseModel):
    task_id: str = Field(min_length=4, max_length=160)
    objective: str = Field(min_length=4, max_length=4000)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)
    allowed_paths: list[str] = Field(default_factory=list, max_length=40)
    constraints: list[str] = Field(default_factory=list, max_length=40)
    requires_network: bool = False
    requires_privileged_execution: bool = False


class RufloAdapterRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=160)
    task: EngineeringTaskEnvelope
    artifact_pin: RufloArtifactPin = Field(default_factory=RufloArtifactPin)
    capabilities: list[AdapterCapability] = Field(
        default_factory=lambda: ["generate_agents", "validate_agents"],
        min_length=1,
        max_length=2,
    )
    validation_only: bool = True
    allow_initializer: bool = False
    allow_codex_cli: bool = False
    allow_mcp_registration: bool = False
    allow_plugin_installation: bool = False
    allow_upstream_config_write: bool = False

    @model_validator(mode="after")
    def enforce_phase10_boundary(self) -> RufloAdapterRequest:
        prohibited = {
            "validation_only": not self.validation_only,
            "allow_initializer": self.allow_initializer,
            "allow_codex_cli": self.allow_codex_cli,
            "allow_mcp_registration": self.allow_mcp_registration,
            "allow_plugin_installation": self.allow_plugin_installation,
            "allow_upstream_config_write": self.allow_upstream_config_write,
            "requires_network": self.task.requires_network,
            "requires_privileged_execution": self.task.requires_privileged_execution,
        }
        enabled = [name for name, value in prohibited.items() if value]
        if enabled:
            raise ValueError(
                "Ruflo adapter request violates the Phase 10 validation-only boundary: "
                + ", ".join(enabled)
            )
        return self

    def canonical_hash(self) -> str:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class RufloPolicyFinding(BaseModel):
    rule_id: str = Field(min_length=2, max_length=120)
    blocked: bool
    detail: str = Field(min_length=2, max_length=2000)


class RufloAdapterReceipt(BaseModel):
    request_id: str
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: AdapterDisposition
    artifact_pin: RufloArtifactPin
    artifact_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    upstream_valid: bool = False
    dap_policy_findings: list[RufloPolicyFinding] = Field(default_factory=list)
    initializer_invoked: bool = False
    codex_cli_invoked: bool = False
    mcp_registered: bool = False
    plugin_installed: bool = False
    upstream_config_written: bool = False
    execution_started: bool = False
    message: str = Field(min_length=4, max_length=2000)

    @model_validator(mode="after")
    def prohibit_execution_side_effects(self) -> RufloAdapterReceipt:
        side_effects = {
            "initializer_invoked": self.initializer_invoked,
            "codex_cli_invoked": self.codex_cli_invoked,
            "mcp_registered": self.mcp_registered,
            "plugin_installed": self.plugin_installed,
            "upstream_config_written": self.upstream_config_written,
            "execution_started": self.execution_started,
        }
        enabled = [name for name, value in side_effects.items() if value]
        if enabled:
            raise ValueError(
                "Ruflo adapter receipt violates the Phase 10 no-execution boundary: "
                + ", ".join(enabled)
            )
        if self.disposition == "accepted" and not self.upstream_valid:
            raise ValueError("accepted Ruflo artifacts must pass upstream validation")
        if self.disposition == "accepted" and any(
            finding.blocked for finding in self.dap_policy_findings
        ):
            raise ValueError("accepted Ruflo artifacts cannot contain blocked findings")
        return self


def accepted_receipt(
    *,
    request: RufloAdapterRequest,
    artifact_sha256: str,
    findings: list[RufloPolicyFinding] | None = None,
) -> RufloAdapterReceipt:
    findings = findings or []
    if any(finding.blocked for finding in findings):
        raise ValueError("blocked findings require a rejected receipt")
    return RufloAdapterReceipt(
        request_id=request.request_id,
        request_hash=request.canonical_hash(),
        disposition="accepted",
        artifact_pin=request.artifact_pin,
        artifact_sha256=artifact_sha256,
        upstream_valid=True,
        dap_policy_findings=findings,
        message=(
            "Ruflo candidate accepted as non-executable engineering guidance. "
            "DAP retains execution and policy authority."
        ),
    )


def rejected_receipt(
    *,
    request: RufloAdapterRequest,
    findings: list[RufloPolicyFinding],
    upstream_valid: bool,
) -> RufloAdapterReceipt:
    if not findings:
        raise ValueError("rejected receipts require at least one policy finding")
    return RufloAdapterReceipt(
        request_id=request.request_id,
        request_hash=request.canonical_hash(),
        disposition="rejected",
        artifact_pin=request.artifact_pin,
        upstream_valid=upstream_valid,
        dap_policy_findings=findings,
        message=(
            "Ruflo candidate rejected by the DAP-owned policy boundary. "
            "No Codex execution or external integration was started."
        ),
    )
