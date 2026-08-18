from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PHASE11H_BENCHMARK_REPORT_SHA256 = (
    "d34293353519f2fb8ae1803e308a965cc35cbab29f820794290467c41ed229fd"
)
PHASE11H_POSITIVE_COMPLETION_RATE = 0.75
PHASE11H_PATH_COMPLIANCE_RATE = 1.0
PHASE11H_EVIDENCE_COMPLETENESS_RATE = 1.0
PHASE11I_RUNTIME_SMOKE_SOURCE_SHA = "9d55ef80d4764758c94fb37c8d474f0218734b4f"

RoutineEngineeringTaskClass = Literal[
    "exact_text_one_file",
    "deterministic_one_file_repair",
]


class Phase11ReadinessEvidence(BaseModel):
    """Immutable evidence snapshot used by the Phase 11J decision."""

    model_config = ConfigDict(frozen=True)

    benchmark_report_sha256: Literal[
        "d34293353519f2fb8ae1803e308a965cc35cbab29f820794290467c41ed229fd"
    ] = PHASE11H_BENCHMARK_REPORT_SHA256
    positive_completion_rate: Literal[0.75] = PHASE11H_POSITIVE_COMPLETION_RATE
    path_compliance_rate: Literal[1.0] = PHASE11H_PATH_COMPLIANCE_RATE
    evidence_completeness_rate: Literal[1.0] = PHASE11H_EVIDENCE_COMPLETENESS_RATE
    failure_recovery_passed: Literal[True] = True
    structured_json_timed_out: Literal[True] = True
    owner_review_smoke_source_sha: Literal[
        "9d55ef80d4764758c94fb37c8d474f0218734b4f"
    ] = PHASE11I_RUNTIME_SMOKE_SOURCE_SHA
    owner_review_smoke_passed: Literal[True] = True
    owner_review_conflict_failed_closed: Literal[True] = True
    production_truth_mutated_by_smoke: Literal[False] = False


class Phase11RoutineLimits(BaseModel):
    """Hard ceiling for the limited owner-reviewed Phase 11 pilot."""

    model_config = ConfigDict(frozen=True)

    max_changed_files: Literal[1] = 1
    deterministic_acceptance_required: Literal[True] = True
    draft_pull_request_required: Literal[True] = True
    owner_review_required: Literal[True] = True
    network_access_allowed: Literal[False] = False
    package_installation_allowed: Literal[False] = False
    privileged_host_access_allowed: Literal[False] = False
    guardian_direct_access_allowed: Literal[False] = False
    docker_systemd_access_allowed: Literal[False] = False
    production_secret_access_allowed: Literal[False] = False
    automatic_routing_enabled: Literal[False] = False
    automatic_merge_allowed: Literal[False] = False
    main_merge_allowed: Literal[False] = False
    release_allowed: Literal[False] = False
    deployment_allowed: Literal[False] = False


class Phase11ProductionReadinessDecision(BaseModel):
    """Final Phase 11 decision: useful, bounded, but not broadly autonomous."""

    model_config = ConfigDict(frozen=True)

    phase: Literal["11J"] = "11J"
    decision: Literal["narrow_supported_task_classes"] = (
        "narrow_supported_task_classes"
    )
    readiness: Literal["limited_owner_reviewed_pilot"] = "limited_owner_reviewed_pilot"
    phase11_complete: Literal[True] = True
    broad_autonomous_engineering_ready: Literal[False] = False
    routine_owner_reviewed_work_allowed: Literal[True] = True
    company_role_remap_allowed: Literal[False] = False
    supported_task_classes: tuple[RoutineEngineeringTaskClass, ...] = (
        "exact_text_one_file",
        "deterministic_one_file_repair",
    )
    unsupported_routine_task_classes: tuple[str, ...] = (
        "structured_json_generation",
        "multi_file_general_engineering",
        "network_required_engineering",
        "dependency_or_package_installation",
        "privileged_or_runtime_administration",
        "protected_control_plane_changes",
        "merge_release_or_deployment",
    )
    limits: Phase11RoutineLimits = Field(default_factory=Phase11RoutineLimits)
    evidence: Phase11ReadinessEvidence = Field(default_factory=Phase11ReadinessEvidence)
    expansion_requires_new_benchmark: Literal[True] = True
    expansion_requires_explicit_owner_milestone: Literal[True] = True
    rationale: str = (
        "Phase 11 safety, path, evidence, owner-review, and cleanup boundaries passed, "
        "but the first fixed empirical benchmark completed only 3 of 4 positive tasks. "
        "Routine use is therefore limited to the task classes that demonstrated reliable "
        "bounded behavior with deterministic acceptance."
    )

    def supports_routine_task_class(self, task_class: str) -> bool:
        return task_class in self.supported_task_classes


phase11_production_readiness_decision = Phase11ProductionReadinessDecision()
