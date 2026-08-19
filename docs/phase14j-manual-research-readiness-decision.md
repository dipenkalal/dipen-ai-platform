# Phase 14J — Manual Research Readiness Decision

Decision date: 2026-08-18 / 2026-08-19 UTC

Decision: **`manual-research-provider-degraded`**

## Decision summary

Phase 14's reliability/operations implementation is accepted and sealable. The manual Research Agent + local SearXNG provider path is **not** promoted to production-ready.

The system demonstrated the desired safety behavior under a real provider-quality failure: a harmless query returned zero admissible search candidates, DAP failed closed, no public-web evidence was fabricated, smart-routing research remained disabled, and the bounded recovery path later completed without broadening authority.

## Evidence considered

Initial failed provider run:

- run ID `2750295c-8acb-465b-86f1-417731d0a022`
- provider: `searxng-local-v1`
- outcome: no admissible URL candidate
- evidence delta: `0`
- retrieval-operations delta: `0`

Successful bounded recovery:

- `84d6dc11-b044-479d-87d3-a6a82d1248bb` — 3 selected URLs, +3 immutable evidence, +3 operations events
- `746654d9-1be0-42a6-9970-0acf404e2419` — 3 selected URLs, +3 immutable evidence, +3 operations events

Final live reliability metrics:

- operations posture: `degraded`
- success rate: `81.25%`
- failure rate: `18.75%`
- retrieval p50: `279.737 ms`
- retrieval p95: `2370.666 ms`
- unique source-family rate: `50%`
- duplicate-content rate: `46.15%`
- provenance-quality average: `83.12`
- SearXNG health latency: `2.374 ms`
- transient retries observed: `0`
- recovered-after-retry observed: `0`

Acer deterministic Phase 14 benchmark passed 5/5 with report SHA-256 `57cf45169f98675df7c7567dc0bbaefae4c4ad1db74805d72bfeac4903f45bfc`.

## Why not `manual-research-production-ready`

The live path failed on one harmless query and the aggregate reliability summary remained degraded. A production-ready classification would ignore the exact failure Phase 14 was built to surface.

Source-family diversity is also only `0.5`, duplicate-content rate is `0.4615`, and tail retrieval latency is materially above median latency. These are reliability/quality issues even though the bounded security model remained intact.

## Why `provider-degraded` instead of only `experimental-only`

The provider-specific path itself produced the failure: SearXNG was reachable/healthy but returned no candidate eligible for bounded retrieval. The operations layer therefore correctly reports `degraded`. The two successful recovery runs show the path is useful and recoverable, but do not erase the provider-level failure.

## Allowed posture after Phase 14

Allowed:

- owner-supervised manual `research-agent` execution;
- explicit bounded `research_search_query`;
- fixed local `searxng-local-v1` only;
- <=3 DAP-selected URLs;
- sealed Phase 12 retrieval/evidence pipeline;
- read-only Research Operations visibility;
- scheduled deterministic regression benchmark.

Not allowed / not activated:

- smart-routing research;
- autonomous background search discovery;
- generic HTTP/socket/browser tools;
- arbitrary provider selection;
- provider credential exposure to models;
- automatic Knowledge mutation;
- destructive evidence cleanup;
- agent-controlled provider restart/remediation;
- broader network authority.

## Exit conditions before future authority expansion

A later milestone should re-benchmark after provider reliability remediation and should require materially improved:

1. no-candidate/query-coverage behavior;
2. source-family diversity;
3. duplicate-content rate;
4. tail retrieval latency;
5. multi-query burn-in success rate over a larger sample.

No smart-routing authority review should begin until those provider/reliability conditions are demonstrated empirically.
