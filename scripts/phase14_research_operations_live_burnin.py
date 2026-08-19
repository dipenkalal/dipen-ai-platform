from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REPO = Path("/home/dipen/dap/source/dipen-ai-platform")
BACKEND = REPO / "platform/backend"
DASH = REPO / "apps/dashboard"
COMPOSE = Path("/home/dipen/dap/compose")
PYTHON = BACKEND / ".venv/bin/python"
TRUTH_DB = Path("/home/dipen/dap/data/agent-history/agent-truth.db")
STATE_PATH = Path("/tmp/dap-phase14-research-operations-live-state.json")
BENCHMARK_REPORT = Path("/tmp/phase14-reliability-benchmark-live.json")
RUNTIME_CONTEXT = Path("/tmp/dap-phase14-dashboard-runtime")

MIN_BURNIN_RUNS = 2
MAX_BURNIN_RUNS = 3
MIN_BURNIN_OPERATIONS_EVENTS = 5

BACKEND_BASE = "http://127.0.0.1:8002"
DASHBOARD_BASE = "http://127.0.0.1"
SEARXNG_BASE = "http://127.0.0.1:8888"

ALLOWED_LOCAL_HTTP_TARGETS = {
    ("127.0.0.1", 80),
    ("127.0.0.1", 8002),
    ("127.0.0.1", 8888),
}


class OperatorError(RuntimeError):
    pass


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise OperatorError(detail)


def emit(name: str, value: Any) -> None:
    if isinstance(value, bool):
        rendered = str(value).lower()
    else:
        rendered = str(value)
    print(f"{name}|{rendered}", flush=True)


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=capture,
    )


def output(command: list[str], *, cwd: Path | None = None) -> str:
    return run(command, cwd=cwd).stdout.strip()


def _validate_local_url(url: str) -> None:
    parsed = urlsplit(url)
    require(parsed.scheme == "http", f"operator HTTP scheme is not fixed local HTTP: {url}")
    host = parsed.hostname or ""
    port = parsed.port or 80
    require(
        (host, port) in ALLOWED_LOCAL_HTTP_TARGETS,
        f"operator HTTP target is outside the fixed local allowlist: {host}:{port}",
    )


def http(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, bytes]:
    _validate_local_url(url)
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed local allowlist above
            return int(response.status), response.read()
    except HTTPError as exc:
        return int(exc.code), exc.read()


def get_json(url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    status, body = http("GET", url, timeout=timeout)
    require(status == 200, f"GET {url} returned HTTP {status}")
    value = json.loads(body.decode("utf-8"))
    require(isinstance(value, dict), f"GET {url} did not return a JSON object")
    return value


def table_count(table: str) -> int:
    require(
        table in {"task_ledger", "research_retrieval_evidence", "research_operations_events"},
        f"unsupported table count: {table}",
    )
    connection = sqlite3.connect(TRUTH_DB)
    try:
        exists = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists or int(exists[0]) != 1:
            return 0
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0] if row else 0)
    finally:
        connection.close()


def service_state(service: str) -> str:
    return output(["systemctl", "is-active", service])


def backend_pid() -> int:
    value = output(["systemctl", "show", "dap-backend.service", "-p", "MainPID", "--value"])
    require(value.isdigit() and int(value) > 0, f"invalid backend PID: {value}")
    return int(value)


def dashboard_health() -> str:
    return output(
        [
            "docker",
            "inspect",
            "-f",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
            "dap-dashboard",
        ]
    )


def searxng_state() -> str:
    return output(["docker", "inspect", "-f", "{{.State.Status}}", "dap-searxng"])


def searxng_binding() -> str:
    return output(["docker", "port", "dap-searxng", "8080/tcp"]).replace("\r", "")


def telegram_setting() -> str:
    env_path = Path("/home/dipen/dap/config/dap-backend.env")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DAP_TELEGRAM_APPROVALS_ENABLED="):
            return line
    return ""


@dataclass
class BurninState:
    expected_head: str
    base_tasks: int
    base_evidence: int
    base_ops: int
    activated_pid: int
    run_ids: list[str]
    last_tasks: int
    last_evidence: int
    last_ops: int
    burnin_complete: bool = False

    @property
    def run_count(self) -> int:
        return len(self.run_ids)

    def save(self) -> None:
        payload = {
            "expected_head": self.expected_head,
            "base_tasks": self.base_tasks,
            "base_evidence": self.base_evidence,
            "base_ops": self.base_ops,
            "activated_pid": self.activated_pid,
            "run_ids": self.run_ids,
            "last_tasks": self.last_tasks,
            "last_evidence": self.last_evidence,
            "last_ops": self.last_ops,
            "burnin_complete": self.burnin_complete,
        }
        STATE_PATH.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls) -> BurninState:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return cls(
            expected_head=str(payload["expected_head"]),
            base_tasks=int(payload["base_tasks"]),
            base_evidence=int(payload["base_evidence"]),
            base_ops=int(payload["base_ops"]),
            activated_pid=int(payload["activated_pid"]),
            run_ids=[str(value) for value in payload.get("run_ids") or []],
            last_tasks=int(payload["last_tasks"]),
            last_evidence=int(payload["last_evidence"]),
            last_ops=int(payload["last_ops"]),
            burnin_complete=bool(payload.get("burnin_complete")),
        )


