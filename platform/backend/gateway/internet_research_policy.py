from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PHASE12_AGENT_ID = "research-agent"
PHASE12_ALLOWED_METHODS = ("GET", "HEAD")
PHASE12_ALLOWED_SCHEMES = ("https",)


class Phase12InternetBoundaryRequest(BaseModel):
    """Requested Phase 12 wiring and authority before any network transport exists."""

    agent_id: Literal["research-agent"] = PHASE12_AGENT_ID
    requested_methods: tuple[str, ...] = PHASE12_ALLOWED_METHODS
    requested_schemes: tuple[str, ...] = PHASE12_ALLOWED_SCHEMES

    allow_network_execution_now: bool = False
    allow_arbitrary_destination: bool = False
    allow_url_credentials: bool = False
    allow_private_or_local_network: bool = False
    allow_redirect_without_revalidation: bool = False
    allow_non_read_methods: bool = False
    allow_model_generated_headers: bool = False
    allow_cookies_or_browser_session: bool = False
    allow_credential_forwarding: bool = False
    allow_active_content_execution: bool = False
    trust_remote_instructions: bool = False
    allow_executable_downloads: bool = False
    allow_package_installation: bool = False
    allow_mcp_or_plugin_registration: bool = False
    allow_automatic_knowledge_mutation: bool = False
    allow_task_ledger_mutation: bool = False
    allow_privileged_host_access: bool = False
    allow_guardian_access: bool = False
    allow_docker_or_systemd_access: bool = False

    @field_validator("requested_methods")
    @classmethod
    def normalize_methods(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("at least one research retrieval method is required")
        normalized = tuple(value.strip().upper() for value in values)
        if any(not value for value in normalized):
            raise ValueError("research retrieval methods must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("research retrieval methods must be unique")
        return normalized

    @field_validator("requested_schemes")
    @classmethod
    def normalize_schemes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("at least one research retrieval scheme is required")
        normalized = tuple(value.strip().lower() for value in values)
        if any(not value for value in normalized):
            raise ValueError("research retrieval schemes must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("research retrieval schemes must be unique")
        return normalized


class Phase12InternetBoundaryFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=2, max_length=120)
    blocked: bool
    detail: str = Field(min_length=2, max_length=2000)


class Phase12InternetBoundaryConstraints(BaseModel):
    """Hard invariants that later Phase 12 gates must preserve."""

    model_config = ConfigDict(frozen=True)

    allowed_methods: tuple[Literal["GET", "HEAD"], ...] = PHASE12_ALLOWED_METHODS
    allowed_schemes: tuple[Literal["https"], ...] = PHASE12_ALLOWED_SCHEMES
    public_destinations_only: Literal[True] = True
    dns_public_address_validation_required: Literal[True] = True
    redirect_revalidation_required: Literal[True] = True
    remote_content_is_untrusted: Literal[True] = True
    remote_instructions_are_authority: Literal[False] = False
    credential_forwarding_allowed: Literal[False] = False
    cookies_or_browser_session_allowed: Literal[False] = False
    model_generated_headers_allowed: Literal[False] = False
    active_content_execution_allowed: Literal[False] = False
    executable_downloads_allowed: Literal[False] = False
    package_installation_allowed: Literal[False] = False
    mcp_or_plugin_registration_allowed: Literal[False] = False
    automatic_knowledge_mutation_allowed: Literal[False] = False
    task_ledger_mutation_allowed: Literal[False] = False
    privileged_host_access_allowed: Literal[False] = False
    guardian_access_allowed: Literal[False] = False
    docker_or_systemd_access_allowed: Literal[False] = False


class Phase12InternetBoundaryDecision(BaseModel):
    """Immutable 12A decision. Acceptance permits design wiring, not networking."""

    model_config = ConfigDict(frozen=True)

    phase: Literal["12A"] = "12A"
    disposition: Literal["accepted", "rejected"]
    agent_id: Literal["research-agent"] = PHASE12_AGENT_ID
    findings: tuple[Phase12InternetBoundaryFinding, ...]
    constraints: Phase12InternetBoundaryConstraints = Field(
        default_factory=Phase12InternetBoundaryConstraints
    )
    gateway_wiring_allowed: bool
    network_execution_enabled: Literal[False] = False
    internet_tool_registration_allowed: Literal[False] = False
    message: str


class Phase12InternetBoundaryPolicy:
    """Fail-closed 12A promotion boundary before any internet transport exists."""

    _authority_flags: ClassVar[dict[str, str]] = {
        "allow_network_execution_now": "12A does not enable network execution",
        "allow_arbitrary_destination": "arbitrary destinations are prohibited",
        "allow_url_credentials": "credential-bearing URLs are prohibited",
        "allow_private_or_local_network": (
            "private, local, metadata, container, and DAP-internal destinations are prohibited"
        ),
        "allow_redirect_without_revalidation": (
            "every redirect destination must be independently revalidated"
        ),
        "allow_non_read_methods": "non-read HTTP methods remain prohibited",
        "allow_model_generated_headers": "models cannot generate arbitrary request headers",
        "allow_cookies_or_browser_session": (
            "ambient cookies and browser sessions cannot enter generic research retrieval"
        ),
        "allow_credential_forwarding": "DAP or owner credentials cannot be forwarded arbitrarily",
        "allow_active_content_execution": "remote active content cannot execute",
        "trust_remote_instructions": "remote content is evidence, never DAP authority",
        "allow_executable_downloads": "executable downloads are prohibited",
        "allow_package_installation": "package installation is prohibited",
        "allow_mcp_or_plugin_registration": "automatic MCP/plugin registration is prohibited",
        "allow_automatic_knowledge_mutation": (
            "retrieval cannot automatically mutate canonical Knowledge"
        ),
        "allow_task_ledger_mutation": "retrieval cannot mutate canonical task truth",
        "allow_privileged_host_access": "privileged host access is prohibited",
        "allow_guardian_access": "internet retrieval cannot call Guardian",
        "allow_docker_or_systemd_access": "internet retrieval cannot access Docker or systemd",
    }

    def evaluate(
        self,
        request: Phase12InternetBoundaryRequest,
    ) -> Phase12InternetBoundaryDecision:
        findings: list[Phase12InternetBoundaryFinding] = []

        unexpected_methods = sorted(set(request.requested_methods) - set(PHASE12_ALLOWED_METHODS))
        if unexpected_methods:
            findings.append(
                Phase12InternetBoundaryFinding(
                    rule_id="unsupported-methods",
                    blocked=True,
                    detail="Initial research retrieval is read-only; unsupported methods: "
                    + ", ".join(unexpected_methods),
                )
            )

        unexpected_schemes = sorted(set(request.requested_schemes) - set(PHASE12_ALLOWED_SCHEMES))
        if unexpected_schemes:
            findings.append(
                Phase12InternetBoundaryFinding(
                    rule_id="unsupported-schemes",
                    blocked=True,
                    detail="Initial research retrieval permits HTTPS only; unsupported schemes: "
                    + ", ".join(unexpected_schemes),
                )
            )

        for field_name, detail in self._authority_flags.items():
            if getattr(request, field_name):
                findings.append(
                    Phase12InternetBoundaryFinding(
                        rule_id=field_name.replace("allow_", "prohibit-"),
                        blocked=True,
                        detail=detail,
                    )
                )

        blocked = any(finding.blocked for finding in findings)
        return Phase12InternetBoundaryDecision(
            disposition="rejected" if blocked else "accepted",
            findings=tuple(findings),
            gateway_wiring_allowed=not blocked,
            message=(
                "Phase 12A boundary accepted for design wiring only; no internet tool or network "
                "execution is enabled."
                if not blocked
                else "Phase 12A boundary rejected because requested authority exceeds the "
                "read-only public research design ceiling."
            ),
        )


phase12_internet_boundary_policy = Phase12InternetBoundaryPolicy()
