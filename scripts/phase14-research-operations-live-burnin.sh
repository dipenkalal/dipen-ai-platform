#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_HEAD="${1:-}"
REPO="/home/dipen/dap/source/dipen-ai-platform"
BACKEND="$REPO/platform/backend"
DASH="$REPO/apps/dashboard"
COMPOSE="/home/dipen/dap/compose"
PY="$BACKEND/.venv/bin/python"
TRUTH_DB="/home/dipen/dap/data/agent-history/agent-truth.db"
STATE="/tmp/dap-phase14-research-operations-live-state.json"
BENCHMARK_REPORT="/tmp/phase14-reliability-benchmark-live.json"
OPS_JSON="/tmp/phase14-operations.json"
HEALTH_JSON="/tmp/phase14-provider-health.json"
RESOURCE_JSON="/tmp/phase14-resource-snapshot.json"
RETENTION_JSON="/tmp/phase14-retention-plan.json"
DASH_OPS_JSON="/tmp/phase14-dashboard-operations.json"
DASH_HEALTH_JSON="/tmp/phase14-dashboard-provider-health.json"
DASH_RESOURCE_JSON="/tmp/phase14-dashboard-resource-snapshot.json"
DASH_RETENTION_JSON="/tmp/phase14-dashboard-retention-plan.json"
SMART_REJECT_JSON="/tmp/phase14-smart-search-reject.json"
CTX="/tmp/dap-phase14-dashboard-runtime"
MIN_BURNIN_RUNS=2
MAX_BURNIN_RUNS=3
MIN_BURNIN_OPERATIONS_EVENTS=5

if [[ -z "$EXPECTED_HEAD" ]]; then
  echo "usage|$0 <expected-head-sha>"
  exit 2
fi

cleanup_ephemeral() {
  rm -f \
    "$OPS_JSON" \
    "$HEALTH_JSON" \
    "$RESOURCE_JSON" \
    "$RETENTION_JSON" \
    "$DASH_OPS_JSON" \
    "$DASH_HEALTH_JSON" \
    "$DASH_RESOURCE_JSON" \
    "$DASH_RETENTION_JSON" \
    "$SMART_REJECT_JSON"
  rm -rf "$CTX"
}
trap cleanup_ephemeral EXIT

count_table_rows() {
  local table="$1"
  local exists
  exists="$(sqlite3 "$TRUTH_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='$table';")"
  if [[ "$exists" == "1" ]]; then
    sqlite3 "$TRUTH_DB" "SELECT COUNT(*) FROM $table;"
  else
    echo "0"
  fi
}

write_state() {
  EXPECTED_HEAD_ENV="$EXPECTED_HEAD" \
  BASE_TASKS_ENV="$BASE_TASKS" \
  BASE_EVIDENCE_ENV="$BASE_EVIDENCE" \
  BASE_OPS_ENV="$BASE_OPS" \
  ACTIVATED_PID_ENV="$ACTIVATED_PID" \
  RUN_COUNT_ENV="$RUN_COUNT" \
  RUN1_ENV="$RUN1" \
  RUN2_ENV="$RUN2" \
  RUN3_ENV="$RUN3" \
  LAST_TASKS_ENV="$LAST_TASKS" \
  LAST_EVIDENCE_ENV="$LAST_EVIDENCE" \
  LAST_OPS_ENV="$LAST_OPS" \
  BURNIN_COMPLETE_ENV="$BURNIN_COMPLETE" \
  "$PY" - "$STATE" <<'PY'
import json
import os
import sys

payload = {
    "expected_head": os.environ["EXPECTED_HEAD_ENV"],
    "base_tasks": int(os.environ["BASE_TASKS_ENV"]),
    "base_evidence": int(os.environ["BASE_EVIDENCE_ENV"]),
    "base_ops": int(os.environ["BASE_OPS_ENV"]),
    "activated_pid": int(os.environ["ACTIVATED_PID_ENV"]),
    "run_count": int(os.environ["RUN_COUNT_ENV"]),
    "run_ids": [
        value
        for value in (
            os.environ["RUN1_ENV"],
            os.environ["RUN2_ENV"],
            os.environ["RUN3_ENV"],
        )
        if value
    ],
    "last_tasks": int(os.environ["LAST_TASKS_ENV"]),
    "last_evidence": int(os.environ["LAST_EVIDENCE_ENV"]),
    "last_ops": int(os.environ["LAST_OPS_ENV"]),
    "burnin_complete": os.environ["BURNIN_COMPLETE_ENV"].lower() == "true",
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

load_state() {
  mapfile -t VALUES < <(
    "$PY" - "$STATE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
run_ids = list(payload.get("run_ids") or [])
while len(run_ids) < 3:
    run_ids.append("")
for value in (
    payload["expected_head"],
    payload["base_tasks"],
    payload["base_evidence"],
    payload["base_ops"],
    payload["activated_pid"],
    payload["run_count"],
    run_ids[0],
    run_ids[1],
    run_ids[2],
    payload["last_tasks"],
    payload["last_evidence"],
    payload["last_ops"],
    str(bool(payload.get("burnin_complete"))).lower(),
):
    print(value)
PY
  )

  STATE_HEAD="${VALUES[0]}"
  BASE_TASKS="${VALUES[1]}"
  BASE_EVIDENCE="${VALUES[2]}"
  BASE_OPS="${VALUES[3]}"
  ACTIVATED_PID="${VALUES[4]}"
  RUN_COUNT="${VALUES[5]}"
  RUN1="${VALUES[6]}"
  RUN2="${VALUES[7]}"
  RUN3="${VALUES[8]}"
  LAST_TASKS="${VALUES[9]}"
  LAST_EVIDENCE="${VALUES[10]}"
  LAST_OPS="${VALUES[11]}"
  BURNIN_COMPLETE="${VALUES[12]}"
}

verify_run_task() {
  local run_id="$1"
  "$PY" - "$TRUTH_DB" "$run_id" <<'PY'
import json
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
connection.row_factory = sqlite3.Row
rows = connection.execute(
    """
    SELECT task_id, status, requested_by, assigned_agent_ids_json, source_run_id
    FROM task_ledger
    WHERE source_run_id = ?
    """,
    (sys.argv[2],),
).fetchall()
connection.close()
assert len(rows) == 1, rows
row = rows[0]
assigned = json.loads(row["assigned_agent_ids_json"])
assert row["status"] == "completed", dict(row)
assert row["requested_by"] == "agent-api", dict(row)
assert assigned == ["research-agent"], assigned
assert row["source_run_id"] == sys.argv[2], dict(row)
print(f"research_task_id|{row['task_id']}")
print(f"research_task_status|{row['status']}")
print("research_task_assigned_agent|research-agent")
print(f"research_task_source_run_id|{row['source_run_id']}")
PY
}

run_burnin_search() {
  local index="$1"
  local query objective response http_code

  case "$index" in
    1)
      query="IANA example domains RFC 2606"
      objective="Using current public sources, briefly explain why IANA example domains exist and cite the retrieved evidence."
      ;;
    2)
      query="robots exclusion protocol RFC 9309"
      objective="Using current public sources, briefly explain what RFC 9309 standardizes and cite the retrieved evidence."
      ;;
    3)
      query="HTTP status code 418 RFC semantics"
      objective="Using current public sources, briefly explain the standards status of HTTP status code 418 and cite the retrieved evidence."
      ;;
    *)
      echo "burnin_index|INVALID"
      exit 1
      ;;
  esac

  response="/tmp/phase14-burnin-run-${index}.json"
  rm -f "$response"

  PAYLOAD="$($PY - "$objective" "$query" <<'PY'
