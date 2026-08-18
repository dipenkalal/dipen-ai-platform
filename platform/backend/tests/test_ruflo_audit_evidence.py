import pytest
from pydantic import ValidationError

from agents.truth_schemas import TaskLedgerRecord
from engineering.ruflo_adapter_contract import (
    RufloPolicyFinding,
    accepted_receipt,
    rejected_receipt,
)
from engineering.ruflo_audit_evidence import RufloAuditEvidenceService
from engineering.ruflo_executive_handoff import (
    RufloExecutiveHandoffService,
    RufloHandoffScope,
)
from executive_office.schemas import ExecutiveExecutionResponse


def _task() -> TaskLedgerRecord:
    return TaskLedgerRecord(
        task_id="executive-delegation-audit-child-1",
        task_type="agent",
        objective="Review a bounded engineering change without executing it.",
        status="assigned",
        priority="normal",
        requested_by="dipen-owner",
        assigned_agent_ids=["system-agent"],
        source_run_id="executive-delegation-audit",
        parent_task_id="executive-delegation-audit-parent",
        current_step="Assigned; runtime execution has not started.",
        progress_percent=0.0,
    )


def _admission() -> ExecutiveExecutionResponse:
    return ExecutiveExecutionResponse(
        execution_id="executive-execution-audit",
        delegation_id="executive-delegation-audit",
        parent_task_id="executive-delegation-audit-parent",
        child_task_ids=["executive-delegation-audit-child-1"],
        disposition="validated",
        state="validated",
        selected_agent_ids=["system-agent"],
        reservation_ids=[],
        validation_evidence=[],
        validation_only=True,
        admission_validated=True,
        task_ledger_mutated=False,
        reservation_acquired=False,
        execution_started=False,
        broker_activated=False,
        message="Validation-only execution admission passed.",
    )


def _handoff():
    return RufloExecutiveHandoffService().build(
        task=_task(),
        admission=_admission(),
        scope=RufloHandoffScope(
            acceptance_criteria=[
                "Return validation-only engineering guidance.",
                "Do not expand authority.",
            ],
            allowed_paths=[
                "platform/backend/engineering/example.py",
                "platform/backend/tests/test_example.py",
            ],
        ),
    )


def _accepted_receipt():
    handoff = _handoff()
    return handoff, accepted_receipt(
        request=handoff.request,
        artifact_sha256="a" * 64,
        findings=[
            RufloPolicyFinding(
                rule_id="phase10-generator-gate",
                blocked=False,
                detail="Candidate passed the DAP-owned validation-only gate.",
            )
        ],
    )


def test_accepted_chain_binds_all_provenance_and_no_execution() -> None:
    handoff, receipt = _accepted_receipt()

    evidence = RufloAuditEvidenceService().build(
        handoff=handoff,
        receipt=receipt,
    )

    assert evidence.source_execution_id == handoff.source_execution_id
    assert evidence.source_delegation_id == handoff.source_delegation_id
    assert evidence.source_parent_task_id == handoff.source_parent_task_id
    assert evidence.source_task_id == handoff.source_task_id
    assert evidence.source_task_sha256 == handoff.source_task_sha256
    assert evidence.source_admission_sha256 == handoff.source_admission_sha256
    assert evidence.request_id == handoff.request.request_id
    assert evidence.request_sha256 == handoff.request.canonical_hash()
    assert evidence.adapter_artifact == handoff.request.artifact_pin
    assert evidence.candidate_artifact_sha256 == "a" * 64
    assert evidence.candidate_disposition == "accepted"
    assert evidence.upstream_valid is True
    assert evidence.initializer_invoked is False
    assert evidence.codex_cli_invoked is False
    assert evidence.mcp_registered is False
    assert evidence.plugin_installed is False
    assert evidence.execution_started is False
    assert evidence.execution_authority_transferred is False
    assert evidence.evidence_persisted is False
    assert len(evidence.source_handoff_sha256) == 64
    assert len(evidence.source_receipt_sha256) == 64
    assert len(evidence.canonical_hash()) == 64


