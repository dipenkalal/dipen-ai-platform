# Phase 11 — DAP Autonomous Engineering Agent

Status: **IN PROGRESS**

Branch: `phase11/autonomous-engineering-agent`

Base checkpoint: `de990ec69d2f8210d1c29f987a3752d803e3f8a6`

## Gate status

- 11A — Phase 10 adoption boundary: **COMPLETE**
- 11B — Engineering Agent service: **COMPLETE**
- 11C — Controlled Codex executor: **COMPLETE**
- 11D — Guardian execution admission: **COMPLETE**
- 11E — Git delivery workflow: **COMPLETE / SEALED**
- 11F — Audit + evidence persistence: **COMPLETE / SEALED**
- 11G — Dashboard Engineering workspace: **IN PROGRESS**
- 11H — Disposable engineering benchmark: **PENDING**
- 11I — Owner review workflow: **PENDING**
- 11J — Production-readiness decision: **PENDING**

## Mission

Turn the Phase 10 Ruflo/Codex evaluation into a DAP-owned engineering capability that can prepare, execute, verify, and deliver bounded repository changes for owner review without transferring DAP control-plane authority to Ruflo, Codex, or any other external engineering runtime.

The governing rule remains:

> **DAP stays boss. Engineering runtimes are employees.**

Phase 11 does not authorize automatic merge to `main`, deployment, privileged host administration, Guardian activation, Telegram approval activation, Docker socket access, systemd access, root access, or production-secret exposure.

## Target flow

```text
Owner
  ↓
DAP Chat / Dashboard
  ↓
Executive Office
  ↓ canonical task + validated admission
Engineering Agent
  ↓ bounded work order
DAP-safe planning helpers (optional Ruflo seam)
  ↓
Controlled Codex executor
  ↓
Guardian-owned execution policy
  ↓
Disposable worktree / development branch
  ↓
Tests + diff + evidence
  ↓
Draft PR
  ↓
Owner review
```

## Gates

### 11A — Phase 10 adoption boundary

- Define the Phase 10 components eligible for Phase 11 production wiring.
- Explicitly quarantine benchmark/evaluation-only paths.
- Preserve the Phase 10 package and artifact pins.
- Reject initializer, MCP/plugin registration, unrestricted network, direct host privilege, and autonomous merge/deploy authority.
- Add deterministic adoption-policy tests.

Exit: DAP can prove exactly what was adopted and what remains prohibited.

### 11B — Engineering Agent service

- Introduce a dedicated `engineering-agent` identity distinct from the advisory `coding-agent`.
- Accept only canonical DAP child tasks selected by a validated Executive Office admission.
- Produce a deterministic bounded engineering work order.
- Require repository-relative allowed paths and explicit acceptance criteria.
- Do not execute commands or mutate Git yet.

Exit: canonical DAP authority can be transformed into a no-execution Engineering Agent work order.

### 11C — Controlled Codex executor

- Execute only inside an isolated disposable worktree/repository checkout.
- Fixed executable and bounded argument construction; no arbitrary shell handoff from Ruflo.
- Explicit allowed-path enforcement before and after execution.
- Timeout, output, process, file-count, and repository-boundary limits.
- No root, Docker socket, systemd, Guardian socket, Telegram credentials, DAP data/config DBs, or production secrets.
- Network disabled by default; any later network-enabled mode requires separate DAP policy.

Exit: a harmless disposable coding task can be completed without escaping its work boundary.

### 11D — Guardian execution admission

- Classify engineering operations by privilege and side-effect level.
- Ensure Codex/Ruflo cannot call Guardian directly.
- Require DAP-owned execution admission for each executable operation class.
- Preserve single-use authorization semantics for anything privileged.

Exit: engineering execution cannot bypass DAP/Guardian authority.

### 11E — Git delivery workflow

- Create/update only a Phase 11 development branch or disposable task branch.
- Generate diffs and commits with bounded files.
- Run configured test/lint/type-check gates.
- Open a draft PR for owner review.
- Never auto-merge, tag, release, or deploy.

Exit: an Engineering Agent result can be delivered as a reviewable draft PR.

### 11F — Audit + evidence persistence

Persist DAP-owned evidence for:

- canonical task and admission hashes;
- work-order hash;
- executor/runtime identity;
- allowed paths;
- commands/actions admitted by DAP;
- changed files and diff hash;
- tests/checks and results;
- commit SHA and draft PR number;
- policy/Guardian decisions;
- failure/cancellation information.

Exit: engineering work is replayable and attributable from canonical DAP evidence.

### 11G — Dashboard Engineering workspace

Expose engineering work without granting UI-side execution authority:

- queued/active/completed/failed work orders;
- task and admission provenance;
- files changed;
- checks/tests;
- commit/PR metadata;
- risk/policy state;
- audit evidence.

Exit: owner can inspect Engineering Agent work from DAP.

### 11H — Disposable engineering benchmark

Run multiple harmless tasks against disposable repositories/worktrees and measure:

- task completion rate;
- path-boundary compliance;
- test quality;
- repair loops;
- latency;
- CPU/RAM/storage impact;
- failure recovery;
- evidence completeness.

Exit: empirical reliability baseline exists before routine DAP use.

### 11I — Owner review workflow

Produce a concise review package containing:

- objective;
- files changed;
- tests/checks;
- commit SHA;
- draft PR;
- risk level;
- evidence ID;
- explicit owner action required.

Exit: the owner can approve or reject delivery without terminal archaeology.

### 11J — Production-readiness decision

Choose one:

- enable routine owner-reviewed Engineering Agent work;
- keep experimental only;
- narrow the supported task classes;
- reject production activation.

No Phase 11 outcome grants autonomous merge/deployment authority. That requires a later explicit milestone.

## Phase 10 components considered for adoption

Eligible for review/adoption:

- DAP-owned Ruflo adapter contract and artifact pinning;
- bounded candidate bridge;
- Executive Office handoff validation;
- immutable audit-evidence model;
- DAP audit repository/persistence seam;
- Guardian/Ruflo anti-bypass regression contracts.

Evaluation-only unless explicitly promoted by a later gate:

- Phase 10 benchmark harnesses and benchmark conclusions;
- full Ruflo runtime installation;
- Ruflo/Codex initializer paths;
- MCP/plugin auto-registration;
- upstream-generated Codex configuration;
- direct arbitrary Ruflo CLI execution;
- local Ollama compatibility probes as an execution mechanism.

## Safety invariants

Throughout Phase 11:

1. DAP owns canonical task truth and owner authorization.
2. Executive Office owns delegation/admission.
3. Guardian owns privileged-action policy.
4. The Engineering Agent receives bounded authority; it does not create authority.
5. Ruflo is optional planning/coordination assistance, never the control plane.
6. Codex is an executor, never the policy authority.
7. Repository changes occur only in explicitly admitted paths and branches/worktrees.
8. `main` merge, tag, release, deployment, and host privilege remain owner-controlled.
9. Production DAP data/config/secrets are not part of the engineering workspace.
10. Every accepted engineering outcome must be evidenced and reviewable.
