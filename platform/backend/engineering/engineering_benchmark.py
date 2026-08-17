from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.truth_schemas import TaskLedgerRecord
from engineering.codex_execution_contract import (
    EngineeringExecutionLimits,
    engineering_execution_policy,
)
from engineering.codex_runner import (
    CODEX_CLI_VERSION,
    BoundedCodexRunner,
    CodexRunResult,
    CodexRunnerConfig,
)
from engineering.engineering_agent_service import (
    EngineeringWorkScope,
    EngineeringWorkOrder,
    engineering_agent_service,
)
from engineering.guardian_execution_admission import (
    EngineeringGuardianAdmission,
    engineering_guardian_admission_service,
)
from executive_office.schemas import ExecutiveExecutionResponse

PHASE11_BRANCH = "phase11/autonomous-engineering-agent"
DEFAULT_TRUTH_DB = Path("/home/dipen/dap/data/agent-history/agent-truth.db")
READ_ONLY_COUNT_TABLES = frozenset({"task_ledger", "engineering_audit_evidence"})
BENCHMARK_OUTPUT_ROOT = "platform/backend/engineering/benchmark_outputs"
REPAIR_TARGET = (
    "platform/backend/engineering/benchmark_fixtures/phase11h_repair_target.py"
)

TaskKind = Literal[
    "exact_text",
    "json_semantic",
    "python_repair",
    "expected_quality_failure",
    "recovery",
]


class BenchmarkTaskSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9-]+$")
    kind: TaskKind
    target_path: str
    objective: str = Field(min_length=10, max_length=2400)
    acceptance_criteria: tuple[str, ...]
    expected_acceptance: bool = True
    max_attempts: int = Field(default=1, ge=1, le=2)
    timeout_seconds: int = Field(default=150, ge=30, le=300)


class BenchmarkCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: str


class BenchmarkAttemptResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_slug: str
    attempt: int
    execution_disposition: str
    execution_succeeded: bool
    acceptance_passed: bool
    path_compliant: bool
    changed_files: tuple[str, ...] = ()
    checks: tuple[BenchmarkCheck, ...] = ()
    wall_seconds: float = Field(ge=0.0)
    child_user_cpu_seconds: float = Field(ge=0.0)
    child_system_cpu_seconds: float = Field(ge=0.0)
    child_max_rss_kib: int = Field(ge=0)
    workspace_bytes: int = Field(ge=0)
    evidence_fields_present: int = Field(ge=0)
    evidence_fields_expected: int = Field(ge=1)
    timed_out: bool = False
    error: str | None = None

    @property
    def evidence_completeness(self) -> float:
        return self.evidence_fields_present / self.evidence_fields_expected


class BenchmarkTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    spec: BenchmarkTaskSpec
    attempts: tuple[BenchmarkAttemptResult, ...]
    passed: bool
    behavior_matched_expectation: bool
    repair_loops: int = Field(ge=0)


class BenchmarkSystemMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_cpu_busy_percent: float = Field(ge=0.0, le=100.0)
    baseline_memory_used_kib: int = Field(ge=0)
    peak_memory_used_kib: int = Field(ge=0)
    peak_memory_delta_kib: int = Field(ge=0)
    min_memory_available_kib: int = Field(ge=0)
    max_load1: float = Field(ge=0.0)


class EngineeringBenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    benchmark_version: Literal["phase11h.1"] = "phase11h.1"
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    codex_runtime: str
    tasks: tuple[BenchmarkTaskResult, ...]
    positive_task_count: int = Field(ge=1)
    positive_tasks_passed: int = Field(ge=0)
    positive_completion_rate: float = Field(ge=0.0, le=1.0)
    attempt_count: int = Field(ge=1)
    path_compliant_attempts: int = Field(ge=0)
    path_compliance_rate: float = Field(ge=0.0, le=1.0)
    expectation_matches: int = Field(ge=0)
    quality_gate_accuracy_rate: float = Field(ge=0.0, le=1.0)
    repair_loops_total: int = Field(ge=0)
    failure_recovery_passed: bool
    evidence_completeness_rate: float = Field(ge=0.0, le=1.0)
    total_wall_seconds: float = Field(ge=0.0)
    child_user_cpu_seconds: float = Field(ge=0.0)
    child_system_cpu_seconds: float = Field(ge=0.0)
    child_max_rss_kib: int = Field(ge=0)
    max_workspace_bytes: int = Field(ge=0)
    disk_free_delta_bytes: int
    system_metrics: BenchmarkSystemMetrics
    production_task_ledger_before: int = Field(ge=0)
    production_task_ledger_after: int = Field(ge=0)
    production_engineering_audit_before: int = Field(ge=0)
    production_engineering_audit_after: int = Field(ge=0)
    production_db_mutated: Literal[False] = False
    remote_git_used: Literal[False] = False
    pull_request_created: Literal[False] = False
    main_merge_performed: Literal[False] = False
    deployment_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    task_ledger_mutated: Literal[False] = False
    source_repo_clean: Literal[True] = True
    sandbox_removed: Literal[True] = True

    def canonical_hash(self) -> str:
        return _hash_json(self.model_dump(mode="json"))


class _SystemSampler:
    def __init__(self) -> None:
        memory = _memory_snapshot()
        self.baseline_memory_used_kib = memory["MemTotal"] - memory["MemAvailable"]
        self.peak_memory_used_kib = self.baseline_memory_used_kib
        self.min_memory_available_kib = memory["MemAvailable"]
        self.max_cpu_busy_percent = 0.0
        self.max_load1 = max(os.getloadavg()[0], 0.0)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._previous_cpu = _cpu_snapshot()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> BenchmarkSystemMetrics:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        return BenchmarkSystemMetrics(
            max_cpu_busy_percent=min(max(self.max_cpu_busy_percent, 0.0), 100.0),
            baseline_memory_used_kib=self.baseline_memory_used_kib,
            peak_memory_used_kib=self.peak_memory_used_kib,
            peak_memory_delta_kib=max(
                self.peak_memory_used_kib - self.baseline_memory_used_kib,
                0,
            ),
            min_memory_available_kib=self.min_memory_available_kib,
            max_load1=max(self.max_load1, 0.0),
        )

    def _run(self) -> None:
        while not self._stop.wait(0.25):
            memory = _memory_snapshot()
            used = memory["MemTotal"] - memory["MemAvailable"]
            self.peak_memory_used_kib = max(self.peak_memory_used_kib, used)
            self.min_memory_available_kib = min(
                self.min_memory_available_kib,
                memory["MemAvailable"],
            )
            self.max_load1 = max(self.max_load1, os.getloadavg()[0])
            current_cpu = _cpu_snapshot()
            busy = _cpu_busy_percent(self._previous_cpu, current_cpu)
            self.max_cpu_busy_percent = max(self.max_cpu_busy_percent, busy)
            self._previous_cpu = current_cpu


