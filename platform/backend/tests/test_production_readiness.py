from company.catalog import ROLES
from engineering.production_readiness import (
    PHASE11H_BENCHMARK_REPORT_SHA256,
    PHASE11I_RUNTIME_SMOKE_SOURCE_SHA,
    phase11_production_readiness_decision,
)


def test_phase11j_selects_narrow_owner_reviewed_pilot() -> None:
    decision = phase11_production_readiness_decision

    assert decision.phase == "11J"
    assert decision.decision == "narrow_supported_task_classes"
    assert decision.readiness == "limited_owner_reviewed_pilot"
    assert decision.phase11_complete is True
    assert decision.broad_autonomous_engineering_ready is False
    assert decision.routine_owner_reviewed_work_allowed is True
    assert decision.company_role_remap_allowed is False


def test_phase11j_preserves_empirical_evidence_without_upgrading_reliability() -> None:
    evidence = phase11_production_readiness_decision.evidence

    assert evidence.benchmark_report_sha256 == PHASE11H_BENCHMARK_REPORT_SHA256
    assert evidence.positive_completion_rate == 0.75
    assert evidence.path_compliance_rate == 1.0
    assert evidence.evidence_completeness_rate == 1.0
    assert evidence.failure_recovery_passed is True
    assert evidence.structured_json_timed_out is True
    assert evidence.owner_review_smoke_source_sha == PHASE11I_RUNTIME_SMOKE_SOURCE_SHA
    assert evidence.owner_review_smoke_passed is True
    assert evidence.owner_review_conflict_failed_closed is True
    assert evidence.production_truth_mutated_by_smoke is False


def test_phase11j_only_allows_demonstrated_routine_task_classes() -> None:
    decision = phase11_production_readiness_decision

    assert decision.supports_routine_task_class("exact_text_one_file") is True
    assert decision.supports_routine_task_class("deterministic_one_file_repair") is True
    assert decision.supports_routine_task_class("structured_json_generation") is False
    assert decision.supports_routine_task_class("multi_file_general_engineering") is False


def test_phase11j_limits_keep_control_plane_and_delivery_authority_disabled() -> None:
    limits = phase11_production_readiness_decision.limits

    assert limits.max_changed_files == 1
    assert limits.deterministic_acceptance_required is True
    assert limits.draft_pull_request_required is True
    assert limits.owner_review_required is True
    assert limits.network_access_allowed is False
    assert limits.package_installation_allowed is False
    assert limits.privileged_host_access_allowed is False
    assert limits.guardian_direct_access_allowed is False
    assert limits.docker_systemd_access_allowed is False
    assert limits.production_secret_access_allowed is False
    assert limits.automatic_routing_enabled is False
    assert limits.automatic_merge_allowed is False
    assert limits.main_merge_allowed is False
    assert limits.release_allowed is False
    assert limits.deployment_allowed is False


def test_software_engineer_role_remains_on_advisory_coding_agent() -> None:
    software_engineer = next(role for role in ROLES if role.id == "software-engineer")

    assert software_engineer.employment_status == "active"
    assert software_engineer.machine_agent_id == "coding-agent"
    assert software_engineer.machine_agent_id != "engineering-agent"


def test_phase11j_requires_new_benchmark_and_owner_milestone_for_expansion() -> None:
    decision = phase11_production_readiness_decision

    assert decision.expansion_requires_new_benchmark is True
    assert decision.expansion_requires_explicit_owner_milestone is True
