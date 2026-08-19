# Phase 14 — Research Operations & Reliability Live Evidence

Date: 2026-08-18 / 2026-08-19 UTC

Branch: `phase14/research-operations-reliability`

Live checkpoint: `2c81aefc434a84b296cf9b0acb135be3663f3f6b`

Final empirical posture: **`manual-research-provider-degraded`**

## Executive result

Phase 14 live validation passed end-to-end. The reliability/operations layer, bounded recovery path, deterministic benchmark, offline dashboard deployment, owner visibility, and preserved authority boundary all passed on the Acer.

The underlying manual Research Agent + local SearXNG provider path is **not** classified production-ready. One harmless first burn-in query produced zero admissible SearXNG candidates, and the final operations summary remained `degraded` despite two successful bounded recovery searches.

This is a provider/retrieval-quality finding, not an authority-boundary failure. Smart-routing research remains disabled.

## First provider failure

Initial query: `IANA example domains RFC 2606`

Research run:

- run ID: `2750295c-8acb-465b-86f1-417731d0a022`
- task ID: `agent-task-67dba442-dd60-43ad-b1cf-1f2e8b5ec385`
- task status: `failed`
- provider reached: `searxng-local-v1`
- outcome: zero URL candidates eligible for bounded DAP retrieval
- public-web evidence delta: `0`
- retrieval-operations delta: `0`

DAP failed closed. The failed run did not broaden destinations, create fallback evidence, expose provider snippets/titles to the model, or activate smart-routing research.

## Bounded provider recovery

The recovery bridge reconciled the failed instrumented task and preserved the already-loaded backend runtime.

Successful recovery run 1:

- run ID: `84d6dc11-b044-479d-87d3-a6a82d1248bb`
- task ID: `agent-task-5e02f7e0-894b-4401-8c45-e2ad24647679`
- status: `completed`
- selected URLs: `3`
- immutable evidence delta: `+3`
- research-operations delta: `+3`

Successful recovery run 2:

- run ID: `746654d9-1be0-42a6-9970-0acf404e2419`
- task ID: `agent-task-59ec8300-64ae-492f-a070-7cd118014c9a`
- status: `completed`
- selected URLs: `3`
- immutable evidence delta: `+3`
- research-operations delta: `+3`

Recovery totals:

- successful manual Research Agent runs: `2`
- provider-failure runs recorded: `1`
- burn-in evidence delta: `+6`
- burn-in operations delta: `+6`
- recovery bridge: `PASS`

No second backend restart was required.

## Live operations metrics

Final owner-visible operations summary:

- reliability posture: `degraded`
- success rate: `0.8125`
- failure rate: `0.1875`
- retrieval p50: `279.737 ms`
- retrieval p95: `2370.666 ms`
- unique source-family rate: `0.5`
- duplicate-content rate: `0.4615`
- transient retry count: `0`
- recovered-after-retry count: `0`
- provenance-quality average: `83.12`
- SearXNG health latency: `2.374 ms`
- backend RSS snapshot: `147.86 MiB`
- future archive candidate count: `0`

The duplicate-content and source-family figures are operational quality indicators only; they are not factual-credibility scores.

## Acer deterministic benchmark

Phase 14 reliability benchmark: **5/5 PASS**

Report SHA-256:

`57cf45169f98675df7c7567dc0bbaefae4c4ad1db74805d72bfeac4903f45bfc`

Cases:

1. `source-family-diversity` — PASS
2. `bounded-transient-retry` — PASS
3. `operations-summary` — PASS
4. `retention-dry-run` — PASS
5. `provider-loopback-boundary` — PASS

Resource snapshot around deterministic benchmark:

- RSS before: `41.76 MiB`
- RSS after: `42.07 MiB`
- smart-routing research activated: `false`
- network authority expanded: `false`

## Read-only API and dashboard proof

Backend Research Operations endpoints returned GET `200` and mutation POST `405` for:

- `/api/v1/research/operations`
- `/api/v1/research/operations/provider-health`
- `/api/v1/research/operations/resource-snapshot`
- `/api/v1/research/operations/retention-plan`

Dashboard proxy mutation attempts also returned `405` for all four operations paths.

Owner visibility:

- `/research`: HTTP `200`
- `/research/operations`: HTTP `200`
- Research Operations page marker: PASS
- dashboard operations models: PASS
- owner operations visibility: PASS

## Offline dashboard deployment

Offline Next.js application build: PASS

Runtime image:

`sha256:9289e6632b6362e647bc814a4ef9429674ee4f8c2fc4bec73318278cdac043d2`

Dashboard container transition:

- before: `942998ae621d5133798fd3a1ee1c748c951654e578ed2a3108948f6d29a50d0f`
- after: `29d16018030cda64756b0d352d7a19b3c4cf21c0272aece9dd763f5495e83b9c`

Dashboard health: `healthy`

Rollback image retained by operator:

`dap-dashboard-phase14-rollback:20260819T010705Z`

## Final production state

- task ledger: `15`
- research retrieval evidence: `16`
- research operations events: `6`
- backend PID: `487274`
- backend: `active`
- Guardian broker: `inactive`
- Telegram approvals: `DAP_TELEGRAM_APPROVALS_ENABLED=false`
- dashboard: `healthy`
- SearXNG: `running`
- SearXNG binding: `127.0.0.1:8888`
- Git source: exact checkpoint and clean

Final live markers:

- `PHASE14_RESEARCH_OPERATIONS_LIVE_BURNIN|PASS`
- `PHASE14_OWNER_OPERATIONS_VISIBILITY|PASS`
- `PHASE14_AUTHORITY_BOUNDARY|PASS`
- `phase14_recovery_exit|0`

## Readiness decision

The empirical result is **`manual-research-provider-degraded`**.

Reasoning:

- the reliability/operations implementation itself passed;
- DAP failed closed correctly on a real provider no-candidate result;
- two bounded recovery searches succeeded and generated six immutable evidence records plus six operations events;
- however, overall reliability remained degraded (`81.25%` success), source-family diversity was only `50%`, duplicate-content rate was `46.15%`, and retrieval p95 was about `2.37 s`;
- therefore the provider-specific path is suitable only for owner-supervised/manual use while provider quality is remediated and monitored.

This decision does **not** activate smart-routing research and does not expand model network authority.