def benchmark_task_specs() -> tuple[BenchmarkTaskSpec, ...]:
    return (
        BenchmarkTaskSpec(
            slug="exact-text-create",
            kind="exact_text",
            target_path=f"{BENCHMARK_OUTPUT_ROOT}/phase11h_exact.txt",
            objective=(
                "Create the target file with exactly PHASE11H_EXACT_OK followed by one "
                "newline. Do not change any other file."
            ),
            acceptance_criteria=(
                "Only the target path changes.",
                "Target content is exactly PHASE11H_EXACT_OK plus one newline.",
            ),
        ),
        BenchmarkTaskSpec(
            slug="structured-json-create",
            kind="json_semantic",
            target_path=f"{BENCHMARK_OUTPUT_ROOT}/phase11h_config.json",
            objective=(
                "Create a valid JSON object at the target path whose semantic value is "
                '{"name":"phase11h","enabled":true,"limit":7}. Formatting may vary. '
                "Do not change any other file."
            ),
            acceptance_criteria=(
                "Only the target path changes.",
                "The target parses as JSON.",
                "The parsed object exactly matches the requested object.",
            ),
        ),
        BenchmarkTaskSpec(
            slug="python-repair",
            kind="python_repair",
            target_path=REPAIR_TARGET,
            objective=(
                "Repair the existing add(left, right) function so it returns the arithmetic "
                "sum for positive and negative integers. Keep the change confined to the "
                "target file and do not add imports or change any other file."
            ),
            acceptance_criteria=(
                "Only the target path changes.",
                "The file compiles as Python.",
                "The module defines add(left, right) with no imports.",
                "add(2, 3) == 5 and add(-4, 1) == -3.",
            ),
            max_attempts=2,
        ),
        BenchmarkTaskSpec(
            slug="expected-quality-failure",
            kind="expected_quality_failure",
            target_path=f"{BENCHMARK_OUTPUT_ROOT}/phase11h_invalid.json",
            objective=(
                'Create the target file with exactly {"phase11h": true, followed by one '
                "newline. This intentionally malformed payload is a quality-gate probe. "
                "Do not change any other file."
            ),
            acceptance_criteria=(
                "Only the target path changes.",
                "The requested malformed payload is written exactly.",
                "The semantic JSON quality check is expected to reject it.",
            ),
            expected_acceptance=False,
        ),
        BenchmarkTaskSpec(
            slug="recovery-after-failure",
            kind="recovery",
            target_path=f"{BENCHMARK_OUTPUT_ROOT}/phase11h_recovery.txt",
            objective=(
                "Create the target file with exactly PHASE11H_RECOVERY_OK followed by one "
                "newline. Do not change any other file."
            ),
            acceptance_criteria=(
                "Only the target path changes.",
                "Target content is exactly PHASE11H_RECOVERY_OK plus one newline.",
            ),
        ),
    )


def _build_work_order(spec: BenchmarkTaskSpec, *, attempt: int) -> EngineeringWorkOrder:
    suffix = f"{spec.slug}-a{attempt}"
    retry_note = (
        " Previous attempt failed the deterministic DAP acceptance check; satisfy every "
        "criterion exactly this time."
        if attempt > 1
        else ""
    )
    task = TaskLedgerRecord(
        task_id=f"phase11h-{suffix}",
        task_type="agent",
        objective=spec.objective + retry_note,
        status="assigned",
        requested_by="dipen-owner",
        assigned_agent_ids=["engineering-agent"],
        source_run_id=f"phase11h-delegation-{suffix}",
        parent_task_id=f"phase11h-parent-{spec.slug}",
    )
    admission = ExecutiveExecutionResponse(
        execution_id=f"phase11h-execution-{suffix}",
        delegation_id=f"phase11h-delegation-{suffix}",
        parent_task_id=f"phase11h-parent-{spec.slug}",
        child_task_ids=[task.task_id],
        disposition="validated",
        state="validated",
        selected_agent_ids=["engineering-agent"],
        validation_only=True,
        admission_validated=True,
        message="Phase 11H disposable benchmark admission.",
    )
    scope = EngineeringWorkScope(
        acceptance_criteria=list(spec.acceptance_criteria),
        allowed_paths=[spec.target_path],
        constraints=[
            "This is a disposable Phase 11H benchmark; never modify the source checkout.",
            "Do not use Git, package managers, network tools, systemd, Docker, Guardian, or services.",
            "Do not change any path other than the single DAP-allowed target path.",
        ],
    )
    return engineering_agent_service.prepare(task=task, admission=admission, scope=scope)


