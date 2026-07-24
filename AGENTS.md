# Dipen AI Platform — Codex Instructions

## Project vision

Dipen AI Platform, or DAP, is a local-first AI operating platform.

Main goals:

- Local AI models through Ollama
- Open WebUI integration
- Infrastructure monitoring dashboard
- FastAPI backend
- Knowledge engine
- AI model router
- Agents and tools
- Modern portfolio-quality UI
- Docker-based production deployment

## Repository structure

- `apps/dashboard` — Next.js, TypeScript and Tailwind dashboard
- `platform/backend` — FastAPI backend and collectors
- `platform/agents` — future agents
- `platform/ai-core` — future AI core
- `platform/knowledge` — future knowledge engine
- `platform/router` — future AI router
- `docker` — deployment assets
- `docs` — architecture and project documentation
- `tests` — tests

## Current milestone

Current version: DAP v0.2

Completed:

- Responsive Next.js dashboard
- Live CPU monitoring
- Live RAM monitoring
- Live disk monitoring
- Live system uptime
- Ollama online status
- Loaded Ollama model reporting
- FastAPI `/health`
- FastAPI `/api/status`
- Next.js `/api/status` proxy route
- Backend running on Acer through systemd
- Backend port is `8002`

## Runtime environment

Development computer:

- Windows
- Repository: `C:\GitHub\dipen-ai-platform`
- Dashboard development address: `http://192.168.40.248:3000`

Production Acer server:

- Host: `192.168.40.212`
- Ubuntu Server
- Repository: `/home/dipen/dap/source/dipen-ai-platform`
- FastAPI systemd service: `dap-api`
- FastAPI port: `8002`
- Ollama port: `11434`
- Open WebUI port: `3000`
- Dashboard intended port: `80`

## Important deployment details

The dashboard container reaches FastAPI using:

`http://host.docker.internal:8002/api/status`

Docker Compose must include:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"