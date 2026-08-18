from engineering.codex_smoke import (
    PHASE11_BRANCH,
    SMOKE_CONTENT,
    SMOKE_TARGET,
    build_smoke_work_order,
)


def test_smoke_work_order_is_single_file_and_non_authoritative() -> None:
    order = build_smoke_work_order()

    assert PHASE11_BRANCH == "phase11/autonomous-engineering-agent"
    assert order.assigned_agent_id == "engineering-agent"
    assert order.allowed_paths == (SMOKE_TARGET,)
    assert SMOKE_CONTENT == "PHASE11C_CODEX_SMOKE_OK\n"
    assert order.validation_only is True
    assert order.owner_review_required is True
    assert order.execution_authority_granted is False
    assert order.repository_mutation_allowed is False
    assert order.git_write_allowed is False
    assert order.codex_execution_allowed is False
    assert order.network_access_allowed is False
    assert order.privileged_access_allowed is False
    assert order.main_merge_allowed is False
    assert order.deployment_allowed is False


def test_smoke_objective_and_constraints_are_explicitly_bounded() -> None:
    order = build_smoke_work_order()

    assert SMOKE_TARGET in order.objective
    assert "Do not change any other file" in order.objective
    assert any("disposable sandbox smoke test" in item for item in order.constraints)
    assert any("Do not run tests" in item for item in order.constraints)
    assert any("Network and privileged host access" in item for item in order.constraints)
    assert any("Owner review is required" in item for item in order.constraints)
