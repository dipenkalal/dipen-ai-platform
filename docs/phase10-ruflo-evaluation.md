# Phase 10 — External Engineering Orchestrator Evaluation (Ruflo)

## Purpose

Evaluate whether Ruflo can safely operate as a subordinate engineering orchestration engine inside DAP for software-development workflows without becoming a second source of authority.

DAP remains the system of record and control plane. Ruflo is an optional worker/harness under DAP policy.

## Sealed starting checkpoint

Phase 10 starts from the validated Phase 9.4 checkpoint:

- DAP branch checkpoint: `ddc20b9779b8296cfa6216b83d2e1c558972ef9c`
- Runtime version: `0.18.1`
- Protected chat baseline: `1|4|0`
- Knowledge documents: `4`
- Safety baseline: `task_ledger=11`, `owner_notification_outbox=13`, `telegram_notification_deliveries=13`
- Guardian broker: inactive
- Telegram approvals: disabled
- Voice: intentionally disabled

## Authority boundary

### DAP must remain authoritative for

- User identity and owner authority
- Guardian and privileged-action policy
- Telegram approval policy
- Canonical task ledger and audit history
- Canonical Knowledge/Qdrant ownership
- Conversation and attachment ownership
- Systemd, Docker, host administration, and privileged execution
- Final model/tool routing policy
- Human-in-control decisions

### Ruflo may be evaluated for

- Engineering task decomposition
- Coding-agent coordination
- Code review
- Test generation
- Architecture review
- Documentation generation
- Git-diff reasoning
- Development-pattern memory
- Codex orchestration
- Sandboxed browser/test workers

### Ruflo must not receive during evaluation

- Root privileges
- Docker socket access
- systemd control
- Guardian broker socket access
- DAP owner/Telegram secrets
- Direct write access to canonical DAP SQLite databases
- Direct write access to canonical Qdrant collection
- Unrestricted host filesystem access
- Authority to merge to `main`, tag, release, or deploy production

## Target architecture

```text
Owner
  |
  v
DAP UI / API
  |
  v
DAP Router / Engineering Agent
  |
  v
Ruflo Adapter
  |
  +--> Architect worker
  +--> Coder worker
  +--> Reviewer worker
  +--> Tester worker
  |
  v
Codex / approved local model executor
  |
  v
DAP evidence + Guardian-controlled execution boundary
```

Principle: **DAP stays boss. Ruflo becomes an employee.**

## Phase gates

### 10A — Architecture and security audit

Read-only evaluation of Ruflo architecture, dependencies, persistence, MCP tools, Codex integration, autonomy, network behavior, filesystem behavior, and security assumptions.

Exit criteria:
- explicit capability/authority matrix
- threat model
- dependency and persistence inventory
- list of forbidden integrations
- sandbox requirements
- adoption risks documented

No Ruflo installation on the DAP production host in 10A.

### 10B — Isolated sandbox

Create a disposable, non-production environment with strict resource and filesystem boundaries.

Exit criteria:
- no access to DAP secrets or databases
- no Docker socket/systemd/root access
- bounded CPU/RAM/storage
- deterministic teardown
- network policy documented

### 10C — Codex adapter proof of concept

Validate Ruflo's Codex coordination model on a disposable repository/task.

Exit criteria:
- task decomposition works
- Codex executes while Ruflo coordinates
- all writes stay inside sandbox workspace
- no production DAP mutation

### 10D — DAP ↔ Ruflo adapter

Implement a narrow DAP-side adapter for engineering jobs.

Exit criteria:
- typed request/response contract
- explicit timeout/cancellation
- bounded task scope
- evidence captured back into DAP

### 10E — Guardian enforcement boundary

Prove Ruflo cannot directly perform privileged DAP actions.

Exit criteria:
- privileged requests fail closed
- Guardian remains the only privileged policy boundary
- no broker/socket bypass

### 10F — Audit and task-ledger integration

Map Ruflo work into DAP's canonical audit/task model without allowing Ruflo to own canonical state.

### 10G — Local-model compatibility

Evaluate approved local Ollama models for worker tasks where practical.

### 10H — Engineering benchmark

Compare DAP-only vs DAP+Ruflo on representative coding tasks for correctness, tests, latency, token/model use, and operator effort.

### 10I — Resource/performance benchmark

Measure CPU, RAM, disk, process count, startup cost, idle cost, and failure recovery on the Acer-class host.

### 10J — Adoption decision

Choose one:

1. Adopt Ruflo as a subordinate engineering engine.
2. Cherry-pick selected architectural ideas while keeping DAP-native orchestration.
3. Reject Ruflo integration.

No production adoption is implied by completing Phase 10.

## Stop conditions

Stop or redesign the evaluation if Ruflo requires any of the following to function:

- privileged Docker/host access
- replacement of DAP's Guardian or task ledger
- unrestricted canonical Knowledge access
- ownership of DAP identity/authorization
- automatic production deployment or main-branch merge
- opaque execution that cannot be audited back into DAP

## Phase 10A initial observations

At the start of Phase 10, Ruflo presents itself as an agent meta-harness with native Codex integration. Its root package is `claude-flow` version `3.38.12`, requires Node.js `>=20`, and includes MCP, Codex, neural, federation, security, vector-memory, and optional native/vector dependencies. The Codex adapter documents the execution model as Ruflo/Claude-Flow orchestrating state and memory while Codex executes code and commands.

These upstream claims are inputs to the audit, not trusted guarantees. DAP must independently enforce its own boundaries.
