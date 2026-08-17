# Phase 10D — DAP ↔ Ruflo Adapter Contract

## Status

Phase 10C is complete. The standalone `@claude-flow/codex` adapter may be used only through selected pure generator and validator functions. Ruflo initializer, Codex CLI execution, MCP registration, plugin installation, upstream-generated Codex configuration, and privileged execution remain prohibited.

Phase 10D starts with a DAP-owned typed contract that prevents Ruflo from expanding its own authority.

## Governing rule

**DAP stays boss. Ruflo remains a bounded engineering employee.**

Ruflo may provide non-executable engineering guidance. DAP owns task identity, policy, authorization, audit, execution admission, Guardian integration, and the final Codex execution envelope.

## Contract location

- `platform/backend/engineering/ruflo_adapter_contract.py`
- tests: `platform/backend/tests/test_ruflo_adapter_contract.py`

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

### 10D.1 — typed boundary

- add the DAP-owned request/receipt schemas;
- pin the evaluated Ruflo artifact;
- reject authority expansion at schema validation;
- add focused unit tests.

### 10D.2 — candidate bridge

Build an adapter service that can invoke only the approved Phase 10C generator gate and convert its receipt into the typed DAP receipt. It must remain validation-only and disabled for production execution.

### 10D.3 — Executive Office handoff

Map an already-authorized DAP engineering task into the Ruflo request envelope without allowing Ruflo to create canonical DAP tasks, owner approvals, or execution authorizations.

### 10D.4 — audit evidence

Persist or expose exact request hash, adapter artifact identity, generated candidate hash, DAP policy result, and no-execution evidence for later Phase 10F task-ledger/audit integration.

## Current boundary

At completion of 10D.1, no Ruflo process is started by the backend and no production runtime path is changed. The new code only defines and tests the safe contract that later adapter code must obey.
