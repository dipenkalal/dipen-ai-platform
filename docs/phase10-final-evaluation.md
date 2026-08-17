# Phase 10 — Ruflo Final Evaluation

## Decision

**ADAPT SELECTED COMPONENTS ONLY. Do not adopt the full Ruflo runtime on the Acer host.**

DAP remains the engineering control plane. The only Ruflo-derived surface admitted by this evaluation is the pinned `@claude-flow/codex@3.0.2` pure generator/validator seam behind DAP-owned policy wrappers. Ruflo does not receive task authority, owner authority, Guardian authority, direct Ollama authority, MCP/plugin registration, root, systemd, Docker, canonical Knowledge ownership, or production deployment authority.

This is deliberately narrower than either full adoption or full rejection: selected pure functions are useful as untrusted candidate-generation/validation helpers, while the autonomous/full Ruflo runtime is rejected for the current host and architecture.

## Final gate ledger

| Gate | Result | Evidence-based conclusion |
|---|---|---|
| 10A Architecture/security audit | COMPLETE | Full Ruflo authority model is too broad for direct DAP adoption; strict subordinate boundary required. |
| 10B Isolated sandbox | COMPLETE | Full npm provisioning was unreliable/impractical on Acer; standalone Codex adapter was provisionable. |
| 10C Codex adapter PoC | COMPLETE | Pure generator/validator seam works; ordinary initializer is blocked because it can mutate Codex/MCP/plugin state and generate unsafe config. |
| 10D DAP ↔ Ruflo adapter | COMPLETE | Typed contract, candidate bridge, Executive Office handoff, and immutable evidence chain all keep execution authority false. |
| 10E Guardian boundary | COMPLETE SUBJECT TO FINAL CI | Phase-10 regressions prove non-root callers fail before privileged execution and Guardian exposes no arbitrary Ruflo command surface. |
| 10F Audit/task integration | COMPLETE SUBJECT TO FINAL CI | Additive immutable evidence persistence references canonical task IDs without mutating task-ledger truth. |
| 10G Ollama compatibility | COMPLETE SUBJECT TO FINAL CI | Selected pure Ruflo seam needs no model runtime; DAP Ollama provider remains the only local-model boundary. |
| 10H Engineering benchmark | COMPLETE — CONSTRAINED RESULT | Full Ruflo coding benchmark is not justified because the full runtime could not be provisioned reliably and the admitted seam does not execute code. DAP-native execution therefore remains the engineering executor baseline. |
| 10I Acer resource/performance | COMPLETE — CONSTRAINED RESULT | Narrow adapter is lightweight enough for use; full Ruflo provisioning cost/reliability is unacceptable on the current host. No new peak-CPU claim is made. |
| 10J Adoption decision | COMPLETE | Adapt/cherry-pick only; reject full runtime adoption now. |

## 10E — Guardian enforcement boundary

The existing Guardian implementation already enforces a fixed privileged action: restart of `dap-backend.service`. It requires effective UID 0, validates a reserved Guardian plan, consumes a single-use root authorization, and does not accept an arbitrary command argument.

Phase 10 adds `platform/guardian/tests/test_phase10_ruflo_boundary.py` so Ruflo integration cannot silently weaken that boundary. The regression suite asserts:

- the executor command is fixed and contains no Ruflo/Node/shell executable;
- non-root execution fails before `subprocess.run`;
- non-root orchestration fails before plan validation or executor invocation;
- non-root callers cannot issue root authorization;
- the root authorization API exposes no caller-supplied action/command/target;
- the privileged execution API exposes no arbitrary command or shell parameter.

No Guardian production service is enabled by this evaluation.

## 10F — audit/task-ledger integration

`engineering/ruflo_audit_repository.py` persists Phase 10D evidence into a dedicated `ruflo_audit_evidence` table in the DAP truth database abstraction.

Important properties:

- evidence rows are immutable by evidence ID;
- an identical replay is idempotent;
- an evidence-ID/content mismatch fails closed;
- rows are indexed by canonical `source_task_id` and request ID;
- the repository **does not update `task_ledger`**;
- the persisted record explicitly reports `task_ledger_mutated=false`.

This gives DAP a durable provenance link to canonical task truth without allowing Ruflo to own or rewrite task state.

## 10G — local Ollama compatibility

