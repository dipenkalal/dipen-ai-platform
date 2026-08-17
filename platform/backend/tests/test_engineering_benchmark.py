from __future__ import annotations

from pathlib import Path

from engineering.engineering_benchmark import (
    BenchmarkAttemptResult,
    BenchmarkCheck,
    BenchmarkSystemMetrics,
    BenchmarkTaskResult,
    EngineeringBenchmarkReport,
    _cpu_busy_percent,
    _report_passed,
    _validate_acceptance,
    benchmark_task_specs,
)


def _spec(slug: str):
    return next(spec for spec in benchmark_task_specs() if spec.slug == slug)


def test_benchmark_task_matrix_is_fixed_and_recovery_follows_failure() -> None:
    specs = benchmark_task_specs()

    assert [spec.slug for spec in specs] == [
        "exact-text-create",
        "structured-json-create",
        "python-repair",
        "expected-quality-failure",
        "recovery-after-failure",
    ]
    assert specs[3].expected_acceptance is False
    assert specs[4].expected_acceptance is True
    assert specs[2].max_attempts == 2
    assert all(spec.max_attempts == 1 for spec in (specs[0], specs[1], specs[3], specs[4]))


def test_exact_text_acceptance(tmp_path: Path) -> None:
    spec = _spec("exact-text-create")
    target = tmp_path / spec.target_path
    target.parent.mkdir(parents=True)
    target.write_text("PHASE11H_EXACT_OK\n", encoding="utf-8")

    passed, checks = _validate_acceptance(spec, tmp_path)

    assert passed is True
    assert all(check.passed for check in checks)


def test_structured_json_acceptance_is_semantic(tmp_path: Path) -> None:
    spec = _spec("structured-json-create")
    target = tmp_path / spec.target_path
    target.parent.mkdir(parents=True)
    target.write_text(
        '{\n  "limit": 7,\n  "enabled": true,\n  "name": "phase11h"\n}\n',
        encoding="utf-8",
    )

    passed, checks = _validate_acceptance(spec, tmp_path)

    assert passed is True
    assert {check.name for check in checks} == {
        "target-exists",
        "json-parse",
        "json-semantic-value",
    }


def test_expected_quality_failure_detects_malformed_json(tmp_path: Path) -> None:
    spec = _spec("expected-quality-failure")
    target = tmp_path / spec.target_path
    target.parent.mkdir(parents=True)
    target.write_text('{"phase11h": true,\n', encoding="utf-8")

    passed, checks = _validate_acceptance(spec, tmp_path)
    check_map = {check.name: check.passed for check in checks}

    assert passed is False
    assert check_map["target-exists"] is True
    assert check_map["malformed-objective-match"] is True
    assert check_map["semantic-json-quality"] is False


def test_python_repair_acceptance_executes_deterministic_cases(tmp_path: Path) -> None:
    spec = _spec("python-repair")
    target = tmp_path / spec.target_path
    target.parent.mkdir(parents=True)
    target.write_text(
        "def add(left: int, right: int) -> int:\n"
        "    return left + right\n",
        encoding="utf-8",
    )

    passed, checks = _validate_acceptance(spec, tmp_path)

    assert passed is True
    assert all(check.passed for check in checks)


def test_python_repair_rejects_imports_even_when_function_works(tmp_path: Path) -> None:
    spec = _spec("python-repair")
    target = tmp_path / spec.target_path
    target.parent.mkdir(parents=True)
    target.write_text(
        "import math\n\n"
        "def add(left: int, right: int) -> int:\n"
        "    return left + right\n",
        encoding="utf-8",
    )

    passed, checks = _validate_acceptance(spec, tmp_path)

    assert passed is False
    assert next(check for check in checks if check.name == "python-no-imports").passed is False


def test_cpu_busy_percent_is_bounded_and_deterministic() -> None:
    assert _cpu_busy_percent((100, 40), (200, 70)) == 70.0
    assert _cpu_busy_percent((100, 40), (100, 40)) == 0.0


def test_report_pass_requires_every_safety_and_quality_metric() -> None:
    specs = benchmark_task_specs()
    attempts: list[BenchmarkAttemptResult] = []
    tasks: list[BenchmarkTaskResult] = []
    for spec in specs:
        acceptance = spec.expected_acceptance
        checks = (
            BenchmarkCheck(name="fixture", passed=acceptance, detail="fixture"),
        )
        attempt = BenchmarkAttemptResult(
            task_slug=spec.slug,
            attempt=1,
            execution_disposition="succeeded",
            execution_succeeded=True,
            acceptance_passed=acceptance,
            path_compliant=True,
            changed_files=(spec.target_path,),
            checks=checks,
            wall_seconds=1.0,
            child_user_cpu_seconds=0.1,
            child_system_cpu_seconds=0.1,
            child_max_rss_kib=1024,
            workspace_bytes=2048,
            evidence_fields_present=8,
            evidence_fields_expected=8,
        )
        attempts.append(attempt)
        tasks.append(
            BenchmarkTaskResult(
                spec=spec,
                attempts=(attempt,),
                passed=True,
                behavior_matched_expectation=True,
                repair_loops=0,
            )
        )

    report = EngineeringBenchmarkReport(
        source_commit="a" * 40,
        codex_runtime="codex-cli 0.146.0",
        tasks=tuple(tasks),
        positive_task_count=4,
        positive_tasks_passed=4,
        positive_completion_rate=1.0,
        attempt_count=5,
        path_compliant_attempts=5,
        path_compliance_rate=1.0,
        expectation_matches=5,
        quality_gate_accuracy_rate=1.0,
        repair_loops_total=0,
        failure_recovery_passed=True,
        evidence_completeness_rate=1.0,
        total_wall_seconds=5.0,
        child_user_cpu_seconds=0.5,
        child_system_cpu_seconds=0.5,
        child_max_rss_kib=1024,
        max_workspace_bytes=2048,
        disk_free_delta_bytes=0,
        system_metrics=BenchmarkSystemMetrics(
            max_cpu_busy_percent=25.0,
            baseline_memory_used_kib=1000,
            peak_memory_used_kib=1200,
            peak_memory_delta_kib=200,
            min_memory_available_kib=8000,
            max_load1=0.5,
        ),
        production_task_ledger_before=11,
        production_task_ledger_after=11,
        production_engineering_audit_before=0,
        production_engineering_audit_after=0,
    )

    assert _report_passed(report) is True
    assert len(report.canonical_hash()) == 64
