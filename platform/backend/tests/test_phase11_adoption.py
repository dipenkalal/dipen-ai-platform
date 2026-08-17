import pytest
from pydantic import ValidationError

from engineering.phase11_adoption import (
    APPROVED_PHASE10_COMPONENTS,
    REQUIRED_PHASE11_COMPONENTS,
    Phase11AdoptionRequest,
    phase11_adoption_policy,
)
from engineering.ruflo_adapter_contract import (
    RUFLO_CODEX_CLI_SHA256,
    RUFLO_CODEX_PACKAGE_VERSION,
)


def safe_request(**overrides) -> Phase11AdoptionRequest:
    payload = {
        "selected_components": sorted(APPROVED_PHASE10_COMPONENTS),
    }
    payload.update(overrides)
    return Phase11AdoptionRequest(**payload)


def test_safe_adoption_is_accepted_without_execution_authority() -> None:
    decision = phase11_adoption_policy.evaluate(safe_request())

    assert decision.disposition == "accepted"
    assert decision.production_wiring_allowed is True
    assert decision.execution_enabled is False
    assert decision.main_merge_allowed is False
    assert decision.deployment_allowed is False
    assert decision.privileged_host_access_allowed is False
    assert decision.findings == ()
    assert set(decision.selected_components) == APPROVED_PHASE10_COMPONENTS


def test_phase10_artifact_pin_is_preserved() -> None:
    decision = phase11_adoption_policy.evaluate(safe_request())

    assert decision.artifact_pin.package_version == RUFLO_CODEX_PACKAGE_VERSION
    assert decision.artifact_pin.cli_sha256 == RUFLO_CODEX_CLI_SHA256


def test_required_dap_boundaries_cannot_be_omitted() -> None:
    missing = next(iter(REQUIRED_PHASE11_COMPONENTS))
    request = safe_request(
        selected_components=sorted(APPROVED_PHASE10_COMPONENTS - {missing})
    )

    decision = phase11_adoption_policy.evaluate(request)

    assert decision.disposition == "rejected"
    assert decision.production_wiring_allowed is False
    assert any(
        finding.rule_id == "missing-required-boundaries"
        and missing in finding.detail
        for finding in decision.findings
    )


def test_evaluation_only_component_is_rejected() -> None:
    request = safe_request(
        selected_components=[
            *sorted(APPROVED_PHASE10_COMPONENTS),
            "ruflo.full_runtime",
        ]
    )

    decision = phase11_adoption_policy.evaluate(request)

    assert decision.disposition == "rejected"
    assert any(
        finding.rule_id == "evaluation-only-components"
        and "ruflo.full_runtime" in finding.detail
        for finding in decision.findings
    )


@pytest.mark.parametrize(
    "flag",
    [
        "allow_full_ruflo_runtime",
        "allow_initializer",
        "allow_direct_codex_cli",
        "allow_mcp_registration",
        "allow_plugin_installation",
        "allow_unrestricted_network",
        "allow_privileged_host_access",
        "allow_main_merge",
        "allow_deployment",
    ],
)
def test_authority_expansion_flags_fail_closed(flag: str) -> None:
    decision = phase11_adoption_policy.evaluate(safe_request(**{flag: True}))

    assert decision.disposition == "rejected"
    assert decision.production_wiring_allowed is False
    assert any(finding.blocked for finding in decision.findings)


def test_unknown_component_is_rejected() -> None:
    request = safe_request(
        selected_components=[
            *sorted(APPROVED_PHASE10_COMPONENTS),
            "engineering.unreviewed_executor",
        ]
    )

    decision = phase11_adoption_policy.evaluate(request)

    assert decision.disposition == "rejected"
    assert any(
        finding.rule_id == "unknown-components"
        and "engineering.unreviewed_executor" in finding.detail
        for finding in decision.findings
    )


def test_component_names_are_unique_and_nonempty() -> None:
    with pytest.raises(ValidationError):
        Phase11AdoptionRequest(selected_components=["", "x"])

    with pytest.raises(ValidationError):
        Phase11AdoptionRequest(selected_components=["x", "x"])


def test_decision_is_immutable() -> None:
    decision = phase11_adoption_policy.evaluate(safe_request())

    with pytest.raises(ValidationError):
        decision.execution_enabled = True
