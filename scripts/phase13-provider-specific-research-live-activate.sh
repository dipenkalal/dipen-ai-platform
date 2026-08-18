#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_HEAD="${1:-}"
REPO="/home/dipen/dap/source/dipen-ai-platform"
BACKEND="$REPO/platform/backend"
DASH="$REPO/apps/dashboard"
COMPOSE="/home/dipen/dap/compose"
PY="$BACKEND/.venv/bin/python"
TRUTH_DB="/home/dipen/dap/data/agent-history/agent-truth.db"
CTX="/tmp/dap-phase13-dashboard-runtime"
RUN_JSON="/tmp/phase13-live-agent-run.json"
NEG_SMART="/tmp/phase13-smart-reject.json"
NEG_AGENT="/tmp/phase13-agent-reject.json"
BACKEND_LIST="/tmp/phase13-backend-research.json"
DASHBOARD_LIST="/tmp/phase13-dashboard-research.json"

if [[ -z "$EXPECTED_HEAD" ]]; then
  echo "usage|$0 <expected-head-sha>"
  exit 2
fi

cleanup_tmp() {
  rm -f "$RUN_JSON" "$NEG_SMART" "$NEG_AGENT" "$BACKEND_LIST" "$DASHBOARD_LIST"
}
trap cleanup_tmp EXIT

echo "============================================================"
echo " PHASE 13 — PROVIDER-SPECIFIC RESEARCH LIVE ACTIVATION"
echo "============================================================"

cd "$REPO"

echo
echo "=== 1. EXACT SOURCE GATE ==="
BRANCH="$(git branch --show-current)"
HEAD_NOW="$(git rev-parse HEAD)"
echo "branch|$BRANCH"
echo "HEAD|$HEAD_NOW"

[[ "$BRANCH" == "phase13/provider-specific-research-activation" ]] || {
  echo "branch_check|FALSE_STOP"
  exit 1
}
[[ "$HEAD_NOW" == "$EXPECTED_HEAD" ]] || {
  echo "head_check|FALSE_STOP"
  exit 1
}
[[ -z "$(git status --porcelain)" ]] || {
  echo "source_status|DIRTY_STOP"
  git status --short
  exit 1
}
echo "source_gate|PASS"

echo
echo "=== 2. PRODUCTION BASELINE ==="
TASKS_BEFORE="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
EVIDENCE_BEFORE="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM research_retrieval_evidence;')"
PID_BEFORE="$(systemctl show dap-backend.service -p MainPID --value)"
BACKEND_BEFORE="$(systemctl is-active dap-backend.service || true)"
GUARDIAN_BEFORE="$(systemctl is-active dap-guardian-broker.service || true)"
TELEGRAM_BEFORE="$(grep '^DAP_TELEGRAM_APPROVALS_ENABLED=' /home/dipen/dap/config/dap-backend.env || true)"
DASHBOARD_ID_BEFORE="$(docker inspect -f '{{.Id}}' dap-dashboard)"
DASHBOARD_IMAGE_ID_BEFORE="$(docker inspect -f '{{.Image}}' dap-dashboard)"
DASHBOARD_IMAGE_REF="$(docker inspect -f '{{.Config.Image}}' dap-dashboard)"
DASHBOARD_HEALTH_BEFORE="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' dap-dashboard)"
SEARX_STATE_BEFORE="$(docker inspect -f '{{.State.Status}}' dap-searxng)"
SEARX_BINDING_BEFORE="$(docker port dap-searxng 8080/tcp | tr -d '\r')"

echo "task_ledger_before|$TASKS_BEFORE"
echo "research_evidence_before|$EVIDENCE_BEFORE"
echo "backend_pid_before|$PID_BEFORE"
echo "backend_before|$BACKEND_BEFORE"
echo "guardian_before|$GUARDIAN_BEFORE"
echo "telegram_before|$TELEGRAM_BEFORE"
echo "dashboard_health_before|$DASHBOARD_HEALTH_BEFORE"
echo "dashboard_image_ref|$DASHBOARD_IMAGE_REF"
echo "searxng_state_before|$SEARX_STATE_BEFORE"
echo "searxng_binding_before|$SEARX_BINDING_BEFORE"

