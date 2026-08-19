# Phase 15.1 — Research UI and Data Hygiene

Status: **COMPLETE / SEALED — ACER LIVE PROOF PASSED; MERGE PENDING OWNER AUTHORIZATION**

Base: Phase 15 merge commit `1a79e3a1e04cb9d372f69c8f2630fc3f007a7830`.

Branch: `maintenance/phase15-1-research-ui-data-hygiene`.

CI-green/live-validation source checkpoint: `abe0bbd9d407a83306513d79575054931ce74842`.

## Purpose

Correct existing Research Workspace and Research Operations presentation/data-hygiene issues before starting Phase 16. This is a maintenance pass, not a new research-authority milestone.

## Issues addressed

1. Historical production-evidence success/failure metrics and the isolated Phase 15 30-case provider-readiness metrics were visually adjacent without enough scope explanation. Both were valid, but values such as historical `81.3%` success and Phase 15 `30.0%` query coverage could be misread as contradictory.
2. Source-family analytics included failed/blocked retrieval destinations. This allowed loopback safety probes such as `127.0.0.1` to appear as a source family even though DAP correctly rejected them.
3. Research Workspace mixed Research Agent-correlated evidence with standalone validation/safety evidence in one undifferentiated default list.
4. Primary navigation intentionally used horizontal overflow but exposed the browser scrollbar/arrow strip at constrained widths.

## Fixes

### Successful-only source-family analytics

`ResearchOperationsService._record_source_family()` now returns no source family for evidence whose outcome is not `succeeded`.

Effects:

- failed and blocked URLs remain immutable evidence;
- they still contribute to failure/evidence-health accounting where appropriate;
- they no longer contribute to source-family counts or source-family provenance fields;
- successful evidence remains unchanged;
- no evidence is deleted, rewritten, or reclassified in storage.

### Research Workspace scope control

The default Research Workspace view now shows evidence correlated to Research Agent history. An explicit `All evidence` view keeps every immutable evidence record accessible, including standalone validation/safety evidence.

This is presentation-only filtering. The backend evidence API remains read-only and returns the same persisted immutable records.

### Research Operations metric clarity

The UI now labels historical evidence/operations separately from the isolated Phase 15 live provider corpus and states that their percentages are not expected to match.

SearXNG health is labeled endpoint reachability only; it is not presented as provider-quality readiness.

Source-family copy explicitly states that only successful retrieval evidence participates and blocked loopback probes are excluded.

### Navigation overflow hygiene

Primary navigation remains horizontally scrollable at constrained widths, but the browser scrollbar is hidden. Icon-only navigation links retain explicit accessible labels and titles.

## Authority boundary

Phase 15.1 does **not** activate smart-routing research and does not expand research authority.

It adds no:

- new provider or provider endpoint;
- model-callable network tool;
- provider switching;
- automatic Knowledge mutation;
- evidence deletion or rewriting;
- Guardian/root/systemd/Docker authority;
- Telegram approval authority;
- autonomous merge/release/deployment authority.

Manual owner-supervised Research Agent execution remains the maximum research authority.

## Validation result

All ten repository workflows passed on source checkpoint `abe0bbd9d407a83306513d79575054931ce74842` before the live gate.

The controlled Acer validation then passed with:

- exact branch/head and clean source;
- baseline production truth: task ledger `15`, research evidence `16`, research operations `6`;
- one controlled backend restart, ending with stable PID `677911`;
- local SearXNG healthy at HTTP `200`, measured health latency `2.371 ms` during the resume proof;
- SearXNG local-only and loopback contract valid;
- no network, mutation, or service-control authority granted by the health projection;
- successful source-family set `domainwheel.com`, `en.wikipedia.org`, `example.com`, `iana.org`, `macmyths.com`, `w3schools.com`;
- `127.0.0.1` absent from successful source-family analytics;
- two blocked loopback safety-evidence records preserved;
- Research Workspace split verified: `8` Research Agent-correlated records and `8` standalone immutable evidence records at initial live validation;
- deployed dashboard bundle verified to contain `reachability only`, `Research Agent runs`, and `Metric scopes:` copy;
- production truth remained exactly `15 / 16 / 6` after validation;
- backend active, Guardian inactive, `DAP_TELEGRAM_APPROVALS_ENABLED=false`, dashboard healthy, SearXNG running on `127.0.0.1:8888`;
- `/research` and `/research/operations` both returned HTTP `200`;
- final source remained exact and clean.

Final live markers:

```text
PHASE15_1_SOURCE_FAMILY_HYGIENE|PASS
PHASE15_1_WORKSPACE_SCOPE|PASS
PHASE15_1_METRIC_SCOPE_CLARITY|PASS
PHASE15_1_NAVIGATION_HYGIENE|PASS
PHASE15_1_AUTHORITY_BOUNDARY|PASS
PHASE15_1_LIVE_GATE|PASS
```

The first live command produced one false-negative verification at the UI-copy check because `curl` inspected initial HTML while the `reachability only` text is client-state rendered. No runtime rollback was performed. The resume proof corrected the verification method by checking the live health API contract and the deployed dashboard bundle, without another backend restart or dashboard rebuild.

Detailed evidence: `docs/phase15-1-live-evidence-2026-08-19.md`.

## Exit state

Phase 15.1 engineering and live-validation gates are complete. Phase 16 remains frozen until this maintenance PR is merged under explicit owner authorization.
