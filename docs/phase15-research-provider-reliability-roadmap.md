# Phase 15 — Research Provider Reliability Remediation Roadmap

Status: **IN PROGRESS — 15A–15H SOURCE COMPLETE / CI GREEN; 15I–15J PENDING LIVE EMPIRICAL GATE**

Base: Phase 14 final merged documentation seal `512c03aaab6c49f7c7ec4c351dcd82e35f36b4bc`.

Branch: `phase15/research-provider-reliability`.

Pre-live code checkpoint: `d3c6289cc7a32da14a18552937826d8f81a99da2`.

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
  -> bounded provider scan / deterministic owner-query-only fallback
  -> bounded candidate selection (<= 3)
  -> sealed Phase 12 retrieval/evidence pipeline
```

## Gates

### 15A — Frontend visibility and runtime baseline — SOURCE COMPLETE / LIVE UI PROOF PENDING

Delivered in source:
- Research navigation visible on the normal Guardian landing page;
- direct Research Operations navigation;
- existing `/research` and `/research/operations` routes preserved;
- browser remains read-only/no-network;
- dashboard boundary/lint/build/production-image CI green.

Remaining exit proof: deploy the Phase 15 dashboard on Acer and confirm owner-visible navigation from `/` without typing a URL.

### 15B — No-candidate diagnosis and bounded provider scanning — COMPLETE

Delivered:
- provider-zero differentiated from malformed/unsafe/policy-filtered zero;
- provider result, considered, invalid and policy-rejected counts;
- provider scan continues past rejected top entries within a fixed 20-result window;
- accepted candidate count remains bounded by the request;
- downstream retrieval ceiling remains `<= 3` and destination policy is unchanged.

Exit gate: PASS in deterministic tests and Guardian boundary.

### 15C — Deterministic query fallback contract — COMPLETE

Delivered:
- original owner query always first;
- fallback only after zero admissible candidates;
- maximum three attempts;
- variants may remove edge tokens but cannot add terms;
- same fixed local SearXNG provider for every attempt;
- no model-generated expansion/provider switching;
- safe attempt/query identities and timing diagnostics recorded in Research Agent history without provider titles/snippets.

Exit gate: PASS in deterministic tests and Guardian boundary.

### 15D — Candidate diversity and duplicate suppression v2 — COMPLETE

Delivered:
- canonical duplicate key normalizes host/default ports, fragments and known tracking parameters;
- selected retrieval URLs themselves are not rewritten;
- unique source families preferred before duplicate-family fallback;
- selected URL count remains `<= 3`;
- provider titles/snippets remain non-evidence;
- selection quality remains explicitly non-credibility.

Exit gate: PASS in deterministic tests.

### 15E — Duplicate-content reduction/readiness measurement — COMPLETE FOR PHASE 15 DESIGN

Delivered:
- immutable normalized-text hashes remain the duplicate-content signal;
- duplicate-content rate is a frozen readiness metric;
- duplicate groups remain owner-visible;
- no destructive evidence deletion/rewrite introduced.

Exit gate: PASS for non-destructive measurement/visibility. Final empirical rate remains a 15I result.

### 15F — Tail-latency remediation and benchmark wall clock — COMPLETE FOR PRE-LIVE DESIGN

Delivered:
- provider-search, retrieval and total-pipeline timing separated;
- sealed retry policy preserved;
- policy/cancellation failures remain non-retryable;
- frozen live-case wall-clock maximum: `60 s`;
- readiness retrieval p95 target frozen at `1500 ms`.

Exit gate: PASS in tests/Guardian. Final empirical latency remains a 15I result.

### 15G — Provider readiness model and owner dashboard — SOURCE COMPLETE / LIVE DATA PENDING

Delivered:
- GET-only provider readiness endpoint and dashboard proxy;
- states: insufficient-data, healthy, degraded, unavailable;
- stable reason codes;
- query coverage, no-candidate, diversity, duplicate and retrieval-p95 indicators;
- missing live report reports pending rather than fabricated readiness;
- no provider restart/reconfiguration controls;
- direct Research Ops navigation.

Remaining exit proof: deployed Acer page reads the live hashed report correctly after 15I.

### 15H — Expanded deterministic benchmark corpus — COMPLETE

Delivered:
- exactly 30 frozen cases;
- categories: official documentation, standards, general factual, multi-source technical;
- deterministic offline fixtures in CI;
- separate real-provider Acer runner;
- per-case diagnostics and success/no-candidate/diversity/duplicate/latency distributions;
- canonical report SHA-256;
- isolated `/tmp` benchmark truth database required for live execution;
- production task truth/evidence mutation explicitly false.

CI result: deterministic benchmark `30/30` PASS.

### 15I — Acer live reliability burn-in — PENDING

Required:
- deploy exact CI-green Phase 15 source checkpoint;
- prove frontend visibility from normal `/` landing page;
- run all 30 frozen cases through fixed local SearXNG + sealed retrieval;
- use isolated `/tmp` benchmark truth DB;
- persist only the hashed live metrics report outside the temp DB;
- verify production task ledger/research evidence/research operations counts are unchanged by the corpus;
- capture success, no-candidate, family, duplicate, latency and resource metrics;
- preserve Guardian inactive, Telegram approvals false and SearXNG loopback-only.

Exit gate: empirical report complete and authority/safety invariants pass. Meeting the numeric production-ready targets is not required for the gate itself; a degraded or experimental result is valid evidence.

### 15J — Provider readiness decision — PENDING

Choose exactly one posture from the frozen live evidence:

- `manual-research-production-ready`;
- `manual-research-experimental-only`;
- `manual-research-provider-degraded`.

A Phase 15 readiness result does **not** activate smart-routing research. Any future authority expansion requires a separate owner-approved milestone.

## Frozen target thresholds

Frozen before the final live corpus:

- live query success rate `>= 0.95`;
- provider no-candidate rate `<= 0.05`;
- selected unique-source-family rate `>= 0.80`;
- duplicate-content rate `<= 0.20`;
- retrieval-source p95 `<= 1500 ms`;
- maximum wall clock per live corpus case `60 s`;
- zero authority-boundary regressions.

These thresholds must not be changed after seeing the final live result merely to force a pass.

## Pre-live validation

All nine repository workflows were green on pre-live code checkpoint `d3c6289cc7a32da14a18552937826d8f81a99da2`, including the Phase 15 backend/Guardian/dashboard gate, deterministic `30/30` benchmark, sealed search/retrieval regressions and production dashboard image build.