def verify_run_task(run_id: str) -> str:
    connection = sqlite3.connect(TRUTH_DB)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT task_id, status, requested_by, assigned_agent_ids_json, source_run_id
            FROM task_ledger
            WHERE source_run_id = ?
            """,
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    require(len(rows) == 1, f"run {run_id} did not map to exactly one task")
    row = rows[0]
    assigned = json.loads(str(row["assigned_agent_ids_json"]))
    require(str(row["status"]) == "completed", f"run task is not completed: {dict(row)}")
    require(str(row["requested_by"]) == "agent-api", f"unexpected requested_by: {dict(row)}")
    require(assigned == ["research-agent"], f"unexpected assigned agents: {assigned}")
    require(str(row["source_run_id"]) == run_id, f"task/run correlation mismatch: {dict(row)}")
    task_id = str(row["task_id"])
    emit("research_task_id", task_id)
    emit("research_task_status", row["status"])
    emit("research_task_assigned_agent", "research-agent")
    emit("research_task_source_run_id", run_id)
    return task_id


def new_state(expected_head: str) -> BurninState:
    base_tasks = table_count("task_ledger")
    base_evidence = table_count("research_retrieval_evidence")
    base_ops = table_count("research_operations_events")
    pid_before = backend_pid()
    emit("task_ledger_before", base_tasks)
    emit("research_evidence_before", base_evidence)
    emit("research_operations_before", base_ops)
    emit("backend_pid_before", pid_before)

    print("\n=== 2. CONTROLLED BACKEND LOAD ===", flush=True)
    run(["sudo", "systemctl", "restart", "dap-backend.service"], capture=False)
    ready = False
    for attempt in range(1, 31):
        try:
            status, _ = http("GET", f"{BACKEND_BASE}/health", timeout=3.0)
        except OSError:
            status = 0
        if status == 200:
            emit("backend_ready_attempt", attempt)
            ready = True
            break
        time.sleep(2)
    if not ready:
        emit("backend_phase14_load", "FAIL")
        run(
            ["sudo", "journalctl", "-u", "dap-backend.service", "-n", "100", "--no-pager"],
            capture=False,
            check=False,
        )
        raise OperatorError("backend did not become healthy after controlled restart")

    activated_pid = backend_pid()
    require(activated_pid != pid_before, "backend restart did not create a new process")
    state = BurninState(
        expected_head=expected_head,
        base_tasks=base_tasks,
        base_evidence=base_evidence,
        base_ops=base_ops,
        activated_pid=activated_pid,
        run_ids=[],
        last_tasks=base_tasks,
        last_evidence=base_evidence,
        last_ops=base_ops,
    )
    state.save()
    emit("backend_phase14_load", "PASS")
    emit("backend_pid_activated", activated_pid)
    return state


def load_or_create_state(expected_head: str) -> BurninState:
    if STATE_PATH.exists():
        state = BurninState.load()
        if state.expected_head != expected_head:
            stale = STATE_PATH.with_name(
                f"{STATE_PATH.name}.stale.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
            )
            STATE_PATH.rename(stale)
            emit("stale_state_moved", stale)
        else:
            emit("phase14_resume_state", "present")
            emit("phase14_resume_run_count", state.run_count)
            emit("phase14_resume_burnin_complete", state.burnin_complete)
            require(table_count("task_ledger") == state.last_tasks, "resume_task_count|MISMATCH_STOP")
            require(
                table_count("research_retrieval_evidence") == state.last_evidence,
                "resume_evidence_count|MISMATCH_STOP",
            )
            require(
                table_count("research_operations_events") == state.last_ops,
                "resume_operations_count|MISMATCH_STOP",
            )
            require(backend_pid() == state.activated_pid, "resume_backend_pid|MISMATCH_STOP")
            require(service_state("dap-backend.service") == "active", "backend is not active")
            emit("phase14_resume_state", "VALID")
            print("\n=== 2. CONTROLLED BACKEND LOAD ===", flush=True)
            emit("backend_phase14_load", "RESUME_ALREADY_LOADED")
            return state
    return new_state(expected_head)


BURNIN_CASES = (
    (
        "IANA example domains RFC 2606",
        "Using current public sources, briefly explain why IANA example domains exist and cite the retrieved evidence.",
    ),
    (
        "robots exclusion protocol RFC 9309",
        "Using current public sources, briefly explain what RFC 9309 standardizes and cite the retrieved evidence.",
    ),
    (
        "HTTP status code 418 RFC semantics",
        "Using current public sources, briefly explain the standards status of HTTP status code 418 and cite the retrieved evidence.",
    ),
)


def run_burnin_search(state: BurninState, index: int) -> None:
    query, objective = BURNIN_CASES[index - 1]
    payload = {
        "mode": "manual",
        "agent_id": "research-agent",
        "objective": objective,
        "research_search_query": query,
        "provider": "ollama",
        "model": "qwen3:1.7b",
        "temperature": 0.1,
        "max_tokens": 320,
        "max_steps": 4,
        "retrieval_limit": 5,
        "score_threshold": 0.4,
    }
    status, body = http(
        "POST",
        f"{BACKEND_BASE}/api/v1/agents/run",
        payload=payload,
        timeout=420.0,
    )
    emit("burnin_run_http", f"{index}|{status}")
    require(status == 200, f"burn-in run {index} failed: {body.decode('utf-8', errors='replace')}")
    response = json.loads(body.decode("utf-8"))
    require(response.get("status") == "completed", f"burn-in response not completed: {response}")
    require(response.get("agent_id") == "research-agent", f"unexpected agent: {response}")
    steps = response.get("steps") or []
    search_steps = [
        step
        for step in steps
        if step.get("title") == "Discover and retrieve public-web evidence via local SearXNG"
    ]
    require(len(search_steps) == 1, f"unexpected search steps: {search_steps}")
    step = search_steps[0]
    require(step.get("success") is True, f"provider-specific search failed: {step}")
    metadata = step.get("output") or {}
    require(metadata.get("provider_id") == "searxng-local-v1", f"provider mismatch: {metadata}")
    selected = list(metadata.get("selected_urls") or [])
    families = list(metadata.get("selected_source_families") or [])
    scores = list(metadata.get("selected_quality_scores") or [])
    require(0 < len(selected) <= 3, f"selected URL bound failed: {selected}")
    require(len(families) == len(selected), f"source-family metadata mismatch: {metadata}")
    require(len(scores) == len(selected), f"selection-score metadata mismatch: {metadata}")
    require(
        metadata.get("source_selection_policy_id") == "dap-source-family-diversity-v1",
        f"selection policy mismatch: {metadata}",
    )
    require(int(metadata.get("unique_source_family_count", 0)) >= 1, f"source-family count missing: {metadata}")
    require(metadata.get("selection_quality_is_factual_credibility") is False, "selection quality claimed credibility")
    require(metadata.get("provider_snippets_are_evidence") is False, "provider snippets became evidence")
    require(metadata.get("provider_snippets_exposed_to_model") is False, "provider snippets reached model")
    require(metadata.get("provider_titles_exposed_to_model") is False, "provider titles reached model")
    require(metadata.get("search_candidates_are_retrieval_evidence") is False, "search candidates became evidence")
    require(metadata.get("candidate_urls_require_full_dap_retrieval") is True, "selected URL bypassed DAP retrieval")
    require(metadata.get("generic_network_client_exposed") is False, "generic network client exposed")
    require(metadata.get("remote_scope_expansion_allowed") is False, "remote scope expansion allowed")

    retrieval_sources = list(metadata.get("retrieval_sources") or [])
    require(len(retrieval_sources) == len(selected), f"retrieval source count mismatch: {metadata}")
    for source in retrieval_sources:
        require("model_context" not in source, "raw model context leaked into status metadata")
        require(int(source.get("attempt_count", 0)) in {1, 2}, f"attempt count invalid: {source}")
        require(int(source.get("transient_retry_count", 0)) in {0, 1}, f"retry count invalid: {source}")
        require(float(source.get("duration_ms", -1)) >= 0, f"duration missing: {source}")

    public_sources = [
        source
        for source in (response.get("sources") or [])
        if source.get("source_kind") == "public_web"
    ]
    require(public_sources, "burn-in returned no successful public-web evidence")
    require(all(source.get("evidence_id") for source in public_sources), "public evidence lacks evidence IDs")
    require(bool(str(response.get("answer") or "").strip()), "burn-in returned empty answer")

    run_id = str(response["run_id"])
    emit("burnin_run_id", f"{index}|{run_id}")
    emit("burnin_selected_url_count", f"{index}|{len(selected)}")
    emit("burnin_public_source_count", f"{index}|{len(public_sources)}")
    emit("burnin_unique_source_family_count", f"{index}|{metadata.get('unique_source_family_count')}")
    emit("burnin_duplicate_family_fallback_count", f"{index}|{metadata.get('duplicate_family_fallback_count', 0)}")

    tasks_now = table_count("task_ledger")
    evidence_now = table_count("research_retrieval_evidence")
    ops_now = table_count("research_operations_events")
    task_delta = tasks_now - state.last_tasks
    evidence_delta = evidence_now - state.last_evidence
    ops_delta = ops_now - state.last_ops
    emit("burnin_task_delta", f"{index}|{task_delta}")
    emit("burnin_evidence_delta", f"{index}|{evidence_delta}")
    emit("burnin_operations_delta", f"{index}|{ops_delta}")
    require(task_delta == 1, f"burn-in task delta is {task_delta}, expected 1")
    require(evidence_delta == len(selected), f"burn-in evidence delta {evidence_delta} != selected {len(selected)}")
    require(ops_delta == len(selected), f"burn-in operations delta {ops_delta} != selected {len(selected)}")
    verify_run_task(run_id)

    state.run_ids.append(run_id)
    state.last_tasks = tasks_now
    state.last_evidence = evidence_now
    state.last_ops = ops_now
    state.save()
    emit("burnin_state_saved", f"run_{index}")


def prove_read_only_operations(state: BurninState) -> dict[str, Any]:
    print("\n=== 3. READ-ONLY OPERATIONS API + AUTHORITY NEGATIVE PROOF ===", flush=True)
    endpoints = (
        "operations",
        "operations/provider-health",
        "operations/resource-snapshot",
        "operations/retention-plan",
    )
    for endpoint in endpoints:
        url = f"{BACKEND_BASE}/api/v1/research/{endpoint}"
        get_status, _ = http("GET", url)
        post_status, _ = http("POST", url)
        emit("backend_get", f"{endpoint}|{get_status}")
        emit("backend_post", f"{endpoint}|{post_status}")
        require(get_status == 200, f"GET endpoint failed: {endpoint}")
        require(post_status == 405, f"POST endpoint did not fail closed: {endpoint}")

    if state.run_count == 0:
        tasks_before = table_count("task_ledger")
        evidence_before = table_count("research_retrieval_evidence")
        ops_before = table_count("research_operations_events")
        status, body = http(
            "POST",
            f"{BACKEND_BASE}/api/v1/agents/run",
            payload={
                "mode": "smart",
                "objective": "Research IANA example domains using current public sources.",
                "research_search_query": "IANA example domains RFC 2606",
                "provider": "ollama",
                "model": "qwen3:1.7b",
            },
            timeout=60.0,
        )
        emit("smart_research_http", status)
        require(status == 400, f"smart research was not rejected: {body.decode('utf-8', errors='replace')}")
        require(table_count("task_ledger") == tasks_before, "smart rejection mutated task ledger")
        require(table_count("research_retrieval_evidence") == evidence_before, "smart rejection mutated evidence")
        require(table_count("research_operations_events") == ops_before, "smart rejection mutated operations")
        emit("smart_routing_research_disabled", "PASS")
    else:
        emit("smart_routing_research_disabled", "PREVIOUSLY_PROVEN_IN_THIS_RUN")
    return {}


def complete_burnin(state: BurninState) -> None:
    print("\n=== 4. MANUAL RESEARCH BURN-IN ===", flush=True)
    if state.burnin_complete:
        emit("manual_research_burnin", "RESUME_ALREADY_COMPLETE")
    else:
        while state.run_count < MIN_BURNIN_RUNS:
            run_burnin_search(state, state.run_count + 1)
        operations_delta = state.last_ops - state.base_ops
        if operations_delta < MIN_BURNIN_OPERATIONS_EVENTS and state.run_count < MAX_BURNIN_RUNS:
            emit("burnin_operations_after_two", operations_delta)
            emit("burnin_third_run", "required")
            run_burnin_search(state, state.run_count + 1)

        operations_delta = state.last_ops - state.base_ops
        task_delta = state.last_tasks - state.base_tasks
        evidence_delta = state.last_evidence - state.base_evidence
        emit("burnin_run_count", state.run_count)
        emit("burnin_task_delta_total", task_delta)
        emit("burnin_evidence_delta_total", evidence_delta)
        emit("burnin_operations_delta_total", operations_delta)
        require(MIN_BURNIN_RUNS <= state.run_count <= MAX_BURNIN_RUNS, "burn-in run count outside bound")
        require(task_delta == state.run_count, "burn-in task delta does not match run count")
        require(evidence_delta == operations_delta, "evidence and operations deltas diverged")
        require(operations_delta >= MIN_BURNIN_OPERATIONS_EVENTS, "burnin_sample|INSUFFICIENT_STOP")
        state.burnin_complete = True
        state.save()
    emit("manual_research_burnin", "PASS")
    for run_id in state.run_ids:
        verify_run_task(run_id)


def validate_live_models(state: BurninState) -> list[Any]:
    print("\n=== 5. LIVE OPERATIONS / RETENTION / HEALTH / RESOURCE PROOF ===", flush=True)
    ops = get_json(f"{BACKEND_BASE}/api/v1/research/operations")
    health = get_json(f"{BACKEND_BASE}/api/v1/research/operations/provider-health")
    resources = get_json(f"{BACKEND_BASE}/api/v1/research/operations/resource-snapshot")
    retention = get_json(f"{BACKEND_BASE}/api/v1/research/operations/retention-plan")
    minimum_new_events = state.last_ops - state.base_ops

    require(ops.get("evidence_total") == state.last_evidence, "operations evidence total mismatch")
    require(int(ops.get("window_event_count", 0)) >= minimum_new_events, "operations event window too small")
    require(ops.get("p50_source_duration_ms") is not None, "p50 latency missing")
    require(ops.get("p95_source_duration_ms") is not None, "p95 latency missing")
    require(int(ops.get("retrieval_attempt_count", 0)) >= minimum_new_events, "attempt count missing")
    require(isinstance(ops.get("transient_retry_count"), int), "retry count missing")
    require(isinstance(ops.get("recovered_after_retry_count"), int), "recovery count missing")
    require(int(ops.get("unique_source_family_count", 0)) >= 1, "source-family visibility missing")
    require(isinstance(ops.get("duplicate_content_group_count"), int), "duplicate visibility missing")
    require(isinstance(ops.get("errors"), list), "error distribution missing")
    require(bool(ops.get("provenance_quality")), "provenance quality missing")
    require(ops.get("average_provenance_quality_score") is not None, "provenance average missing")
    require(ops.get("factual_correctness_measured") is False, "operations claimed factual correctness")
    require(ops.get("workspace_mode") == "read_only", "operations workspace not read-only")
    require(ops.get("network_authority_granted") is False, "operations granted network authority")
    require(ops.get("mutation_authority_granted") is False, "operations granted mutation authority")

    require(health.get("provider_id") == "searxng-local-v1", "provider health ID mismatch")
    require(health.get("endpoint") == "http://127.0.0.1:8888/", "provider health endpoint mismatch")
    require(health.get("healthy") is True and health.get("status_code") == 200, f"SearXNG degraded: {health}")
    require(health.get("provider_is_local_only") is True, "provider health lost local-only contract")
    require(health.get("loopback_contract_valid") is True, "provider health loopback contract failed")
    require(health.get("service_control_authority_granted") is False, "provider health granted service control")
    require(health.get("credentials_used") is False, "provider health used credentials")

    require(int(resources.get("process_id", 0)) == state.activated_pid, "resource snapshot PID mismatch")
    require(resources.get("scope") == "dap-backend-process", "resource scope mismatch")
    require(resources.get("research_specific_attribution") is False, "resource snapshot claims per-request attribution")
    require(resources.get("read_only") is True, "resource snapshot not read-only")
    require(resources.get("service_control_authority_granted") is False, "resource snapshot granted service control")
    require(float(resources.get("process_rss_mib", -1)) >= 0, "resource RSS missing")

    policy = retention.get("policy") or {}
    require(retention.get("mode") == "dry_run", "retention is not dry-run")
    require(retention.get("evidence_deleted") is False, "retention deleted evidence")
    require(retention.get("evidence_mutated") is False, "retention mutated evidence")
    require(policy.get("default_preserve_all") is True, "retention default is not preserve-all")
    require(policy.get("automatic_deletion_enabled") is False, "automatic evidence deletion enabled")
    require(policy.get("automatic_archive_enabled") is False, "automatic archive enabled")
    require(policy.get("owner_action_required_for_future_cleanup") is True, "retention bypassed owner action")
    require(retention.get("total_evidence") == state.last_evidence, "retention evidence total mismatch")

    values = [
        ops.get("reliability_posture"),
        ops.get("success_rate"),
        ops.get("failure_rate"),
        ops.get("p50_source_duration_ms"),
        ops.get("p95_source_duration_ms"),
        ops.get("unique_source_family_rate"),
        ops.get("duplicate_content_rate"),
        ops.get("transient_retry_count"),
        ops.get("recovered_after_retry_count"),
        ops.get("average_provenance_quality_score"),
        health.get("latency_ms"),
        resources.get("process_rss_mib"),
        retention.get("future_archive_candidate_count"),
    ]
    names = [
        "reliability_posture",
        "success_rate",
        "failure_rate",
        "retrieval_p50_ms",
        "retrieval_p95_ms",
        "unique_source_family_rate",
        "duplicate_content_rate",
        "transient_retry_count",
        "recovered_after_retry_count",
        "provenance_quality_average",
        "searxng_health_latency_ms",
        "backend_rss_mib",
        "future_archive_candidate_count",
    ]
    for name, value in zip(names, values, strict=True):
        emit(name, value)
    emit("live_operations_visibility", "PASS")
    return values


def run_benchmark(expected_head: str) -> None:
    print("\n=== 6. DETERMINISTIC RELIABILITY BENCHMARK ON ACER ===", flush=True)
    BENCHMARK_REPORT.unlink(missing_ok=True)
    run(
        [
            str(PYTHON),
            "-m",
            "gateway.research_reliability_benchmark",
            "--source-commit",
            expected_head,
            "--output",
            str(BENCHMARK_REPORT),
        ],
        cwd=BACKEND,
        capture=False,
    )
    report = json.loads(BENCHMARK_REPORT.read_text(encoding="utf-8"))
    require(report.get("benchmark_version") == "phase14i.1", "benchmark version mismatch")
    require(report.get("source_commit") == expected_head, "benchmark source commit mismatch")
    require(report.get("case_count") == 5 and report.get("cases_passed") == 5, "benchmark did not pass 5/5")
    require(report.get("completion_rate") == 1.0 and report.get("all_cases_passed") is True, "benchmark incomplete")
    require(report.get("smart_routing_research_activated") is False, "benchmark expanded smart routing")
    require(report.get("network_authority_expanded") is False, "benchmark expanded network authority")
    require(report.get("destructive_retention_action_performed") is False, "benchmark mutated retention")
    require(len(str(report.get("report_sha256") or "")) == 64, "benchmark report hash missing")
    for key in ("resource_snapshot_before", "resource_snapshot_after"):
        snapshot = report.get(key) or {}
        require(snapshot.get("scope") == "dap-backend-process", f"benchmark resource scope invalid: {snapshot}")
        require(snapshot.get("research_specific_attribution") is False, "benchmark resource snapshot claims request attribution")
        require(snapshot.get("service_control_authority_granted") is False, "benchmark resource snapshot grants control")
    emit("phase14_live_benchmark_sha256", report["report_sha256"])
    emit("phase14_live_reliability_benchmark", "PASS")


def clean_dashboard_tree() -> None:
    next_path = DASH / ".next"
    if not next_path.exists():
        return
    try:
        shutil.rmtree(next_path)
        emit("dashboard_build_tree_cleanup", "user")
    except PermissionError:
        emit("dashboard_build_tree_cleanup", "sudo_fixed_path")
        run(["sudo", "rm", "-rf", "--", str(next_path)], capture=False)
    require(not next_path.exists(), "dashboard .next cleanup failed")


def build_dashboard() -> tuple[str, str, str, str]:
    print("\n=== 7. OFFLINE DASHBOARD BUILD ===", flush=True)
    dashboard_id_before = output(["docker", "inspect", "-f", "{{.Id}}", "dap-dashboard"])
    dashboard_image_before = output(["docker", "inspect", "-f", "{{.Image}}", "dap-dashboard"])
    dashboard_image_ref = output(["docker", "inspect", "-f", "{{.Config.Image}}", "dap-dashboard"])
    rollback_tag = f"dap-dashboard-phase14-rollback:{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    run(["docker", "tag", dashboard_image_before, rollback_tag])
    emit("rollback_image", rollback_tag)

    clean_dashboard_tree()
    require((DASH / "node_modules/next").is_dir(), "local_node_modules|MISSING_STOP")
    run(["docker", "image", "inspect", "node:24-alpine"])
    run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-e",
            "HOME=/tmp",
            "-e",
            "NEXT_TELEMETRY_DISABLED=1",
            "-v",
            f"{DASH}:/app",
            "-w",
            "/app",
            "node:24-alpine",
            "sh",
            "-lc",
            "npm run build",
        ],
        capture=False,
    )
    emit("offline_dashboard_app_build", "PASS")
    require((DASH / ".next/standalone/server.js").is_file(), "standalone server missing")
    require((DASH / ".next/static").is_dir(), "Next static output missing")
    require((DASH / "public").is_dir(), "dashboard public directory missing")
    require(output(["git", "status", "--porcelain"], cwd=REPO) == "", "source_after_dashboard_build|DIRTY_STOP")

    if RUNTIME_CONTEXT.exists():
        shutil.rmtree(RUNTIME_CONTEXT)
    RUNTIME_CONTEXT.mkdir(parents=True)
    shutil.copytree(DASH / ".next/standalone", RUNTIME_CONTEXT, dirs_exist_ok=True)
    (RUNTIME_CONTEXT / ".next").mkdir(exist_ok=True)
    shutil.copytree(DASH / ".next/static", RUNTIME_CONTEXT / ".next/static")
    shutil.copytree(DASH / "public", RUNTIME_CONTEXT / "public")
    (RUNTIME_CONTEXT / "Dockerfile").write_text(
        """FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs \\
    && adduser --system --uid 1001 nextjs
