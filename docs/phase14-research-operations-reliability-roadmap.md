# Phase 14 — Research Operations & Reliability Roadmap

Status: **COMPLETE / SEALED — 14A–14J PASSED; FINAL POSTURE `manual-research-provider-degraded`; SMART-ROUTING RESEARCH REMAINS OUT OF SCOPE**

Base: Phase 13 final merged seal `5f4afa1869497aafee3d1cba3de9b96cdad2e8dd`.

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

Delivered:
- explicit research reliability metrics and thresholds;
- stable machine-readable operations models;
- clear distinction between source-selection quality, provenance quality, and factual correctness;
- no hidden credibility claims.

Exit gate: contracts frozen in tests and Guardian boundary — PASS.

### 14B — Source-family diversity and duplicate handling — COMPLETE

Delivered:
- deterministic canonical source-family extraction from candidate hostnames;
- selection that prefers unique source families before duplicate families;
- exact URL duplicate suppression;
- post-retrieval duplicate-content detection using immutable normalized-text hashes;
- owner-visible duplicate/family metadata;
- provider titles/snippets remain non-evidence.

Exit gate: selected URL count remains <= 3 and every selected URL still requires full DAP retrieval — PASS.

### 14C — Retrieval latency, attempt, timeout and retry telemetry — COMPLETE

Delivered:
- per-source wall-clock duration;
- attempt count and transient retry count;
- stable transient/non-transient error classification;
- bounded retry policy for safe GET retrieval only;
- no retry after destination-policy rejection, content-policy rejection, redirect-policy failure or cancellation;
- append-only operational telemetry separate from immutable retrieval evidence.

Exit gate: deterministic retry ceiling with no destination/method expansion — PASS.

### 14D — Evidence retention and cleanup policy — COMPLETE

Delivered:
- owner-visible retention classification;
- dry-run cleanup planner;
- duplicate/superseded candidates surfaced without deleting canonical evidence;
- default preserve-all policy;
- no automatic deletion.

Exit gate: planner is read-only and reports only future owner-action candidates — PASS.

### 14E — SearXNG health telemetry — COMPLETE

Delivered:
- fixed-local-provider health check;
- latency/status sample;
- loopback-binding expectation in operations status;
- provider health visibility without agent control.

Exit gate: health check cannot mutate provider configuration or start/restart services — PASS.

### 14F — Research Operations API — COMPLETE

Delivered GET-only endpoints under `/api/v1/research/operations` for reliability summary, provider health, resource snapshot and retention plan.

Exit gate: POST mutation attempts return 405 — PASS.

### 14G — Owner dashboard — COMPLETE

Delivered `/research/operations` showing reliability, source-family diversity, duplicate-content rate, latency/attempt/retry metrics, SearXNG health, failure/recovery state, retention plan, provenance-quality indicators and explicit read-only/no-network-authority labels.

Exit gate: dashboard cannot fetch arbitrary URLs, mutate evidence/Knowledge/tasks, or control SearXNG — PASS.

### 14H — Failure/recovery visibility — COMPLETE

Delivered:
- transient vs terminal failure visibility;
- recovered-after-retry count;
- failure-stage/error-code breakdown;
- evidence completeness checks;
- explicit degraded-provider state;
- bounded live provider-failure recovery operator for 14J.

Exit gate: failure visibility/recovery evidence grants no new agent remediation authority — PASS.

### 14I — Periodic regression benchmark — COMPLETE

Delivered:
- deterministic CI reliability benchmark;
- Acer live reliability benchmark;
- machine-readable JSON report with SHA-256;
- source-diversity, retry, operations, retention and provider-loopback cases;
- weekly scheduled deterministic regression workflow.

Acer benchmark: 5/5 PASS.

Report SHA-256: `57cf45169f98675df7c7567dc0bbaefae4c4ad1db74805d72bfeac4903f45bfc`.

Exit gate: benchmark did not activate smart-routing research or expand network authority — PASS.

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

This posture means:

- manual owner-supervised research remains available under the Phase 13 boundary;
- the reliability layer is complete and working;
- the SearXNG-backed provider path is not promoted to production-ready;
- smart-routing research remains disabled;
- a future authority-expansion review is blocked until provider reliability is remediated and re-benchmarked.

## Completion criteria

1. 14A–14I deterministic CI gates green — PASS.
2. Acer live operations proof without authority broadening — PASS.
3. owner dashboard/API expose read-only operational state — PASS.
4. evidence retention remains non-destructive — PASS.
5. Phase 12 destination/content/evidence regressions pass — PASS.
6. Phase 13 manual-only search-routing regressions pass — PASS.
7. 14J empirical readiness posture recorded — PASS (`manual-research-provider-degraded`).

Live evidence: `docs/phase14-research-operations-live-evidence-2026-08-18.md`.

Phase 14 is **COMPLETE / SEALED**. No Phase 14 result activates smart-routing research.
