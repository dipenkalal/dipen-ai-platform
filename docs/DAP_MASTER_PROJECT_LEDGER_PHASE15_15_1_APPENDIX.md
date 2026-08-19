# DAP Master Project Ledger — Phase 15–15.1 Verified Appendix

Date: 2026-08-19 UTC

This appendix extends `docs/DAP_MASTER_PROJECT_LEDGER.md` and `docs/DAP_MASTER_PROJECT_LEDGER_PHASE12_14_APPENDIX.md`. It records the verified Phase 15 and Phase 15.1 milestones without rewriting older reconstructed history.

## Phase 15 — Research Provider Reliability Remediation

Status: **COMPLETE / SEALED / MERGED**.

PR: #69.

Final CI/documentation head: `18b6a41c0cc9b01cf8ced589631ad73454cd5405`.

Merge commit: `1a79e3a1e04cb9d372f69c8f2630fc3f007a7830`.

Delivered:
- Research and Research Ops discoverability from the normal DAP landing page;
- bounded SearXNG scan window while preserving the `<= 3` retrieval ceiling;
- explicit provider-zero versus DAP-filtered-zero diagnostics;
- deterministic bounded fallback queries;
- stronger duplicate URL/source-family normalization;
- separate provider-search, retrieval-source, and pipeline timing;
- read-only provider-readiness projection;
- frozen 30-case provider corpus;
- isolated live benchmark database so production task/evidence/operations truth is not polluted;
- Research Operations provider-readiness dashboard panel;
- Guardian and regression boundaries preserving existing research authority.

### Phase 15 live evidence

The frozen 30-case Acer corpus completed with:
- success count `9 / 30`;
- query coverage `0.30`;
- no-candidate count `21 / 30`;
- no-candidate rate `0.70`;
- selected unique-source-family rate `0.963`;
- duplicate-content rate `0.0`;
- retrieval-source p95 approximately `7648 ms`;
- pipeline p95 approximately `23.4 s`.

Canonical Phase 15 report SHA-256:
`ade3a36bd60382cad33529af465d8f08f0c5e9feac71c1d823ed2f9af214ac7d`.

Final empirical posture: **`manual-research-provider-degraded`**.

Interpretation:
- diversity and duplicate suppression improved materially;
- provider query coverage remains poor;
- tail retrieval latency remains too high;
- smart-routing research remains disabled;
- no provider/network/knowledge/privileged authority expansion was granted.

## Phase 15.1 — Research UI and Data Hygiene

Status: **COMPLETE / SEALED / MERGED**.

PR: #70.

Live-validation source checkpoint: `abe0bbd9d407a83306513d79575054931ce74842`.

Final documentation/CI head: `0a49cb79c457d1c3b909dca1f34c663e9c25fecb`.

Merge commit: `d47c11166f5e52b2067f8804deeb75ffa048c1fb`.

Delivered:
- historical production evidence metrics and isolated Phase 15 corpus metrics clearly separated by scope;
- failed/blocked retrievals excluded from successful source-family analytics;
- loopback SSRF safety probes no longer appear as successful source families;
- failed immutable safety evidence remains preserved and inspectable;
- Research Workspace defaults to Research Agent-correlated evidence with an explicit `All evidence` view;
- primary navigation horizontal overflow no longer exposes the browser scrollbar strip;
- SearXNG health labeled as reachability only, not provider-quality readiness.

### Phase 15.1 Acer live proof

Final production truth remained unchanged:
- task ledger `15`;
- research evidence `16`;
- research operations events `6`.

Runtime proof:
- backend active, stable PID `677911` after one controlled restart;
- Guardian inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- dashboard healthy;
- SearXNG running and bound only to `127.0.0.1:8888`;
- local SearXNG health HTTP `200`, observed health latency `2.371 ms`;
- `/research` HTTP `200`;
- `/research/operations` HTTP `200`;
- `127.0.0.1` absent from successful source-family analytics;
- two blocked loopback safety evidence records preserved;
- source checkout clean.

Final live markers:

```text
PHASE15_1_SOURCE_FAMILY_HYGIENE|PASS
PHASE15_1_WORKSPACE_SCOPE|PASS
PHASE15_1_METRIC_SCOPE_CLARITY|PASS
PHASE15_1_NAVIGATION_HYGIENE|PASS
PHASE15_1_AUTHORITY_BOUNDARY|PASS
PHASE15_1_LIVE_GATE|PASS
```

## Current verified continuation checkpoint

Completed through: **Phase 15.1**.

Current production research posture:
- manual owner-supervised Research Agent only;
- fixed local `searxng-local-v1` on loopback;
- provider posture **`manual-research-provider-degraded`**;
- smart-routing research disabled;
- Guardian inactive;
- Telegram approvals disabled;
- no generic model-callable network authority;
- no automatic Knowledge mutation.

Remaining known research-system issue:
- provider coverage / no-candidate reliability;
- retrieval tail latency.

Next milestone: **Phase 16 — Research Provider Coverage & Latency Remediation**.

Phase 16 should remediate those measured provider-quality problems without expanding research authority.
