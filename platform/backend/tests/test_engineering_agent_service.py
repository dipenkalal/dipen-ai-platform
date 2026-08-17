import pytest
from pydantic import ValidationError

from agents.truth_schemas import TaskLedgerRecord
from engineering.engineering_agent_service import (
    ENGINEERING_AGENT_ID,
    EngineeringWorkScope,
    engineering_agent_service,
)
from executive_office.schemas import ExecutiveExecutionResponse


def source_task(**overrides) -> TaskLedgerRecord:
    payload = {
        "task_id": "phase11-child-1",
        "task_type": "agent",
        "objective": "Implement a bounded backend change for owner review.",
        "status": "assigned",
        "requested_by": "dipen-owner",
        "assigned_agent_ids": [ENGINEERING_AGENT_ID],
        "source_run_id": "phase11-delegation",
        "parent_task_id": "phase11-parent",
    }
    payload.update(overrides)
    return TaskLedgerRecord(**payload)


def source_admission(**overrides) -> ExecutiveExecutionResponse:
    payload = {
        "execution_id": "phase11-execution",
        "delegation_id": "phase11-delegation",
        "parent_task_id": "phase11-parent",
        "child_task_ids": ["phase11-child-1"],
        "disposition": "validated",
        "state": "validated",
        "selected_agent_ids": [ENGINEERING_AGENT_ID],
        "validation_only": True,
        "admission_validated": True,
        "message": "Validation-only Engineering Agent admission passed.",
    }
    payload.update(overrides)
    return ExecutiveExecutionResponse(**payload)


def work_scope(**overrides) -> EngineeringWorkScope:
    payload = {
        "acceptance_criteria": [
            "Targeted backend tests pass.",
            "No files outside the admitted paths change.",
        ],
        "allowed_paths": [
            "platform/backend/engineering/example.py",
            "platform/backend/tests/test_example.py",
        ],
    }
    payload.update(overrides)
    return EngineeringWorkScope(**payload)


def test_prepare_builds_deterministic_non_executing_work_order() -> None:
    first = engineering_agent_service.prepare(
        task=source_task(),
        admission=source_admission(),
        scope=work_scope(),
    )
    second = engineering_agent_service.prepare(
        task=source_task(),
        admission=source_admission(),
        scope=work_scope(),
    )

    assert first == second
    assert first.canonical_hash() == second.canonical_hash()
    assert first.work_order_id.startswith("engineering-work-")
    assert first.assigned_agent_id == ENGINEERING_AGENT_ID
    assert first.validation_only is True
    assert first.owner_review_required is True
    assert first.execution_authority_granted is False
    assert first.repository_mutation_allowed is False
    assert first.git_write_allowed is False
    assert first.codex_execution_allowed is False
    assert first.network_access_allowed is False
    assert first.privileged_access_allowed is False
    assert first.main_merge_allowed is False
    assert first.deployment_allowed is False


def test_prepare_binds_task_and_admission_hashes() -> None:
    order = engineering_agent_service.prepare(
        task=source_task(),
        admission=source_admission(),
        scope=work_scope(),
    )

    assert len(order.source_task_sha256) == 64
    assert len(order.source_admission_sha256) == 64
    assert len(order.canonical_hash()) == 64


def test_prepare_requires_engineering_agent_assignment() -> None:
    with pytest.raises(ValueError, match="assigned only to engineering-agent"):
        engineering_agent_service.prepare(
            task=source_task(assigned_agent_ids=["coding-agent"]),
            admission=source_admission(selected_agent_ids=["coding-agent"]),
            scope=work_scope(),
        )


def test_prepare_requires_validated_admission() -> None:
    with pytest.raises(ValueError, match="not validated"):
        engineering_agent_service.prepare(
            task=source_task(),
            admission=source_admission(
                disposition="rejected",
                state="rejected",
                admission_validated=False,
            ),
            scope=work_scope(),
        )


def test_prepare_rejects_admission_side_effects() -> None:
    with pytest.raises(ValueError, match="prohibited side effects"):
        engineering_agent_service.prepare(
            task=source_task(),
            admission=source_admission(execution_started=True),
            scope=work_scope(),
        )


def test_prepare_rejects_wrong_task_binding() -> None:
    with pytest.raises(ValueError, match="not selected"):
        engineering_agent_service.prepare(
            task=source_task(),
            admission=source_admission(child_task_ids=["other-task"]),
            scope=work_scope(),
        )


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../outside.py",
        "a/../b.py",
        ".git/config",
        ".github/workflows/ci.yml",
        "platform/backend/guardian/broker.py",
        "C:\\temp\\file.py",
    ],
)
def test_scope_rejects_unsafe_or_protected_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        work_scope(allowed_paths=[path])


def test_scope_normalizes_and_preserves_repository_relative_paths() -> None:
    scope = work_scope(
        allowed_paths=[
            " platform/backend/engineering/service.py ",
            "platform/backend/tests/test_service.py",
        ]
    )

    assert scope.allowed_paths == [
        "platform/backend/engineering/service.py",
        "platform/backend/tests/test_service.py",
    ]


def test_work_order_is_immutable() -> None:
    order = engineering_agent_service.prepare(
        task=source_task(),
        admission=source_admission(),
        scope=work_scope(),
    )

    with pytest.raises(ValidationError):
        order.repository_mutation_allowed = True
