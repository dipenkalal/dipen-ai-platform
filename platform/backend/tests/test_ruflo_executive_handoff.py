import pytest
from pydantic import ValidationError

from agents.truth_schemas import TaskLedgerRecord
from engineering.ruflo_executive_handoff import (
    RufloExecutiveHandoffService,
    RufloHandoffScope,
)
from executive_office.schemas import ExecutiveExecutionResponse


def _task(**overrides: object) -> TaskLedgerRecord:
    payload: dict[str, object] = {
        "task_id": "executive-delegation-test-child-1",
        "task_type": "agent",
        "objective": "Review a bounded engineering change without executing it.",
        "status": "assigned",
        "priority": "normal",
        "requested_by": "dipen-owner",
        "assigned_agent_ids": ["system-agent"],
        "source_run_id": "executive-delegation-test",
        "parent_task_id": "executive-delegation-test-parent",
        "current_step": "Assigned; runtime execution has not started.",
        "progress_percent": 0.0,
    }
    payload.update(overrides)
    return TaskLedgerRecord(**payload)


def _admission(**overrides: object) -> ExecutiveExecutionResponse:
    payload: dict[str, object] = {
        "execution_id": "executive-execution-test",
        "delegation_id": "executive-delegation-test",
        "parent_task_id": "executive-delegation-test-parent",
        "child_task_ids": ["executive-delegation-test-child-1"],
        "disposition": "validated",
        "state": "validated",
        "selected_agent_ids": ["system-agent"],
        "reservation_ids": [],
        "validation_evidence": [],
        "validation_only": True,
        "admission_validated": True,
        "task_ledger_mutated": False,
        "reservation_acquired": False,
        "execution_started": False,
        "broker_activated": False,
        "message": "Validation-only execution admission passed.",
    }
    payload.update(overrides)
    return ExecutiveExecutionResponse(**payload)


def _scope() -> RufloHandoffScope:
    return RufloHandoffScope(
        acceptance_criteria=[
            "Return validation-only engineering guidance.",
            "Do not expand execution authority.",
        ],
        allowed_paths=[
            "platform/backend/engineering/example.py",
            "platform/backend/tests/test_example.py",
        ],
        constraints=["Keep the candidate deterministic."],
    )


def test_validated_dap_task_maps_to_bounded_ruflo_request() -> None:
    service = RufloExecutiveHandoffService()
    task = _task()
    admission = _admission()

    handoff = service.build(task=task, admission=admission, scope=_scope())

    assert handoff.source_execution_id == admission.execution_id
    assert handoff.source_delegation_id == admission.delegation_id
    assert handoff.source_task_id == task.task_id
    assert len(handoff.source_task_sha256) == 64
    assert len(handoff.source_admission_sha256) == 64
    assert handoff.request.task.objective == task.objective
    assert handoff.request.task.requires_network is False
    assert handoff.request.task.requires_privileged_execution is False
    assert handoff.request.validation_only is True
    assert handoff.request.allow_codex_cli is False
    assert handoff.request.allow_mcp_registration is False
    assert handoff.execution_authority_transferred is False
    assert handoff.owner_approval_created is False
    assert handoff.canonical_task_created is False


def test_handoff_is_deterministic_for_same_canonical_inputs() -> None:
    service = RufloExecutiveHandoffService()
    task = _task()
    admission = _admission()
    scope = _scope()

    first = service.build(task=task, admission=admission, scope=scope)
    second = service.build(task=task, admission=admission, scope=scope)

    assert first.request.request_id == second.request.request_id
    assert first.request.canonical_hash() == second.request.canonical_hash()
    assert first.source_task_sha256 == second.source_task_sha256
    assert first.source_admission_sha256 == second.source_admission_sha256


def test_idempotent_replay_of_validated_admission_is_accepted() -> None:
    handoff = RufloExecutiveHandoffService().build(
        task=_task(),
        admission=_admission(disposition="idempotent_replay", idempotent_replay=True),
        scope=_scope(),
    )

    assert handoff.request.validation_only is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"disposition": "rejected", "state": "rejected", "admission_validated": False},
        {"state": "rejected", "admission_validated": False},
        {"validation_only": False},
        {"task_ledger_mutated": True},
        {"reservation_acquired": True, "reservation_ids": ["reservation-1"]},
        {"execution_started": True},
        {"broker_activated": True},
    ],
)
def test_handoff_rejects_unvalidated_or_side_effecting_admission(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        RufloExecutiveHandoffService().build(
            task=_task(),
            admission=_admission(**overrides),
            scope=_scope(),
        )


@pytest.mark.parametrize(
    "task",
    [
        _task(task_type="orchestration"),
        _task(status="queued"),
        _task(task_id="different-child"),
        _task(source_run_id="different-delegation"),
        _task(parent_task_id="different-parent"),
        _task(assigned_agent_ids=[]),
        _task(assigned_agent_ids=["system-agent", "review-agent"]),
        _task(assigned_agent_ids=["review-agent"]),
    ],
)
def test_handoff_rejects_noncanonical_task_relationship(
    task: TaskLedgerRecord,
) -> None:
    with pytest.raises(ValueError):
        RufloExecutiveHandoffService().build(
            task=task,
            admission=_admission(),
            scope=_scope(),
        )


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../outside.py",
        "src/../outside.py",
        "./src/file.py",
        "src//file.py",
        "C:\\Windows\\system.ini",
        "~/secret",
    ],
)
def test_handoff_scope_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        RufloHandoffScope(
            acceptance_criteria=["Remain validation-only."],
            allowed_paths=[path],
        )


def test_handoff_scope_rejects_duplicate_or_empty_text() -> None:
    with pytest.raises(ValidationError):
        RufloHandoffScope(
            acceptance_criteria=["same", "same"],
            allowed_paths=["src/file.py"],
        )

    with pytest.raises(ValidationError):
        RufloHandoffScope(
            acceptance_criteria=["   "],
            allowed_paths=["src/file.py"],
        )


def test_handoff_adds_nonnegotiable_dap_constraints() -> None:
    handoff = RufloExecutiveHandoffService().build(
        task=_task(),
        admission=_admission(),
        scope=_scope(),
    )

    constraints = handoff.request.task.constraints
    assert "Keep the candidate deterministic." in constraints
    assert any("no Codex execution" in item for item in constraints)
    assert any("Network access" in item for item in constraints)
    assert any("MCP registration" in item for item in constraints)
    assert any("DAP-listed repository paths" in item for item in constraints)