import json
import sys
print(json.dumps({
    "mode": "manual",
    "agent_id": "research-agent",
    "objective": sys.argv[1],
    "research_search_query": sys.argv[2],
    "provider": "ollama",
    "model": "qwen3:1.7b",
    "temperature": 0.1,
    "max_tokens": 320,
    "max_steps": 4,
    "retrieval_limit": 5,
    "score_threshold": 0.4,
}))
PY
)"

  http_code="$(curl -sS --max-time 420 \
    -o "$response" \
    -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST http://127.0.0.1:8002/api/v1/agents/run \
    --data-binary "$PAYLOAD")"
  echo "burnin_run_http|$index|$http_code"
  [[ "$http_code" == "200" ]] || { cat "$response"; exit 1; }

  mapfile -t RUN_META < <(
    "$PY" - "$response" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
assert payload.get("status") == "completed", payload
assert payload.get("agent_id") == "research-agent", payload
steps = payload.get("steps") or []
search_steps = [
    step
    for step in steps
    if step.get("title") == "Discover and retrieve public-web evidence via local SearXNG"
]
assert len(search_steps) == 1, search_steps
step = search_steps[0]
assert step.get("success") is True, step
out = step.get("output") or {}
assert out.get("provider_id") == "searxng-local-v1", out
selected = out.get("selected_urls") or []
families = out.get("selected_source_families") or []
scores = out.get("selected_quality_scores") or []
assert 0 < len(selected) <= 3, selected
assert len(families) == len(selected), (families, selected)
assert len(scores) == len(selected), (scores, selected)
assert out.get("source_selection_policy_id") == "dap-source-family-diversity-v1", out
assert int(out.get("unique_source_family_count", 0)) >= 1, out
assert out.get("selection_quality_is_factual_credibility") is False, out
assert out.get("provider_snippets_are_evidence") is False, out
assert out.get("provider_snippets_exposed_to_model") is False, out
assert out.get("provider_titles_exposed_to_model") is False, out
assert out.get("search_candidates_are_retrieval_evidence") is False, out
assert out.get("candidate_urls_require_full_dap_retrieval") is True, out
assert out.get("generic_network_client_exposed") is False, out
assert out.get("remote_scope_expansion_allowed") is False, out
retrieval_sources = out.get("retrieval_sources") or []
assert len(retrieval_sources) == len(selected), (retrieval_sources, selected)
for source in retrieval_sources:
    assert "model_context" not in source, source
    assert int(source.get("attempt_count", 0)) in (1, 2), source
    assert int(source.get("transient_retry_count", 0)) in (0, 1), source
    assert float(source.get("duration_ms", -1)) >= 0, source
public_sources = [
    source
    for source in (payload.get("sources") or [])
    if source.get("source_kind") == "public_web"
]
assert public_sources, payload.get("sources")
assert all(source.get("evidence_id") for source in public_sources), public_sources
assert (payload.get("answer") or "").strip(), payload
print(payload["run_id"])
print(len(selected))
print(len(public_sources))
print(out.get("unique_source_family_count"))
print(out.get("duplicate_family_fallback_count", 0))
PY
  )

  local run_id selected_count public_count family_count fallback_count
  run_id="${RUN_META[0]}"
  selected_count="${RUN_META[1]}"
  public_count="${RUN_META[2]}"
  family_count="${RUN_META[3]}"
  fallback_count="${RUN_META[4]}"

  echo "burnin_run_id|$index|$run_id"
  echo "burnin_selected_url_count|$index|$selected_count"
  echo "burnin_public_source_count|$index|$public_count"
  echo "burnin_unique_source_family_count|$index|$family_count"
  echo "burnin_duplicate_family_fallback_count|$index|$fallback_count"

  local tasks_now evidence_now ops_now task_delta evidence_delta ops_delta
  tasks_now="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
  evidence_now="$(count_table_rows research_retrieval_evidence)"
  ops_now="$(count_table_rows research_operations_events)"
  task_delta="$((tasks_now - LAST_TASKS))"
  evidence_delta="$((evidence_now - LAST_EVIDENCE))"
  ops_delta="$((ops_now - LAST_OPS))"

  echo "burnin_task_delta|$index|$task_delta"
  echo "burnin_evidence_delta|$index|$evidence_delta"
  echo "burnin_operations_delta|$index|$ops_delta"

  [[ "$task_delta" -eq 1 ]] || exit 1
  [[ "$evidence_delta" -eq "$selected_count" ]] || exit 1
  [[ "$ops_delta" -eq "$selected_count" ]] || exit 1
  verify_run_task "$run_id"

  RUN_COUNT="$index"
  case "$index" in
    1) RUN1="$run_id" ;;
    2) RUN2="$run_id" ;;
    3) RUN3="$run_id" ;;
  esac
  LAST_TASKS="$tasks_now"
  LAST_EVIDENCE="$evidence_now"
  LAST_OPS="$ops_now"
  write_state
  echo "burnin_state_saved|run_$index"
}

