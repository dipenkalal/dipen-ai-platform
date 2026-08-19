# Phase 15 — Research Provider Reliability Remediation Roadmap

Status: **COMPLETE / SEALED — FINAL POSTURE: `manual-research-provider-degraded`**

Base: Phase 14 final merged documentation seal `512c03aaab6c49f7c7ec4c351dcd82e35f36b4bc`.

Branch: `phase15/research-provider-reliability`.

Live source checkpoint: `6fae0c2a6de7413bb093607c8558eced9877cd0f`.

## Mission

Remediate the provider-quality weaknesses measured in Phase 14 without widening DAP research authority. Phase 15 targeted provider query coverage, no-candidate diagnosis, source-family diversity, duplicate-result/content reduction, tail latency, benchmark breadth, and owner-visible frontend discoverability.

Phase 15 does **not** activate smart-routing research. Manual owner-supervised Research Agent execution remains the maximum research authority.

## Non-negotiable authority boundary — preserved

Phase 15 did not grant:

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

## Gate results

### 15A — Frontend visibility and runtime baseline — COMPLETE / SEALED

Delivered:

- Research navigation visible from the normal Guardian landing page;
- direct owner-visible Research Operations navigation;
- `/research` and `/research/operations` preserved;
- browser authority remains read-only/no-network;
- Acer deployment proof on the exact live checkpoint.

Live proof:

- `/research` -> HTTP 200;
- `/research/operations` -> HTTP 200;
- landing-page Research and Research Ops links present;
- dashboard healthy;
- `PHASE15_FRONTEND_VISIBILITY|PASS`.

### 15B — No-candidate diagnosis and bounded provider scanning — COMPLETE / SEALED

Delivered:

- provider-zero and DAP-filtered-zero outcomes distinguished;
- provider result/considered/rejection counts exposed in diagnostics;
- bounded scan of up to 20 raw provider results;
- downstream retrieval remains <= 3 URLs;
- sealed URL/destination policy unchanged.

### 15C — Deterministic query fallback contract — COMPLETE / SEALED

Delivered:

- original owner query attempted first;
- fallback only after zero admissible candidates;
- maximum three attempts;
- fallback variants derived deterministically only from the owner query;
- same fixed local SearXNG provider for every attempt;
- no model-generated autonomous expansion and no provider switching;
- attempt/query identity exposed in safe Research Agent history metadata.

### 15D — Candidate diversity and duplicate suppression v2 — COMPLETE / SEALED

Delivered:

- stronger canonical URL duplicate handling;
- deterministic tracking/query-fragment duplicate suppression;
- unique source families preferred before duplicate-family fallback;
- selected retrieval URL ceiling <= 3 preserved;
- selection quality remains explicitly non-credibility.

Live unique-source-family rate: `0.963` — target PASS.

### 15E — Duplicate-content reduction — COMPLETE / SEALED

Delivered:

- immutable retrieved-content hashes used for duplicate visibility;
- duplicate-content rate included in readiness reporting;
- no immutable evidence deletion or rewriting.

Live duplicate-content rate: `0.0` — target PASS.

### 15F — Tail-latency remediation — COMPLETE / SEALED AS MEASUREMENT/BOUNDARY WORK

Delivered:

- provider-search, retrieval-source and full-pipeline timing separated;
- sealed retry/destination-policy behavior preserved;
- each live corpus case hard-bounded to 60 seconds.

Live measurements show the latency target is still not met:

- provider-search p95: `2117.782 ms`;
- retrieval-source p95: `7648.376 ms`;
- pipeline p95: `23413.71 ms`;
- frozen retrieval p95 target: `<= 1500 ms` — FAIL.

The remediation gate is sealed because the timing/limit controls and empirical measurement are complete; the provider remains degraded.

### 15G — Provider readiness model and owner dashboard — COMPLETE / SEALED

Delivered:

- owner-visible provider state and stable reason codes;
- query coverage, diversity, duplicate and latency indicators;
- read-only Research Ops projection;
- no provider restart/reconfiguration action exposed.

Final state: `degraded`.

Final reason codes:

- `operations-reliability-degraded`;
- `query-coverage-below-target`;
- `no-candidate-rate-above-target`;
- `retrieval-p95-above-target`.

### 15H — Expanded deterministic benchmark corpus — COMPLETE / SEALED

Delivered:

- frozen exactly-30-case corpus across official documentation, standards, general factual and multi-source technical topics;
- deterministic offline provider fixtures;
- separate live Acer corpus;
- machine-readable diagnostics and report hashing.

Offline CI benchmark: `30/30 PASS`.

### 15I — Acer live reliability burn-in — COMPLETE / SEALED

The live corpus ran on exact source checkpoint `6fae0c2a6de7413bb093607c8558eced9877cd0f`.

Results:

- success: `9/30` = `0.30`;
- no-candidate: `21/30` = `0.70`;
- fallback cases: `21`;
- unique-source-family rate: `0.963`;
- duplicate-content rate: `0.0`;
- retrieval-source p95: `7648.376 ms`;
- report SHA-256: `ade3a36bd60382cad33529af465d8f08f0c5e9feac71c1d823ed2f9af214ac7d`.

Production truth was unchanged by the corpus:

- task ledger `15 -> 15`;
- research evidence `16 -> 16`;
- research operations `6 -> 6`.

The isolated benchmark DB contained `0` task rows and `27` research evidence / `27` operations rows.

Final runtime safety:

- Guardian inactive;
- Telegram approvals false;
- SearXNG running and loopback-only at `127.0.0.1:8888`;
- dashboard healthy;
- backend active;
- source exact and clean;
- live gate shell exit `0`.

### 15J — Provider readiness decision — COMPLETE / SEALED

Frozen decision set:

- `manual-research-production-ready`;
- `manual-research-experimental-only`;
- `manual-research-provider-degraded`.

Chosen empirical posture:

**`manual-research-provider-degraded`**

Rationale:

- query success target failed materially (`0.30` vs `>= 0.95`);
- no-candidate target failed materially (`0.70` vs `<= 0.05`);
- retrieval p95 target failed materially (`7648.376 ms` vs `<= 1500 ms`);
- diversity and duplicate-content targets passed;
- all authority/safety gates passed.

The correct engineering response is to keep research manual and improve provider coverage/reliability before considering any broader research authority.

## Frozen target outcomes

| Metric | Target | Result | Outcome |
|---|---:|---:|---|
| Live query success | >= 0.95 | 0.30 | FAIL |
| Provider no-candidate | <= 0.05 | 0.70 | FAIL |
| Unique source family | >= 0.80 | 0.963 | PASS |
| Duplicate content | <= 0.20 | 0.0 | PASS |
| Retrieval p95 | <= 1500 ms | 7648.376 ms | FAIL |
| Authority regressions | 0 | 0 | PASS |

Thresholds were frozen before the live run and were not revised after seeing the result.

## Phase 15 seal

Phase 15 is **COMPLETE / SEALED** at `manual-research-provider-degraded`.

Live evidence: `docs/phase15-research-provider-reliability-live-evidence-2026-08-19.md`.

PR #69 remains draft/open/unmerged until explicit owner authorization. A future provider-reliability milestone may improve coverage/latency, but any smart-routing or broader network/provider authority must remain a separate owner-approved milestone.
