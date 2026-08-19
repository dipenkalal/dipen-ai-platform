# Phase 15 — Research Provider Reliability Remediation Roadmap

Status: **IN PROGRESS — 15A FRONTEND VISIBILITY STARTED; NO AUTHORITY EXPANSION**

Base: Phase 14 final merged documentation seal `512c03aaab6c49f7c7ec4c351dcd82e35f36b4bc`.

Branch: `phase15/research-provider-reliability`.

## Mission

Remediate the provider-quality weaknesses measured in Phase 14 without widening DAP research authority. Phase 15 targets provider query coverage, no-candidate diagnosis, source-family diversity, duplicate-result/content reduction, tail latency, benchmark breadth, and owner-visible frontend discoverability.

The milestone does **not** activate smart-routing research. Manual owner-supervised Research Agent execution remains the maximum research authority.

## Non-negotiable authority boundary

Phase 15 does not grant:

- smart-routing research;
- automatic research on unrelated agent requests;
- generic HTTP/socket/browser tools to models;
- arbitrary provider selection or configurable provider endpoints;
- provider credentials to models;
- provider titles/snippets as retrieval evidence;
- automatic Knowledge mutation;
- destructive evidence cleanup;
- Guardian/root/systemd/Docker authority to agents;
- autonomous merge/release/deployment authority.

The active provider boundary remains:

```text
manual research-agent
  -> explicit bounded research_search_query
  -> fixed local searxng-local-v1 on 127.0.0.1:8888
  -> bounded candidate selection (<= 3)
  -> sealed Phase 12 retrieval/evidence pipeline
```

## Gates

### 15A — Frontend visibility and runtime baseline

Deliver:
- Research navigation visible from the normal Guardian landing page;
- direct owner-visible Research Operations navigation;
- existing `/research` and `/research/operations` routes preserved;
- browser authority remains read-only/no-network;
- deployment proof that the Acer is serving the expected dashboard source checkpoint.

Exit gate:
- owner can reach Research and Research Ops from the normal DAP landing screen without typing a URL.

### 15B — No-candidate diagnosis and bounded provider scanning

Deliver:
- distinguish provider-zero-results from malformed/unsafe/policy-rejected results;
- expose provider result count, considered count and rejection counts to internal diagnostics;
- scan a bounded provider result window until requested admissible candidates are collected instead of truncating before policy filtering;
- preserve candidate ceiling and sealed URL preflight.

Exit gate:
- no extra destination authority; only more complete use of the single fixed local provider response.

### 15C — Deterministic query fallback contract

Deliver:
- bounded deterministic fallback only when the original local-provider query yields zero admissible candidates;
- strict maximum attempt count;
- fallback variants derived only from the owner-supplied query;
- every attempt uses the same fixed local SearXNG endpoint;
- original and fallback query identities retained for telemetry.

Exit gate:
- no model-generated autonomous query expansion and no provider switching.

### 15D — Candidate diversity and duplicate suppression v2

Deliver:
- stronger canonical URL duplicate handling;
- hostname/source-family balancing before duplicate-family fallback;
- bounded normalization for tracking/query-fragment duplicates;
- selected URL count remains <= 3;
- provider titles/snippets remain non-evidence.

Exit gate:
- deterministic tests prove better diversity without credibility claims.

### 15E — Duplicate-content reduction

Deliver:
- use immutable retrieved-content hashes from Phase 14 telemetry to identify recurring duplicate families;
- benchmark duplicate rate independently from candidate URL duplication;
- no destructive deletion or rewriting of immutable evidence.

Exit gate:
- duplicate-content visibility improves selection/benchmark reporting only.

### 15F — Tail-latency remediation

Deliver:
- provider/retrieval stage timing separation;
- bounded timeout/retry tuning based on Phase 14 evidence;
- no retries for destination/content/policy rejection or cancellation;
- deterministic maximum wall-clock budget.

Exit gate:
- p95 budget is explicit and retries cannot broaden destinations or methods.

### 15G — Provider readiness model and owner dashboard

Deliver:
- owner-visible provider state with explicit reasons: healthy, degraded, unavailable;
- query-coverage, diversity, duplicate and latency indicators;
- Research Ops page surfaces Phase 15 readiness without service-control actions;
- direct link remains visible from primary navigation.

Exit gate:
- dashboard is read-only and cannot restart/reconfigure SearXNG.

### 15H — Expanded deterministic benchmark corpus

Deliver:
- frozen 30-case minimum benchmark corpus across official documentation, technical facts, standards, general factual discovery and multi-source topics;
- machine-readable per-case diagnostics;
- success, no-candidate, diversity, duplicate and latency distributions;
- deterministic offline provider-response fixtures for CI plus a separate live Acer corpus.

Exit gate:
- benchmark authority remains identical to manual provider research.

### 15I — Acer live reliability burn-in

Deliver:
- run the live corpus through fixed local SearXNG and sealed retrieval;
- capture resource, latency, success, diversity and duplicate metrics;
- confirm frontend visibility from the deployed dashboard;
- preserve Guardian inactive, Telegram approvals false and SearXNG loopback-only.

Exit gate:
- empirical evidence is complete enough for a readiness decision.

### 15J — Provider readiness decision

Choose exactly one posture from empirical evidence:

- `manual-research-production-ready`;
- `manual-research-experimental-only`;
- `manual-research-provider-degraded`.

A Phase 15 readiness result does **not** activate smart-routing research. Any future authority expansion requires a separate owner-approved milestone.

## Initial target thresholds

These are engineering targets, not claims about current performance:

- live query success rate >= 0.95;
- provider no-candidate rate <= 0.05;
- selected unique-source-family rate >= 0.80 where at least three distinct admissible families exist;
- duplicate-content rate <= 0.20;
- retrieval p95 <= 1500 ms for the frozen live corpus, excluding explicitly recorded remote-source outliers only when the benchmark policy says so in advance;
- zero authority-boundary regressions.

Thresholds may be revised only by a documented source change before the final live corpus is run; they must not be changed after seeing the final result merely to force a pass.