def _validate_acceptance(
    spec: BenchmarkTaskSpec,
    workspace: Path,
) -> tuple[bool, tuple[BenchmarkCheck, ...]]:
    target = workspace / spec.target_path
    checks: list[BenchmarkCheck] = []
    exists = target.is_file()
    checks.append(BenchmarkCheck(name="target-exists", passed=exists, detail=str(target)))
    if not exists:
        return False, tuple(checks)

    content = target.read_text(encoding="utf-8")
    if spec.kind == "exact_text":
        exact = content == "PHASE11H_EXACT_OK\n"
        checks.append(
            BenchmarkCheck(
                name="exact-content",
                passed=exact,
                detail="Expected PHASE11H_EXACT_OK plus one newline.",
            )
        )
        return all(check.passed for check in checks), tuple(checks)

    if spec.kind == "recovery":
        exact = content == "PHASE11H_RECOVERY_OK\n"
        checks.append(
            BenchmarkCheck(
                name="recovery-content",
                passed=exact,
                detail="Expected PHASE11H_RECOVERY_OK plus one newline.",
            )
        )
        return all(check.passed for check in checks), tuple(checks)

    if spec.kind == "json_semantic":
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            checks.append(
                BenchmarkCheck(name="json-parse", passed=False, detail=str(error))
            )
            return False, tuple(checks)
        checks.append(BenchmarkCheck(name="json-parse", passed=True, detail="valid JSON"))
        semantic = parsed == {"name": "phase11h", "enabled": True, "limit": 7}
        checks.append(
            BenchmarkCheck(
                name="json-semantic-value",
                passed=semantic,
                detail="Parsed object must exactly match the benchmark request.",
            )
        )
        return all(check.passed for check in checks), tuple(checks)

    if spec.kind == "expected_quality_failure":
        exact = content == '{"phase11h": true,\n'
        checks.append(
            BenchmarkCheck(
                name="malformed-objective-match",
                passed=exact,
                detail="The intentionally malformed requested payload must be exact.",
            )
        )
        try:
            json.loads(content)
        except json.JSONDecodeError:
            checks.append(
                BenchmarkCheck(
                    name="semantic-json-quality",
                    passed=False,
                    detail="DAP quality gate correctly rejected malformed JSON.",
                )
            )
            return False, tuple(checks)
        checks.append(
            BenchmarkCheck(
                name="semantic-json-quality",
                passed=True,
                detail="Unexpectedly valid JSON; failure probe was not exercised.",
            )
        )
        return all(check.passed for check in checks), tuple(checks)

    if spec.kind == "python_repair":
        try:
            code = compile(content, spec.target_path, "exec")
        except SyntaxError as error:
            checks.append(
                BenchmarkCheck(name="python-compile", passed=False, detail=str(error))
            )
            return False, tuple(checks)
        checks.append(
            BenchmarkCheck(name="python-compile", passed=True, detail="compile succeeded")
        )

        import ast

        tree = ast.parse(content)
        import_nodes = tuple(
            node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        )
        no_imports = not import_nodes
        checks.append(
            BenchmarkCheck(
                name="python-no-imports",
                passed=no_imports,
                detail="Repair target must not add imports.",
            )
        )
        namespace: dict[str, object] = {"__builtins__": {"int": int}}
        try:
            exec(code, namespace, namespace)
            add = namespace.get("add")
            functional = callable(add) and add(2, 3) == 5 and add(-4, 1) == -3
        except Exception as error:
            functional = False
            functional_detail = str(error)
        else:
            functional_detail = "add() passed positive and negative deterministic cases."
        checks.append(
            BenchmarkCheck(
                name="python-functional-test",
                passed=functional,
                detail=functional_detail,
            )
        )
        return all(check.passed for check in checks), tuple(checks)

    raise ValueError(f"unsupported benchmark task kind: {spec.kind}")


def _receipt_hash(result: CodexRunResult) -> str:
    return _hash_json(result.receipt.model_dump(mode="json"))


def _evidence_presence(
    *,
    work_order: EngineeringWorkOrder,
    ticket_hash: str,
    guardian_admission: EngineeringGuardianAdmission,
    result: CodexRunResult | None,
    checks: tuple[BenchmarkCheck, ...],
) -> tuple[int, int]:
    expected = (
        work_order.source_task_sha256,
        work_order.source_admission_sha256,
        work_order.canonical_hash(),
        ticket_hash,
        guardian_admission.canonical_hash(),
        result.command_sha256 if result else None,
        _receipt_hash(result) if result else None,
        checks if checks else None,
    )
    return sum(value is not None and value != () for value in expected), len(expected)