[[ "$BACKEND_BEFORE" == "active" ]] || exit 1
[[ "$GUARDIAN_BEFORE" == "inactive" ]] || exit 1
[[ "$TELEGRAM_BEFORE" == "DAP_TELEGRAM_APPROVALS_ENABLED=false" ]] || exit 1
[[ "$DASHBOARD_HEALTH_BEFORE" == "healthy" ]] || exit 1
[[ "$SEARX_STATE_BEFORE" == "running" ]] || exit 1
[[ "$SEARX_BINDING_BEFORE" == "127.0.0.1:8888" ]] || exit 1
curl -fsS --max-time 10 http://127.0.0.1:8888/ >/dev/null
echo "baseline_safety|PASS"

echo
echo "=== 3. CONTROLLED BACKEND ACTIVATION ==="
sudo systemctl restart dap-backend.service
READY=0
for ATTEMPT in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:8002/health >/dev/null 2>&1; then
    READY=1
    echo "backend_ready_attempt|$ATTEMPT"
    break
  fi
  sleep 2
done
[[ "$READY" -eq 1 ]] || {
  echo "backend_activation|FAIL"
  sudo journalctl -u dap-backend.service -n 100 --no-pager
  exit 1
}
PID_ACTIVATED="$(systemctl show dap-backend.service -p MainPID --value)"
echo "backend_pid_activated|$PID_ACTIVATED"
[[ "$PID_ACTIVATED" =~ ^[1-9][0-9]*$ ]] || exit 1
[[ "$PID_ACTIVATED" != "$PID_BEFORE" ]] || {
  echo "backend_new_process|FAIL"
  exit 1
}
echo "backend_activation|PASS"

echo
echo "=== 4. LIVE NEGATIVE AUTHORITY PROOFS ==="
EVIDENCE_PRE_NEGATIVE="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM research_retrieval_evidence;')"
SMART_HTTP="$(curl -sS --max-time 30 -o "$NEG_SMART" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:8002/api/v1/agents/run \
  --data-binary '{"mode":"smart","objective":"Research example domains using current public sources.","research_search_query":"IANA example domains purpose","provider":"ollama","model":"qwen3:1.7b"}')"
AGENT_HTTP="$(curl -sS --max-time 30 -o "$NEG_AGENT" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:8002/api/v1/agents/run \
  --data-binary '{"mode":"manual","agent_id":"coding-agent","objective":"Research example domains using current public sources.","research_search_query":"IANA example domains purpose","provider":"ollama","model":"qwen3:1.7b"}')"
EVIDENCE_POST_NEGATIVE="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM research_retrieval_evidence;')"
echo "smart_search_http|$SMART_HTTP"
echo "nonresearch_search_http|$AGENT_HTTP"
echo "negative_evidence_before|$EVIDENCE_PRE_NEGATIVE"
echo "negative_evidence_after|$EVIDENCE_POST_NEGATIVE"
[[ "$SMART_HTTP" == "400" ]] || { cat "$NEG_SMART"; exit 1; }
[[ "$AGENT_HTTP" == "400" ]] || { cat "$NEG_AGENT"; exit 1; }
[[ "$EVIDENCE_PRE_NEGATIVE" == "$EVIDENCE_POST_NEGATIVE" ]] || exit 1
echo "negative_authority_proofs|PASS"

echo
echo "=== 5. LIVE MANUAL RESEARCH-AGENT SEARCH ==="
RUN_HTTP="$(curl -sS --max-time 360 -o "$RUN_JSON" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:8002/api/v1/agents/run \
  --data-binary '{"mode":"manual","agent_id":"research-agent","objective":"Using current public sources, explain what the IANA example domains are for. Keep the answer concise and cite the retrieved public-web sources.","research_search_query":"IANA example domains purpose","provider":"ollama","model":"qwen3:1.7b","temperature":0.1,"max_tokens":350,"max_steps":4,"retrieval_limit":5,"score_threshold":0.4}')"
echo "manual_search_http|$RUN_HTTP"
[[ "$RUN_HTTP" == "200" ]] || { cat "$RUN_JSON"; exit 1; }

