# DAP Backend systemd Service

This directory contains the managed service definition used to run the Dipen AI Platform backend on the homelab host.

## Purpose

The service runs Uvicorn without development reload mode, starts automatically after boot, and restarts after unexpected failures.

Runtime dependencies remain on the host:

- Ollama: `http://127.0.0.1:11434`
- Qdrant: `http://127.0.0.1:6333`
- Agent history database: `/home/dipen/dap/data/agent-history/agent-runs.db`
- Knowledge uploads: `/home/dipen/dap/data/knowledge/uploads`

## Install or Update

```bash
sudo install -m 0644 \
  deploy/systemd/dap-backend.service \
  /etc/systemd/system/dap-backend.service

sudo systemctl daemon-reload
sudo systemctl enable dap-backend.service
sudo systemctl restart dap-backend.service
```

## Verify

```bash
systemctl --no-pager --full status dap-backend.service
curl -sS http://127.0.0.1:8002/health
./scripts/check-dev-health.sh
```

The managed process should not include `--reload`.

## Logs

```bash
sudo journalctl -u dap-backend.service -n 100 --no-pager
sudo journalctl -u dap-backend.service -f
```

## Stop or Disable

```bash
sudo systemctl stop dap-backend.service
sudo systemctl disable dap-backend.service
```

Stopping or disabling the service does not delete the history database, knowledge uploads, source code, or virtual environment.
