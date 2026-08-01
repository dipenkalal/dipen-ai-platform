#!/usr/bin/env bash
set -u

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8002}"
DASHBOARD_URL="${DASHBOARD_URL:-http://192.168.40.212:3001}"
TIMEOUT="${HEALTH_TIMEOUT_SECONDS:-10}"

checks=(
  "Backend API|${BACKEND_URL}/openapi.json"
  "Backend monitoring|${BACKEND_URL}/api/monitoring/overview"
  "Dashboard home|${DASHBOARD_URL}/"
  "Execution history|${DASHBOARD_URL}/agents/history"
  "Monitoring page|${DASHBOARD_URL}/monitoring"
)

failures=0

echo "DAP development health check"
echo

for check in "${checks[@]}"; do
  name="${check%%|*}"
  url="${check#*|}"

  if status="$(
    curl \
      --location \
      --silent \
      --show-error \
      --output /dev/null \
      --write-out "%{http_code}" \
      --max-time "${TIMEOUT}" \
      "${url}"
  )"; then
    if [[ "${status}" =~ ^[23][0-9][0-9]$ ]]; then
      printf "PASS  %-20s HTTP %s\n" "${name}" "${status}"
    else
      printf "FAIL  %-20s HTTP %s\n" "${name}" "${status}"
      failures=$((failures + 1))
    fi
  else
    printf "FAIL  %-20s connection error\n" "${name}"
    failures=$((failures + 1))
  fi
done

echo

if (( failures > 0 )); then
  echo "Health check failed: ${failures} check(s) unsuccessful."
  exit 1
fi

echo "All DAP development services are reachable."