RUN_ID="$($PY - "$RUN_JSON" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
assert p.get('status') == 'completed', p
assert p.get('agent_id') == 'research-agent', p
steps=p.get('steps') or []
search=[s for s in steps if s.get('title') == 'Discover and retrieve public-web evidence via local SearXNG']
assert len(search) == 1, search
step=search[0]
assert step.get('success') is True, step
assert step.get('tool_id') is None, step
inp=step.get('input') or {}
out=step.get('output') or {}
assert inp.get('provider_id') == 'searxng-local-v1', inp
assert inp.get('retrieval_limit') == 3, inp
assert out.get('provider_id') == 'searxng-local-v1', out
assert 0 < int(out.get('candidate_count', 0)), out
selected=out.get('selected_urls') or []
assert 0 < len(selected) <= 3, selected
assert out.get('provider_snippets_are_evidence') is False, out
assert out.get('provider_snippets_exposed_to_model') is False, out
assert out.get('provider_titles_exposed_to_model') is False, out
assert out.get('search_candidates_are_retrieval_evidence') is False, out
assert out.get('candidate_urls_require_full_dap_retrieval') is True, out
assert out.get('generic_network_client_exposed') is False, out
assert out.get('remote_scope_expansion_allowed') is False, out
public_sources=[s for s in (p.get('sources') or []) if s.get('source_kind') == 'public_web']
assert public_sources, p.get('sources')
assert all(s.get('evidence_id') for s in public_sources), public_sources
assert (p.get('answer') or '').strip(), p
print(p['run_id'])
print(f"search_candidate_count|{out.get('candidate_count')}", file=sys.stderr)
print(f"search_selected_url_count|{len(selected)}", file=sys.stderr)
print(f"public_web_source_count|{len(public_sources)}", file=sys.stderr)
PY
)"
echo "research_run_id|$RUN_ID"
echo "manual_provider_specific_search|PASS"

echo
echo "=== 6. EVIDENCE DELTA + OWNER VISIBILITY ==="
EVIDENCE_AFTER_RUN="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM research_retrieval_evidence;')"
EVIDENCE_DELTA="$((EVIDENCE_AFTER_RUN - EVIDENCE_BEFORE))"
echo "research_evidence_after_run|$EVIDENCE_AFTER_RUN"
echo "research_evidence_delta|$EVIDENCE_DELTA"
[[ "$EVIDENCE_DELTA" -gt 0 ]] || exit 1

curl -fsS --max-time 20 'http://127.0.0.1:8002/api/v1/research/evidence?limit=500' -o "$BACKEND_LIST"
curl -fsS --max-time 20 'http://127.0.0.1/api/research/evidence?limit=500' -o "$DASHBOARD_LIST"
$PY - "$BACKEND_LIST" "$DASHBOARD_LIST" "$EVIDENCE_AFTER_RUN" <<'PY'
import json, sys
expected_total=int(sys.argv[3])
for label, path in [('backend', sys.argv[1]), ('dashboard', sys.argv[2])]:
    p=json.load(open(path, encoding='utf-8'))
    assert p.get('workspace_mode') == 'read_only', p
    assert p.get('network_authority_granted') is False, p
    assert p.get('mutation_authority_granted') is False, p
    assert p.get('search_candidate_metadata_included') is False, p
    assert int(p.get('total', -1)) == expected_total, (label, p.get('total'), expected_total)
    print(f"{label}_research_workspace|PASS")
PY
POST_HTTP="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1/api/research/evidence)"
echo "research_workspace_post_http|$POST_HTTP"
[[ "$POST_HTTP" == "405" ]] || exit 1
echo "owner_visibility|PASS"

echo
echo "=== 7. OFFLINE DASHBOARD APPLICATION BUILD ==="
[[ -d "$DASH/node_modules/next" ]] || { echo "local_node_modules|MISSING_STOP"; exit 1; }
docker image inspect node:24-alpine >/dev/null 2>&1 || { echo "node_base_image|MISSING_STOP"; exit 1; }
ROLLBACK_TAG="dap-dashboard-phase13-rollback:$(date -u +%Y%m%dT%H%M%SZ)"
docker tag "$DASHBOARD_IMAGE_ID_BEFORE" "$ROLLBACK_TAG"
echo "rollback_image|$ROLLBACK_TAG"
rm -rf "$DASH/.next"
docker run --rm --network none \
  -e NEXT_TELEMETRY_DISABLED=1 \
  -v "$DASH:/app" -w /app node:24-alpine \
  sh -lc 'npm run build'