DAP already owns an Ollama provider under `gateway/providers/ollama.py`, including a configurable base URL and `/api/tags`/`/api/chat` integration. The selected Ruflo seam consists only of pure generator/validator functions and therefore requires no model inference itself.

The Phase 10 compatibility contract intentionally says:

- Ruflo may not configure Ollama;
- Ruflo may not call Ollama directly;
- Ruflo may not replace the DAP provider;
- any future local-model execution remains routed by DAP.

A live Ollama generation is not required to prove compatibility of this selected non-inference seam. This avoids introducing a new network/model authority solely for the evaluation.

## 10H — engineering benchmark

The benchmark question was whether DAP+Ruflo improves representative coding work enough to justify the added orchestration layer.

Observed evidence:

- the admitted adapter generates/validates a small AGENTS guidance candidate and does not produce an executable code patch;
- the DAP-owned bridge and policy layer work reliably and deterministically;
- full Ruflo CLI provisioning repeatedly timed out/hung on the Acer environment;
- ordinary Ruflo initialization would create local state and attempt Codex MCP/plugin registration, which violates the evaluation boundary;
- no safe full-runtime coding path was available without weakening the control model.

Therefore a full DAP-only versus DAP+Ruflo code-execution race would test an architecture that the security/provisioning gates have already rejected. The benchmark result is **no demonstrated coding-execution advantage sufficient to justify full Ruflo adoption**. The useful measured contribution is limited to candidate guidance/validation.

## 10I — Acer resource/performance benchmark

Runtime evidence collected during the evaluation:

- Acer baseline: approximately 11 GiB RAM total with roughly 9.3 GiB available at the audit checkpoint; swap unused; about 54–55 GiB disk free;
- full `ruflo@3.38.12` installation attempts timed out/hung and were aborted/cleaned;
- minimal full CLI provisioning also exceeded the bounded install window;
- standalone `@claude-flow/codex@3.0.2` installed with 59 packages in about 3 seconds and occupied about 18 MiB;
- the candidate gate/bridge leaves no persistent Ruflo process or listener;
- evidence outputs are only small Markdown/JSON artifacts;
- no production daemon, MCP server, plugin, or Ruflo memory service is retained.

No claim is made for an unmeasured peak CPU/RSS value. The resource conclusion is based on provisioning reliability, disk footprint, retained processes, and observed bounded execution: **narrow adapter acceptable; full runtime unacceptable on this host today.**

## 10J — adoption matrix

### Adopt now

- DAP-owned typed Ruflo request/receipt models;
- DAP-owned candidate bridge;
- DAP-owned Executive Office handoff;
- immutable evidence chain and additive audit persistence;
- pinned pure `@claude-flow/codex@3.0.2` generator/validator functions only;
- independent DAP policy scanning of every generated candidate.

### Explicitly reject now

- full Ruflo CLI/runtime installation on production Acer;
- Ruflo `init` in the live DAP repository;
- Ruflo MCP registration;
- Ruflo/Codex plugin installation;
- upstream-generated Codex config as executable policy;
- Ruflo-owned memory as canonical DAP memory;
- direct Ruflo Ollama calls;
- arbitrary Ruflo shell execution;
- Docker/systemd/root/Guardian access;
- task-ledger ownership;
- automatic merge, release, or deployment.

### Re-evaluation triggers

A future full-runtime evaluation requires a new phase if any of the following materially change:

- a smaller, reliably installable Ruflo execution component becomes available;
- Ruflo exposes a documented no-MCP/no-plugin/no-init execution mode;
- artifact/version drift occurs from the pinned adapter;
- DAP creates a Guardian-mediated Codex executor path suitable for disposable coding benchmarks;
- host resources change enough to justify repeating the full-runtime performance test.

## Final architecture

```text
Owner
  ↓
DAP UI / API
  ↓
DAP Executive Office + canonical task truth
  ↓
DAP Ruflo handoff
  ↓
DAP candidate bridge + policy gate
  ↓
pinned pure Ruflo generator/validator functions
  ↓
DAP audit evidence

Future execution, if separately authorized:
DAP → Guardian → approved executor
```

Ruflo never becomes a peer control plane.

## Production status

Phase 10 does **not** merge to `main`, tag, release, enable Guardian, enable Telegram approvals, register MCP, install plugins, or create a production Ruflo daemon. The evaluation branch remains isolated until the owner explicitly decides how to consume the selected changes.
