from __future__ import annotations

import pytest

from gateway.internet_research_policy import (
    PHASE12_ALLOWED_METHODS,
    PHASE12_ALLOWED_SCHEMES,
    Phase12InternetBoundaryPolicy,
    Phase12InternetBoundaryRequest,
)


def test_default_boundary_is_design_only_and_fail_closed() -> None:
    decision = Phase12InternetBoundaryPolicy().evaluate(Phase12InternetBoundaryRequest())

    assert decision.disposition == "accepted"
    assert decision.gateway_wiring_allowed is True
    assert decision.network_execution_enabled is False
    assert decision.internet_tool_registration_allowed is False
    assert decision.findings == ()
    assert decision.constraints.allowed_methods == PHASE12_ALLOWED_METHODS
    assert decision.constraints.allowed_schemes == PHASE12_ALLOWED_SCHEMES
    assert decision.constraints.public_destinations_only is True
    assert decision.constraints.dns_public_address_validation_required is True
    assert decision.constraints.redirect_revalidation_required is True
    assert decision.constraints.remote_content_is_untrusted is True
    assert decision.constraints.remote_instructions_are_authority is False
    assert decision.constraints.credential_forwarding_allowed is False
    assert decision.constraints.cookies_or_browser_session_allowed is False
    assert decision.constraints.active_content_execution_allowed is False
    assert decision.constraints.automatic_knowledge_mutation_allowed is False
    assert decision.constraints.task_ledger_mutation_allowed is False
    assert decision.constraints.privileged_host_access_allowed is False
    assert decision.constraints.guardian_access_allowed is False
    assert decision.constraints.docker_or_systemd_access_allowed is False


@pytest.mark.parametrize(
    "field_name",
    [
        "allow_network_execution_now",
        "allow_arbitrary_destination",
        "allow_url_credentials",
        "allow_private_or_local_network",
        "allow_redirect_without_revalidation",
        "allow_non_read_methods",
        "allow_model_generated_headers",
        "allow_cookies_or_browser_session",
        "allow_credential_forwarding",
        "allow_active_content_execution",
        "trust_remote_instructions",
        "allow_executable_downloads",
        "allow_package_installation",
        "allow_mcp_or_plugin_registration",
        "allow_automatic_knowledge_mutation",
        "allow_task_ledger_mutation",
        "allow_privileged_host_access",
        "allow_guardian_access",
        "allow_docker_or_systemd_access",
    ],
)
def test_dangerous_authority_flags_are_rejected(field_name: str) -> None:
    request = Phase12InternetBoundaryRequest(**{field_name: True})

    decision = Phase12InternetBoundaryPolicy().evaluate(request)

    assert decision.disposition == "rejected"
    assert decision.gateway_wiring_allowed is False
    assert decision.network_execution_enabled is False
    assert decision.internet_tool_registration_allowed is False
    assert any(finding.blocked for finding in decision.findings)


def test_non_read_method_is_rejected_even_without_authority_flag() -> None:
    request = Phase12InternetBoundaryRequest(requested_methods=("GET", "POST"))

    decision = Phase12InternetBoundaryPolicy().evaluate(request)

    assert decision.disposition == "rejected"
    assert {finding.rule_id for finding in decision.findings} == {"unsupported-methods"}


def test_non_https_scheme_is_rejected_even_without_authority_flag() -> None:
    request = Phase12InternetBoundaryRequest(requested_schemes=("https", "file"))

    decision = Phase12InternetBoundaryPolicy().evaluate(request)

    assert decision.disposition == "rejected"
    assert {finding.rule_id for finding in decision.findings} == {"unsupported-schemes"}


def test_method_and_scheme_normalization_is_deterministic() -> None:
    request = Phase12InternetBoundaryRequest(
        requested_methods=(" get ", "head"),
        requested_schemes=(" HTTPS ",),
    )

    assert request.requested_methods == ("GET", "HEAD")
    assert request.requested_schemes == ("https",)


def test_duplicate_methods_and_schemes_fail_validation() -> None:
    with pytest.raises(ValueError, match="methods must be unique"):
        Phase12InternetBoundaryRequest(requested_methods=("GET", "get"))

    with pytest.raises(ValueError, match="schemes must be unique"):
        Phase12InternetBoundaryRequest(requested_schemes=("HTTPS", "https"))


def test_12a_policy_never_grants_live_network_or_tool_authority() -> None:
    decision = Phase12InternetBoundaryPolicy().evaluate(Phase12InternetBoundaryRequest())

    assert decision.network_execution_enabled is False
    assert decision.internet_tool_registration_allowed is False
    assert decision.constraints.model_generated_headers_allowed is False
    assert decision.constraints.credential_forwarding_allowed is False
    assert decision.constraints.guardian_access_allowed is False
