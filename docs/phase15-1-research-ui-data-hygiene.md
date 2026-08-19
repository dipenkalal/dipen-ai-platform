# Phase 15.1 — Research UI and Data Hygiene

Status: **SOURCE FIXES IMPLEMENTED — CI / ACER VALIDATION PENDING**

Base: Phase 15 merge commit `1a79e3a1e04cb9d372f69c8f2630fc3f007a7830`.

Branch: `maintenance/phase15-1-research-ui-data-hygiene`.

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

## Validation gate

Required before merge:

- targeted backend Ruff/Mypy/compile/tests;
- explicit regression proving failed/blocked evidence cannot become a source family;
- Research Workspace and Research Operations dashboard boundary checks;
- Guardian maintenance boundary;
- dashboard lint/build and production image build;
- repository-wide workflows green;
- controlled Acer backend/dashboard deployment proof;
- live confirmation that `127.0.0.1` is absent from source-family analytics while failed immutable safety evidence remains inspectable in `All evidence`;
- live confirmation that navigation no longer exposes the browser scrollbar strip.

No Phase 16 work starts until this maintenance pass is sealed.
