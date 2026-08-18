# Phase 10D — DAP ↔ Ruflo Adapter Contract

## Status

Phase 10C is complete. The standalone `@claude-flow/codex` adapter may be used only through selected pure generator and validator functions. Ruflo initializer, Codex CLI execution, MCP registration, plugin installation, upstream-generated Codex configuration, and privileged execution remain prohibited.

Phase 10D now has a tested typed boundary, a tested sandbox candidate bridge, a tested Executive Office handoff, and an immutable audit-evidence implementation ready for Acer verification.

## Governing rule

**DAP stays boss. Ruflo remains a bounded engineering employee.**

Ruflo may provide non-executable engineering guidance. DAP owns task identity, policy, authorization, audit, execution admission, Guardian integration, and the final Codex execution envelope.

## Components

- `platform/backend/engineering/ruflo_adapter_contract.py`
- `platform/backend/engineering/ruflo_candidate_bridge.py`
- `platform/backend/engineering/ruflo_executive_handoff.py`
- `platform/backend/engineering/ruflo_audit_evidence.py`
- focused tests under `platform/backend/tests/test_ruflo_*.py`

## Allowed request surface

The Phase 10D request contract permits only:

- `generate_agents`
- `validate_agents`
- validation-only behavior
- explicitly scoped engineering task metadata
- explicitly listed repository-relative allowed paths
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

Every admitted or rejected Ruflo candidate is represented by a DAP-owned receipt containing request identity, exact adapter identity, candidate hash when applicable, upstream-validation status, DAP-owned policy findings, explicit side-effect flags, and final disposition.

The receipt schema rejects claims that the initializer, Codex CLI, MCP registration, plugin installation, upstream-config write, or execution was started.

## Relationship to existing DAP authority

Phase 10D is subordinate to the Executive Office and canonical task ledger. Existing DAP delegation and execution admission separate planning, authorization, task truth, and execution. Ruflo candidate generation remains advisory/validation work and cannot create canonical DAP tasks, owner approvals, reservations, or execution authority.

No Phase 10D object grants owner authorization, Guardian permission, shell privileges, Docker/systemd access, database/Qdrant access, network access, Git push/merge/release authority, or Codex execution authority.

## 10D gates

### 10D.1 — typed boundary — COMPLETE

The DAP-owned request/receipt schemas pin the evaluated Ruflo artifact and reject authority expansion at validation time.

Acer verification:

```text
11 passed, 1 warning in 0.09s
pytest_exit|0
```

The warning is the existing `pytest-asyncio` Python 3.14 deprecation warning.

### 10D.2 — candidate bridge — COMPLETE

`RufloCandidateBridge` invokes only `scripts/phase10-codex-adapter-gate.mjs`, the DAP-owned Phase 10C generator gate. It is not wired into the production API.

The bridge uses an explicit Node path, an isolated evidence directory outside source, a bounded timeout, argument-vector execution without a shell, a reduced environment, artifact re-verification, output-file allowlisting, independent Python policy scanning, and fail-closed conversion of malformed/tampered evidence into rejected receipts.

Acer verification completed with:

```text
20 passed, 1 warning
pytest_exit|0
All checks passed!
ruff_exit|0
```

The real sandbox smoke produced an accepted validation-only receipt, no Ruflo/Codex process or listener remained, DAP stayed clean, Guardian stayed inactive, and Telegram approvals stayed disabled.

### 10D.3 — Executive Office handoff — COMPLETE

`RufloExecutiveHandoffService` maps only a canonical `assigned` child task plus a validated, validation-only Executive Office admission into the bounded Ruflo request contract.

It verifies task/delegation/parent/agent identity, rejects any admission that already contains task mutation, reservations, execution, or broker activation, and binds SHA-256 hashes of the canonical task and admission snapshots. Scope paths must be repository-relative POSIX paths.

The handoff explicitly records:

- `canonical_task_created = false`
- `owner_approval_created = false`
- `execution_authority_transferred = false`

Acer verification completed with:

```text
47 passed, 1 warning
pytest_exit|0
All checks passed!
ruff_exit|0
smoke_exit|0
```

### 10D.4 — audit evidence — CODE READY / ACER TEST PENDING

`RufloAuditEvidenceService` binds the complete validation-only provenance chain:

```text
canonical DAP child task
  -> Executive Office admission
  -> Ruflo handoff
  -> Ruflo bridge receipt
  -> frozen DAP audit evidence
```

The evidence stores task/admission/handoff/request/receipt hashes, exact adapter identity, candidate hash and disposition, upstream validation, DAP policy findings, and explicit no-authority/no-execution flags. The object is frozen after construction and exposes a deterministic canonical SHA-256.

The service fails closed on request ID/hash mismatch, artifact identity mismatch, handoff authority transfer, bridge execution side effects, accepted candidates without a hash/upstream validation, accepted candidates with blocked policy findings, or rejected candidates without findings.

10D.4 intentionally does not persist evidence. `evidence_persisted = false` remains part of the model; durable persistence belongs to Phase 10F after the Phase 10E Guardian-boundary evaluation.

## Current boundary

No production runtime path has changed. Phase 10D components remain backend library code plus focused tests. Ruflo initializer execution, Codex CLI execution through Ruflo, MCP registration, plugin installation, upstream-generated Codex configuration, network access, privileged execution, and production persistence remain prohibited.
