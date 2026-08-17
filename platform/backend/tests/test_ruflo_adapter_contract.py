import pytest
from pydantic import ValidationError

from engineering.ruflo_adapter_contract import (
    EngineeringTaskEnvelope,
    RufloAdapterReceipt,
    RufloAdapterRequest,
    RufloArtifactPin,
    RufloPolicyFinding,
    accepted_receipt,
    rejected_receipt,
)


def _request(**overrides: object) -> RufloAdapterRequest:
    payload: dict[str, object] = {
        "request_id": "ruflo-contract-test-001",
        "task": EngineeringTaskEnvelope(
            task_id="task-engineering-001",
            objective="Generate bounded engineering guidance for a disposable task.",
            acceptance_criteria=["No privileged execution occurs."],
            allowed_paths=["src/example.py", "tests/test_example.py"],
        ),
    }
    payload.update(overrides)
    return RufloAdapterRequest(**payload)


def test_safe_request_is_validation_only_and_hash_is_stable() -> None:
    request = _request()

    assert request.validation_only is True
    assert request.allow_initializer is False
    assert request.allow_codex_cli is False
    assert request.allow_mcp_registration is False
    assert request.allow_plugin_installation is False
    assert request.allow_upstream_config_write is False
    assert request.canonical_hash() == request.canonical_hash()
    assert len(request.canonical_hash()) == 64


@pytest.mark.parametrize(
    "override",
    [
        {"validation_only": False},
        {"allow_initializer": True},
        {"allow_codex_cli": True},
        {"allow_mcp_registration": True},
        {"allow_plugin_installation": True},
        {"allow_upstream_config_write": True},
    ],
)
def test_request_rejects_prohibited_adapter_capabilities(
    override: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _request(**override)


def test_request_rejects_network_or_privileged_task() -> None:
    for task in (
        EngineeringTaskEnvelope(
            task_id="task-network-001",
            objective="Use external network access for engineering work.",
            requires_network=True,
        ),
        EngineeringTaskEnvelope(
            task_id="task-privileged-001",
            objective="Use privileged execution for engineering work.",
            requires_privileged_execution=True,
        ),
    ):
        with pytest.raises(ValidationError):
            _request(task=task)


def test_artifact_pin_rejects_release_drift() -> None:
    with pytest.raises(ValidationError):
        RufloArtifactPin(package_version="3.0.3")


def test_accepted_receipt_requires_clean_dap_policy() -> None:
    request = _request()
    receipt = accepted_receipt(
        request=request,
        artifact_sha256="a" * 64,
        findings=[
            RufloPolicyFinding(
                rule_id="guidance-only",
                blocked=False,
                detail="Candidate contains guidance only.",
            )
        ],
    )

    assert receipt.disposition == "accepted"
    assert receipt.upstream_valid is True
    assert receipt.execution_started is False

    with pytest.raises(ValueError):
        accepted_receipt(
            request=request,
            artifact_sha256="b" * 64,
            findings=[
                RufloPolicyFinding(
                    rule_id="dangerous-config",
                    blocked=True,
                    detail="Candidate attempted to expand execution authority.",
                )
            ],
        )


def test_rejected_receipt_keeps_execution_paths_false() -> None:
    request = _request()
    receipt = rejected_receipt(
        request=request,
        upstream_valid=True,
        findings=[
            RufloPolicyFinding(
                rule_id="unpinned-execution",
                blocked=True,
                detail="Candidate referenced an unpinned executable dependency.",
            )
        ],
    )

    assert receipt.disposition == "rejected"
    assert receipt.codex_cli_invoked is False
    assert receipt.mcp_registered is False
    assert receipt.plugin_installed is False

    with pytest.raises(ValidationError):
        RufloAdapterReceipt(
            request_id=request.request_id,
            request_hash=request.canonical_hash(),
            disposition="rejected",
            artifact_pin=request.artifact_pin,
            upstream_valid=True,
            dap_policy_findings=receipt.dap_policy_findings,
            codex_cli_invoked=True,
            message="This receipt must be rejected by schema validation.",
        )
