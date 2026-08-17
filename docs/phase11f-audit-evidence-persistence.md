# Phase 11F — Audit + Evidence Persistence

## Status

**COMPLETE / SEALED.** Phase 11 engineering work now has a DAP-owned immutable evidence model, exact commit-diff evidence, additive persistence beside canonical Agent Truth, deterministic replay semantics, and Guardian anti-privilege regression coverage.

## Purpose

Phase 11F makes every terminal Engineering Agent attempt attributable and replayable without transferring task authority to Codex, Ruflo, GitHub, or the engineering evidence store.

The governing storage rule is:

> Engineering evidence references canonical DAP task truth; it does not rewrite canonical DAP task truth.

## Evidence chain

The persisted evidence binds the complete Phase 11 authority and delivery chain:

```text
canonical child task + Executive admission
  ↓ hashes
EngineeringWorkOrder
  ↓ hash
CodexExecutionTicket
  ↓ hash
EngineeringGuardianAdmission
  ↓ hash
Codex execution receipt + runtime/command identity
  ↓
changed-file set + exact binary commit-diff SHA-256
  ↓
GitDeliveryPlan + local delivery receipt + commit SHA
  ↓
RemoteGitPublicationPlan + publication receipt
  ↓
draft PR metadata
  ↓
EngineeringAuditEvidence
  ↓ immutable additive persistence
engineering_audit_evidence table
```

## DAP-owned implementation

Phase 11F adds:

- `platform/backend/engineering/engineering_diff_evidence.py`
- `platform/backend/engineering/engineering_audit_evidence.py`
- `platform/backend/engineering/engineering_audit_repository.py`
- `platform/backend/tests/test_engineering_diff_evidence.py`
- `platform/backend/tests/test_engineering_audit_evidence.py`
- `platform/backend/tests/test_engineering_audit_repository.py`

The dedicated Phase 11 workflow now includes those files in Ruff, mypy, compile, and pytest coverage.

## Canonical evidence fields

`EngineeringAuditEvidence` version `phase11f.1` binds:

- canonical source execution, delegation, parent-task, and child-task identifiers;
- canonical source task SHA-256;
- Executive admission SHA-256;
- work-order ID and SHA-256;
- Codex ticket ID and SHA-256;
- Guardian admission ID, SHA-256, and fixed non-privileged risk class;
- pinned executor runtime identity;
- exact admitted command SHA-256 when execution starts;
- allowed repository paths;
- DAP-admitted action classes;
- DAP/Guardian/owner policy decisions;
- execution receipt hash, disposition, exit code, findings, and changed files;
- exact committed diff SHA-256;
- lint/type-check/compile/test/CI/policy check results;
- delivery ID, plan hash, receipt hash, and commit SHA;
- remote-publication ID, plan hash, receipt hash, delivery branch, and remote commit SHA;
- draft PR number, URL, and draft state;
- terminal outcome and stage;
- failure information or cancellation information when applicable.

The model permanently preserves the Phase 11 prohibitions as evidence fields: no GitHub credentials exposed to Codex/Ruflo, no Codex/Ruflo Git authority, no force push, no protected-branch update, no PR auto-merge, no main merge, no tag, no release, no deployment, and no task-ledger mutation.

## Terminal evidence shapes

The service supports three validated terminal paths.

### Successful delivery

A successful record is accepted only when the complete execution → local commit → diff → remote publication chain is mutually bound and all required delivery fields are present. It requires at least one passed check and rejects any failed check. The resulting PR must remain draft.

### Failed or rejected execution

A failed/rejected record captures the bounded execution receipt, findings, changed-file observation, check results if any, terminal stage, and explicit failure information. Delivery/publication evidence is not fabricated when the run did not reach those stages.

### Cancelled before execution

A pre-execution cancellation preserves the admitted work-order/ticket/Guardian authority chain but records `execution_disposition=not_started` plus explicit cancellation information. It does not pretend that Codex, Git, or GitHub actions occurred.

## Exact diff evidence

`EngineeringDiffEvidenceCapture` operates only on the isolated local delivery repository after the exact commit has been created.

It verifies:

- repository HEAD equals the recorded local commit SHA;
- HEAD parent equals the original source commit;
- changed files equal the delivery receipt allowlist;
- the delivery repository still has zero remotes.

It then hashes the exact binary Git diff (`HEAD^..HEAD`) with SHA-256. This gives 11F a canonical content fingerprint in addition to the commit SHA and file list.

## Persistence boundary

`EngineeringAuditRepository` uses the existing `AgentTruthRepository` connection abstraction and creates a dedicated additive table:

`engineering_audit_evidence`

The table is indexed by source task, work order, and outcome. It stores the immutable evidence JSON and its canonical SHA-256 alongside selected lookup fields.

Persistence rules:

1. The source task must already exist in canonical `task_ledger`.
2. The evidence ID is deterministic and immutable.
3. Identical replay is idempotent and returns the existing stored record.
4. Reusing an evidence ID with different content raises `EngineeringAuditPersistenceConflict`.
5. Persisting engineering evidence never calls `upsert_task` and never changes `task_ledger`.
6. Read paths support exact evidence lookup, task history, work-order history, and bounded recent-history listing.

No Phase 11F CI/test work writes to the production Agent Truth database; repository tests use temporary SQLite databases.

## Guardian boundary

Phase 11 Guardian regression coverage now treats the 11F evidence/diff/persistence modules as non-privileged code. They may not import Guardian/root authorization clients or gain systemd, Docker-socket, broker, root, merge, release, or deployment authority.

The Guardian broker remains outside the engineering evidence persistence path.

## Validation seal — 2026-08-17

Validated Phase 11 implementation head before this documentation seal:

`3c244cc8ecc2f3e3728a3b0b293bfba98cbe0a35`

GitHub Actions results for that head:

- Repository `CI`: **success**;
- `Phase 10 Ruflo Evaluation`: **success**;
- `Phase 7 Owner Channel`: **success**;
- `Phase 11 Engineering Agent`: **success**.

Dedicated Phase 11 backend-engineering evidence:

- Ruff: **pass**;
- mypy: **success, no issues in 15 source files**;
- compile: **pass**;
- Phase 11 engineering tests: **142 passed, 1 external pytest-asyncio deprecation warning**.

Dedicated Guardian boundary job: **pass**.

Repository baseline CI on the same head also passed its Guardian, backend, and dashboard gates; the backend suite reported **241 passed**.

## Exit criteria

Phase 11F exit criteria are satisfied:

- canonical task and admission hashes are preserved;
- work-order/ticket/Guardian hashes are preserved;
- executor/runtime and admitted command identity are preserved;
- allowed paths and admitted action classes are preserved;
- changed files and exact binary diff hash are preserved;
- checks and results are preserved;
- commit and draft-PR metadata are preserved;
- policy/Guardian decisions are preserved;
- failure/rejection/cancellation paths are explicit;
- persistence is immutable and idempotent;
- conflicting evidence IDs fail closed;
- canonical task existence is required;
- task-ledger mutation remains false;
- no production DB mutation was required to validate the gate.

**Phase 11F is sealed.**
