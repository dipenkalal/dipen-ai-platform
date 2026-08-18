# Phase 12F — Citation + Retrieval Evidence Persistence

Status: **COMPLETE / SEALED**

Sealed implementation checkpoint: `1317afb403b4c5589d8b809ce9422d2937b10a0f`

## Purpose

Persist attributable public-internet retrieval outcomes as immutable DAP-owned evidence without allowing research retrieval to rewrite canonical task truth or Knowledge.

## Evidence chain

```text
ResearchRequest
  ↓
12C destination admission
  ↓
12D bounded retrieval
  ↓
12E untrusted content evidence
  ↓
ResearchRetrievalEvidence + ResearchCitation
  ↓
research_retrieval_evidence table
```

The evidence table is additive and lives beside canonical task truth.

## Immutable evidence

Successful evidence binds:

- research request ID/hash;
- source-registry hash;
- optional canonical task/admission binding;
- public-web provider identity;
- requested/final URL and method;
- transport identity;
- HTTP status, content type, byte count and source-body hash;
- normalized content evidence ID/hash/text hash/title;
- prompt-injection finding rule IDs as diagnostic metadata;
- per-hop destination admission hashes and connected addresses;
- deterministic citation identity;
- timezone-aware observation timestamp;
- permanent non-mutation/non-privilege flags.

Failure and cancellation outcomes are first-class terminal evidence with stage, error code/detail and no fabricated citation.

## Citation contract

`ResearchCitation` is derived only from DAP-owned terminal evidence. It binds the research request, provider, source URL/title, normalized content evidence identity/hash and retrieval timestamp.

Remote content cannot supply or override citation identity.

## Persistence contract

`ResearchRetrievalRepository` creates the additive table `research_retrieval_evidence` with request/task/outcome indexes.

Persistence behavior:

- validates the canonical evidence hash before storage;
- if task-bound, requires the canonical DAP task to already exist;
- standalone research evidence may exist without creating a task;
- never inserts/updates/deletes `task_ledger`;
- never writes Knowledge/Qdrant;
- uses `BEGIN IMMEDIATE` for immutable ID arbitration;
- exact replay is idempotent;
- same evidence ID with different content fails closed with `ResearchRetrievalPersistenceConflict`;
- supports exact lookup and bounded request/task/recent listing.

Persisted records permanently declare:

```text
evidence_persisted = true
task_ledger_mutated = false
knowledge_mutated = false
```

## Determinism defect found and fixed

The first behavior run exposed a timestamp canonicalization mismatch: the factory hashed UTC timestamps as `+00:00` while Pydantic serialized the same UTC instant as `Z`. The evidence validator correctly rejected every mismatch.

The factory now uses one canonical JSON datetime serializer, making creation, validation, replay and persistence deterministic.

No production database was touched while diagnosing or fixing this issue.

## Test evidence

The Phase 12 suite covers:

- successful citation/evidence binding;
- deterministic evidence identity;
- prompt-injection findings as metadata only;
- failure evidence;
- cancellation evidence;
- public-web source requirement;
- mismatched normalized content rejection;
- timezone-awareness enforcement;
- task-bound persistence without task mutation;
- standalone persistence without task creation;
- missing canonical-task rejection;
- idempotent replay;
- conflicting evidence-ID rejection;
- tampered-hash rejection;
- failure/cancellation queryability;
- bounded listing.

All 112 Phase-12 boundary/persistence tests passed at the sealed checkpoint, together with Ruff, mypy, compile and the Guardian boundary.

Repository CI backend, Guardian and dashboard jobs, Phase 11 regression and Phase 10 regression also passed on the same implementation checkpoint.

## Authority statement

12F does not expose network tools to agents, mutate task/Knowledge truth, contact Guardian, grant privileged access, or authorize merge/release/deployment. Research Agent integration remains gated to 12G.
