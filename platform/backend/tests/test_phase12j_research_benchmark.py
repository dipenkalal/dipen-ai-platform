from __future__ import annotations

from gateway.research_benchmark import (
    ResearchBenchmarkCaseResult,
    ResearchBenchmarkCheck,
    ResearchBenchmarkReport,
    ResearchBenchmarkSystemMetrics,
    _common_output_check,
    _prompt_injection_case,
    benchmark_case_specs,
    suggest_activation_posture,
)


def _result(slug: str, *, passed: bool = True) -> ResearchBenchmarkCaseResult:
    spec = next(spec for spec in benchmark_case_specs() if spec.slug == slug)
    return ResearchBenchmarkCaseResult(
        spec=spec,
        passed=passed,
        checks=(
            ResearchBenchmarkCheck(
                name="fixture",
                passed=passed,
                detail="fixture benchmark result",
            ),
        ),
        wall_seconds=1.0,
    )


def test_phase12j_benchmark_matrix_is_frozen() -> None:
    specs = benchmark_case_specs()

    assert [spec.slug for spec in specs] == [
        "public-retrieval",
        "ssrf-rejection",
        "failure-recovery",
        "searxng-to-retrieval",
        "prompt-injection-boundary",
    ]
    assert [spec.requires_live_network for spec in specs] == [
        True,
        False,
        True,
        True,
        False,
    ]
    assert all(spec.required_for_safety for spec in specs)


def test_prompt_injection_fixture_denies_remote_authority() -> None:
    spec = next(
        spec for spec in benchmark_case_specs() if spec.slug == "prompt-injection-boundary"
    )

    result = _prompt_injection_case(spec)

    assert result.passed is True
    assert all(check.passed for check in result.checks)


def test_common_output_boundary_requires_every_no_authority_flag() -> None:
    safe = {
        "generic_network_client_exposed": False,
        "remote_scope_expansion_allowed": False,
        "automatic_knowledge_mutation_performed": False,
        "task_ledger_mutation_performed": False,
        "guardian_contacted": False,
        "privileged_host_action_performed": False,
    }

    assert _common_output_check(safe).passed is True

    unsafe = dict(safe)
    unsafe["guardian_contacted"] = True
    assert _common_output_check(unsafe).passed is False


def test_posture_rejects_any_safety_failure() -> None:
    results = tuple(_result(spec.slug) for spec in benchmark_case_specs())

    assert (
        suggest_activation_posture(
            results=results,
            all_safety_cases_passed=False,
            total_wall_seconds=10.0,
            research_evidence_delta=10,
        )
        == "reject-activation"
    )


def test_posture_is_experimental_when_search_is_not_reliable() -> None:
    results = tuple(
        _result(spec.slug, passed=spec.slug != "searxng-to-retrieval")
        for spec in benchmark_case_specs()
    )

    assert (
        suggest_activation_posture(
            results=results,
            all_safety_cases_passed=True,
            total_wall_seconds=10.0,
            research_evidence_delta=5,
        )
        == "experimental-only"
    )


def test_posture_is_experimental_when_latency_is_high() -> None:
    results = tuple(_result(spec.slug) for spec in benchmark_case_specs())

    assert (
        suggest_activation_posture(
            results=results,
            all_safety_cases_passed=True,
            total_wall_seconds=121.0,
            research_evidence_delta=5,
        )
        == "experimental-only"
    )


def test_posture_allows_only_provider_specific_activation_after_full_pass() -> None:
    results = tuple(_result(spec.slug) for spec in benchmark_case_specs())

    assert (
        suggest_activation_posture(
            results=results,
            all_safety_cases_passed=True,
            total_wall_seconds=60.0,
            research_evidence_delta=5,
        )
        == "provider-specific-activation"
    )


def test_report_hash_is_stable_and_task_ledger_is_non_mutating() -> None:
    results = tuple(_result(spec.slug) for spec in benchmark_case_specs())
    report = ResearchBenchmarkReport(
        source_commit="a" * 40,
        cases=results,
        case_count=len(results),
        cases_passed=len(results),
        completion_rate=1.0,
        all_safety_cases_passed=True,
        total_wall_seconds=5.0,
        system_metrics=ResearchBenchmarkSystemMetrics(
            load1_before=0.1,
            load1_after=0.2,
            memory_available_before_kib=1_000_000,
            memory_available_after_kib=999_000,
            process_user_cpu_seconds=0.5,
            process_system_cpu_seconds=0.1,
            process_max_rss_kib=50_000,
        ),
        task_ledger_before=11,
        task_ledger_after=11,
        research_evidence_before=0,
        research_evidence_after=5,
        research_evidence_delta=5,
        suggested_activation_posture="provider-specific-activation",
    )

    assert len(report.canonical_hash()) == 64
    assert report.task_ledger_mutated is False
    assert report.automatic_knowledge_mutation_performed is False
    assert report.guardian_contacted is False
    assert report.privileged_host_action_performed is False
