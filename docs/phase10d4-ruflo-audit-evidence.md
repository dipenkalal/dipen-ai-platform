# Phase 10D.4 — Ruflo Audit Evidence Chain

## Purpose

Phase 10D.4 creates a DAP-owned provenance object that binds the complete validation-only Ruflo path without persisting it yet.

The chain is:

```text
canonical DAP child task
  -> Executive Office validation-only admission
  -> Phase 10D.3 handoff
  -> Phase 10D.2 Ruflo candidate receipt
  -> Phase 10D.4 immutable audit evidence
```

Ruflo does not become a source of canonical task identity, owner approval, execution authorization, or audit authority.

## Implementation

- `platform/backend/engineering/ruflo_audit_evidence.py`
- `platform/backend/tests/test_ruflo_audit_evidence.py`

`RufloAuditEvidenceService.build()` accepts only an already-created `RufloExecutiveHandoff` plus its DAP-owned `RufloAdapterReceipt`.

## Bound provenance

The evidence object records:

- canonical execution ID;
- delegation ID;
- parent task ID;
- child task ID;
- SHA-256 of the canonical source task snapshot;
- SHA-256 of the Executive Office admission snapshot;
- SHA-256 of the complete handoff object;
- Ruflo request ID and deterministic request SHA-256;
- exact pinned Ruflo adapter identity;
- SHA-256 of the complete bridge receipt;
- candidate disposition;
- candidate artifact SHA-256 when accepted;
- upstream validation result;
- DAP-owned policy findings;
- explicit no-execution / no-authority flags.

The evidence object is Pydantic-frozen after creation and exposes a deterministic `canonical_hash()` for later persistence and audit verification.

## Fail-closed chain checks

Evidence creation fails if:

- bridge receipt request ID differs from the handoff;
- bridge receipt request hash differs from the handoff request hash;
- adapter package/hash identity differs between handoff and receipt;
- the handoff claims task creation, owner approval creation, or authority transfer;
- the bridge receipt claims initializer, Codex CLI, MCP, plugin, upstream-config, or execution activity;
- an accepted receipt lacks upstream validation;
- an accepted receipt lacks a candidate artifact SHA-256;
- an accepted receipt contains a blocked DAP policy finding;
- a rejected receipt contains no DAP policy finding.

These checks are repeated even though earlier contract models already constrain many of the same fields. The audit boundary therefore detects objects tampered through unvalidated copies or alternate in-process construction.

## No persistence in 10D.4

Phase 10D.4 deliberately does **not** write this evidence into the task ledger, truth database, chat database, Knowledge, Qdrant, or a new audit table.

The evidence object records `evidence_persisted = false`.

Persistence belongs to Phase 10F, after the Guardian enforcement boundary in 10E has been evaluated. This keeps Phase 10D limited to mapping, validation, provenance, and audit-object construction.

## Authority boundary

The evidence object cannot authorize:

- Codex execution;
- Guardian activation;
- broker activation;
- task state transitions;
- reservations;
- Docker or systemd access;
- network access;
- MCP registration;
- plugin installation;
- Git push, merge, tag, or release operations.

The Phase 10 principle remains: **DAP stays boss; Ruflo remains a bounded engineering employee.**
