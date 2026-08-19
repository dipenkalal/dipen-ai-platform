from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path("/home/dipen/dap/source/dipen-ai-platform")
BACKEND = REPO / "platform/backend"
PYTHON = BACKEND / ".venv/bin/python"
TRUTH_DB = Path("/home/dipen/dap/data/agent-history/agent-truth.db")
STATE_PATH = Path("/tmp/dap-phase14-research-operations-live-state.json")
BACKEND_RUN_URL = "http://127.0.0.1:8002/api/v1/agents/run"
LIVE_OPERATOR = REPO / "scripts/phase14-research-operations-live-burnin.sh"

MIN_SUCCESSFUL_RUNS = 2
MIN_OPERATIONS_EVENTS = 5
MAX_FALLBACK_ATTEMPTS = 3

FALLBACK_CASES = (
    (
        "Example Domain",
        "Using current public sources, briefly explain what Example Domain is and cite the retrieved evidence.",
    ),
    (
        "Python programming language",
        "Using current public sources, briefly explain what the Python programming language is and cite the retrieved evidence.",
    ),
    (
        "HTTP Semantics RFC 9110",
        "Using current public sources, briefly explain what RFC 9110 standardizes and cite the retrieved evidence.",
    ),
)


class RecoveryError(RuntimeError):
    pass


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise RecoveryError(detail)


def emit(name: str, value: Any) -> None:
    if isinstance(value, bool):
        value = str(value).lower()
    print(f"{name}|{value}", flush=True)


