#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_HEAD="${1:-}"
EXPECTED_BACKEND_PID="${2:-}"
EXPECTED_EVIDENCE_TOTAL="${3:-}"
RUN_ID="${4:-}"

ORIGINAL_ACTIVATION_HEAD="2bb068c0bc39604e75faa75660ebf39ebed80f56"
EXPECTED_TASK_LEDGER="11"
REPO="/home/dipen/dap/source/dipen-ai-platform"
BACKEND="$REPO/platform/backend"
DASH="$REPO/apps/dashboard"
COMPOSE="/home/dipen/dap/compose"
PY="$BACKEND/.venv/bin/python"
TRUTH_DB="/home/dipen/dap/data/agent-history/agent-truth.db"
CTX="/tmp/dap-phase13-dashboard-runtime-resume"
AGENTS_JSON="/tmp/phase13-dashboard-agents-resume.json"

if [[ -z "$EXPECTED_HEAD" || -z "$EXPECTED_BACKEND_PID" || -z "$EXPECTED_EVIDENCE_TOTAL" || -z "$RUN_ID" ]]; then
  echo "usage|$0 <expected-head-sha> <expected-backend-pid> <expected-evidence-total> <research-run-id>"
  exit 2
fi

cleanup_tmp() {
  rm -f "$AGENTS_JSON"
  rm -rf "$CTX"
}
trap cleanup_tmp EXIT

echo "============================================================"
echo " PHASE 13 — LIVE ACTIVATION RESUME / DASHBOARD CLOSURE"
echo "============================================================"

cd "$REPO"

echo
echo "=== R1. RESUME SOURCE + RUNTIME GATE ==="
BRANCH="$(git branch --show-current)"
HEAD_NOW="$(git rev-parse HEAD)"
SOURCE_STATE="clean"
[[ -z "$(git status --porcelain)" ]] || SOURCE_STATE="DIRTY"

echo "branch|$BRANCH"
echo "HEAD|$HEAD_NOW"
echo "source|$SOURCE_STATE"

[[ "$BRANCH" == "phase13/provider-specific-research-activation" ]] || exit 1
[[ "$HEAD_NOW" == "$EXPECTED_HEAD" ]] || exit 1
[[ "$SOURCE_STATE" == "clean" ]] || exit 1

if git diff --quiet "$ORIGINAL_ACTIVATION_HEAD" "$HEAD_NOW" -- platform/backend apps/dashboard deploy/phase12h-searxng; then
  echo "runtime_source_delta_since_live_proof|false"
else
  echo "runtime_source_delta_since_live_proof|TRUE_STOP"
  git diff --stat "$ORIGINAL_ACTIVATION_HEAD" "$HEAD_NOW" -- platform/backend apps/dashboard deploy/phase12h-searxng
  exit 1
fi

TASKS_NOW="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
EVIDENCE_NOW="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM research_retrieval_evidence;')"
PID_NOW="$(systemctl show dap-backend.service -p MainPID --value)"
BACKEND_NOW="$(systemctl is-active dap-backend.service || true)"
GUARDIAN_NOW="$(systemctl is-active dap-guardian-broker.service || true)"
TELEGRAM_NOW="$(grep '^DAP_TELEGRAM_APPROVALS_ENABLED=' /home/dipen/dap/config/dap-backend.env || true)"
DASHBOARD_HEALTH_NOW="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' dap-dashboard)"
DASHBOARD_ID_BEFORE="$(docker inspect -f '{{.Id}}' dap-dashboard)"
DASHBOARD_IMAGE_ID_BEFORE="$(docker inspect -f '{{.Image}}' dap-dashboard)"
DASHBOARD_IMAGE_REF="$(docker inspect -f '{{.Config.Image}}' dap-dashboard)"
SEARX_STATE_NOW="$(docker inspect -f '{{.State.Status}}' dap-searxng)"
SEARX_BINDING_NOW="$(docker port dap-searxng 8080/tcp | tr -d '\r')"

echo "task_ledger_resume|$TASKS_NOW"
echo "research_evidence_resume|$EVIDENCE_NOW"
echo "backend_pid_resume|$PID_NOW"
echo "backend_resume|$BACKEND_NOW"
echo "guardian_resume|$GUARDIAN_NOW"
echo "telegram_resume|$TELEGRAM_NOW"
echo "dashboard_resume|$DASHBOARD_HEALTH_NOW"
echo "searxng_state_resume|$SEARX_STATE_NOW"
echo "searxng_binding_resume|$SEARX_BINDING_NOW"

[[ "$TASKS_NOW" == "$EXPECTED_TASK_LEDGER" ]] || exit 1
[[ "$EVIDENCE_NOW" == "$EXPECTED_EVIDENCE_TOTAL" ]] || exit 1
[[ "$PID_NOW" == "$EXPECTED_BACKEND_PID" ]] || exit 1
[[ "$BACKEND_NOW" == "active" ]] || exit 1
[[ "$GUARDIAN_NOW" == "inactive" ]] || exit 1
[[ "$TELEGRAM_NOW" == "DAP_TELEGRAM_APPROVALS_ENABLED=false" ]] || exit 1
[[ "$DASHBOARD_HEALTH_NOW" == "healthy" ]] || exit 1
[[ "$SEARX_STATE_NOW" == "running" ]] || exit 1
[[ "$SEARX_BINDING_NOW" == "127.0.0.1:8888" ]] || exit 1
curl -fsS --max-time 10 http://127.0.0.1:8888/ >/dev/null
echo "resume_runtime_gate|PASS"

echo
echo "=== R2. CLEAN GENERATED DASHBOARD BUILD TREE ==="
ROLLBACK_TAG="dap-dashboard-phase13-rollback-resume:$(date -u +%Y%m%dT%H%M%SZ)"
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
[[ ! -e "$DASH/.next" ]] || { echo "dashboard_build_tree_cleanup|FAIL"; exit 1; }
echo "dashboard_build_tree_cleanup|PASS"

echo
echo "=== R3. OFFLINE DASHBOARD APPLICATION BUILD ==="
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
[[ -z "$(git status --porcelain)" ]] || { echo "source_after_app_build|DIRTY_STOP"; git status --short; exit 1; }

echo
echo "=== R4. PACKAGE DASHBOARD RUNTIME WITHOUT NPM ==="
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
echo "=== R5. RECREATE ONLY DASHBOARD ==="
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
curl -fsS --max-time 20 http://127.0.0.1/api/agents >"$AGENTS_JSON"
"$PY" - "$AGENTS_JSON" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
agents=p.get('agents') or []
r=next(a for a in agents if a.get('id') == 'research-agent')
assert 'Local SearXNG URL discovery' in (r.get('capabilities') or []), r
assert r.get('tools') == ['knowledge.search', 'internet.research.retrieve'], r
print('dashboard_research_agent_scope|PASS')
PY

echo
echo "=== R6. FINAL PRODUCTION SAFETY ==="
TASKS_FINAL="$(sqlite3 "$TRUTH_DB" 'SELECT COUNT(*) FROM task_ledger;')"
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

echo "task_ledger_final|$TASKS_FINAL"
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

[[ "$TASKS_FINAL" == "$EXPECTED_TASK_LEDGER" ]] || exit 1
[[ "$EVIDENCE_FINAL" == "$EXPECTED_EVIDENCE_TOTAL" ]] || exit 1
[[ "$PID_FINAL" == "$EXPECTED_BACKEND_PID" ]] || exit 1
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
echo "phase13_resume_without_duplicate_research|PASS"
echo "research_run_id|$RUN_ID"
echo "rollback_image|$ROLLBACK_TAG"
