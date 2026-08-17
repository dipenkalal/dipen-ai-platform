# Phase 10D — DAP ↔ Ruflo Adapter Contract

## Status

Phase 10C is complete. The standalone `@claude-flow/codex` adapter may be used only through selected pure generator and validator functions. Ruflo initializer, Codex CLI execution, MCP registration, plugin installation, upstream-generated Codex configuration, and privileged execution remain prohibited.

Phase 10D now has a tested DAP-owned typed contract and a candidate bridge implementation ready for sandbox verification.

## Governing rule

**DAP stays boss. Ruflo remains a bounded engineering employee.**

Ruflo may provide non-executable engineering guidance. DAP owns task identity, policy, authorization, audit, execution admission, Guardian integration, and the final Codex execution envelope.

## Contract location

- `platform/backend/engineering/ruflo_adapter_contract.py`
- contract tests: `platform/backend/tests/test_ruflo_adapter_contract.py`
- candidate bridge: `platform/backend/engineering/ruflo_candidate_bridge.py`
- bridge tests: `platform/backend/tests/test_ruflo_candidate_bridge.py`

## Allowed request surface

The Phase 10D request contract permits only:

- `generate_agents`
- `validate_agents`
- validation-only behavior
- explicitly scoped engineering task metadata
- explicitly listed allowed repository paths
- the exact evaluated adapter artifact pin

The evaluated artifact pin is:

- package: `@claude-flow/codex`
- npm package version: `3.0.2`
- installed CLI SHA-256: `1df00b5aa26c6d76b354bbf2d80042c9c91e83b877c7bacc22f96ee098bea096`

Any package-version or artifact-hash drift requires a new evaluation before admission.

## Prohibited request surface

Schema validation rejects requests that attempt to enable any of the following:

- Ruflo initializer
- Codex CLI invocation
- MCP registration
- Codex/Ruflo plugin installation
- writing upstream-generated Codex configuration
- network-requiring engineering work
- privileged execution
- non-validation execution mode

These are contract violations, not optional warnings.

## Receipt contract

Every admitted or rejected Ruflo candidate is represented by a DAP-owned receipt containing:

- request ID
- deterministic request SHA-256
- exact adapter artifact pin
- candidate artifact SHA-256 when applicable
- upstream-validation status
- DAP-owned policy findings
- explicit side-effect flags
- final disposition

The receipt schema itself rejects any claim that the initializer, Codex CLI, MCP registration, plugin installation, upstream config write, or execution was started.

An accepted receipt additionally requires:

- upstream validation passed;
- zero blocked DAP policy findings.

A rejected receipt requires at least one DAP policy finding and still records all execution paths as false.

## Relationship to existing DAP authority

The contract is intentionally subordinate to the Executive Office and task-ledger model. Existing DAP delegation already separates planning/delegation from execution and records parent/child tasks without starting workers or the broker. Phase 10D follows the same principle: Ruflo candidate generation is advisory/validation work, not execution authorization.

No Phase 10D contract object grants:

- owner authorization;
- Guardian permission;
- shell privileges;
- Docker/systemd access;
- database or Qdrant access;
- network access;
- Git push/merge/release authority;
- Codex execution authority.

## 10D gates

### 10D.1 — typed boundary — COMPLETE

The DAP-owned request/receipt schemas pin the evaluated Ruflo artifact and reject authority expansion at validation time.

Acer verification used the backend virtual environment and completed:

```text
11 passed, 1 warning in 0.09s
pytest_exit|0
```

The warning was an existing `pytest-asyncio` deprecation warning under Python 3.14 and was unrelated to the Phase 10 contract. The import smoke also confirmed all execution-expansion flags remained false and produced a deterministic 64-character request SHA-256. DAP source remained clean, Guardian remained inactive, and Telegram approvals remained disabled.

### 10D.2 — candidate bridge — CODE READY / SANDBOX TEST PENDING

`RufloCandidateBridge` may invoke only `scripts/phase10-codex-adapter-gate.mjs`, the DAP-owned Phase 10C generator gate. It is not wired into the production API.

The bridge:

- requires an explicit absolute Node binary;
- requires the evidence directory to be outside the DAP source tree;
- enforces a maximum 30-second configured timeout and uses 15 seconds by default;
- starts the gate with an argument vector rather than shell execution;
- provides a reduced environment with an isolated HOME;
- re-verifies npm package version and CLI SHA-256 from the gate receipt;
- requires upstream validation success for the AGENTS candidate;
- requires the upstream generated-config negative control to be rejected by DAP;
- requires initializer, Codex CLI, MCP, plugin, and upstream-config-write evidence to remain false;
- permits exactly `AGENTS.candidate.md` and `adapter-gate-receipt.json` as output files;
- independently scans the candidate again in Python for DAP-denied execution patterns;
- hashes the accepted candidate and binds that hash to the typed DAP receipt;
- converts timeouts, process failures, evidence tampering, release drift, unsafe candidates, or unexpected output into rejected no-execution receipts.

It does not call Ruflo `init`, Codex, MCP, plugins, Docker, systemd, Guardian, or any production executor.

### 10D.3 — Executive Office handoff

Map an already-authorized DAP engineering task into the Ruflo request envelope without allowing Ruflo to create canonical DAP tasks, owner approvals, or execution authorizations.

### 10D.4 — audit evidence

Persist or expose exact request hash, adapter artifact identity, generated candidate hash, DAP policy result, and no-execution evidence for later Phase 10F task-ledger/audit integration.

## Current boundary

At the current 10D.2 checkpoint, no production runtime path has changed. The bridge exists only as backend library code plus focused tests. Phase 10 still prohibits Ruflo initializer execution, Codex CLI execution through Ruflo, MCP registration, plugin installation, upstream-generated Codex configuration, network access, and privileged execution.
