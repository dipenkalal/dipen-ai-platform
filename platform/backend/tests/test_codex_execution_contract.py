import pytest
from pydantic import ValidationError

from agents.truth_schemas import TaskLedgerRecord
from engineering.codex_execution_contract import (
    CodexRunnerObservation,
    EngineeringExecutionLimits,
    codex_execution_validator,
    engineering_execution_policy,
)
from engineering.engineering_agent_service import (
    EngineeringWorkScope,
    engineering_agent_service,
)
from executive_office.schemas import ExecutiveExecutionResponse


def work_order():
    task = TaskLedgerRecord(
        task_id="phase11c-child-1",
        task_type="agent",
        objective="Implement a bounded backend change.",
        status="assigned",
        requested_by="dipen-owner",
        assigned_agent_ids=["engineering-agent"],
        source_run_id="phase11c-delegation",
        parent_task_id="phase11c-parent",
    )
    admission = ExecutiveExecutionResponse(
        execution_id="phase11c-execution",
        delegation_id="phase11c-delegation",
        parent_task_id="phase11c-parent",
        child_task_ids=["phase11c-child-1"],
        disposition="validated",
        state="validated",
        selected_agent_ids=["engineering-agent"],
        validation_only=True,
        admission_validated=True,
        message="Validation-only admission passed.",
    )
    scope = EngineeringWorkScope(
        acceptance_criteria=["Tests pass."],
        allowed_paths=[
            "platform/backend/engineering/example.py",
            "platform/backend/tests/test_example.py",
        ],
    )
    return engineering_agent_service.prepare(
        task=task,
        admission=admission,
        scope=scope,
    )


def ticket():
    return engineering_execution_policy.issue_ticket(
        work_order=work_order(),
        workspace_id="phase11c-disposable-worktree-1",
    )


def test_ticket_allows_only_workspace_execution_authority() -> None:
    issued = ticket()

    assert issued.sandbox_mode == "workspace-write"
    assert issued.approval_policy == "on-request"
    assert issued.workspace_file_write_allowed is True
    assert issued.codex_execution_allowed is True
    assert issued.shell_execution_inside_sandbox_allowed is True
    assert issued.network_access_allowed is False
    assert issued.privileged_access_allowed is False
    assert issued.git_metadata_write_allowed is False
    assert issued.external_repository_write_allowed is False
    assert issued.guardian_access_allowed is False
    assert issued.production_secret_access_allowed is False
    assert issued.main_merge_allowed is False
    assert issued.deployment_allowed is False
    assert issued.owner_review_required is True
    assert len(issued.canonical_hash()) == 64


def test_ticket_id_is_deterministic_for_same_work_order_and_workspace() -> None:
    first = ticket()
    second = ticket()

    assert first == second
    assert first.ticket_id == second.ticket_id


def test_ticket_limits_are_bounded() -> None:
    with pytest.raises(ValidationError):
        EngineeringExecutionLimits(timeout_seconds=10)
    with pytest.raises(ValidationError):
        EngineeringExecutionLimits(max_changed_files=41)
    with pytest.raises(ValidationError):
        EngineeringExecutionLimits(max_output_bytes=10_000_000)


def test_successful_observation_is_eligible_for_later_git_delivery() -> None:
    issued = ticket()
    observation = CodexRunnerObservation(
        exit_code=0,
        changed_files=["platform/backend/engineering/example.py"],
        output_bytes=2048,
        subprocess_spawned=True,
    )

    receipt = codex_execution_validator.evaluate(
        ticket=issued,
        observation=observation,
    )

    assert receipt.disposition == "succeeded"
    assert receipt.delivery_allowed is True
    assert receipt.execution_started is True
    assert receipt.findings == ()
    assert receipt.git_commit_created is False
    assert receipt.pull_request_created is False
    assert receipt.main_merge_performed is False
    assert receipt.deployment_performed is False


def test_nonzero_exit_is_failed_not_deliverable() -> None:
    receipt = codex_execution_validator.evaluate(
        ticket=ticket(),
        observation=CodexRunnerObservation(
            exit_code=2,
            changed_files=[],
            output_bytes=512,
            subprocess_spawned=True,
        ),
    )

    assert receipt.disposition == "failed"
    assert receipt.delivery_allowed is False


def test_changed_file_outside_ticket_is_rejected() -> None:
    receipt = codex_execution_validator.evaluate(
        ticket=ticket(),
        observation=CodexRunnerObservation(
            exit_code=0,
            changed_files=["README.md"],
            output_bytes=512,
            subprocess_spawned=True,
        ),
    )

    assert receipt.disposition == "rejected"
    assert receipt.delivery_allowed is False
    assert any(
        finding.rule_id == "changed-files-outside-scope"
        for finding in receipt.findings
    )


@pytest.mark.parametrize(
    ("field", "rule_id"),
    [
        ("network_attempted", "network-attempt"),
        ("privileged_access_attempted", "privileged-access-attempt"),
        ("git_metadata_modified", "git-metadata-modified"),
        ("external_repository_modified", "external-repository-modified"),
        ("guardian_access_attempted", "guardian-access-attempt"),
        ("production_secret_access_attempted", "production-secret-access-attempt"),
    ],
)
def test_prohibited_executor_observations_fail_closed(
    field: str,
    rule_id: str,
) -> None:
    payload = {
        "exit_code": 0,
        "changed_files": [],
        "output_bytes": 512,
        "subprocess_spawned": True,
        field: True,
    }
    receipt = codex_execution_validator.evaluate(
        ticket=ticket(),
        observation=CodexRunnerObservation(**payload),
    )

    assert receipt.disposition == "rejected"
    assert receipt.delivery_allowed is False
    assert any(finding.rule_id == rule_id for finding in receipt.findings)


def test_changed_file_limit_is_enforced() -> None:
    order = work_order().model_copy(
        update={
            "allowed_paths": tuple(f"src/file_{index}.py" for index in range(25))
        }
    )
    issued = engineering_execution_policy.issue_ticket(
        work_order=order,
        workspace_id="phase11c-worktree-file-limit",
        limits=EngineeringExecutionLimits(max_changed_files=20),
    )
    observation = CodexRunnerObservation(
        exit_code=0,
        changed_files=list(order.allowed_paths),
        output_bytes=512,
        subprocess_spawned=True,
    )

    receipt = codex_execution_validator.evaluate(
        ticket=issued,
        observation=observation,
    )

    assert receipt.disposition == "rejected"
    assert any(
        finding.rule_id == "changed-file-limit" for finding in receipt.findings
    )


def test_output_limit_is_enforced() -> None:
    issued = engineering_execution_policy.issue_ticket(
        work_order=work_order(),
        workspace_id="phase11c-worktree-output-limit",
        limits=EngineeringExecutionLimits(max_output_bytes=4096),
    )
    observation = CodexRunnerObservation(
        exit_code=0,
        changed_files=[],
        output_bytes=4097,
        subprocess_spawned=True,
    )

    receipt = codex_execution_validator.evaluate(
        ticket=issued,
        observation=observation,
    )

    assert receipt.disposition == "rejected"
    assert any(finding.rule_id == "output-limit" for finding in receipt.findings)


def test_ticket_and_receipt_are_immutable() -> None:
    issued = ticket()
    receipt = codex_execution_validator.evaluate(
        ticket=issued,
        observation=CodexRunnerObservation(
            exit_code=0,
            changed_files=[],
            output_bytes=0,
        ),
    )

    with pytest.raises(ValidationError):
        issued.network_access_allowed = True
    with pytest.raises(ValidationError):
        receipt.delivery_allowed = False