def test_evidence_is_deterministic_for_same_handoff_and_receipt() -> None:
    handoff, receipt = _accepted_receipt()
    service = RufloAuditEvidenceService()

    first = service.build(handoff=handoff, receipt=receipt)
    second = service.build(handoff=handoff, receipt=receipt)

    assert first.evidence_id == second.evidence_id
    assert first.source_handoff_sha256 == second.source_handoff_sha256
    assert first.source_receipt_sha256 == second.source_receipt_sha256
    assert first.canonical_hash() == second.canonical_hash()


def test_evidence_is_frozen() -> None:
    handoff, receipt = _accepted_receipt()
    evidence = RufloAuditEvidenceService().build(
        handoff=handoff,
        receipt=receipt,
    )

    with pytest.raises(ValidationError):
        evidence.message = "mutated"


def test_rejected_receipt_is_recorded_without_candidate_execution() -> None:
    handoff = _handoff()
    receipt = rejected_receipt(
        request=handoff.request,
        upstream_valid=True,
        findings=[
            RufloPolicyFinding(
                rule_id="unsafe-guidance",
                blocked=True,
                detail="Candidate matched a DAP-denied policy rule.",
            )
        ],
    )

    evidence = RufloAuditEvidenceService().build(
        handoff=handoff,
        receipt=receipt,
    )

    assert evidence.candidate_disposition == "rejected"
    assert evidence.candidate_artifact_sha256 is None
    assert evidence.dap_policy_findings[0].blocked is True
    assert evidence.execution_started is False
    assert evidence.evidence_persisted is False


def test_receipt_request_identity_mismatch_is_rejected() -> None:
    handoff, receipt = _accepted_receipt()

    with pytest.raises(ValueError, match="different handoff request"):
        RufloAuditEvidenceService().build(
            handoff=handoff,
            receipt=receipt.model_copy(update={"request_id": "other-request"}),
        )

    with pytest.raises(ValueError, match="request hash"):
        RufloAuditEvidenceService().build(
            handoff=handoff,
            receipt=receipt.model_copy(update={"request_hash": "b" * 64}),
        )


def test_receipt_artifact_identity_mismatch_is_rejected() -> None:
    handoff, receipt = _accepted_receipt()
    tampered_pin = receipt.artifact_pin.model_copy(
        update={"cli_sha256": "b" * 64}
    )

    with pytest.raises(ValueError, match="artifact identity"):
        RufloAuditEvidenceService().build(
            handoff=handoff,
            receipt=receipt.model_copy(update={"artifact_pin": tampered_pin}),
        )


def test_tampered_handoff_authority_is_rejected() -> None:
    handoff, receipt = _accepted_receipt()

    with pytest.raises(ValueError, match="authority transfer"):
        RufloAuditEvidenceService().build(
            handoff=handoff.model_copy(
                update={"execution_authority_transferred": True}
            ),
            receipt=receipt,
        )


def test_tampered_receipt_side_effect_is_rejected() -> None:
    handoff, receipt = _accepted_receipt()

    with pytest.raises(ValueError, match="execution side effects"):
        RufloAuditEvidenceService().build(
            handoff=handoff,
            receipt=receipt.model_copy(update={"codex_cli_invoked": True}),
        )


def test_accepted_receipt_missing_candidate_hash_is_rejected() -> None:
    handoff, receipt = _accepted_receipt()

    with pytest.raises(ValueError, match="missing candidate hash"):
        RufloAuditEvidenceService().build(
            handoff=handoff,
            receipt=receipt.model_copy(update={"artifact_sha256": None}),
        )


def test_accepted_receipt_with_blocked_finding_is_rejected() -> None:
    handoff, receipt = _accepted_receipt()
    blocked = RufloPolicyFinding(
        rule_id="tampered-block",
        blocked=True,
        detail="Tampered accepted receipt contains a blocked policy finding.",
    )

    with pytest.raises(ValueError, match="blocked DAP findings"):
        RufloAuditEvidenceService().build(
            handoff=handoff,
            receipt=receipt.model_copy(
                update={"dap_policy_findings": [blocked]}
            ),
        )
