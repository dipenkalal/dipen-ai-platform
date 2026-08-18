# Phase 14 — Research Operations & Reliability Roadmap

Status: **IN PROGRESS — 14A STARTED; SMART-ROUTING RESEARCH REMAINS OUT OF SCOPE**

Base: Phase 13 final merged seal `5f4afa1869497aafee3d1cba3de9b96cdad2e8dd`.

## Mission

Make the already-activated manual Research Agent + local SearXNG path dependable for routine owner use without expanding network or routing authority.

Phase 14 is an operations/reliability milestone. It must improve observability, source diversity, recovery, evidence lifecycle planning, and benchmark discipline while preserving the sealed Phase 12/13 authority boundary.

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

### 14A — Reliability contract and SLO model

Deliver:
- explicit research reliability metrics and thresholds;
- stable machine-readable operations models;
- clear distinction between source-selection quality, provenance quality, and factual correctness;
- no hidden credibility claims.

Exit gate:
- contracts frozen in tests and Guardian boundary.

### 14B — Source-family diversity and duplicate handling

Deliver:
- deterministic canonical source-family extraction from candidate hostnames;
- selection that prefers unique source families before duplicate families;
- exact URL duplicate suppression;
- post-retrieval duplicate-content detection using immutable normalized-text hashes;
- owner-visible duplicate/family metadata;
- provider titles/snippets remain non-evidence.

Exit gate:
- selected URL count remains <= 3 and every selected URL still requires full DAP retrieval.

### 14C — Retrieval latency, attempt, timeout and retry telemetry

Deliver:
- per-source wall-clock duration;
- attempt count and transient retry count;
- stable transient/non-transient error classification;
- bounded retry policy for safe GET retrieval only;
- no retry after destination-policy rejection, content-policy rejection, or cancellation;
- append-only operational telemetry separate from immutable retrieval evidence.

Exit gate:
- retry ceiling is deterministic and does not broaden destinations or methods.

### 14D — Evidence retention and cleanup policy

Deliver:
- owner-visible retention classification;
- dry-run cleanup planner;
- duplicate/superseded candidates surfaced without deleting canonical evidence;
- default policy preserves all immutable evidence;
- no automatic deletion in Phase 14.

Exit gate:
- planner is read-only and reports what could be archived/purged under a future owner action.

### 14E — SearXNG health telemetry

Deliver:
- fixed-local-provider health check;
- latency/status sample;
- loopback-binding expectation exposed in operations status;
- provider health failures visible without granting agent control.

Exit gate:
- health check cannot mutate provider configuration or start/restart services.

### 14F — Research Operations API

Deliver read-only endpoints under `/api/v1/research/operations` for:
- reliability summary;
- source families and duplicate-content groups;
- recent failures/recovery metrics;
- provider health;
- retention dry-run plan.

Exit gate:
- GET-only API; POST/PUT/PATCH/DELETE are rejected.

### 14G — Owner dashboard

Deliver an owner-facing Research Operations view showing:
- success/failure/cancelled rate;
- source-family diversity;
- duplicate-content count;
- latency/attempt/retry metrics;
- SearXNG health;
- failure/error distribution;
- evidence retention plan;
- provenance-quality indicators;
- explicit read-only/no-network-authority labels.

Exit gate:
- dashboard cannot fetch arbitrary URLs, mutate evidence, mutate Knowledge/tasks, or control SearXNG.

### 14H — Failure/recovery visibility

Deliver:
- transient vs terminal failure classification;
- recovered-after-retry count;
- failure-stage/error-code breakdown;
- evidence completeness checks;
- clear degraded-provider state.

Exit gate:
- failure visibility is evidence/telemetry only and grants no remediation authority.

### 14I — Periodic regression benchmark

Deliver:
- deterministic CI reliability benchmark;
- Acer live benchmark runner that uses harmless public retrieval and local SearXNG;
- machine-readable JSON report with hash;
- latency, success, source-diversity, duplicate, retry, failure-recovery and evidence-completeness checks.

Exit gate:
- benchmark does not mutate task truth except normal explicitly-invoked agent instrumentation when intentionally exercised.

### 14J — Burn-in and readiness decision

Use empirical results to choose one posture:
- `manual-research-production-ready`;
- `manual-research-experimental-only`;
- `manual-research-provider-degraded`.

Smart-routing research is **not** activated by 14J. A later milestone would require a separate explicit authority review and owner decision.

## Completion criteria

Phase 14 seals only when:

1. 14A–14I deterministic CI gates are green.
2. Acer live operations proof passes without broadening authority.
3. owner dashboard/API expose reliable read-only operational state.
4. evidence retention remains non-destructive by default.
5. Phase 12 destination/content/evidence regressions still pass.
6. Phase 13 manual-only search-routing regressions still pass.
7. 14J records an empirical manual-research readiness posture.
