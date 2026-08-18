from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_BRANCH = "phase12/internet-research-gateway"
DEFAULT_REPO = Path("/home/dipen/dap/source/dipen-ai-platform")
DEFAULT_TRUTH_DB = Path("/home/dipen/dap/data/agent-history/agent-truth.db")
DEFAULT_BACKEND_API = "http://127.0.0.1:8002"
DEFAULT_DASHBOARD_API = "http://127.0.0.1"
DEFAULT_SEARXNG_API = "http://127.0.0.1:8888"
DEFAULT_REPORT = Path("/tmp/phase12j-research-benchmark.json")
DEFAULT_LOG = Path("/tmp/phase12j-research-benchmark.log")


class SealFailure(RuntimeError):
    pass


def emit(name: str, value: object) -> None:
    print(f"{name}|{value}", flush=True)


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise SealFailure(f"command failed ({completed.returncode}): {' '.join(command)}: {detail}")
    return completed


def git_value(repo: Path, *arguments: str) -> str:
    return run(["git", *arguments], cwd=repo).stdout.strip()


def sqlite_scalar(db_path: Path, sql: str) -> int:
    connection = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    try:
        row = connection.execute(sql).fetchone()
    finally:
        connection.close()
    if row is None:
        raise SealFailure("SQLite scalar query returned no row")
    return int(row[0])


def table_exists(db_path: Path, table: str) -> bool:
    connection = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    try:
        row = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    finally:
        connection.close()
    return bool(row and int(row[0]) == 1)


def evidence_ids(db_path: Path) -> set[str]:
    if not table_exists(db_path, "research_retrieval_evidence"):
        return set()
    connection = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    try:
        rows = connection.execute(
            "SELECT evidence_id FROM research_retrieval_evidence"
        ).fetchall()
    finally:
        connection.close()
    return {str(row[0]) for row in rows}


def service_state(unit: str) -> str:
    completed = run(["systemctl", "is-active", unit], check=False)
    return completed.stdout.strip() or "unknown"


def service_pid(unit: str) -> str:
    return run(["systemctl", "show", unit, "-p", "MainPID", "--value"]).stdout.strip()


def docker_state(container: str) -> str:
    return run(["docker", "inspect", "-f", "{{.State.Status}}", container]).stdout.strip()


def docker_health(container: str) -> str:
    return run(
        [
            "docker",
            "inspect",
            "-f",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
            container,
        ]
    ).stdout.strip()


def docker_port(container: str, container_port: str) -> str:
    return run(["docker", "port", container, container_port]).stdout.strip()


def telegram_setting() -> str:
    env_path = Path("/home/dipen/dap/config/dap-backend.env")
    if not env_path.is_file():
        return "missing"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DAP_TELEGRAM_APPROVALS_ENABLED="):
            return line.strip()
    return "missing"


