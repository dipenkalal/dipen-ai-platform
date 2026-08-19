# Phase 15 Status

Status: **COMPLETE / SEALED — `manual-research-provider-degraded`**

Base: Phase 14 final merged documentation seal `512c03aaab6c49f7c7ec4c351dcd82e35f36b4bc`.

Branch: `phase15/research-provider-reliability`.

Live source checkpoint: `6fae0c2a6de7413bb093607c8558eced9877cd0f`.

PR #69 remains draft/open/unmerged. Merge requires explicit owner authorization.

## What Phase 15 completed

Phase 15 remediated the provider-quality weaknesses exposed by Phase 14 while preserving manual-only research authority.

Completed engineering gates:

- 15A — frontend visibility and runtime baseline;
- 15B — no-candidate diagnosis and bounded provider scanning;
- 15C — deterministic owner-query-only fallback;
- 15D — stronger canonical duplicate suppression and source-family diversity;
- 15E — duplicate-content measurement without evidence rewriting/deletion;
- 15F — provider/retrieval/pipeline timing and bounded live wall-clock policy;
- 15G — read-only provider readiness model and Research Ops dashboard projection;
- 15H — frozen exactly-30-case deterministic benchmark corpus;
- 15I — Acer deployment + isolated 30-case live corpus + frontend/safety proof;
- 15J — empirical provider-readiness decision.

## Frontend visibility result

The original frontend issue is fixed and live.

The Phase 15 dashboard deployment proved:

- the normal Guardian landing page exposes `Research`;
- the normal Guardian landing page exposes direct `Research Ops`;
- `/research` returns HTTP 200;
- `/research/operations` returns HTTP 200;
- the dashboard readiness projection is reachable;
- the dashboard finished healthy.

`PHASE15_FRONTEND_VISIBILITY|PASS`

## Empirical provider result

Frozen live targets were intentionally not changed after seeing the result.

Live 30-case result:

- success: `9/30` = `0.30` versus target `>= 0.95`;
- no-candidate: `21/30` = `0.70` versus target `<= 0.05`;
- unique-source-family rate: `0.963` versus target `>= 0.80`;
- duplicate-content rate: `0.0` versus target `<= 0.20`;
- retrieval-source p95: `7648.376 ms` versus target `<= 1500 ms`;
- provider-search p95: `2117.782 ms`;
- total-pipeline p95: `23413.71 ms`;
- fallback used on `21` cases.

Canonical live report SHA-256:

`ade3a36bd60382cad33529af465d8f08f0c5e9feac71c1d823ed2f9af214ac7d`

Final read-only readiness state: `degraded`.

Final reason codes:

- `operations-reliability-degraded`;
- `query-coverage-below-target`;
- `no-candidate-rate-above-target`;
- `retrieval-p95-above-target`.

Final Phase 15 posture:

**`manual-research-provider-degraded`**

## Safety result

The provider-quality result is degraded, but the Phase 15 safety/live gate passed completely.

Production truth before and after the isolated corpus was unchanged:

- task ledger: `15 -> 15`;
- immutable research evidence: `16 -> 16`;
- research operations events: `6 -> 6`.

The isolated benchmark DB contained `0` task rows and `27` retrieval-evidence / `27` operations rows.

Final runtime boundary:

- backend active;
- Guardian broker inactive;
- Telegram approvals false;
- dashboard healthy;
- SearXNG running and bound only to `127.0.0.1:8888`;
- source branch/head unchanged and clean;
- smart-routing research still disabled;
- no generic model network authority;
- no provider switching;
- no automatic Knowledge mutation;
- no destructive evidence cleanup;
- no agent Guardian/root/systemd/Docker authority.

## Final engineering interpretation

Phase 15 proved that source selection diversity and duplicate suppression can meet their targets with the fixed provider. It also proved that the dominant remaining limitations are provider coverage/no-candidate behavior and retrieval tail latency.

Those provider-quality limitations do not justify authority expansion. Manual owner-supervised Research Agent execution remains the maximum research authority.

Live evidence: `docs/phase15-research-provider-reliability-live-evidence-2026-08-19.md`.