def _run_attempt(
    *,
    spec: BenchmarkTaskSpec,
    attempt: int,
    runner: BoundedCodexRunner,
) -> BenchmarkAttemptResult:
    work_order = _build_work_order(spec, attempt=attempt)
    ticket = engineering_execution_policy.issue_ticket(
        work_order=work_order,
        workspace_id=f"phase11h-{spec.slug}-a{attempt}",
        limits=EngineeringExecutionLimits(
            timeout_seconds=spec.timeout_seconds,
            max_changed_files=1,
            max_output_bytes=262_144,
        ),
    )
    admission = engineering_guardian_admission_service.admit(
        work_order=work_order,
        ticket=ticket,
    )

    before_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    result: CodexRunResult | None = None
    checks: tuple[BenchmarkCheck, ...] = ()
    workspace_bytes = 0
    error_text: str | None = None
    try:
        result = runner.execute(
            work_order=work_order,
            ticket=ticket,
            guardian_admission=admission,
        )
        acceptance_passed, checks = _validate_acceptance(spec, result.workspace)
        workspace_bytes = _tree_size(result.workspace)
        changed = result.receipt.changed_files
        path_compliant = set(changed).issubset(set(ticket.allowed_paths)) and not any(
            finding.blocked for finding in result.receipt.findings
        )
        execution_succeeded = (
            result.receipt.disposition == "succeeded"
            and result.receipt.delivery_allowed
            and not result.timed_out
        )
        disposition = result.receipt.disposition
        timed_out = result.timed_out
    except Exception as error:
        acceptance_passed = False
        path_compliant = False
        execution_succeeded = False
        disposition = "exception"
        changed = ()
        timed_out = False
        error_text = f"{type(error).__name__}: {error}"
    finally:
        if result is not None and result.workspace.exists():
            try:
                runner.cleanup(result.workspace)
            except Exception as cleanup_error:
                error_text = (
                    (error_text + "; ") if error_text else ""
                ) + f"cleanup: {type(cleanup_error).__name__}: {cleanup_error}"

    elapsed = time.monotonic() - started
    after_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    evidence_present, evidence_expected = _evidence_presence(
        work_order=work_order,
        ticket_hash=ticket.canonical_hash(),
        guardian_admission=admission,
        result=result,
        checks=checks,
    )
    return BenchmarkAttemptResult(
        task_slug=spec.slug,
        attempt=attempt,
        execution_disposition=disposition,
        execution_succeeded=execution_succeeded,
        acceptance_passed=acceptance_passed,
        path_compliant=path_compliant,
        changed_files=tuple(changed),
        checks=checks,
        wall_seconds=elapsed,
        child_user_cpu_seconds=max(after_usage.ru_utime - before_usage.ru_utime, 0.0),
        child_system_cpu_seconds=max(after_usage.ru_stime - before_usage.ru_stime, 0.0),
        child_max_rss_kib=max(int(after_usage.ru_maxrss), 0),
        workspace_bytes=workspace_bytes,
        evidence_fields_present=evidence_present,
        evidence_fields_expected=evidence_expected,
        timed_out=timed_out,
        error=error_text,
    )


def _run_task(
    *,
    spec: BenchmarkTaskSpec,
    runner: BoundedCodexRunner,
) -> BenchmarkTaskResult:
    attempts: list[BenchmarkAttemptResult] = []
    for attempt_number in range(1, spec.max_attempts + 1):
        attempt = _run_attempt(spec=spec, attempt=attempt_number, runner=runner)
        attempts.append(attempt)
        behavior_matches = (
            attempt.execution_succeeded
            and attempt.path_compliant
            and attempt.acceptance_passed == spec.expected_acceptance
        )
        if behavior_matches:
            break

    final = attempts[-1]
    behavior_matches = (
        final.execution_succeeded
        and final.path_compliant
        and final.acceptance_passed == spec.expected_acceptance
    )
    return BenchmarkTaskResult(
        spec=spec,
        attempts=tuple(attempts),
        passed=behavior_matches,
        behavior_matched_expectation=behavior_matches,
        repair_loops=max(len(attempts) - 1, 0),
    )