echo "offline_dashboard_app_build|PASS"
[[ -f "$DASH/.next/standalone/server.js" ]] || exit 1
[[ -d "$DASH/.next/static" ]] || exit 1
[[ -d "$DASH/public" ]] || exit 1
cd "$REPO"
[[ -z "$(git status --porcelain)" ]] || { echo "source_after_app_build|DIRTY_STOP"; git status --short; exit 1; }

echo
echo "=== 8. PACKAGE DASHBOARD RUNTIME WITHOUT NPM ==="
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
echo "=== 9. RECREATE ONLY DASHBOARD ==="
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
curl -fsS --max-time 20 http://127.0.0.1/agents >/dev/null
curl -fsS --max-time 20 http://127.0.0.1/research >/dev/null
curl -fsS --max-time 20 http://127.0.0.1/api/agents >/tmp/phase13-dashboard-agents.json
$PY - /tmp/phase13-dashboard-agents.json <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
agents=p.get('agents') or []
r=next(a for a in agents if a.get('id') == 'research-agent')
assert 'Local SearXNG URL discovery' in (r.get('capabilities') or []), r
assert r.get('tools') == ['knowledge.search', 'internet.research.retrieve'], r
print('dashboard_research_agent_scope|PASS')
PY
rm -f /tmp/phase13-dashboard-agents.json

echo
echo "=== 10. FINAL PRODUCTION SAFETY ==="
TASKS_AFTER="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
EVIDENCE_FINAL="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM research_retrieval_evidence;')"
PID_FINAL="$(systemctl show dap-backend.service -p MainPID --value)"
BACKEND_FINAL="$(systemctl is-active dap-backend.service || true)"
GUARDIAN_FINAL="$(systemctl is-active dap-guardian-broker.service || true)"
TELEGRAM_FINAL="$(grep '^DAP_TELEGRAM_APPROVALS_ENABLED=' /home/dipen/dap/config/dap-backend.env || true)"
DASHBOARD_FINAL="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' dap-dashboard)"
SEARX_STATE_FINAL="$(docker inspect -f '{{.State.Status}}' dap-searxng)"
SEARX_BINDING_FINAL="$(docker port dap-searxng 8080/tcp | tr -d '\r')"
cd "$REPO"
HEAD_FINAL="$(git rev-parse HEAD)"
SOURCE_FINAL="clean"
[[ -z "$(git status --porcelain)" ]] || SOURCE_FINAL="DIRTY"

echo "task_ledger_after|$TASKS_AFTER"
echo "research_evidence_final|$EVIDENCE_FINAL"
echo "backend_pid_final|$PID_FINAL"
echo "backend_final|$BACKEND_FINAL"
echo "guardian_final|$GUARDIAN_FINAL"
echo "telegram_final|$TELEGRAM_FINAL"
echo "dashboard_final|$DASHBOARD_FINAL"
echo "searxng_state_final|$SEARX_STATE_FINAL"
echo "searxng_binding_final|$SEARX_BINDING_FINAL"
echo "HEAD_final|$HEAD_FINAL"
echo "source_final|$SOURCE_FINAL"

[[ "$TASKS_AFTER" == "$TASKS_BEFORE" ]] || exit 1
[[ "$EVIDENCE_FINAL" -gt "$EVIDENCE_BEFORE" ]] || exit 1
[[ "$PID_FINAL" == "$PID_ACTIVATED" ]] || exit 1
[[ "$BACKEND_FINAL" == "active" ]] || exit 1
[[ "$GUARDIAN_FINAL" == "inactive" ]] || exit 1
[[ "$TELEGRAM_FINAL" == "DAP_TELEGRAM_APPROVALS_ENABLED=false" ]] || exit 1
[[ "$DASHBOARD_FINAL" == "healthy" ]] || exit 1
[[ "$SEARX_STATE_FINAL" == "running" ]] || exit 1
[[ "$SEARX_BINDING_FINAL" == "127.0.0.1:8888" ]] || exit 1
[[ "$HEAD_FINAL" == "$EXPECTED_HEAD" ]] || exit 1
[[ "$SOURCE_FINAL" == "clean" ]] || exit 1

echo
echo "PHASE13_PROVIDER_SPECIFIC_ACTIVATION|PASS"
echo "PHASE13_LIVE_EVIDENCE_GATE|PASS"
echo "research_run_id|$RUN_ID"
echo "rollback_image|$ROLLBACK_TAG"
