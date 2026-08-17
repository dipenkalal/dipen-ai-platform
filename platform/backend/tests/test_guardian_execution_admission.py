import pytest
from pydantic import ValidationError

from agents.truth_schemas import TaskLedgerRecord
from engineering.codex_execution_contract import engineering_execution_policy
from engineering.engineering_agent_service import (
    EngineeringWorkScope,
    engineering_agent_service,
)
from engineering.guardian_execution_admission import (
    EngineeringGuardianAdmission,
    engineering_guardian_admission_service,
)
from executive_office.schemas import ExecutiveExecutionResponse


def work_order():
    task = TaskLedgerRecord(
        task_id="phase11d-child-1",
        task_type="agent",
        objective="Implement one bounded engineering change.",
        status="assigned",
        requested_by="dipen-owner",
        assigned_agent_ids=["engineering-agent"],
        source_run_id="phase11d-delegation",
        parent_task_id="phase11d-parent",
    )
    executive_admission = ExecutiveExecutionResponse(
        execution_id="phase11d-execution",
        delegation_id="phase11d-delegation",
        parent_task_id="phase11d-parent",
        child_task_ids=[task.task_id],
        disposition="validated",
        state="validated",
        selected_agent_ids=["engineering-agent"],
        validation_only=True,
        admission_validated=True,
        message="Validation-only admission passed.",
    )
    return engineering_agent_service.prepare(
        task=task,
        admission=executive_admission,
        scope=EngineeringWorkScope(
            acceptance_criteria=["Targeted tests pass."],
            allowed_paths=["platform/backend/engineering/example.py"],
        ),
    )


def ticket(order=None):
    order = order or work_order()
    return engineering_execution_policy.issue_ticket(
        work_order=order,
        workspace_id="phase11d-workspace",
    )


def test_admission_is_deterministic_and_non_privileged() -> None:
    order = work_order()
    issued = ticket(order)

    first = engineering_guardian_admission_service.admit(
        work_order=order,
        ticket=issued,
    )
    second = engineering_guardian_admission_service.admit(
        work_order=order,
        ticket=issued,
    )

    assert first == second
    assert first.admission_id.startswith("guardian-admission-")
    assert first.work_order_sha256 == order.canonical_hash()
    assert first.ticket_sha256 == issued.canonical_hash()
    assert first.risk_class == "non_privileged_workspace"
    assert first.codex_execution_admitted is True
    assert first.execution_may_proceed is True
    assert first.guardian_service_contact_required is False
    assert first.guardian_service_contacted is False
    assert first.guardian_broker_contact_allowed is False
    assert first.root_authorization_required is False
    assert first.root_authorization_granted is False
    assert first.network_access_allowed is False
    assert first.privileged_access_allowed is False
    assert first.git_metadata_write_allowed is False
    assert first.external_repository_write_allowed is False
    assert first.production_secret_access_allowed is False
    assert first.main_merge_allowed is False
    assert first.deployment_allowed is False
    assert first.owner_review_required is True
    assert len(first.canonical_hash()) == 64


def test_work_order_binding_mismatch_is_rejected() -> None:
    order = work_order()
    issued = ticket(order).model_copy(update={"work_order_id": "other-work-order"})

    with pytest.raises(ValueError, match="another work order"):
        engineering_guardian_admission_service.admit(
            work_order=order,
            ticket=issued,
        )


def test_work_order_hash_mismatch_is_rejected() -> None:
    order = work_order()
    issued = ticket(order).model_copy(update={"work_order_sha256": "0" * 64})

    with pytest.raises(ValueError, match="work-order hash"):
        engineering_guardian_admission_service.admit(
            work_order=order,
            ticket=issued,
        )


def test_path_scope_drift_is_rejected() -> None:
    order = work_order()
    issued = ticket(order).model_copy(update={"allowed_paths": ("README.md",)})

    with pytest.raises(ValueError, match="path scope"):
        engineering_guardian_admission_service.admit(
            work_order=order,
            ticket=issued,
        )


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("network_access_allowed", "network"),
        ("privileged_access_allowed", "privileged"),
        ("git_metadata_write_allowed", "git-metadata"),
        ("external_repository_write_allowed", "external-repository"),
        ("guardian_access_allowed", "guardian"),
        ("production_secret_access_allowed", "production-secret"),
        ("main_merge_allowed", "main-merge"),
        ("deployment_allowed", "deployment"),
    ],
)
def test_authority_expansion_is_rejected_instead_of_escalated(
    field: str,
    label: str,
) -> None:
    order = work_order()
    issued = ticket(order).model_copy(update={field: True})

    with pytest.raises(ValueError, match=label):
        engineering_guardian_admission_service.admit(
            work_order=order,
            ticket=issued,
        )


def test_wrong_sandbox_or_approval_policy_is_rejected() -> None:
    order = work_order()
    wrong_sandbox = ticket(order).model_copy(update={"sandbox_mode": "read-only"})
    wrong_approval = ticket(order).model_copy(update={"approval_policy": "never"})

    with pytest.raises(ValueError, match="workspace-write"):
        engineering_guardian_admission_service.admit(
            work_order=order,
            ticket=wrong_sandbox,
        )
    with pytest.raises(ValueError, match="on-request"):
        engineering_guardian_admission_service.admit(
            work_order=order,
            ticket=wrong_approval,
        )


def test_admission_is_immutable() -> None:
    order = work_order()
    admitted = engineering_guardian_admission_service.admit(
        work_order=order,
        ticket=ticket(order),
    )

    with pytest.raises(ValidationError):
        admitted.guardian_broker_contact_allowed = True


def test_pydantic_model_cannot_construct_authority_expansion() -> None:
    order = work_order()
    issued = ticket(order)
    admitted = engineering_guardian_admission_service.admit(
        work_order=order,
        ticket=issued,
    )
    payload = admitted.model_dump()
    payload["root_authorization_granted"] = True

    with pytest.raises(ValidationError):
        EngineeringGuardianAdmission(**payload)