def _aggregate_report(
    *,
    source_commit: str,
    tasks: tuple[BenchmarkTaskResult, ...],
    total_wall_seconds: float,
    system_metrics: BenchmarkSystemMetrics,
    disk_free_delta_bytes: int,
    task_ledger_before: int,
    task_ledger_after: int,
    audit_before: int,
    audit_after: int,
    source_repo_clean: bool,
    sandbox_removed: bool,
) -> EngineeringBenchmarkReport:
    positive = tuple(task for task in tasks if task.spec.expected_acceptance)
    positive_passed = sum(task.passed for task in positive)
    attempts = tuple(attempt for task in tasks for attempt in task.attempts)
    path_compliant = sum(attempt.path_compliant for attempt in attempts)
    expectation_matches = sum(task.behavior_matched_expectation for task in tasks)
    evidence_values = [attempt.evidence_completeness for attempt in attempts]
    negative = next(task for task in tasks if not task.spec.expected_acceptance)
    recovery = next(task for task in tasks if task.spec.kind == "recovery")
    child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return EngineeringBenchmarkReport(
        source_commit=source_commit,
        codex_runtime=CODEX_CLI_VERSION,
        tasks=tasks,
        positive_task_count=len(positive),
        positive_tasks_passed=positive_passed,
        positive_completion_rate=positive_passed / len(positive),
        attempt_count=len(attempts),
        path_compliant_attempts=path_compliant,
        path_compliance_rate=path_compliant / len(attempts),
        expectation_matches=expectation_matches,
        quality_gate_accuracy_rate=expectation_matches / len(tasks),
        repair_loops_total=sum(task.repair_loops for task in tasks),
        failure_recovery_passed=(negative.passed and recovery.passed),
        evidence_completeness_rate=(
            sum(evidence_values) / len(evidence_values) if evidence_values else 0.0
        ),
        total_wall_seconds=total_wall_seconds,
        child_user_cpu_seconds=max(child_usage.ru_utime, 0.0),
        child_system_cpu_seconds=max(child_usage.ru_stime, 0.0),
        child_max_rss_kib=max(int(child_usage.ru_maxrss), 0),
        max_workspace_bytes=max((attempt.workspace_bytes for attempt in attempts), default=0),
        disk_free_delta_bytes=disk_free_delta_bytes,
        system_metrics=system_metrics,
        production_task_ledger_before=task_ledger_before,
        production_task_ledger_after=task_ledger_after,
        production_engineering_audit_before=audit_before,
        production_engineering_audit_after=audit_after,
        production_db_mutated=False,
        source_repo_clean=True if source_repo_clean else False,  # type: ignore[arg-type]
        sandbox_removed=True if sandbox_removed else False,  # type: ignore[arg-type]
    )


