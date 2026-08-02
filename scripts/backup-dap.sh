#!/usr/bin/env bash

set -Eeuo pipefail

DAP_ROOT="${DAP_ROOT:-$HOME/dap}"
COMPOSE_DIR="${COMPOSE_DIR:-$DAP_ROOT/compose}"
REPO_DIR="${REPO_DIR:-$DAP_ROOT/source/dipen-ai-platform}"
BACKUP_DIR="${BACKUP_DIR:-/data/dap-backups}"
BACKEND_SERVICE="${BACKEND_SERVICE:-dap-backend.service}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_DIR/dap-data-$STAMP.tar.gz"
CHECKSUM="$BACKUP.sha256"
LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/dap-backup.lock"

COMPOSE_SERVICES=(ollama qdrant open-webui)
CONTAINERS=(dap-ollama dap-qdrant dap-open-webui)
DATA_PATHS=(
  compose/docker-compose.yml
  data/ollama
  data/qdrant
  data/open-webui
  data/agent-history
  data/knowledge
)

for command in docker findmnt flock sha256sum sudo systemctl tar; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Required command not found: $command" >&2
    exit 1
  }
done

[ -f "$COMPOSE_DIR/docker-compose.yml" ] || {
  echo "Compose file not found: $COMPOSE_DIR/docker-compose.yml" >&2
  exit 1
}

for relative_path in "${DATA_PATHS[@]}"; do
  [ -e "$DAP_ROOT/$relative_path" ] || {
    echo "Required backup path not found: $DAP_ROOT/$relative_path" >&2
    exit 1
  }
done

mkdir -p "$BACKUP_DIR"
[ -w "$BACKUP_DIR" ] || {
  echo "Backup directory is not writable: $BACKUP_DIR" >&2
  exit 1
}

findmnt -T "$BACKUP_DIR" >/dev/null || {
  echo "Backup directory is not on a mounted filesystem: $BACKUP_DIR" >&2
  exit 1
}

exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "Another DAP backup is already running." >&2
  exit 1
}

sudo -v

backend_was_active=0
if systemctl is-active --quiet "$BACKEND_SERVICE"; then
  backend_was_active=1
fi

declare -A container_was_running=()
for container in "${CONTAINERS[@]}"; do
  running="$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true)"
  container_was_running["$container"]="$running"
done

services_restarted=0

restart_services() {
  local rc=0

  if [ "$services_restarted" -eq 1 ]; then
    return 0
  fi

  echo
  echo "Starting previously running DAP services..."

  cd "$COMPOSE_DIR"

  local services_to_start=()
  local index
  for index in "${!CONTAINERS[@]}"; do
    if [ "${container_was_running[${CONTAINERS[$index]}]}" = "true" ]; then
      services_to_start+=("${COMPOSE_SERVICES[$index]}")
    fi
  done

  if [ "${#services_to_start[@]}" -gt 0 ]; then
    docker compose start "${services_to_start[@]}" || rc=1
  fi

  if [ "$backend_was_active" -eq 1 ]; then
    sudo systemctl start "$BACKEND_SERVICE" || rc=1
  fi

  services_restarted=1
  return "$rc"
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  restart_services || true
  exit "$rc"
}

trap cleanup EXIT INT TERM

echo "Backup destination filesystem:"
findmnt -T "$BACKUP_DIR" -o TARGET,SOURCE,FSTYPE,OPTIONS

echo
echo "Stopping services that write persistent DAP data..."

if [ "$backend_was_active" -eq 1 ]; then
  sudo systemctl stop "$BACKEND_SERVICE"
fi

cd "$COMPOSE_DIR"
services_to_stop=()
for index in "${!CONTAINERS[@]}"; do
  if [ "${container_was_running[${CONTAINERS[$index]}]}" = "true" ]; then
    services_to_stop+=("${COMPOSE_SERVICES[$index]}")
  fi
done

if [ "${#services_to_stop[@]}" -gt 0 ]; then
  docker compose stop "${services_to_stop[@]}"
fi

echo
echo "Creating sparse-aware backup: $BACKUP"
cd "$DAP_ROOT"

sudo tar \
  --sparse \
  --acls \
  --xattrs \
  --numeric-owner \
  -czf "$BACKUP" \
  "${DATA_PATHS[@]}"

sudo chown "$USER:$(id -gn)" "$BACKUP"

echo "Validating archive structure..."
tar -tzf "$BACKUP" >/dev/null

sha256sum "$BACKUP" > "$CHECKSUM"

restart_services
trap - EXIT INT TERM

echo
echo "Waiting for container health checks..."
for attempt in {1..24}; do
  all_healthy=1

  for container in "${CONTAINERS[@]}"; do
    if [ "${container_was_running[$container]}" != "true" ]; then
      continue
    fi

    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{if .State.Running}}running{{else}}stopped{{end}}{{end}}' "$container")"
    printf '%-18s %s\n' "$container" "$status"

    case "$status" in
      healthy|running) ;;
      *) all_healthy=0 ;;
    esac
  done

  [ "$all_healthy" -eq 1 ] && break
  echo "---"
  sleep 5
done

if [ "$backend_was_active" -eq 1 ]; then
  systemctl is-active --quiet "$BACKEND_SERVICE" || {
    echo "Backend service did not return to active state." >&2
    exit 1
  }
fi

echo
echo "Verifying checksum..."
sha256sum -c "$CHECKSUM"

echo
echo "Backup completed successfully:"
ls -lh "$BACKUP" "$CHECKSUM"

if [ -x "$REPO_DIR/scripts/check-dev-health.sh" ]; then
  echo
  echo "Running DAP end-to-end health verification..."
  "$REPO_DIR/scripts/check-dev-health.sh"
fi