echo "============================================================"
echo " PHASE 14 — RESEARCH OPERATIONS RELIABILITY LIVE BURN-IN"
echo "============================================================"

cd "$REPO"

echo
echo "=== 1. EXACT SOURCE + PRODUCTION BASELINE ==="
BRANCH="$(git branch --show-current)"
HEAD_NOW="$(git rev-parse HEAD)"
SOURCE_STATE="clean"
[[ -z "$(git status --porcelain)" ]] || SOURCE_STATE="DIRTY"

echo "branch|$BRANCH"
echo "HEAD|$HEAD_NOW"
echo "source_status|$SOURCE_STATE"
[[ "$BRANCH" == "phase14/research-operations-reliability" ]] || exit 1
[[ "$HEAD_NOW" == "$EXPECTED_HEAD" ]] || exit 1
[[ "$SOURCE_STATE" == "clean" ]] || exit 1
[[ -x "$PY" ]] || { echo "backend_python|MISSING_STOP"; exit 1; }
[[ -f "$TRUTH_DB" ]] || { echo "truth_db|MISSING_STOP"; exit 1; }

GUARDIAN_NOW="$(systemctl is-active dap-guardian-broker.service || true)"
TELEGRAM_NOW="$(grep '^DAP_TELEGRAM_APPROVALS_ENABLED=' /home/dipen/dap/config/dap-backend.env || true)"
DASHBOARD_NOW="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' dap-dashboard)"
SEARX_STATE_NOW="$(docker inspect -f '{{.State.Status}}' dap-searxng)"
SEARX_BINDING_NOW="$(docker port dap-searxng 8080/tcp | tr -d '\r')"
BACKEND_NOW="$(systemctl is-active dap-backend.service || true)"

echo "backend_baseline|$BACKEND_NOW"
echo "guardian_baseline|$GUARDIAN_NOW"
echo "telegram_baseline|$TELEGRAM_NOW"
echo "dashboard_baseline|$DASHBOARD_NOW"
echo "searxng_state_baseline|$SEARX_STATE_NOW"
echo "searxng_binding_baseline|$SEARX_BINDING_NOW"
[[ "$BACKEND_NOW" == "active" ]] || exit 1
[[ "$GUARDIAN_NOW" == "inactive" ]] || exit 1
[[ "$TELEGRAM_NOW" == "DAP_TELEGRAM_APPROVALS_ENABLED=false" ]] || exit 1
[[ "$DASHBOARD_NOW" == "healthy" ]] || exit 1
[[ "$SEARX_STATE_NOW" == "running" ]] || exit 1
[[ "$SEARX_BINDING_NOW" == "127.0.0.1:8888" ]] || exit 1
curl -fsS --max-time 10 http://127.0.0.1:8888/ >/dev/null

echo "source_and_runtime_baseline|PASS"

RUN1=""
RUN2=""
RUN3=""
RUN_COUNT=0
BURNIN_COMPLETE="false"