def output(command: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def table_count(table: str) -> int:
    require(
        table in {"task_ledger", "research_retrieval_evidence", "research_operations_events"},
        f"unsupported table: {table}",
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


def task_for_run(run_id: str) -> sqlite3.Row:
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
    require(len(rows) == 1, f"run {run_id} did not map to exactly one task row")
    return rows[0]


def verify_task(run_id: str, expected_status: str) -> None:
    row = task_for_run(run_id)
    assigned = json.loads(str(row["assigned_agent_ids_json"]))
    require(str(row["status"]) == expected_status, f"unexpected task status: {dict(row)}")
    require(str(row["requested_by"]) == "agent-api", f"unexpected requested_by: {dict(row)}")
    require(assigned == ["research-agent"], f"unexpected assigned agents: {assigned}")
    require(str(row["source_run_id"]) == run_id, f"task/run mismatch: {dict(row)}")
    emit("research_task_id", row["task_id"])
    emit("research_task_status", row["status"])
    emit("research_task_source_run_id", run_id)


def post_agent(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    request = Request(
        BACKEND_RUN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=420) as response:  # noqa: S310 - fixed loopback URL
            status = int(response.status)
            body = response.read()
    except HTTPError as exc:
        status = int(exc.code)
        body = exc.read()
    value = json.loads(body.decode("utf-8"))
    require(isinstance(value, dict), "agent response was not a JSON object")
    return status, value


def allowed_source_transition(old_head: str, new_head: str) -> None:
    if old_head == new_head:
        return
    changed = output(["git", "diff", "--name-only", f"{old_head}..{new_head}"], cwd=REPO)
    paths = [line.strip() for line in changed.splitlines() if line.strip()]
    allowed_prefixes = (
        "scripts/phase14",
        "platform/guardian/tests/test_phase14",
        ".github/workflows/phase14",
        "docs/phase14",
    )
    require(paths, "source transition contained no files")
    unexpected = [path for path in paths if not path.startswith(allowed_prefixes)]
    require(not unexpected, f"runtime source changed since live backend load: {unexpected}")
    emit("runtime_source_delta_since_failed_run", False)


def load_state(expected_head: str) -> dict[str, Any]:
    require(STATE_PATH.is_file(), f"missing Phase 14 state: {STATE_PATH}")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    require(isinstance(state, dict), "Phase 14 state is not a JSON object")
    old_head = str(state.get("expected_head") or "")
    require(old_head, "Phase 14 state has no expected_head")
    allowed_source_transition(old_head, expected_head)
    state["expected_head"] = expected_head
    return state


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def reconcile_failed_attempt(state: dict[str, Any], failed_run_id: str) -> None:
    tasks_now = table_count("task_ledger")
    evidence_now = table_count("research_retrieval_evidence")
    ops_now = table_count("research_operations_events")
    last_tasks = int(state["last_tasks"])
    last_evidence = int(state["last_evidence"])
    last_ops = int(state["last_ops"])

    already = failed_run_id in list(state.get("provider_failure_run_ids") or [])
    if already:
        require(tasks_now == last_tasks, "reconciled task count changed unexpectedly")
        require(evidence_now == last_evidence, "reconciled evidence count changed unexpectedly")
        require(ops_now == last_ops, "reconciled operations count changed unexpectedly")
        emit("failed_attempt_reconciliation", "ALREADY_RECORDED")
        return

    require(tasks_now == last_tasks + 1, "expected exactly one unrecorded failed task")
    require(evidence_now == last_evidence, "failed search unexpectedly changed evidence count")
    require(ops_now == last_ops, "failed search unexpectedly changed retrieval operations count")
    verify_task(failed_run_id, "failed")

    failures = list(state.get("provider_failure_run_ids") or [])
    failures.append(failed_run_id)
    state["provider_failure_run_ids"] = failures
    state["last_tasks"] = tasks_now
    state["last_evidence"] = evidence_now
    state["last_ops"] = ops_now
    save_state(state)
    emit("failed_attempt_reconciliation", "PASS")
    emit("provider_failure_run_id", failed_run_id)


def successful_step(response: dict[str, Any]) -> dict[str, Any] | None:
    for step in response.get("steps") or []:
        if step.get("title") == "Discover and retrieve public-web evidence via local SearXNG":
            return step
    return None


def validate_completed_response(response: dict[str, Any]) -> int:
    require(response.get("agent_id") == "research-agent", "unexpected burn-in agent")
    step = successful_step(response)
    require(step is not None, "completed run did not contain the successful SearXNG retrieval step")
    require(step.get("success") is True, f"retrieval step was not successful: {step}")
    metadata = step.get("output") or {}
    require(metadata.get("provider_id") == "searxng-local-v1", "unexpected search provider")
    selected = list(metadata.get("selected_urls") or [])
    families = list(metadata.get("selected_source_families") or [])
    scores = list(metadata.get("selected_quality_scores") or [])
    require(0 < len(selected) <= 3, f"selected URL bound failed: {selected}")
    require(len(families) == len(selected), "source-family metadata length mismatch")
    require(len(scores) == len(selected), "selection-quality metadata length mismatch")
    require(metadata.get("source_selection_policy_id") == "dap-source-family-diversity-v1", "selection policy mismatch")
    require(metadata.get("selection_quality_is_factual_credibility") is False, "selection score became credibility")
    require(metadata.get("provider_snippets_exposed_to_model") is False, "provider snippets reached model")
    require(metadata.get("provider_titles_exposed_to_model") is False, "provider titles reached model")
    require(metadata.get("search_candidates_are_retrieval_evidence") is False, "search candidates became evidence")
    require(metadata.get("candidate_urls_require_full_dap_retrieval") is True, "DAP retrieval requirement missing")
    require(metadata.get("generic_network_client_exposed") is False, "generic network client exposed")
    require(metadata.get("remote_scope_expansion_allowed") is False, "remote scope expansion allowed")
    return len(selected)


def run_fallback(state: dict[str, Any], query: str, objective: str, attempt_index: int) -> bool:
    before_tasks = table_count("task_ledger")
    before_evidence = table_count("research_retrieval_evidence")
    before_ops = table_count("research_operations_events")
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
    status, response = post_agent(payload)
    emit("provider_recovery_http", f"{attempt_index}|{status}")
    require(status == 200, f"fallback agent call returned HTTP {status}: {response}")
    run_id = str(response.get("run_id") or "")
    require(run_id, "fallback agent response did not contain run_id")

    after_tasks = table_count("task_ledger")
    after_evidence = table_count("research_retrieval_evidence")
    after_ops = table_count("research_operations_events")
    require(after_tasks == before_tasks + 1, "fallback run did not create exactly one instrumented task")

    if response.get("status") != "completed":
        verify_task(run_id, "failed")
        require(after_evidence == before_evidence, "failed fallback unexpectedly persisted evidence")
        require(after_ops == before_ops, "failed fallback unexpectedly persisted retrieval telemetry")
        failures = list(state.get("provider_failure_run_ids") or [])
        failures.append(run_id)
        state["provider_failure_run_ids"] = failures
        state["last_tasks"] = after_tasks
        state["last_evidence"] = after_evidence
        state["last_ops"] = after_ops
        save_state(state)
        emit("provider_recovery_result", f"{attempt_index}|provider_no_candidate")
        emit("provider_failure_run_id", run_id)
        return False

    selected_count = validate_completed_response(response)
    verify_task(run_id, "completed")
    evidence_delta = after_evidence - before_evidence
    ops_delta = after_ops - before_ops
    require(evidence_delta == selected_count, f"evidence delta {evidence_delta} != selected {selected_count}")
    require(ops_delta == selected_count, f"operations delta {ops_delta} != selected {selected_count}")

    successes = list(state.get("run_ids") or [])
    successes.append(run_id)
    state["run_ids"] = successes
    state["run_count"] = len(successes)
    state["last_tasks"] = after_tasks
    state["last_evidence"] = after_evidence
    state["last_ops"] = after_ops
    save_state(state)

    emit("provider_recovery_result", f"{attempt_index}|completed")
    emit("provider_recovery_run_id", run_id)
    emit("provider_recovery_selected_url_count", selected_count)
    emit("provider_recovery_evidence_delta", evidence_delta)
    emit("provider_recovery_operations_delta", ops_delta)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--failed-run-id", required=True)
    args = parser.parse_args()

    print("============================================================")
    print(" PHASE 14 — PROVIDER FAILURE RECOVERY BRIDGE")
    print("============================================================")

    require(output(["git", "branch", "--show-current"], cwd=REPO) == "phase14/research-operations-reliability", "wrong branch")
    require(output(["git", "rev-parse", "HEAD"], cwd=REPO) == args.expected_head, "wrong HEAD")
    require(not output(["git", "status", "--porcelain"], cwd=REPO), "source tree is dirty")
    require(output(["systemctl", "is-active", "dap-backend.service"]) == "active", "backend is not active")

    state = load_state(args.expected_head)
    require(int(state.get("activated_pid", 0)) > 0, "state has no activated backend PID")
    current_pid = int(output(["systemctl", "show", "dap-backend.service", "-p", "MainPID", "--value"]))
    require(current_pid == int(state["activated_pid"]), "backend PID changed since failed run")

    reconcile_failed_attempt(state, args.failed_run_id)

    successes = list(state.get("run_ids") or [])
    attempts_used = 0
    for query, objective in FALLBACK_CASES:
        if len(successes) >= MIN_SUCCESSFUL_RUNS and (
            int(state["last_ops"]) - int(state["base_ops"]) >= MIN_OPERATIONS_EVENTS
        ):
            break
        if attempts_used >= MAX_FALLBACK_ATTEMPTS:
            break
        attempts_used += 1
        run_fallback(state, query, objective, attempts_used)
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        successes = list(state.get("run_ids") or [])

    ops_delta = int(state["last_ops"]) - int(state["base_ops"])
    require(len(successes) >= MIN_SUCCESSFUL_RUNS, "provider recovery did not obtain two successful burn-in runs")
    require(ops_delta >= MIN_OPERATIONS_EVENTS, f"provider recovery produced only {ops_delta} operations events")

    state["run_count"] = len(successes)
    state["burnin_complete"] = True
    state["provider_recovery_applied"] = True
    save_state(state)

    emit("provider_recovery_successful_run_count", len(successes))
    emit("provider_recovery_operations_delta_total", ops_delta)
    emit("provider_recovery_failure_count", len(state.get("provider_failure_run_ids") or []))
    emit("provider_recovery_bridge", "PASS")
    emit("delegating_to_live_operator", LIVE_OPERATOR)

    completed = subprocess.run(
        ["bash", str(LIVE_OPERATOR), args.expected_head],
        cwd=str(REPO),
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RecoveryError as exc:
        print(f"provider_recovery_error|{exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
