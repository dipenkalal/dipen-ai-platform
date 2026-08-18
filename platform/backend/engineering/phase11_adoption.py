from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from engineering.ruflo_adapter_contract import (
    RUFLO_CODEX_CLI_SHA256,
    RUFLO_CODEX_PACKAGE,
    RUFLO_CODEX_PACKAGE_VERSION,
)

APPROVED_PHASE10_COMPONENTS = frozenset(
    {
        "engineering.ruflo_adapter_contract",
        "engineering.ruflo_candidate_bridge",
        "engineering.ruflo_executive_handoff",
        "engineering.ruflo_audit_evidence",
        "engineering.ruflo_audit_repository",
        "guardian.phase10_ruflo_boundary_regression",
    }
)

REQUIRED_PHASE11_COMPONENTS = frozenset(
    {
        "engineering.ruflo_adapter_contract",
        "engineering.ruflo_executive_handoff",
        "engineering.ruflo_audit_evidence",
        "engineering.ruflo_audit_repository",
        "guardian.phase10_ruflo_boundary_regression",
    }
)

EVALUATION_ONLY_COMPONENTS = frozenset(
    {
        "engineering.ruflo_ollama_compatibility",
        "scripts.phase10_codex_adapter_gate",
        "phase10.benchmark_harness",
        "phase10.resource_benchmark",
        "ruflo.full_runtime",
        "ruflo.initializer",
        "ruflo.upstream_codex_config",
    }
)


class Phase11AdoptionRequest(BaseModel):
    """Requested Phase 10 components and authority for Phase 11 adoption."""

    selected_components: list[str] = Field(min_length=1, max_length=20)
    allow_full_ruflo_runtime: bool = False
    allow_initializer: bool = False
    allow_direct_codex_cli: bool = False
    allow_mcp_registration: bool = False
    allow_plugin_installation: bool = False
    allow_unrestricted_network: bool = False
    allow_privileged_host_access: bool = False
    allow_main_merge: bool = False
    allow_deployment: bool = False

    @field_validator("selected_components")
    @classmethod
    def normalize_components(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("adoption component names must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("adoption component names must be unique")
        return normalized


class Phase11AdoptionFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=2, max_length=120)
    blocked: bool
    detail: str = Field(min_length=2, max_length=2000)


class Phase11ArtifactPin(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_name: Literal["@claude-flow/codex"] = RUFLO_CODEX_PACKAGE
    package_version: Literal["3.0.2"] = RUFLO_CODEX_PACKAGE_VERSION
    cli_sha256: Literal[
        "1df00b5aa26c6d76b354bbf2d80042c9c91e83b877c7bacc22f96ee098bea096"
    ] = RUFLO_CODEX_CLI_SHA256


class Phase11AdoptionDecision(BaseModel):
    """Immutable DAP decision describing the Phase 11 adoption boundary."""

    model_config = ConfigDict(frozen=True)

    disposition: Literal["accepted", "rejected"]
    selected_components: tuple[str, ...]
    quarantined_components: tuple[str, ...]
    artifact_pin: Phase11ArtifactPin = Field(default_factory=Phase11ArtifactPin)
    findings: tuple[Phase11AdoptionFinding, ...]
    production_wiring_allowed: bool
    execution_enabled: Literal[False] = False
    main_merge_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False
    privileged_host_access_allowed: Literal[False] = False
    message: str


class Phase11AdoptionPolicy:
    """Fail-closed promotion gate from Phase 10 evaluation to Phase 11 wiring."""

    _authority_flags: ClassVar[dict[str, str]] = {
        "allow_full_ruflo_runtime": "full Ruflo runtime remains prohibited",
        "allow_initializer": "Ruflo/Codex initializer remains prohibited",
        "allow_direct_codex_cli": (
            "direct Codex execution is deferred to the controlled 11C executor"
        ),
        "allow_mcp_registration": "automatic MCP registration remains prohibited",
        "allow_plugin_installation": "automatic plugin installation remains prohibited",
        "allow_unrestricted_network": "unrestricted engineering network access is prohibited",
        "allow_privileged_host_access": "privileged host access is prohibited",
        "allow_main_merge": "automatic or delegated main merge is prohibited",
        "allow_deployment": "automatic or delegated deployment is prohibited",
    }

    def evaluate(self, request: Phase11AdoptionRequest) -> Phase11AdoptionDecision:
        findings: list[Phase11AdoptionFinding] = []
        selected = set(request.selected_components)

        unknown = sorted(
            selected - APPROVED_PHASE10_COMPONENTS - EVALUATION_ONLY_COMPONENTS
        )
        if unknown:
            findings.append(
                Phase11AdoptionFinding(
                    rule_id="unknown-components",
                    blocked=True,
                    detail="Unreviewed Phase 10 components requested: " + ", ".join(unknown),
                )
            )

        evaluation_only = sorted(selected & EVALUATION_ONLY_COMPONENTS)
        if evaluation_only:
            findings.append(
                Phase11AdoptionFinding(
                    rule_id="evaluation-only-components",
                    blocked=True,
                    detail=(
                        "Evaluation-only components cannot enter Phase 11 production wiring: "
                        + ", ".join(evaluation_only)
                    ),
                )
            )

        missing = sorted(REQUIRED_PHASE11_COMPONENTS - selected)
        if missing:
            findings.append(
                Phase11AdoptionFinding(
                    rule_id="missing-required-boundaries",
                    blocked=True,
                    detail=(
                        "Required DAP authority/evidence boundaries are missing: "
                        + ", ".join(missing)
                    ),
                )
            )

        for field_name, detail in self._authority_flags.items():
            if getattr(request, field_name):
                findings.append(
                    Phase11AdoptionFinding(
                        rule_id=field_name.replace("allow_", "prohibit-"),
                        blocked=True,
                        detail=detail,
                    )
                )

        blocked = any(finding.blocked for finding in findings)
        selected_approved = tuple(sorted(selected & APPROVED_PHASE10_COMPONENTS))

        return Phase11AdoptionDecision(
            disposition="rejected" if blocked else "accepted",
            selected_components=selected_approved,
            quarantined_components=tuple(sorted(EVALUATION_ONLY_COMPONENTS)),
            findings=tuple(findings),
            production_wiring_allowed=not blocked,
            message=(
                "Phase 11 adoption boundary accepted; selected Phase 10 components may "
                "be wired behind DAP authority, but no execution authority is enabled."
                if not blocked
                else "Phase 11 adoption request rejected by the DAP promotion boundary."
            ),
        )


phase11_adoption_policy = Phase11AdoptionPolicy()