if [[ -f "$STATE" ]]; then
  load_state
  if [[ "$STATE_HEAD" != "$EXPECTED_HEAD" ]]; then
    STALE_STATE="${STATE}.stale.$(date -u +%Y%m%dT%H%M%SZ)"
    mv "$STATE" "$STALE_STATE"
    echo "stale_state_moved|$STALE_STATE"
    RUN1=""
    RUN2=""
    RUN3=""
    RUN_COUNT=0
    BURNIN_COMPLETE="false"
  else
    echo "phase14_resume_state|present"
    echo "phase14_resume_run_count|$RUN_COUNT"
    echo "phase14_resume_burnin_complete|$BURNIN_COMPLETE"
    CURRENT_TASKS="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
    CURRENT_EVIDENCE="$(count_table_rows research_retrieval_evidence)"
    CURRENT_OPS="$(count_table_rows research_operations_events)"
    CURRENT_PID="$(systemctl show dap-backend.service -p MainPID --value)"
    [[ "$CURRENT_TASKS" == "$LAST_TASKS" ]] || { echo "resume_task_count|MISMATCH_STOP"; exit 1; }
    [[ "$CURRENT_EVIDENCE" == "$LAST_EVIDENCE" ]] || { echo "resume_evidence_count|MISMATCH_STOP"; exit 1; }
    [[ "$CURRENT_OPS" == "$LAST_OPS" ]] || { echo "resume_operations_count|MISMATCH_STOP"; exit 1; }
    [[ "$CURRENT_PID" == "$ACTIVATED_PID" ]] || { echo "resume_backend_pid|MISMATCH_STOP"; exit 1; }
    echo "phase14_resume_state|VALID"
  fi
fi

if [[ ! -f "$STATE" ]]; then
  BASE_TASKS="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
  BASE_EVIDENCE="$(count_table_rows research_retrieval_evidence)"
  BASE_OPS="$(count_table_rows research_operations_events)"
  PID_BEFORE="$(systemctl show dap-backend.service -p MainPID --value)"
  echo "task_ledger_before|$BASE_TASKS"
  echo "research_evidence_before|$BASE_EVIDENCE"
  echo "research_operations_before|$BASE_OPS"
  echo "backend_pid_before|$PID_BEFORE"

  echo
echo "=== 2. CONTROLLED BACKEND LOAD ==="
  sudo systemctl restart dap-backend.service
  BACKEND_READY=0
  for ATTEMPT in $(seq 1 30); do
    if curl -fsS --max-time 3 http://127.0.0.1:8002/health >/dev/null 2>&1; then
      BACKEND_READY=1
      echo "backend_ready_attempt|$ATTEMPT"
      break
    fi
    sleep 2
  done
  if [[ "$BACKEND_READY" -ne 1 ]]; then
    echo "backend_phase14_load|FAIL"
    sudo journalctl -u dap-backend.service -n 100 --no-pager
    exit 1
  fi
  ACTIVATED_PID="$(systemctl show dap-backend.service -p MainPID --value)"
  [[ "$ACTIVATED_PID" =~ ^[1-9][0-9]*$ ]] || exit 1
  [[ "$ACTIVATED_PID" != "$PID_BEFORE" ]] || exit 1
  LAST_TASKS="$BASE_TASKS"
  LAST_EVIDENCE="$BASE_EVIDENCE"
  LAST_OPS="$BASE_OPS"
  write_state
  echo "backend_phase14_load|PASS"
  echo "backend_pid_activated|$ACTIVATED_PID"
else
  echo
echo "=== 2. CONTROLLED BACKEND LOAD ==="
  echo "backend_phase14_load|RESUME_ALREADY_LOADED"
  [[ "$(systemctl is-active dap-backend.service || true)" == "active" ]] || exit 1
fi

echo
echo "=== 3. READ-ONLY OPERATIONS API + AUTHORITY NEGATIVE PROOF ==="
for endpoint in \
  operations \
  operations/provider-health \
  operations/resource-snapshot \
  operations/retention-plan; do
  code="$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "http://127.0.0.1:8002/api/v1/research/$endpoint")"
  echo "backend_get|$endpoint|$code"
  [[ "$code" == "200" ]] || exit 1
  post_code="$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8002/api/v1/research/$endpoint")"
  echo "backend_post|$endpoint|$post_code"
  [[ "$post_code" == "405" ]] || exit 1
done

if [[ "$RUN_COUNT" -eq 0 ]]; then
  NEG_TASKS_BEFORE="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
  NEG_EVIDENCE_BEFORE="$(count_table_rows research_retrieval_evidence)"
  NEG_OPS_BEFORE="$(count_table_rows research_operations_events)"
  SMART_HTTP="$(curl -sS --max-time 60 \
    -o "$SMART_REJECT_JSON" \
    -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST http://127.0.0.1:8002/api/v1/agents/run \
    --data-binary '{"mode":"smart","objective":"Research IANA example domains using current public sources.","research_search_query":"IANA example domains RFC 2606","provider":"ollama","model":"qwen3:1.7b"}')"
  echo "smart_research_http|$SMART_HTTP"
  [[ "$SMART_HTTP" == "400" ]] || { cat "$SMART_REJECT_JSON"; exit 1; }
  [[ "$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')" == "$NEG_TASKS_BEFORE" ]] || exit 1
  [[ "$(count_table_rows research_retrieval_evidence)" == "$NEG_EVIDENCE_BEFORE" ]] || exit 1
  [[ "$(count_table_rows research_operations_events)" == "$NEG_OPS_BEFORE" ]] || exit 1
  echo "smart_routing_research_disabled|PASS"
