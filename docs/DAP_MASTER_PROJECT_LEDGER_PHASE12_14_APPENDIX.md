# DAP Master Project Ledger — Phase 12–14 Verified Appendix

Date: 2026-08-19 UTC

This appendix extends `docs/DAP_MASTER_PROJECT_LEDGER.md`, whose reconstructed body currently stops at the Phase 11-era checkpoint. It records the later milestones with exact repository/live evidence without rewriting older reconstructed history.

## Phase 12 — Internet Research Gateway

Status: **COMPLETE / SEALED / MERGED**.

Outcome:
- bounded public internet retrieval gateway;
- destination/DNS/redirect/SSRF policy;
- untrusted-content/prompt-injection boundary;
- immutable retrieval evidence and citations;
- Research Agent integration;
- local SearXNG provider adapter;
- read-only Research Workspace dashboard;
- final 5/5 live benchmark and production safety seal.

Final benchmark posture before activation: `provider-specific-activation`.

Phase 12 PR #64 merged to `main` before isolated Phase 13 activation work.

## Phase 13 — Provider-Specific Research Activation

Status: **COMPLETE / SEALED / MERGED**.

Main activation merge: `1130ddd8f7132a30666161d19898e18aec6c139c`.

Post-merge Phase 13 documentation cleanup main checkpoint: `5f4afa1869497aafee3d1cba3de9b96cdad2e8dd`.

Production authority after Phase 13:

```text
manual research-agent
  -> explicit research_search_query
  -> fixed local searxng-local-v1 on 127.0.0.1:8888
  -> DAP selects <= 3 candidate URLs
  -> sealed Phase 12 retrieval/evidence pipeline
```

Preserved boundaries:
- smart-routing cannot initiate web search;
- other agents cannot use the search field;
- no generic HTTP/socket/browser tool;
- provider snippets/titles are not evidence/model context;
- no automatic Knowledge mutation;
- Guardian and Telegram approval authority unchanged.

Phase 13 Acer live acceptance passed before merge.

## Phase 14 — Research Operations & Reliability

Status: **COMPLETE / SEALED / MERGED**.

PR: #67.

Final CI-green branch head: `08fe62a0fd58e1c036a8012c82830e67944ecd4e`.

Merge commit: `f9b49781ddcf98346c199128d52ec75e33d3f6fc`.

Delivered:
- source-family diversity and exact URL duplicate suppression;
- bounded transient GET retry telemetry;
- append-only research operations events;
- duplicate-content detection;
- dry-run/non-destructive retention planning;
- fixed-loopback SearXNG health telemetry;
- backend resource snapshots;
- GET-only Research Operations APIs;
- read-only `/research/operations` owner dashboard;
- deterministic reliability benchmark and weekly regression;
- resumable Acer burn-in and bounded provider-failure recovery.

### 14J live evidence

First burn-in run `2750295c-8acb-465b-86f1-417731d0a022` failed closed because local SearXNG returned zero admissible candidates. It created no public-web evidence or retrieval-operations event.

Two bounded recovery runs succeeded:
- `84d6dc11-b044-479d-87d3-a6a82d1248bb` — +3 evidence / +3 operations;
- `746654d9-1be0-42a6-9970-0acf404e2419` — +3 evidence / +3 operations.

Acer deterministic benchmark: 5/5 PASS.

Benchmark SHA-256: `57cf45169f98675df7c7567dc0bbaefae4c4ad1db74805d72bfeac4903f45bfc`.

Final live metrics:
- success rate `0.8125`;
- failure rate `0.1875`;
- retrieval p50 `279.737 ms`;
- retrieval p95 `2370.666 ms`;
- unique source-family rate `0.5`;
- duplicate-content rate `0.4615`;
- provenance-quality average `83.12`;
- SearXNG health latency `2.374 ms`.

Final production snapshot at live proof:
- task ledger `15`;
- research evidence `16`;
- research operations events `6`;
- backend PID `487274`, active;
- Guardian inactive;
- Telegram approvals false;
- dashboard healthy;
- SearXNG running on `127.0.0.1:8888`;
- source checkout clean.

Final empirical posture: **`manual-research-provider-degraded`**.

Interpretation:
- Phase 14 reliability/operations milestone passed and is merged;
- owner-supervised manual research remains available;
- provider path is not promoted to production-ready;
- smart-routing research remains disabled;
- next work should remediate provider/query reliability before any authority expansion.

## Current continuation checkpoint

Completed through: **Phase 14**.

Current production research posture: **manual provider-specific research enabled, provider degraded, smart-routing research disabled**.

Recommended next milestone: **Phase 15 — Research Provider Reliability Remediation**.

Suggested Phase 15 goals:
- improve no-candidate/query coverage without opening arbitrary provider authority;
- larger fixed-query burn-in sample;
- improve source-family diversity;
- reduce duplicate-content rate;
- improve p95/tail retrieval latency;
- distinguish provider reachability from useful-result health;
- re-run empirical readiness benchmark;
- do not begin smart-routing authority review until provider reliability meets explicit thresholds.
