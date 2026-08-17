# Phase 10 Ruflo Evaluation — Architecture and Security Audit

## Status

Phase 10A audit in progress. No Ruflo installation or DAP runtime integration has been performed.

## Sealed parent checkpoint

Phase 9.4 parent: `ddc20b9779b8296cfa6216b83d2e1c558972ef9c`

## Current DAP invariants

DAP remains the authority for:

- user identity and owner intent
- company roles and routing
- Guardian policy and privileged-action boundaries
- canonical audit history and task ledger
- canonical Knowledge/Qdrant ownership
- Telegram authorization state
- systemd, Docker, host administration, and privileged execution

Ruflo must never become an alternate authority for these concerns.

## Upstream Ruflo facts reviewed

- Repository: `ruvnet/ruflo`
- License: MIT
- Current root package version observed during audit: `3.38.12`
- Node engine: `>=20`
- Native Codex adapter exists (`@claude-flow/codex`)
- Codex adapter execution model: Ruflo/Claude-Flow orchestrates; Codex executes
- Ruflo init can generate or modify project-local `AGENTS.md`, `.agents/`, `.codex/`, and `.claude-flow/` state and can auto-register an MCP server
- Ruflo maintains its own vector/pattern memory
- Ruflo security package advertises command allowlisting, path validation, input validation, and credential primitives

These upstream capabilities are useful, but DAP does not trust them as replacements for DAP Guardian or DAP audit controls.

## Acer host observations

Observed at Phase 10A start:

- Node: `v22.22.1` — compatible with Ruflo's `>=20` engine requirement
- npm/npx: `9.2.0`
- Codex CLI: `0.146.0`
- Ruflo root package currently declares development dependency `@openai/codex ^0.98.0`; therefore Codex compatibility must be tested rather than assumed
- Host RAM: about 11 GiB total, about 9.3 GiB available at audit time
- Root filesystem: about 55 GiB free at audit time
- Existing DAP workspace already contains an `AGENTS.md`

## Initial capability matrix

| Capability | Ruflo evaluation | Production ownership |
|---|---:|---|
| Decompose coding objectives | Allowed | Ruflo subordinate worker |
| Coordinate 1–3 coding/review/test workers | Allowed in sandbox | Ruflo subordinate worker |
| Codex task orchestration | Allowed in sandbox | Via DAP adapter only if adopted |
| Code review/test generation | Allowed | Ruflo subordinate worker |
| Engineering pattern memory | Evaluate | Non-canonical; DAP may import selected results |
| Local Ollama use | Evaluate later | DAP controls model endpoint/policy |
| Global DAP Knowledge | Read only through explicit future adapter | DAP |
| DAP user identity | Forbidden | DAP |
| DAP company role authority | Forbidden | DAP |
| Guardian policy | Forbidden | DAP Guardian |
| Owner authorization | Forbidden | DAP |
| Telegram approvals | Forbidden | DAP |
| Canonical task ledger/audit | Forbidden direct writes | DAP |
| systemd / Docker / root | Forbidden | DAP privileged boundary |
| Arbitrary host shell | Forbidden | DAP policy/executor boundary |

## Threat model

### T1 — Project mutation during init

Ruflo's Codex init may create or modify `AGENTS.md`, `.agents/`, `.codex/`, `.claude-flow/`, and MCP registration. Running init in the DAP source tree could overwrite or conflict with DAP instructions and state.

**Control:** never initialize Ruflo inside `/home/dipen/dap/source/dipen-ai-platform` during evaluation.

### T2 — Alternate memory authority

Ruflo can maintain its own vector memory and learned patterns. Treating that memory as canonical could split provenance and lifecycle from DAP Knowledge.

**Control:** Ruflo memory remains sandbox-local and disposable. No direct Qdrant writes during Phase 10B/C.

### T3 — Alternate execution authority

Ruflo/Codex can execute code and commands. If given host-level access it could bypass DAP Guardian or create a second execution path.

**Control:** no Docker socket, no systemd/dbus socket, no sudo, no DAP secrets, no Guardian broker socket, no root token, and no write mount of DAP runtime/data directories.

### T4 — Workspace escape

A coding agent may attempt to read or write outside its assigned project.

**Control:** Phase 10B uses a dedicated sandbox directory. Initial tests use only synthetic fixture repositories. DAP source is not mounted writable into the sandbox.

### T5 — Resource exhaustion

Ruflo advertises larger swarms than the Acer should run safely alongside DAP/Ollama.

**Control:** initial cap 1–3 workers; no large swarm, no daemon/autopilot loop, and resource measurements are mandatory before increasing concurrency.

### T6 — Codex version drift

A newer locally installed Codex CLI may differ from the version Ruflo currently develops against.

**Control:** verify adapter startup and a non-destructive task in the sandbox before any DAP adapter work.

### T7 — Supply-chain/dependency expansion

Ruflo introduces a substantial Node/native/WASM dependency graph.

**Control:** inspect package metadata and npm audit results in the sandbox; do not add Ruflo dependencies to DAP packages during evaluation.

## Forbidden-access matrix for Phase 10B/C

Ruflo sandbox must not receive:

- `/var/run/docker.sock`
- systemd/dbus control sockets
- `/home/dipen/dap/secrets`
- `/home/dipen/dap/config/dap-backend.env`
- `/home/dipen/dap/data/agent-history`
- `/home/dipen/dap/data/qdrant`
- `/home/dipen/dap/data/ollama`
- DAP Guardian broker credentials/socket
- Telegram bot secrets or approval controls
- root/sudo credentials

The sandbox may use:

- its own isolated project directory
- its own Ruflo state/memory
- network access only when required for package retrieval during setup
- Codex only during the explicit Phase 10C compatibility test
- Ollama only in Phase 10G under an explicit resource gate

## Phase 10B sandbox design

Initial sandbox root:

`/home/dipen/dap/sandboxes/ruflo-eval`

Subdirectories:

- `workspace/` — synthetic disposable Git fixture
- `home/` — isolated HOME for Ruflo/Codex configuration during tests
- `npm-cache/` — isolated npm cache
- `evidence/` — command output, package metadata, audit results, resource snapshots

Rules:

1. Do not run Ruflo commands from the DAP source directory.
2. Do not point `HOME` at `/home/dipen` for Ruflo initialization.
3. Do not register MCP globally during Phase 10B.
4. Do not start daemon/autopilot/federation features.
5. Do not expose DAP secrets/data/privileged sockets.
6. Keep initial worker concurrency at one; expand to at most three only after resource measurements.
7. Every Ruflo-generated file must remain under the sandbox root.
8. Sandbox must be removable without affecting DAP.

## 10A exit criteria

10A is complete when:

- capability matrix is documented
- threat model is documented
- forbidden-access matrix is documented
- host capacity/toolchain is recorded
- sandbox layout and isolation rules are fixed
- protected DAP baseline remains unchanged
- no Ruflo installation has occurred in DAP or globally