else
  echo "smart_routing_research_disabled|PREVIOUSLY_PROVEN_IN_THIS_RUN"
fi

echo
echo "=== 4. MANUAL RESEARCH BURN-IN ==="
if [[ "$BURNIN_COMPLETE" != "true" ]]; then
  if [[ "$RUN_COUNT" -lt 1 ]]; then
    run_burnin_search 1
  fi
  if [[ "$RUN_COUNT" -lt "$MIN_BURNIN_RUNS" ]]; then
    run_burnin_search 2
  fi

  BURNIN_OPS_DELTA="$((LAST_OPS - BASE_OPS))"
  if [[ "$BURNIN_OPS_DELTA" -lt "$MIN_BURNIN_OPERATIONS_EVENTS" && "$RUN_COUNT" -lt "$MAX_BURNIN_RUNS" ]]; then
    echo "burnin_operations_after_two|$BURNIN_OPS_DELTA"
    echo "burnin_third_run|required"
    run_burnin_search 3
  fi

  BURNIN_OPS_DELTA="$((LAST_OPS - BASE_OPS))"
  BURNIN_TASK_DELTA="$((LAST_TASKS - BASE_TASKS))"
  BURNIN_EVIDENCE_DELTA="$((LAST_EVIDENCE - BASE_EVIDENCE))"
  echo "burnin_run_count|$RUN_COUNT"
  echo "burnin_task_delta_total|$BURNIN_TASK_DELTA"
  echo "burnin_evidence_delta_total|$BURNIN_EVIDENCE_DELTA"
  echo "burnin_operations_delta_total|$BURNIN_OPS_DELTA"
  [[ "$RUN_COUNT" -ge "$MIN_BURNIN_RUNS" ]] || exit 1
  [[ "$RUN_COUNT" -le "$MAX_BURNIN_RUNS" ]] || exit 1
  [[ "$BURNIN_TASK_DELTA" -eq "$RUN_COUNT" ]] || exit 1
  [[ "$BURNIN_EVIDENCE_DELTA" -eq "$BURNIN_OPS_DELTA" ]] || exit 1
  [[ "$BURNIN_OPS_DELTA" -ge "$MIN_BURNIN_OPERATIONS_EVENTS" ]] || {
    echo "burnin_sample|INSUFFICIENT_STOP"
    exit 1
  }
  BURNIN_COMPLETE="true"
  write_state
else
  echo "manual_research_burnin|RESUME_ALREADY_COMPLETE"
fi

echo "manual_research_burnin|PASS"
for run_id in "$RUN1" "$RUN2" "$RUN3"; do
  if [[ -n "$run_id" ]]; then
    verify_run_task "$run_id"
  fi
done

echo
echo "=== 5. LIVE OPERATIONS / RETENTION / HEALTH / RESOURCE PROOF ==="
curl -fsS --max-time 30 http://127.0.0.1:8002/api/v1/research/operations -o "$OPS_JSON"
curl -fsS --max-time 30 http://127.0.0.1:8002/api/v1/research/operations/provider-health -o "$HEALTH_JSON"
curl -fsS --max-time 30 http://127.0.0.1:8002/api/v1/research/operations/resource-snapshot -o "$RESOURCE_JSON"
curl -fsS --max-time 30 http://127.0.0.1:8002/api/v1/research/operations/retention-plan -o "$RETENTION_JSON"