COPY --chown=nextjs:nodejs . .
USER nextjs
EXPOSE 3000
CMD [\"node\", \"server.js\"]
""",
        encoding="utf-8",
    )
    run(
        [
            "docker",
            "build",
            "--pull=false",
            "--network=none",
            "-t",
            dashboard_image_ref,
            str(RUNTIME_CONTEXT),
        ],
        capture=False,
    )
    new_image_id = output(["docker", "image", "inspect", "-f", "{{.Id}}", dashboard_image_ref])
    emit("dashboard_new_image_id", new_image_id)
    require(new_image_id != dashboard_image_before, "dashboard runtime image did not change")
    emit("dashboard_runtime_image", "PASS")
    return dashboard_id_before, new_image_id, dashboard_image_ref, rollback_tag


def deploy_dashboard(
    state: BurninState,
    dashboard_id_before: str,
    new_image_id: str,
    dashboard_image_ref: str,
    rollback_tag: str,
) -> None:
    print("\n=== 8. RECREATE ONLY DASHBOARD + OWNER VISIBILITY ===", flush=True)
    run(
        ["docker", "compose", "up", "-d", "--no-deps", "--no-build", "--force-recreate", "dashboard"],
        cwd=COMPOSE,
        capture=False,
    )
    ready = False
    for attempt in range(1, 46):
        status = dashboard_health()
        emit("dashboard_health_attempt", f"{attempt}|{status}")
        if status == "healthy":
            ready = True
            break
        time.sleep(2)
    if not ready:
        emit("dashboard_health", "FAIL")
        run(["docker", "logs", "--tail=150", "dap-dashboard"], capture=False, check=False)
        run(["docker", "tag", rollback_tag, dashboard_image_ref], check=False)
        run(
            ["docker", "compose", "up", "-d", "--no-deps", "--no-build", "--force-recreate", "dashboard"],
            cwd=COMPOSE,
            capture=False,
            check=False,
        )
        emit("dashboard_rollback_attempted", True)
        raise OperatorError("dashboard did not become healthy")

    emit("dashboard_health", "PASS")
    dashboard_id_after = output(["docker", "inspect", "-f", "{{.Id}}", "dap-dashboard"])
    running_image = output(["docker", "inspect", "-f", "{{.Image}}", "dap-dashboard"])
    emit("dashboard_container_before", dashboard_id_before)
    emit("dashboard_container_after", dashboard_id_after)
    emit("dashboard_running_image", running_image)
    require(dashboard_id_after != dashboard_id_before, "dashboard container was not recreated")
    require(running_image == new_image_id, "dashboard is not running the new image")

    research_status, _ = http("GET", f"{DASHBOARD_BASE}/research")
    operations_status, operations_html = http("GET", f"{DASHBOARD_BASE}/research/operations")
    emit("research_page_http", research_status)
    emit("research_operations_page_http", operations_status)
    require(research_status == 200 and operations_status == 200, "research dashboard page failed")
    require(b"Reliability and evidence health" in operations_html, "research_operations_page_marker|FAIL")
    emit("research_operations_page_marker", "PASS")

    ops = get_json(f"{DASHBOARD_BASE}/api/research/operations")
    health = get_json(f"{DASHBOARD_BASE}/api/research/operations/provider-health")
    resources = get_json(f"{DASHBOARD_BASE}/api/research/operations/resource-snapshot")
    retention = get_json(f"{DASHBOARD_BASE}/api/research/operations/retention-plan")
    require(ops.get("evidence_total") == state.last_evidence, "dashboard operations evidence total mismatch")
    require(ops.get("workspace_mode") == "read_only", "dashboard operations not read-only")
    require(ops.get("network_authority_granted") is False, "dashboard operations granted network authority")
    require(ops.get("mutation_authority_granted") is False, "dashboard operations granted mutation authority")
    require(health.get("healthy") is True, "dashboard provider health degraded")
    require(health.get("service_control_authority_granted") is False, "dashboard health grants service control")
    require(int(resources.get("process_id", 0)) == state.activated_pid, "dashboard resource PID mismatch")
    require(resources.get("read_only") is True, "dashboard resource snapshot not read-only")
    require(resources.get("service_control_authority_granted") is False, "dashboard resource snapshot grants control")
    require(retention.get("mode") == "dry_run", "dashboard retention not dry-run")
    require(retention.get("evidence_deleted") is False, "dashboard retention deleted evidence")
    require(retention.get("evidence_mutated") is False, "dashboard retention mutated evidence")
    emit("dashboard_operations_models", "PASS")

    for endpoint in (
        "operations",
        "operations/provider-health",
        "operations/resource-snapshot",
        "operations/retention-plan",
    ):
        status, _ = http("POST", f"{DASHBOARD_BASE}/api/research/{endpoint}")
        emit("dashboard_post", f"{endpoint}|{status}")
        require(status == 405, f"dashboard POST did not fail closed: {endpoint}")
    emit("owner_operations_visibility", "PASS")


def final_safety(state: BurninState, expected_head: str, live_values: list[Any], rollback_tag: str) -> None:
    print("\n=== 9. FINAL PRODUCTION SAFETY ===", flush=True)
    tasks = table_count("task_ledger")
    evidence = table_count("research_retrieval_evidence")
    operations = table_count("research_operations_events")
    pid = backend_pid()
    backend = service_state("dap-backend.service")
    guardian = service_state("dap-guardian-broker.service")
    telegram = telegram_setting()
    dashboard = dashboard_health()
    searx_state = searxng_state()
    searx_binding_value = searxng_binding()
    head = output(["git", "rev-parse", "HEAD"], cwd=REPO)
    source = "clean" if output(["git", "status", "--porcelain"], cwd=REPO) == "" else "DIRTY"

    for name, value in (
        ("task_ledger_final", tasks),
        ("research_evidence_final", evidence),
        ("research_operations_final", operations),
        ("backend_pid_final", pid),
        ("backend_final", backend),
        ("guardian_final", guardian),
        ("telegram_final", telegram),
        ("dashboard_final", dashboard),
        ("searxng_state_final", searx_state),
        ("searxng_binding_final", searx_binding_value),
        ("HEAD_final", head),
        ("source_final", source),
    ):
        emit(name, value)

    require(tasks == state.last_tasks, "final task count changed")
    require(evidence == state.last_evidence, "final evidence count changed")
    require(operations == state.last_ops, "final operations count changed")
    require(pid == state.activated_pid, "backend restarted after Phase 14 load")
    require(backend == "active", "backend not active")
    require(guardian == "inactive", "Guardian unexpectedly active")
    require(telegram == "DAP_TELEGRAM_APPROVALS_ENABLED=false", "Telegram approvals changed")
    require(dashboard == "healthy", "dashboard not healthy")
    require(searx_state == "running", "SearXNG not running")
    require(searx_binding_value == "127.0.0.1:8888", "SearXNG binding changed")
    require(head == expected_head, "source HEAD changed")
    require(source == "clean", "source checkout dirty")
    require(state.burnin_complete, "burn-in state is not complete")
    for run_id in state.run_ids:
        verify_run_task(run_id)

    print("\nPHASE14_RESEARCH_OPERATIONS_LIVE_BURNIN|PASS", flush=True)
    print("PHASE14_OWNER_OPERATIONS_VISIBILITY|PASS", flush=True)
    print("PHASE14_AUTHORITY_BOUNDARY|PASS", flush=True)
    emit("phase14_burnin_run_count", state.run_count)
    emit("phase14_burnin_evidence_delta", state.last_evidence - state.base_evidence)
    emit("phase14_burnin_operations_delta", state.last_ops - state.base_ops)
    emit("phase14_live_reliability_posture", live_values[0])
    emit("phase14_state", STATE_PATH)
    emit("phase14_benchmark_report", BENCHMARK_REPORT)
    emit("rollback_image", rollback_tag)


def baseline(expected_head: str) -> None:
    print("============================================================")
    print(" PHASE 14 — RESEARCH OPERATIONS RELIABILITY LIVE BURN-IN")
    print("============================================================")
    print("\n=== 1. EXACT SOURCE + PRODUCTION BASELINE ===", flush=True)
    branch = output(["git", "branch", "--show-current"], cwd=REPO)
    head = output(["git", "rev-parse", "HEAD"], cwd=REPO)
    source = "clean" if output(["git", "status", "--porcelain"], cwd=REPO) == "" else "DIRTY"
    emit("branch", branch)
    emit("HEAD", head)
    emit("source_status", source)
    require(branch == "phase14/research-operations-reliability", "unexpected branch")
    require(head == expected_head, "unexpected Phase 14 source checkpoint")
    require(source == "clean", "source checkout is dirty")
    require(PYTHON.is_file() and os.access(PYTHON, os.X_OK), "backend_python|MISSING_STOP")
    require(TRUTH_DB.is_file(), "truth_db|MISSING_STOP")

    backend = service_state("dap-backend.service")
    guardian = service_state("dap-guardian-broker.service")
    telegram = telegram_setting()
    dashboard = dashboard_health()
    searx_state = searxng_state()
    searx_binding_value = searxng_binding()
    emit("backend_baseline", backend)
    emit("guardian_baseline", guardian)
    emit("telegram_baseline", telegram)
    emit("dashboard_baseline", dashboard)
    emit("searxng_state_baseline", searx_state)
    emit("searxng_binding_baseline", searx_binding_value)
    require(backend == "active", "backend baseline is not active")
    require(guardian == "inactive", "Guardian baseline is not inactive")
    require(telegram == "DAP_TELEGRAM_APPROVALS_ENABLED=false", "Telegram approvals baseline changed")
    require(dashboard == "healthy", "dashboard baseline is not healthy")
    require(searx_state == "running", "SearXNG baseline is not running")
    require(searx_binding_value == "127.0.0.1:8888", "SearXNG is not loopback-only")
    status, _ = http("GET", f"{SEARXNG_BASE}/", timeout=10.0)
    require(status == 200, f"SearXNG local HTTP preflight returned {status}")
    emit("source_and_runtime_baseline", "PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected_head")
    args = parser.parse_args()
    expected_head = args.expected_head.strip()
    require(len(expected_head) == 40, "expected head must be a full 40-character commit SHA")

    baseline(expected_head)
    state = load_or_create_state(expected_head)
    prove_read_only_operations(state)
    complete_burnin(state)
    live_values = validate_live_models(state)
    run_benchmark(expected_head)
    dashboard_id_before, new_image_id, dashboard_image_ref, rollback_tag = build_dashboard()
    deploy_dashboard(
        state,
        dashboard_id_before,
        new_image_id,
        dashboard_image_ref,
        rollback_tag,
    )
    final_safety(state, expected_head, live_values, rollback_tag)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OperatorError as exc:
        print(f"phase14_operator_error|{exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