def _print_report(report: EngineeringBenchmarkReport) -> None:
    print("=== PHASE 11H DISPOSABLE ENGINEERING BENCHMARK ===")
    print(f"source_commit|{report.source_commit}")
    print(f"codex_runtime|{report.codex_runtime}")
    for task in report.tasks:
        print(
            "task|"
            f"{task.spec.slug}|passed={str(task.passed).lower()}|"
            f"expected_acceptance={str(task.spec.expected_acceptance).lower()}|"
            f"attempts={len(task.attempts)}|repair_loops={task.repair_loops}"
        )
        for attempt in task.attempts:
            print(
                "attempt|"
                f"{task.spec.slug}|{attempt.attempt}|"
                f"execution={attempt.execution_disposition}|"
                f"acceptance={str(attempt.acceptance_passed).lower()}|"
                f"path_compliant={str(attempt.path_compliant).lower()}|"
                f"timed_out={str(attempt.timed_out).lower()}|"
                f"wall_s={attempt.wall_seconds:.3f}|"
                f"cpu_user_s={attempt.child_user_cpu_seconds:.3f}|"
                f"cpu_system_s={attempt.child_system_cpu_seconds:.3f}|"
                f"workspace_bytes={attempt.workspace_bytes}|"
                f"evidence={attempt.evidence_fields_present}/{attempt.evidence_fields_expected}"
            )
            if attempt.error:
                print(f"attempt_error|{task.spec.slug}|{attempt.error}")
            for check in attempt.checks:
                print(
                    "check|"
                    f"{task.spec.slug}|{check.name}|{str(check.passed).lower()}|"
                    f"{check.detail.replace(chr(10), ' ')}"
                )

    print(f"positive_task_count|{report.positive_task_count}")
    print(f"positive_tasks_passed|{report.positive_tasks_passed}")
    print(f"positive_completion_rate|{report.positive_completion_rate:.4f}")
    print(f"attempt_count|{report.attempt_count}")
    print(f"path_compliant_attempts|{report.path_compliant_attempts}")
    print(f"path_compliance_rate|{report.path_compliance_rate:.4f}")
    print(f"quality_gate_accuracy_rate|{report.quality_gate_accuracy_rate:.4f}")
    print(f"repair_loops_total|{report.repair_loops_total}")
    print(f"failure_recovery_passed|{str(report.failure_recovery_passed).lower()}")
    print(f"evidence_completeness_rate|{report.evidence_completeness_rate:.4f}")
    print(f"total_wall_seconds|{report.total_wall_seconds:.3f}")
    print(f"child_user_cpu_seconds|{report.child_user_cpu_seconds:.3f}")
    print(f"child_system_cpu_seconds|{report.child_system_cpu_seconds:.3f}")
    print(f"child_max_rss_kib|{report.child_max_rss_kib}")
    print(f"max_workspace_bytes|{report.max_workspace_bytes}")
    print(f"disk_free_delta_bytes|{report.disk_free_delta_bytes}")
    print(f"max_cpu_busy_percent|{report.system_metrics.max_cpu_busy_percent:.2f}")
    print(f"peak_memory_delta_kib|{report.system_metrics.peak_memory_delta_kib}")
    print(f"max_load1|{report.system_metrics.max_load1:.3f}")
    print(f"task_ledger_before|{report.production_task_ledger_before}")
    print(f"task_ledger_after|{report.production_task_ledger_after}")
    print(f"engineering_audit_before|{report.production_engineering_audit_before}")
    print(f"engineering_audit_after|{report.production_engineering_audit_after}")
    print(f"production_db_mutated|{str(report.production_db_mutated).lower()}")
    print(f"remote_git_used|{str(report.remote_git_used).lower()}")
    print(f"pull_request_created|{str(report.pull_request_created).lower()}")
    print(f"main_merge_performed|{str(report.main_merge_performed).lower()}")
    print(f"deployment_performed|{str(report.deployment_performed).lower()}")
    print(f"guardian_contacted|{str(report.guardian_contacted).lower()}")
    print(f"task_ledger_mutated|{str(report.task_ledger_mutated).lower()}")
    print(f"source_repo_clean|{str(report.source_repo_clean).lower()}")
    print(f"sandbox_removed|{str(report.sandbox_removed).lower()}")
    print(f"benchmark_report_sha256|{report.canonical_hash()}")
    print("benchmark_disposition|" + ("succeeded" if _report_passed(report) else "failed"))


def _report_passed(report: EngineeringBenchmarkReport) -> bool:
    return (
        report.positive_completion_rate == 1.0
        and report.path_compliance_rate == 1.0
        and report.quality_gate_accuracy_rate == 1.0
        and report.failure_recovery_passed
        and report.evidence_completeness_rate == 1.0
        and not report.production_db_mutated
        and report.source_repo_clean
        and report.sandbox_removed
    )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _truth_db_path() -> Path:
    configured = os.environ.get("DAP_AGENT_TRUTH_DB", "").strip()
    return Path(configured).expanduser().resolve() if configured else DEFAULT_TRUTH_DB


def _table_count_read_only(database: Path, table: str) -> int:
    if table not in READ_ONLY_COUNT_TABLES:
        raise ValueError(f"unsupported Phase 11H count table: {table}")
    import sqlite3

    uri = f"file:{database}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=10.0) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists is None:
            return 0
        row = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
        return int(row[0]) if row else 0