mapfile -t LIVE_META < <(
  "$PY" - "$OPS_JSON" "$HEALTH_JSON" "$RESOURCE_JSON" "$RETENTION_JSON" "$LAST_EVIDENCE" "$ACTIVATED_PID" "$((LAST_OPS - BASE_OPS))" <<'PY'
import json
import sys

ops=json.load(open(sys.argv[1], encoding='utf-8'))
health=json.load(open(sys.argv[2], encoding='utf-8'))
resources=json.load(open(sys.argv[3], encoding='utf-8'))
retention=json.load(open(sys.argv[4], encoding='utf-8'))
expected_evidence=int(sys.argv[5])
expected_pid=int(sys.argv[6])
minimum_new_events=int(sys.argv[7])

assert ops.get('evidence_total') == expected_evidence, ops.get('evidence_total')
assert int(ops.get('window_event_count', 0)) >= minimum_new_events, ops
assert ops.get('p50_source_duration_ms') is not None, ops
assert ops.get('p95_source_duration_ms') is not None, ops
assert int(ops.get('retrieval_attempt_count', 0)) >= minimum_new_events, ops
assert isinstance(ops.get('transient_retry_count'), int), ops
assert isinstance(ops.get('recovered_after_retry_count'), int), ops
assert int(ops.get('unique_source_family_count', 0)) >= 1, ops
assert isinstance(ops.get('duplicate_content_group_count'), int), ops
assert isinstance(ops.get('errors'), list), ops
assert ops.get('provenance_quality'), ops
assert ops.get('average_provenance_quality_score') is not None, ops
assert ops.get('factual_correctness_measured') is False, ops
assert ops.get('workspace_mode') == 'read_only', ops
assert ops.get('network_authority_granted') is False, ops
assert ops.get('mutation_authority_granted') is False, ops

assert health.get('provider_id') == 'searxng-local-v1', health
assert health.get('endpoint') == 'http://127.0.0.1:8888/', health
assert health.get('healthy') is True, health
assert health.get('status_code') == 200, health
assert health.get('provider_is_local_only') is True, health
assert health.get('loopback_contract_valid') is True, health
assert health.get('service_control_authority_granted') is False, health
assert health.get('credentials_used') is False, health

assert resources.get('process_id') == expected_pid, resources
assert resources.get('scope') == 'dap-backend-process', resources
assert resources.get('research_specific_attribution') is False, resources
assert resources.get('read_only') is True, resources
assert resources.get('service_control_authority_granted') is False, resources
assert float(resources.get('process_rss_mib', -1)) >= 0, resources

assert retention.get('mode') == 'dry_run', retention
assert retention.get('evidence_deleted') is False, retention
assert retention.get('evidence_mutated') is False, retention
policy=retention.get('policy') or {}
assert policy.get('default_preserve_all') is True, policy
assert policy.get('automatic_deletion_enabled') is False, policy
assert policy.get('automatic_archive_enabled') is False, policy
assert policy.get('owner_action_required_for_future_cleanup') is True, policy
assert retention.get('total_evidence') == expected_evidence, retention

print(ops.get('reliability_posture'))
print(ops.get('success_rate'))
print(ops.get('failure_rate'))
print(ops.get('p50_source_duration_ms'))
print(ops.get('p95_source_duration_ms'))
print(ops.get('unique_source_family_rate'))
print(ops.get('duplicate_content_rate'))
print(ops.get('transient_retry_count'))
print(ops.get('recovered_after_retry_count'))
print(ops.get('average_provenance_quality_score'))
print(health.get('latency_ms'))
print(resources.get('process_rss_mib'))
print(retention.get('future_archive_candidate_count'))
PY
)

echo "reliability_posture|${LIVE_META[0]}"
echo "success_rate|${LIVE_META[1]}"
echo "failure_rate|${LIVE_META[2]}"
echo "retrieval_p50_ms|${LIVE_META[3]}"
echo "retrieval_p95_ms|${LIVE_META[4]}"
echo "unique_source_family_rate|${LIVE_META[5]}"
echo "duplicate_content_rate|${LIVE_META[6]}"
echo "transient_retry_count|${LIVE_META[7]}"
echo "recovered_after_retry_count|${LIVE_META[8]}"
echo "provenance_quality_average|${LIVE_META[9]}"
echo "searxng_health_latency_ms|${LIVE_META[10]}"
echo "backend_rss_mib|${LIVE_META[11]}"
echo "future_archive_candidate_count|${LIVE_META[12]}"
echo "live_operations_visibility|PASS"

echo
echo "=== 6. DETERMINISTIC RELIABILITY BENCHMARK ON ACER ==="
cd "$BACKEND"
rm -f "$BENCHMARK_REPORT"
"$PY" -m gateway.research_reliability_benchmark \
  --source-commit "$EXPECTED_HEAD" \
  --output "$BENCHMARK_REPORT"
"$PY" - "$BENCHMARK_REPORT" "$EXPECTED_HEAD" <<'PY'
import json
import sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
assert p.get('benchmark_version') == 'phase14i.1', p
assert p.get('source_commit') == sys.argv[2], p
assert p.get('case_count') == 5, p
assert p.get('cases_passed') == 5, p
assert p.get('completion_rate') == 1.0, p
assert p.get('all_cases_passed') is True, p
assert p.get('smart_routing_research_activated') is False, p
assert p.get('network_authority_expanded') is False, p
assert p.get('destructive_retention_action_performed') is False, p
assert len(p.get('report_sha256', '')) == 64, p
for key in ('resource_snapshot_before', 'resource_snapshot_after'):
    snapshot=p.get(key) or {}
    assert snapshot.get('scope') == 'dap-backend-process', snapshot
    assert snapshot.get('research_specific_attribution') is False, snapshot
    assert snapshot.get('service_control_authority_granted') is False, snapshot
print(f"phase14_live_benchmark_sha256|{p['report_sha256']}")
PY
echo "phase14_live_reliability_benchmark|PASS"

echo
echo "=== 7. OFFLINE DASHBOARD BUILD ==="
cd "$REPO"
DASHBOARD_ID_BEFORE="$(docker inspect -f '{{.Id}}' dap-dashboard)"
DASHBOARD_IMAGE_ID_BEFORE="$(docker inspect -f '{{.Image}}' dap-dashboard)"
DASHBOARD_IMAGE_REF="$(docker inspect -f '{{.Config.Image}}' dap-dashboard)"
ROLLBACK_TAG="dap-dashboard-phase14-rollback:$(date -u +%Y%m%dT%H%M%SZ)"
docker tag "$DASHBOARD_IMAGE_ID_BEFORE" "$ROLLBACK_TAG"
echo "rollback_image|$ROLLBACK_TAG"

if [[ -e "$DASH/.next" ]]; then
  if rm -rf "$DASH/.next" 2>/dev/null; then
    echo "dashboard_build_tree_cleanup|user"
  else
    echo "dashboard_build_tree_cleanup|sudo_fixed_path"
    sudo rm -rf -- "$DASH/.next"
  fi
