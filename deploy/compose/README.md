# DAP Docker Compose Deployment

This directory tracks the Docker Compose configuration used by the DAP homelab host.

The deployed file is:

```text
/home/dipen/dap/compose/docker-compose.yml
```

The tracked source is:

```text
deploy/compose/docker-compose.yml
```

## Services

The Compose stack runs:

- Ollama on port `11434`
- Qdrant on ports `6333` and `6334`
- Open WebUI on port `3000`
- DAP dashboard on port `80`

The DAP backend is managed separately by `dap-backend.service` on port `8002`.

## Health checks

Docker health checks are configured for:

- Dashboard: HTTP request to `127.0.0.1:3000`
- Ollama: native `ollama list` command
- Qdrant: HTTP request to `/healthz` using Bash `/dev/tcp`

Open WebUI provides its own image health check.

## Validate configuration

```bash
docker compose \
  -f deploy/compose/docker-compose.yml \
  config --quiet
```

A successful validation produces no error output.

## Deploy safely

Back up the active Compose file before replacing it:

```bash
cp ~/dap/compose/docker-compose.yml \
  ~/dap/compose/docker-compose.yml.backup-$(date +%Y%m%d-%H%M%S)

cp deploy/compose/docker-compose.yml \
  ~/dap/compose/docker-compose.yml
```

Validate the deployed file:

```bash
docker compose \
  -f ~/dap/compose/docker-compose.yml \
  config --quiet
```

Recreate one service at a time and verify it before continuing:

```bash
cd ~/dap/compose

docker compose up -d --no-deps --force-recreate dashboard
docker compose up -d --no-deps --force-recreate ollama
docker compose up -d --no-deps --force-recreate qdrant
```

Inspect container health:

```bash
docker ps \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' \
  --filter name=dap-
```

Run the DAP end-to-end health check after deployment:

```bash
cd ~/dap/source/dipen-ai-platform
./scripts/check-dev-health.sh
```

## Rollback

Restore the most recent known-good backup, validate it, and recreate only the affected service:

```bash
cp ~/dap/compose/docker-compose.yml.backup-YYYYMMDD-HHMMSS \
  ~/dap/compose/docker-compose.yml

docker compose \
  -f ~/dap/compose/docker-compose.yml \
  config --quiet
```

Do not remove persistent data directories during configuration rollback.
