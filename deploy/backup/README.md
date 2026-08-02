# DAP backup and restore

This guide covers consistent backups of DAP persistent data to the mounted storage disk at `/data`.

## What is backed up

The backup script archives:

- `compose/docker-compose.yml`
- `data/ollama`
- `data/qdrant`
- `data/open-webui`
- `data/agent-history`
- `data/knowledge`

The repository itself is not included because it is already stored in GitHub.

## Backup destination

The default destination is:

```text
/data/dap-backups
```

The directory should be owned by the user running DAP and should not live on the same filesystem as the live DAP data.

Verify the mount before relying on it:

```bash
findmnt /data
grep -nE 'NASDATA|/data|sdb1' /etc/fstab
```

Create the directory once:

```bash
sudo install -d -o "$USER" -g "$(id -gn)" -m 0750 /data/dap-backups
```

## Run a backup

From the repository root:

```bash
bash scripts/backup-dap.sh
```

The script:

1. verifies required paths and commands;
2. prevents overlapping backup runs;
3. records which services were running;
4. stops the backend, Ollama, Qdrant, and Open WebUI when required;
5. creates a sparse-aware compressed archive;
6. validates the archive and writes a SHA-256 checksum;
7. restarts only the services that were previously running;
8. waits for container health checks;
9. runs the DAP end-to-end health check.

The dashboard remains running during backup, although backend-dependent actions are briefly unavailable.

## Configuration overrides

Environment variables can override the defaults:

```bash
BACKUP_DIR=/data/dap-backups \
DAP_ROOT="$HOME/dap" \
bash scripts/backup-dap.sh
```

Available variables:

- `BACKUP_DIR`
- `DAP_ROOT`
- `COMPOSE_DIR`
- `REPO_DIR`
- `BACKEND_SERVICE`

## Verify an existing backup

```bash
BACKUP=/data/dap-backups/dap-data-YYYYMMDD-HHMMSS.tar.gz
sha256sum -c "$BACKUP.sha256"
tar -tzf "$BACKUP" >/dev/null
echo "Backup is readable."
```

## Non-destructive restore rehearsal

A restore rehearsal extracts into an isolated directory and does not modify live data:

```bash
BACKUP=/data/dap-backups/dap-data-YYYYMMDD-HHMMSS.tar.gz
TEST_DIR="/data/dap-restore-test-$(date +%Y%m%d-%H%M%S)"

sha256sum -c "$BACKUP.sha256"
mkdir -p "$TEST_DIR"
tar --sparse --no-same-owner -xzf "$BACKUP" -C "$TEST_DIR"

for path in \
  compose/docker-compose.yml \
  data/ollama \
  data/qdrant \
  data/open-webui \
  data/agent-history \
  data/knowledge
do
  test -e "$TEST_DIR/$path" || {
    echo "Missing restored path: $path" >&2
    exit 1
  }
done

echo "Restore rehearsal completed: $TEST_DIR"
```

Remove only the isolated rehearsal directory after validation:

```bash
case "$TEST_DIR" in
  /data/dap-restore-test-*) rm -rf -- "$TEST_DIR" ;;
  *) echo "Refusing unexpected path: $TEST_DIR" >&2; exit 1 ;;
esac
```

## Full restore policy

A full restore replaces live persistent data and must be handled as a controlled maintenance operation. Before restoring:

1. verify the archive checksum;
2. confirm the backup timestamp and contents;
3. stop the backend and data-writing containers;
4. move the current live data to a dated rollback directory rather than deleting it;
5. extract the backup with ACL, xattr, numeric-owner, and sparse-file support;
6. start services and verify all health checks;
7. keep the rollback directory until the restored system has been validated.

Do not perform a full restore directly from an unverified archive.

## Current validated baseline

The initial manual backup and restore rehearsal validated:

- archive creation on `/data`;
- SHA-256 verification;
- restoration of all expected paths;
- Compose file comparison;
- container recovery;
- active backend service;
- all five DAP end-to-end checks returning HTTP 200.