fi
[[ ! -e "$DASH/.next" ]] || exit 1
[[ -d "$DASH/node_modules/next" ]] || { echo "local_node_modules|MISSING_STOP"; exit 1; }
docker image inspect node:24-alpine >/dev/null 2>&1 || { echo "node_base_image|MISSING_STOP"; exit 1; }

docker run --rm --network none \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -e NEXT_TELEMETRY_DISABLED=1 \
  -v "$DASH:/app" -w /app node:24-alpine \
  sh -lc 'npm run build'

echo "offline_dashboard_app_build|PASS"
[[ -f "$DASH/.next/standalone/server.js" ]] || exit 1
[[ -d "$DASH/.next/static" ]] || exit 1
[[ -d "$DASH/public" ]] || exit 1
cd "$REPO"
[[ -z "$(git status --porcelain)" ]] || { echo "source_after_dashboard_build|DIRTY_STOP"; git status --short; exit 1; }

rm -rf "$CTX"
mkdir -p "$CTX/.next"
cp -a "$DASH/.next/standalone/." "$CTX/"
cp -a "$DASH/.next/static" "$CTX/.next/static"
cp -a "$DASH/public" "$CTX/public"
cat > "$CTX/Dockerfile" <<'EOF'
FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs
COPY --chown=nextjs:nodejs . .
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
EOF

docker build --pull=false --network=none -t "$DASHBOARD_IMAGE_REF" "$CTX"
NEW_IMAGE_ID="$(docker image inspect -f '{{.Id}}' "$DASHBOARD_IMAGE_REF")"
echo "dashboard_new_image_id|$NEW_IMAGE_ID"
[[ "$NEW_IMAGE_ID" != "$DASHBOARD_IMAGE_ID_BEFORE" ]] || exit 1
echo "dashboard_runtime_image|PASS"

echo
echo "=== 8. RECREATE ONLY DASHBOARD + OWNER VISIBILITY ==="
cd "$COMPOSE"
docker compose up -d --no-deps --no-build --force-recreate dashboard
DASH_READY=0
for ATTEMPT in $(seq 1 45); do
  STATUS="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' dap-dashboard 2>/dev/null || true)"
  echo "dashboard_health_attempt|$ATTEMPT|$STATUS"
  if [[ "$STATUS" == "healthy" ]]; then
    DASH_READY=1
    break
  fi
  sleep 2
done
if [[ "$DASH_READY" -ne 1 ]]; then
  echo "dashboard_health|FAIL"
  docker logs --tail=150 dap-dashboard
  docker tag "$ROLLBACK_TAG" "$DASHBOARD_IMAGE_REF"
  docker compose up -d --no-deps --no-build --force-recreate dashboard || true
  echo "dashboard_rollback_attempted|true"
  exit 1
fi

echo "dashboard_health|PASS"
NEW_DASHBOARD_ID="$(docker inspect -f '{{.Id}}' dap-dashboard)"
RUNNING_DASHBOARD_IMAGE="$(docker inspect -f '{{.Image}}' dap-dashboard)"
echo "dashboard_container_before|$DASHBOARD_ID_BEFORE"
echo "dashboard_container_after|$NEW_DASHBOARD_ID"
echo "dashboard_running_image|$RUNNING_DASHBOARD_IMAGE"
[[ "$NEW_DASHBOARD_ID" != "$DASHBOARD_ID_BEFORE" ]] || exit 1
[[ "$RUNNING_DASHBOARD_IMAGE" == "$NEW_IMAGE_ID" ]] || exit 1

RESEARCH_HTTP="$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' http://127.0.0.1/research)"
OPS_PAGE="/tmp/phase14-research-operations-page.html"
OPS_PAGE_HTTP="$(curl -sS --max-time 20 -o "$OPS_PAGE" -w '%{http_code}' http://127.0.0.1/research/operations)"
echo "research_page_http|$RESEARCH_HTTP"
echo "research_operations_page_http|$OPS_PAGE_HTTP"
[[ "$RESEARCH_HTTP" == "200" ]] || exit 1
[[ "$OPS_PAGE_HTTP" == "200" ]] || exit 1
grep -q 'Reliability and evidence health' "$OPS_PAGE" || { echo "research_operations_page_marker|FAIL"; exit 1; }
echo "research_operations_page_marker|PASS"

curl -fsS --max-time 30 http://127.0.0.1/api/research/operations -o "$DASH_OPS_JSON"
curl -fsS --max-time 30 http://127.0.0.1/api/research/operations/provider-health -o "$DASH_HEALTH_JSON"
curl -fsS --max-time 30 http://127.0.0.1/api/research/operations/resource-snapshot -o "$DASH_RESOURCE_JSON"
curl -fsS --max-time 30 http://127.0.0.1/api/research/operations/retention-plan -o "$DASH_RETENTION_JSON"

