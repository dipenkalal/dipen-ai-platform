# Phase 14 Status

Status: **COMPLETE / SEALED / MERGED — 14A–14J PASS; EMPIRICAL POSTURE `manual-research-provider-degraded`**

Base: Phase 13 final merged seal `5f4afa1869497aafee3d1cba3de9b96cdad2e8dd`.

Phase 14 merge commit: `f9b49781ddcf98346c199128d52ec75e33d3f6fc`.

Development branch: `phase14/research-operations-reliability`.

Live evidence checkpoint: `2c81aefc434a84b296cf9b0acb135be3663f3f6b`.

Final CI-green branch head: `08fe62a0fd58e1c036a8012c82830e67944ecd4e`.

Live evidence record: `docs/phase14-research-operations-live-evidence-2026-08-18.md`.

## Completed scope

- deterministic source-family diversity and exact URL duplicate suppression;
- source-selection quality metadata explicitly separated from factual/source credibility;
- one bounded retry for clearly transient GET retrieval failures only;
- append-only research operations telemetry;
- exact duplicate-content visibility using immutable normalized-text SHA-256;
- GET-only reliability summary, provider-health, resource-snapshot and retention-plan APIs;
- non-destructive evidence-retention dry-run policy;
- fixed-loopback SearXNG health telemetry with no service-control authority;
- read-only backend CPU/RSS and host utilization snapshot;
- owner-facing `/research/operations` dashboard;
- deterministic five-case reliability benchmark with resource snapshots and report hash;
- weekly scheduled deterministic regression benchmark;
- Phase 14 Guardian/browser authority boundaries;
- resumable Acer live burn-in/deployment operator;
- bounded provider-failure recovery bridge.

## Preserved authority boundary

Phase 14 did not activate smart-routing research, generic model network tools, arbitrary provider access, automatic Knowledge mutation, destructive evidence cleanup, Guardian/root/systemd authority, Docker privilege, or autonomous merge/release/deployment authority.

Production research scope remains manual `research-agent` + explicit bounded search query + fixed local `searxng-local-v1` + sealed Phase 12 retrieval/evidence.

## Deterministic gate

All eight repository workflows passed on final branch head `08fe62a0fd58e1c036a8012c82830e67944ecd4e` before merge. The Phase 14-specific gate passed backend reliability tests, deterministic 5/5 reliability benchmark, sealed Phase 12/13 regressions, live operator/recovery syntax, Guardian boundaries, dashboard authority/lint/build checks and production dashboard image build.

## 14J live result

The first harmless burn-in query (`IANA example domains RFC 2606`) reached local SearXNG but returned zero URL candidates eligible for bounded DAP retrieval. DAP failed closed, created no public-web evidence, and preserved the manual-only authority boundary.

The bounded recovery bridge then:

- reconciled the single failed instrumented Research Agent task;
- ran two successful manual Research Agent fallback searches;
- selected exactly three URLs in each successful run;
- added six immutable research evidence records;
- added six append-only research operations events;
- resumed the original live operator without a second backend restart;
- passed operations visibility, deterministic benchmark, offline dashboard deployment and final production safety gates.

Successful recovery run IDs:

- `84d6dc11-b044-479d-87d3-a6a82d1248bb`
- `746654d9-1be0-42a6-9970-0acf404e2419`

Failed provider run retained as evidence:

- `2750295c-8acb-465b-86f1-417731d0a022`

## Empirical metrics

- reliability posture reported by operations layer: `degraded`
- success rate: `0.8125`
- failure rate: `0.1875`
- retrieval p50: `279.737 ms`
- retrieval p95: `2370.666 ms`
- unique source-family rate: `0.5`
- duplicate-content rate: `0.4615`
- provenance-quality average: `83.12`
- SearXNG health latency: `2.374 ms`
- backend RSS snapshot: `147.86 MiB`
- future archive candidates: `0`

Acer deterministic benchmark remained 5/5 green with report SHA-256 `57cf45169f98675df7c7567dc0bbaefae4c4ad1db74805d72bfeac4903f45bfc`.

## Final production safety

- task ledger: `15`
- research evidence: `16`
- research operations events: `6`
- backend PID: `487274`
- backend: `active`
- Guardian: `inactive`
- Telegram approvals: `false`
- dashboard: `healthy`
- SearXNG: `running`
- SearXNG binding: `127.0.0.1:8888`
- source tree: clean at live proof

Final markers:

- `PHASE14_RESEARCH_OPERATIONS_LIVE_BURNIN|PASS`
- `PHASE14_OWNER_OPERATIONS_VISIBILITY|PASS`
- `PHASE14_AUTHORITY_BOUNDARY|PASS`
- `phase14_recovery_exit|0`

## Readiness decision

Final 14J posture: **`manual-research-provider-degraded`**.

Phase 14 is complete, sealed, and merged because its reliability, telemetry, recovery, dashboard, benchmark, retention, and authority-boundary goals all passed. The underlying provider-specific research path is **not** promoted to production-ready and smart-routing research remains disabled.

Next reliability work should remediate provider query coverage, source-family diversity, duplicate-content rate and tail latency before any later authority-expansion review.
