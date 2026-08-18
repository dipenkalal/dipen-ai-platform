# Phase 13 — Provider-Specific Research Activation Live Evidence

Date: 2026-08-18

Status: **LIVE EVIDENCE GATE PASSED**

Validated source checkpoint: `3f7dc4318abe165629e59cf45264c781d7a6784f`

Phase 12 base merge: `4ca48a1d68e3f90f43265017befe0ce7c263229c`

## Live activation result

The bounded provider-specific research path was activated and validated on the Acer production host.

The successful manual run used:

- mode: `manual`;
- agent: `research-agent`;
- provider: fixed local `searxng-local-v1`;
- research run ID: `801daf77-af76-49bb-a45d-fb414cb2fc11`;
- selected candidate URLs: bounded to at most three;
- all selected URLs passed through the sealed Phase 12 retrieval/evidence path.

Live negative authority proofs also passed:

- smart-routing search request rejected;
- non-Research-Agent search request rejected;
- provider titles/snippets remained discovery metadata only;
- no generic model-visible network client was exposed;
- no remote-scope expansion was granted.

## Persistent evidence

Before Phase 13 manual activation:

- `research_retrieval_evidence`: 7
- `task_ledger`: 11

After the successful manual Research Agent run:

- `research_retrieval_evidence`: 10
- `task_ledger`: 12

The three new retrieval-evidence rows are expected immutable Internet Evidence produced by the bounded retrieval path.

The single additional task-ledger row is also expected. Normal runtime instrumentation creates exactly one `agent` task for an instrumented manual agent execution and later upserts the same task through completion with the run ID.

The live row was proven to be:

- task ID: `agent-task-292c8d68-1d69-4fd3-b716-a4dadb99b076`;
- status: `completed`;
- requested by: `agent-api`;
- assigned agent: `research-agent`;
- source run ID: `801daf77-af76-49bb-a45d-fb414cb2fc11`;
- ledger delta: exactly `+1`.

No unrelated task-ledger mutation was accepted.

## Dashboard closure

The first dashboard closure attempt exposed a pre-existing ownership issue: the generated `.next` tree was root-owned from an earlier container build. The recovery path was hardened to remove only the fixed generated `apps/dashboard/.next` path when privileged cleanup is required and then rebuild as the normal host UID.

Final dashboard closure passed:

- generated `.next` cleanup: PASS;
- offline Next.js application build: PASS;
- runtime image build without npm network install: PASS;
- new image: `sha256:b8f861c7f5300db031d9d122e74d6219a3f19b3295653faa946c5618b4324454`;
- dashboard-only container recreation: PASS;
- dashboard health: PASS;
- owner-facing Research Agent scope check: PASS.

## Final production invariants

Final observed state:

- task ledger: `12`;
- research evidence: `10`;
- backend PID: `462906`;
- backend: `active`;
- Guardian broker: `inactive`;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- dashboard: `healthy`;
- SearXNG: `running`;
- SearXNG bind: `127.0.0.1:8888` only;
- Git checkout: exact approved head and clean.

The resume closure explicitly did **not** rerun the Research Agent and did **not** create duplicate evidence.

## Final verdict

`PHASE13_PROVIDER_SPECIFIC_ACTIVATION|PASS`

`PHASE13_LIVE_EVIDENCE_GATE|PASS`

`phase13_resume_without_duplicate_research|PASS`

Phase 13 is therefore technically complete and ready for repository integration. The activated production posture remains intentionally narrow: manual Research Agent only, fixed local SearXNG discovery, sealed Phase 12 retrieval/evidence boundaries, and no smart-routing or generic network authority.