"$PY" - "$DASH_OPS_JSON" "$DASH_HEALTH_JSON" "$DASH_RESOURCE_JSON" "$DASH_RETENTION_JSON" "$LAST_EVIDENCE" "$ACTIVATED_PID" <<'PY'
import json
import sys
ops=json.load(open(sys.argv[1], encoding='utf-8'))
health=json.load(open(sys.argv[2], encoding='utf-8'))
resources=json.load(open(sys.argv[3], encoding='utf-8'))
retention=json.load(open(sys.argv[4], encoding='utf-8'))
assert ops.get('evidence_total') == int(sys.argv[5]), ops
assert ops.get('workspace_mode') == 'read_only', ops
assert ops.get('network_authority_granted') is False, ops
assert ops.get('mutation_authority_granted') is False, ops
assert health.get('healthy') is True, health
assert health.get('service_control_authority_granted') is False, health
assert resources.get('process_id') == int(sys.argv[6]), resources
assert resources.get('read_only') is True, resources
assert resources.get('service_control_authority_granted') is False, resources
assert retention.get('mode') == 'dry_run', retention
assert retention.get('evidence_deleted') is False, retention
assert retention.get('evidence_mutated') is False, retention
print('dashboard_operations_models|PASS')
PY

for endpoint in \
  operations \
  operations/provider-health \
  operations/resource-snapshot \
  operations/retention-plan; do
  post_code="$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1/api/research/$endpoint")"
  echo "dashboard_post|$endpoint|$post_code"
  [[ "$post_code" == "405" ]] || exit 1
done

echo "owner_operations_visibility|PASS"

echo
echo "=== 9. FINAL PRODUCTION SAFETY ==="
cd "$REPO"
TASKS_FINAL="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
EVIDENCE_FINAL="$(count_table_rows research_retrieval_evidence)"
OPS_FINAL="$(count_table_rows research_operations_events)"
PID_FINAL="$(systemctl show dap-backend.service -p MainPID --value)"
BACKEND_FINAL="$(systemctl is-active dap-backend.service || true)"
GUARDIAN_FINAL="$(systemctl is-active dap-guardian-broker.service || true)"
TELEGRAM_FINAL="$(grep '^DAP_TELEGRAM_APPROVALS_ENABLED=' /home/dipen/dap/config/dap-backend.env || true)"
DASHBOARD_FINAL="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' dap-dashboard)"
SEARX_STATE_FINAL="$(docker inspect -f '{{.State.Status}}' dap-searxng)"
SEARX_BINDING_FINAL="$(docker port dap-searxng 8080/tcp | tr -d '\r')"
HEAD_FINAL="$(git rev-parse HEAD)"
SOURCE_FINAL="clean"
[[ -z "$(git status --porcelain)" ]] || SOURCE_FINAL="DIRTY"

echo "task_ledger_final|$TASKS_FINAL"
echo "research_evidence_final|$EVIDENCE_FINAL"
echo "research_operations_final|$OPS_FINAL"
echo "backend_pid_final|$PID_FINAL"
echo "backend_final|$BACKEND_FINAL"
echo "guardian_final|$GUARDIAN_FINAL"
echo "telegram_final|$TELEGRAM_FINAL"
echo "dashboard_final|$DASHBOARD_FINAL"
echo "searxng_state_final|$SEARX_STATE_FINAL"
echo "searxng_binding_final|$SEARX_BINDING_FINAL"
echo "HEAD_final|$HEAD_FINAL"
echo "source_final|$SOURCE_FINAL"

[[ "$TASKS_FINAL" == "$LAST_TASKS" ]] || exit 1
[[ "$EVIDENCE_FINAL" == "$LAST_EVIDENCE" ]] || exit 1
[[ "$OPS_FINAL" == "$LAST_OPS" ]] || exit 1
[[ "$PID_FINAL" == "$ACTIVATED_PID" ]] || exit 1
[[ "$BACKEND_FINAL" == "active" ]] || exit 1
[[ "$GUARDIAN_FINAL" == "inactive" ]] || exit 1
[[ "$TELEGRAM_FINAL" == "DAP_TELEGRAM_APPROVALS_ENABLED=false" ]] || exit 1
[[ "$DASHBOARD_FINAL" == "healthy" ]] || exit 1
[[ "$SEARX_STATE_FINAL" == "running" ]] || exit 1
[[ "$SEARX_BINDING_FINAL" == "127.0.0.1:8888" ]] || exit 1
[[ "$HEAD_FINAL" == "$EXPECTED_HEAD" ]] || exit 1
[[ "$SOURCE_FINAL" == "clean" ]] || exit 1
[[ "$BURNIN_COMPLETE" == "true" ]] || exit 1

for run_id in "$RUN1" "$RUN2" "$RUN3"; do
  if [[ -n "$run_id" ]]; then
    verify_run_task "$run_id"
  fi
done

echo
echo "PHASE14_RESEARCH_OPERATIONS_LIVE_BURNIN|PASS"
echo "PHASE14_OWNER_OPERATIONS_VISIBILITY|PASS"
echo "PHASE14_AUTHORITY_BOUNDARY|PASS"
echo "phase14_burnin_run_count|$RUN_COUNT"
echo "phase14_burnin_evidence_delta|$((LAST_EVIDENCE - BASE_EVIDENCE))"
echo "phase14_burnin_operations_delta|$((LAST_OPS - BASE_OPS))"
echo "phase14_live_reliability_posture|${LIVE_META[0]}"
echo "phase14_state|$STATE"
echo "phase14_benchmark_report|$BENCHMARK_REPORT"
echo "rollback_image|$ROLLBACK_TAG"