def http_status(url: str, *, method: str = "GET", timeout: float = 20.0) -> int:
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1)
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def http_json(url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if int(response.status) != 200:
            raise SealFailure(f"unexpected HTTP status {response.status} from {url}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise SealFailure(f"JSON response from {url} was not an object")
    return payload


def require(condition: bool, name: str, detail: str) -> None:
    emit(f"check|{name}", str(condition).lower())
    if not condition:
        raise SealFailure(detail)


def run_streamed(command: list[str], *, cwd: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log_handle.write(line)
        return process.wait()


def validate_workspace_payload(payload: dict[str, Any], new_ids: set[str]) -> None:
    require(payload.get("workspace_mode") == "read_only", "workspace_read_only", "workspace mode changed")
    require(payload.get("network_authority_granted") is False, "workspace_network_authority_false", "workspace network authority expanded")
    require(payload.get("mutation_authority_granted") is False, "workspace_mutation_authority_false", "workspace mutation authority expanded")
    require(
        payload.get("search_candidate_metadata_included") is False,
        "workspace_search_metadata_false",
        "provider candidate metadata entered owner evidence",
    )
    items = payload.get("items")
    if not isinstance(items, list):
        raise SealFailure("workspace items were not a list")
    indexed = {
        item.get("evidence", {}).get("evidence_id"): item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("evidence"), dict)
    }
    require(bool(new_ids), "new_evidence_nonempty", "benchmark created no research evidence")
    require(new_ids.issubset(indexed), "workspace_contains_new_evidence", "workspace omitted new benchmark evidence")
    for evidence_id in new_ids:
        item = indexed[evidence_id]
        if not (
            item.get("provenance_kind") == "internet_evidence"
            and item.get("provenance_label") == "Internet Evidence"
            and item.get("knowledge_record") is False
            and item.get("ui_network_authority_granted") is False
            and item.get("ui_mutation_authority_granted") is False
        ):
            raise SealFailure(f"read-only provenance boundary failed for {evidence_id}")
    emit("check|workspace_new_item_boundaries", "true")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the fixed Phase 12J Acer live benchmark seal.")
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--truth-db", type=Path, default=DEFAULT_TRUTH_DB)
    parser.add_argument("--backend-api", default=DEFAULT_BACKEND_API)
    parser.add_argument("--dashboard-api", default=DEFAULT_DASHBOARD_API)
    parser.add_argument("--searxng-api", default=DEFAULT_SEARXNG_API)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args()

    repo = args.repo.resolve()
    backend = repo / "platform" / "backend"
    truth_db = args.truth_db.resolve()

    print("============================================================")
    print(" PHASE 12J — FIXED FINAL LIVE BENCHMARK + PRODUCTION SEAL")
    print("============================================================")

    try:
        print("\n=== 1. SOURCE ===")
        branch = git_value(repo, "branch", "--show-current")
        head_before = git_value(repo, "rev-parse", "HEAD")
        source_status = git_value(repo, "status", "--porcelain")
        emit("branch", branch)
        emit("HEAD", head_before)
        emit("source_status", "clean" if not source_status else "DIRTY")
        require(branch == EXPECTED_BRANCH, "branch_exact", "unexpected Git branch")
        require(head_before == args.expected_head, "head_exact", "Acer is not on the approved 12J head")
        require(not source_status, "source_clean", "source checkout is dirty")

        print("\n=== 2. SAFE FIRST-USE EVIDENCE SCHEMA BOOTSTRAP ===")
        task_pre_bootstrap = sqlite_scalar(truth_db, "SELECT COUNT(*) FROM task_ledger")
        table_pre = table_exists(truth_db, "research_retrieval_evidence")
        evidence_pre_bootstrap = (
            sqlite_scalar(truth_db, "SELECT COUNT(*) FROM research_retrieval_evidence")
            if table_pre
            else 0
        )
        emit("task_ledger_pre_bootstrap", task_pre_bootstrap)
        emit("research_evidence_table_pre", "present" if table_pre else "absent")
        emit("research_evidence_pre_bootstrap", evidence_pre_bootstrap)

        bootstrap = run(
            [
                sys.executable,
                "-m",
                "gateway.research_benchmark_bootstrap",
                "--truth-db",
                str(truth_db),
            ],
            cwd=backend,
            check=False,
        )
        if bootstrap.stdout:
            print(bootstrap.stdout, end="" if bootstrap.stdout.endswith("\n") else "\n")
        if bootstrap.stderr:
            print(bootstrap.stderr, file=sys.stderr, end="" if bootstrap.stderr.endswith("\n") else "\n")
        require(bootstrap.returncode == 0, "bootstrap_exit_zero", "research evidence schema bootstrap failed")

        task_post_bootstrap = sqlite_scalar(truth_db, "SELECT COUNT(*) FROM task_ledger")
        require(table_exists(truth_db, "research_retrieval_evidence"), "evidence_table_present", "research evidence table still missing")
        evidence_post_bootstrap = sqlite_scalar(
            truth_db, "SELECT COUNT(*) FROM research_retrieval_evidence"
        )
        emit("task_ledger_post_bootstrap", task_post_bootstrap)
        emit("research_evidence_post_bootstrap", evidence_post_bootstrap)
        require(task_pre_bootstrap == task_post_bootstrap, "bootstrap_task_ledger_unchanged", "bootstrap mutated task ledger")
        require(evidence_pre_bootstrap == evidence_post_bootstrap, "bootstrap_added_no_evidence", "bootstrap added evidence rows")

        print("\n=== 3. PRODUCTION BASELINE ===")
        tasks_before = task_post_bootstrap
        evidence_before = evidence_post_bootstrap
        ids_before = evidence_ids(truth_db)
        backend_state_before = service_state("dap-backend.service")
        backend_pid_before = service_pid("dap-backend.service")
        guardian_before = service_state("dap-guardian-broker.service")
        telegram_before = telegram_setting()
        dashboard_state_before = docker_state("dap-dashboard")
        dashboard_health_before = docker_health("dap-dashboard")
        searx_state_before = docker_state("dap-searxng")
        searx_binding_before = docker_port("dap-searxng", "8080/tcp")

        emit("task_ledger_before", tasks_before)
        emit("research_evidence_before", evidence_before)
        emit("backend_state_before", backend_state_before)
        emit("backend_pid_before", backend_pid_before)
        emit("guardian_before", guardian_before)
        emit("telegram_before", telegram_before)
        emit("dashboard_state_before", dashboard_state_before)
        emit("dashboard_health_before", dashboard_health_before)
        emit("searxng_state_before", searx_state_before)
        emit("searxng_binding_before", searx_binding_before)

        require(backend_state_before == "active", "backend_active_before", "backend is not active")
        require(backend_pid_before.isdigit() and int(backend_pid_before) > 0, "backend_pid_valid", "backend PID invalid")
        require(guardian_before == "inactive", "guardian_inactive_before", "Guardian broker must remain inactive")
        require(telegram_before == "DAP_TELEGRAM_APPROVALS_ENABLED=false", "telegram_false_before", "Telegram approvals must remain disabled")
        require(dashboard_state_before == "running", "dashboard_running_before", "dashboard is not running")
        require(dashboard_health_before == "healthy", "dashboard_healthy_before", "dashboard is not healthy")
        require(searx_state_before == "running", "searxng_running_before", "SearXNG is not running")
        require(searx_binding_before == "127.0.0.1:8888", "searxng_loopback_before", "SearXNG is not loopback-only")
        require(http_status(args.searxng_api + "/") == 200, "searxng_http_before", "SearXNG HTTP preflight failed")
        require(http_status(args.backend_api + "/api/v1/research/evidence?limit=1") == 200, "backend_research_api_before", "backend Research API preflight failed")
        require(http_status(args.dashboard_api + "/api/research/evidence?limit=1") == 200, "dashboard_research_proxy_before", "dashboard Research proxy preflight failed")

        print("\n=== 4. FROZEN LIVE BENCHMARK ===")
        args.report.unlink(missing_ok=True)
        args.log.unlink(missing_ok=True)
        benchmark_rc = run_streamed(
            [
                sys.executable,
                "-m",
                "gateway.research_benchmark",
                "--repo-root",
                str(repo),
                "--truth-db",
                str(truth_db),
                "--output",
                str(args.report),
            ],
            cwd=backend,
            log_path=args.log,
        )
        emit("benchmark_exit", benchmark_rc)

        print("\n=== 5. DATABASE + REPORT VALIDATION ===")
        tasks_after = sqlite_scalar(truth_db, "SELECT COUNT(*) FROM task_ledger")
        evidence_after = sqlite_scalar(truth_db, "SELECT COUNT(*) FROM research_retrieval_evidence")
        ids_after = evidence_ids(truth_db)
        new_ids = ids_after - ids_before
        evidence_delta = evidence_after - evidence_before
        emit("task_ledger_after", tasks_after)
        emit("research_evidence_after", evidence_after)
        emit("research_evidence_delta", evidence_delta)
        emit("new_evidence_count", len(new_ids))
        for evidence_id in sorted(new_ids):
            emit("new_evidence", evidence_id)

        require(benchmark_rc == 0, "benchmark_exit_zero", "frozen benchmark failed")
        require(args.report.is_file(), "benchmark_report_present", "benchmark report missing")
        report = json.loads(args.report.read_text(encoding="utf-8"))
        require(report.get("benchmark_version") == "phase12j.1", "report_version", "benchmark version mismatch")
        require(report.get("source_commit") == args.expected_head, "report_source_commit", "report source commit mismatch")
        require(report.get("case_count") == 5, "report_case_count", "benchmark case count mismatch")
        require(report.get("cases_passed") == 5, "report_cases_passed", "not all benchmark cases passed")
        require(report.get("completion_rate") == 1.0, "report_completion_rate", "benchmark completion was not 100%")
        require(report.get("all_safety_cases_passed") is True, "report_safety_passed", "one or more safety cases failed")
        require(report.get("task_ledger_before") == tasks_before, "report_task_before", "report task baseline mismatch")
        require(report.get("task_ledger_after") == tasks_after, "report_task_after", "report task final count mismatch")
        require(report.get("research_evidence_before") == evidence_before, "report_evidence_before", "report evidence baseline mismatch")
        require(report.get("research_evidence_after") == evidence_after, "report_evidence_after", "report evidence final count mismatch")
        require(report.get("research_evidence_delta") == evidence_delta, "report_evidence_delta", "report evidence delta mismatch")
        require(tasks_before == tasks_after, "task_ledger_unchanged", "benchmark mutated task ledger")
        require(evidence_delta > 0 and evidence_delta == len(new_ids), "evidence_delta_exact", "unexpected evidence delta")
        posture = report.get("suggested_activation_posture")
        require(posture in {"provider-specific-activation", "experimental-only"}, "activation_posture_allowed", "benchmark recommended rejection")
        emit("suggested_activation_posture", posture)
        emit("total_wall_seconds", report.get("total_wall_seconds"))
        metrics = report.get("system_metrics", {})
        if isinstance(metrics, dict):
            emit("process_user_cpu_seconds", metrics.get("process_user_cpu_seconds"))
            emit("process_system_cpu_seconds", metrics.get("process_system_cpu_seconds"))
            emit("process_max_rss_kib", metrics.get("process_max_rss_kib"))

        print("\n=== 6. READ-ONLY OWNER VISIBILITY ===")
        backend_payload = http_json(args.backend_api + "/api/v1/research/evidence?limit=500")
        dashboard_payload = http_json(args.dashboard_api + "/api/research/evidence?limit=500")
        validate_workspace_payload(backend_payload, new_ids)
        validate_workspace_payload(dashboard_payload, new_ids)
        first_new_id = sorted(new_ids)[0]
        backend_detail = http_json(args.backend_api + f"/api/v1/research/evidence/{first_new_id}")
        dashboard_detail = http_json(args.dashboard_api + f"/api/research/evidence/{first_new_id}")
        for label, detail in (("backend_detail", backend_detail), ("dashboard_detail", dashboard_detail)):
            require(detail.get("evidence", {}).get("evidence_id") in new_ids, f"{label}_new_evidence", f"{label} did not return new evidence")
            require(
                detail.get("provenance_kind") == "internet_evidence"
                and detail.get("knowledge_record") is False
                and detail.get("ui_network_authority_granted") is False
                and detail.get("ui_mutation_authority_granted") is False,
                f"{label}_read_only",
                f"{label} violated read-only provenance boundary",
            )
        require(http_status(args.dashboard_api + "/research") == 200, "research_page_http_200", "Research page did not return HTTP 200")
        require(http_status(args.dashboard_api + "/api/research/evidence", method="POST") == 405, "research_proxy_post_405", "Research proxy accepted POST")

        print("\n=== 7. FINAL PRODUCTION SAFETY ===")
        backend_state_after = service_state("dap-backend.service")
        backend_pid_after = service_pid("dap-backend.service")
        guardian_after = service_state("dap-guardian-broker.service")
        telegram_after = telegram_setting()
        dashboard_state_after = docker_state("dap-dashboard")
        dashboard_health_after = docker_health("dap-dashboard")
        searx_state_after = docker_state("dap-searxng")
        searx_binding_after = docker_port("dap-searxng", "8080/tcp")
        head_after = git_value(repo, "rev-parse", "HEAD")
        source_after = git_value(repo, "status", "--porcelain")

        emit("backend_pid_after", backend_pid_after)
        emit("guardian_after", guardian_after)
        emit("telegram_after", telegram_after)
        emit("dashboard_state_after", dashboard_state_after)
        emit("dashboard_health_after", dashboard_health_after)
        emit("searxng_state_after", searx_state_after)
        emit("searxng_binding_after", searx_binding_after)
        emit("HEAD_after", head_after)
        emit("source_status_after", "clean" if not source_after else "DIRTY")

        require(backend_state_after == "active", "backend_active_after", "backend stopped during benchmark")
        require(backend_pid_after == backend_pid_before, "backend_pid_unchanged", "backend restarted during benchmark")
        require(guardian_after == "inactive", "guardian_inactive_after", "Guardian state changed")
        require(telegram_after == "DAP_TELEGRAM_APPROVALS_ENABLED=false", "telegram_false_after", "Telegram approval state changed")
        require(dashboard_state_after == "running" and dashboard_health_after == "healthy", "dashboard_healthy_after", "dashboard state changed")
        require(searx_state_after == "running" and searx_binding_after == "127.0.0.1:8888", "searxng_safe_after", "SearXNG state/binding changed")
        require(head_after == args.expected_head, "source_head_unchanged", "source HEAD changed")
        require(not source_after, "source_clean_after", "source checkout became dirty")

        print("\n=== FINAL ===")
        emit("PHASE12J_FINAL", "PASS")
        emit("PHASE12_LIVE_EVIDENCE_GATE", "PASS")
        emit("report", args.report)
        emit("log", args.log)
        return 0
    except (SealFailure, OSError, sqlite3.Error, urllib.error.URLError, json.JSONDecodeError) as exc:
        print("\n=== FINAL ===")
        emit("PHASE12J_FINAL", "FAIL_REVIEW_REQUIRED")
        emit("error", f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
