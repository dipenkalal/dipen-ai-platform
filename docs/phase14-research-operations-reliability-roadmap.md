# Phase 14 — Research Operations & Reliability Roadmap

Status: **COMPLETE / SEALED / MERGED — 14A–14J PASSED; FINAL POSTURE `manual-research-provider-degraded`; SMART-ROUTING RESEARCH REMAINS OUT OF SCOPE**

Base: Phase 13 final merged seal `5f4afa1869497aafee3d1cba3de9b96cdad2e8dd`.

Phase 14 merge commit: `f9b49781ddcf98346c199128d52ec75e33d3f6fc`.

## Mission

Make the already-activated manual Research Agent + local SearXNG path dependable for routine owner use without expanding network or routing authority.

Phase 14 is an operations/reliability milestone. It improves observability, source diversity, recovery, evidence lifecycle planning, and benchmark discipline while preserving the sealed Phase 12/13 authority boundary.

## Non-negotiable authority boundary

Phase 14 does **not** grant:

- smart-routing research activation;
- autonomous search discovery;
- generic HTTP/socket/browser tools;
- arbitrary provider selection;
- provider credential access by models;
- provider title/snippet evidence authority;
- automatic Knowledge mutation;
- automatic destructive evidence deletion;
- Guardian/root/systemd authority to agents;
- Docker socket or privileged-container authority;
- autonomous merge/release/deployment authority.

The active production search scope remains:

```text
manual research-agent
  -> explicit bounded research_search_query
  -> local searxng-local-v1 on 127.0.0.1:8888
  -> bounded candidate selection
  -> sealed Phase 12 retrieval/evidence pipeline
```

## Gates

### 14A — Reliability contract and SLO model — COMPLETE

Delivered explicit research reliability metrics and thresholds, stable machine-readable operations models, and clear distinction between source-selection quality, provenance quality, and factual correctness. Exit gate: PASS.

### 14B — Source-family diversity and duplicate handling — COMPLETE

Delivered deterministic canonical source-family extraction, unique-family preference, exact URL duplicate suppression, post-retrieval duplicate-content detection, and owner-visible family/duplicate metadata. Provider titles/snippets remain non-evidence. Exit gate: PASS.

### 14C — Retrieval latency, attempt, timeout and retry telemetry — COMPLETE

Delivered per-source duration, attempt/retry telemetry, stable error classification, and exactly one bounded retry for safe transient GET failures. No retry after destination/content/redirect-policy failure or cancellation. Exit gate: PASS.

### 14D — Evidence retention and cleanup policy — COMPLETE

Delivered owner-visible retention classification and dry-run cleanup planning with preserve-all default. No automatic deletion/archive. Exit gate: PASS.

### 14E — SearXNG health telemetry — COMPLETE

Delivered fixed-loopback provider health and latency/status visibility without provider service-control authority. Exit gate: PASS.

### 14F — Research Operations API — COMPLETE

Delivered GET-only reliability summary, provider health, resource snapshot and retention-plan endpoints under `/api/v1/research/operations`. Mutation POST attempts return 405. Exit gate: PASS.

### 14G — Owner dashboard — COMPLETE

Delivered `/research/operations` with reliability, source-family, duplicate, latency/retry, provider health, failure/recovery, retention and provenance-quality visibility. Dashboard has no arbitrary fetch, evidence/Knowledge/task mutation or provider-control authority. Exit gate: PASS.

### 14H — Failure/recovery visibility — COMPLETE

Delivered transient/terminal failure visibility, recovery counts, error breakdown, evidence completeness checks, explicit degraded-provider state, and the bounded live provider-failure recovery bridge used during 14J. Exit gate: PASS.

### 14I — Periodic regression benchmark — COMPLETE

Delivered deterministic CI and Acer reliability benchmarks plus weekly scheduled regression. Acer benchmark: 5/5 PASS. Report SHA-256: `57cf45169f98675df7c7567dc0bbaefae4c4ad1db74805d72bfeac4903f45bfc`. Smart-routing research remained false and network authority remained unchanged. Exit gate: PASS.

### 14J — Burn-in and readiness decision — COMPLETE

First live burn-in query (`IANA example domains RFC 2606`) produced zero admissible local-SearXNG candidates. DAP failed closed with run `2750295c-8acb-465b-86f1-417731d0a022`, no public-web evidence and no retrieval-operations event.

Bounded recovery then completed two successful manual Research Agent runs:

- `84d6dc11-b044-479d-87d3-a6a82d1248bb` — 3 selected URLs, +3 evidence, +3 operations events;
- `746654d9-1be0-42a6-9970-0acf404e2419` — 3 selected URLs, +3 evidence, +3 operations events.

Live operations result:

- reliability posture: `degraded`;
- success rate: `0.8125`;
- failure rate: `0.1875`;
- retrieval p50: `279.737 ms`;
- retrieval p95: `2370.666 ms`;
- unique source-family rate: `0.5`;
- duplicate-content rate: `0.4615`;
- provenance-quality average: `83.12`;
- provider health latency: `2.374 ms`.

Final 14J posture: **`manual-research-provider-degraded`**.

Smart-routing research is **not** activated by 14J.

This posture means manual owner-supervised research remains available under the Phase 13 boundary, the reliability layer is complete and working, the SearXNG-backed provider path is not promoted to production-ready, and any future authority-expansion review is blocked until provider reliability is remediated and re-benchmarked.

## Completion criteria

1. 14A–14I deterministic CI gates green — PASS.
2. Acer live operations proof without authority broadening — PASS.
3. Owner dashboard/API expose read-only operational state — PASS.
4. Evidence retention remains non-destructive — PASS.
5. Phase 12 destination/content/evidence regressions pass — PASS.
6. Phase 13 manual-only search-routing regressions pass — PASS.
7. 14J empirical readiness posture recorded — PASS (`manual-research-provider-degraded`).
8. Final branch head `08fe62a0fd58e1c036a8012c82830e67944ecd4e` passed all eight repository workflows — PASS.
9. PR #67 merged to `main` at `f9b49781ddcf98346c199128d52ec75e33d3f6fc` — PASS.

Live evidence: `docs/phase14-research-operations-live-evidence-2026-08-18.md`.

Phase 14 is **COMPLETE / SEALED / MERGED**. No Phase 14 result activates smart-routing research.