def _tree_size(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            total += path.stat().st_size
    return total


def _memory_snapshot() -> dict[str, int]:
    values: dict[str, int] = {}
    with Path("/proc/meminfo").open(encoding="utf-8") as source:
        for line in source:
            key, _, remainder = line.partition(":")
            if key in {"MemTotal", "MemAvailable"}:
                values[key] = int(remainder.strip().split()[0])
    if set(values) != {"MemTotal", "MemAvailable"}:
        raise RuntimeError("unable to read Linux memory metrics")
    return values


def _cpu_snapshot() -> tuple[int, int]:
    first = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
    parts = first.split()
    if not parts or parts[0] != "cpu" or len(parts) < 6:
        raise RuntimeError("unable to read Linux CPU metrics")
    numbers = [int(value) for value in parts[1:]]
    total = sum(numbers)
    idle = numbers[3] + (numbers[4] if len(numbers) > 4 else 0)
    return total, idle


def _cpu_busy_percent(previous: tuple[int, int], current: tuple[int, int]) -> float:
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        return 0.0
    busy = 100.0 * (total_delta - idle_delta) / total_delta
    return min(max(busy, 0.0), 100.0)


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    repo = _repo_root()
    if _git(repo, "branch", "--show-current") != PHASE11_BRANCH:
        raise RuntimeError(f"Phase 11H benchmark requires branch {PHASE11_BRANCH!r}")
    if _git(repo, "status", "--porcelain"):
        raise RuntimeError("source repository must be clean before Phase 11H benchmark")

    source_commit = _git(repo, "rev-parse", "HEAD")
    codex_path = shutil.which("codex")
    bwrap_path = shutil.which("bwrap")
    if codex_path is None:
        raise RuntimeError("codex executable is unavailable")
    if bwrap_path is None:
        raise RuntimeError("bubblewrap is unavailable")
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
    if not codex_home.is_dir():
        raise RuntimeError(f"Codex auth home is unavailable: {codex_home}")

    truth_db = _truth_db_path()
    if not truth_db.is_file():
        raise RuntimeError(f"Agent Truth database is unavailable: {truth_db}")
    task_ledger_before = _table_count_read_only(truth_db, "task_ledger")
    audit_before = _table_count_read_only(truth_db, "engineering_audit_evidence")

    sandbox_parent = Path(
        os.environ.get("DAP_PHASE11_SANDBOX_ROOT", "/home/dipen/dap/sandboxes")
    ).resolve()
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    disk_free_before = shutil.disk_usage(sandbox_parent).free
    run_root = Path(
        tempfile.mkdtemp(prefix="phase11h-benchmark-", dir=sandbox_parent)
    ).resolve()

    runner = BoundedCodexRunner(
        config=CodexRunnerConfig(
            codex_binary=Path(codex_path).resolve(),
            codex_home=codex_home,
            source_repo=repo,
            source_commit=source_commit,
            workspace_root=run_root,
        )
    )

    sampler = _SystemSampler()
    benchmark_started = time.monotonic()
    tasks: tuple[BenchmarkTaskResult, ...] = ()
    system_metrics: BenchmarkSystemMetrics | None = None
    try:
        sampler.start()
        tasks = tuple(
            _run_task(spec=spec, runner=runner) for spec in benchmark_task_specs()
        )
    finally:
        system_metrics = sampler.stop()
        shutil.rmtree(run_root, ignore_errors=True)

    total_wall_seconds = time.monotonic() - benchmark_started
    disk_free_after = shutil.disk_usage(sandbox_parent).free
    task_ledger_after = _table_count_read_only(truth_db, "task_ledger")
    audit_after = _table_count_read_only(truth_db, "engineering_audit_evidence")
    source_repo_clean = not _git(repo, "status", "--porcelain")
    sandbox_removed = not run_root.exists()
    production_db_mutated = (
        task_ledger_after != task_ledger_before or audit_after != audit_before
    )
    if production_db_mutated:
        raise RuntimeError("production Agent Truth changed during Phase 11H benchmark")
    if system_metrics is None:
        raise RuntimeError("Phase 11H system metrics were not captured")

    report = _aggregate_report(
        source_commit=source_commit,
        tasks=tasks,
        total_wall_seconds=total_wall_seconds,
        system_metrics=system_metrics,
        disk_free_delta_bytes=disk_free_after - disk_free_before,
        task_ledger_before=task_ledger_before,
        task_ledger_after=task_ledger_after,
        audit_before=audit_before,
        audit_after=audit_after,
        source_repo_clean=source_repo_clean,
        sandbox_removed=sandbox_removed,
    )
    _print_report(report)
    return 0 if _report_passed(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
