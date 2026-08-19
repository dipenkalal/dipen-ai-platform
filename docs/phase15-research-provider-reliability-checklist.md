# Phase 15 — Research Provider Reliability Remediation Checklist

## Authority baseline

- [x] Phase 14 is COMPLETE / SEALED / MERGED.
- [x] Phase 15 starts from `main` merge seal `512c03aaab6c49f7c7ec4c351dcd82e35f36b4bc`.
- [x] Work is isolated on `phase15/research-provider-reliability`.
- [x] Smart-routing research remains disabled.
- [x] Manual Research Agent remains the maximum research authority.
- [x] SearXNG endpoint remains fixed to `127.0.0.1:8888`.
- [x] Selected retrieval URL ceiling remains <= 3.
- [x] Provider titles/snippets remain non-evidence.
- [x] Automatic Knowledge mutation remains disabled.
- [x] Destructive evidence cleanup remains disabled.
- [x] Agent Guardian/root/systemd/Docker authority remains absent.

## 15A — Frontend visibility and runtime baseline

- [x] `/research` route exists.
- [x] `/research/operations` route exists.
- [x] Research page links to Research Operations.
- [x] Primary navigation exposes `Research`.
- [x] Primary navigation exposes direct `Research Ops`.
- [x] Primary navigation is no longer hidden on the normal `/` Guardian landing page.
- [x] Chat navigation isolation remains unchanged.
- [x] Dashboard boundary test freezes the visibility contract.
- [x] Dashboard lint/build pass on Phase 15 branch.
- [x] Acer serves the expected Phase 15 dashboard checkpoint.
- [x] Live landing-page HTML contains both Research navigation links.
- [x] `/research` and `/research/operations` return HTTP 200.
- [x] `PHASE15_FRONTEND_VISIBILITY|PASS`.

## 15B — No-candidate diagnosis and bounded provider scanning

- [x] Provider raw result count recorded.
- [x] Provider considered-result count recorded.
- [x] Invalid/malformed result count recorded.
- [x] Destination-policy rejection count recorded.
- [x] Provider-zero and filtering-zero outcomes are distinguishable.
- [x] Provider scans beyond rejected top entries without exceeding bounded response/result limits.
- [x] Accepted candidate count never exceeds requested count.
- [x] Destination policy remains unchanged.
- [x] Unit tests cover safe result after rejected entries.
- [x] Guardian boundary covers no authority expansion.

## 15C — Deterministic query fallback contract

- [x] Original query always attempted first.
- [x] Fallback occurs only after zero admissible candidates.
- [x] Maximum fallback attempt count frozen at three.
- [x] Fallback variants derived deterministically from owner-supplied query.
- [x] No model-generated autonomous expansion.
- [x] Same fixed local provider used for every attempt.
- [x] Attempt/query identity exposed in safe Research Agent history metadata.
- [x] Provider titles/snippets remain excluded from that history/model context.

## 15D — Candidate diversity and duplicate suppression v2

- [x] Canonical URL duplicate handling strengthened.
- [x] Tracking/query-fragment duplicates handled deterministically.
- [x] Unique source families preferred.
- [x] Duplicate-family fallback remains explicit.
- [x] Selected URL ceiling <= 3 preserved.
- [x] Selection quality remains explicitly non-credibility.
- [x] Live unique-source-family rate `0.963` meets target `>= 0.80`.

## 15E — Duplicate-content reduction

- [x] Immutable normalized-content hashes retained.
- [x] Duplicate-content rate included in provider readiness.
- [x] No evidence deletion/rewrite introduced.
- [x] Duplicate-content groups remain measurable/owner-visible.
- [x] Live duplicate-content rate `0.0` meets target `<= 0.20`.

## 15F — Tail-latency remediation

- [x] Provider latency separated from retrieval latency.
- [x] Retry/timeout limits documented and frozen.
- [x] Policy/cancellation failures never broaden destinations or methods.
- [x] Maximum live per-case wall-clock budget frozen at 60 seconds.
- [x] Live provider-search p95 recorded: `2117.782 ms`.
- [x] Live retrieval-source p95 recorded: `7648.376 ms`.
- [x] Live total-pipeline p95 recorded: `23413.71 ms`.
- [x] Retrieval p95 target result recorded as FAIL (`7648.376 ms` vs `<= 1500 ms`).

## 15G — Provider readiness model and owner dashboard

- [x] Provider readiness state exposes reason codes.
- [x] Query coverage shown read-only.
- [x] Diversity shown read-only.
- [x] Duplicate rate shown read-only.
- [x] Latency shown read-only.
- [x] No provider restart/reconfiguration action exposed.
- [x] Backend and dashboard projections load the same validated live report SHA.
- [x] Final readiness state is `degraded`.

## 15H — Expanded deterministic benchmark corpus

- [x] Frozen corpus contains exactly 30 cases.
- [x] Corpus categories documented.
- [x] CI fixture benchmark deterministic.
- [x] Offline CI benchmark passes `30/30`.
- [x] Live Acer benchmark separated from offline CI.
- [x] Success/no-candidate/diversity/duplicate/latency distributions emitted.
- [x] Machine-readable report hash emitted.
- [x] Live report SHA-256 is `ade3a36bd60382cad33529af465d8f08f0c5e9feac71c1d823ed2f9af214ac7d`.

## 15I — Acer live reliability burn-in

- [x] Exact source checkpoint recorded: `6fae0c2a6de7413bb093607c8558eced9877cd0f`.
- [x] Live provider corpus executed.
- [x] Success rate recorded: `0.30` (`9/30`).
- [x] No-candidate rate recorded: `0.70` (`21/30`).
- [x] Unique-source-family rate recorded: `0.963`.
- [x] Duplicate-content rate recorded: `0.0`.
- [x] Provider-search p50/p95 recorded: `964.589 / 2117.782 ms`.
- [x] Retrieval-source p50/p95 recorded: `2202.51 / 7648.376 ms`.
- [x] Pipeline p95 recorded: `23413.71 ms`.
- [x] Resource snapshot recorded.
- [x] Production task truth unchanged: `15 -> 15`.
- [x] Production research evidence unchanged: `16 -> 16`.
- [x] Production research operations unchanged: `6 -> 6`.
- [x] Isolated benchmark task ledger remains `0`.
- [x] Guardian remains inactive.
- [x] Telegram approvals remain false.
- [x] SearXNG remains loopback-only at `127.0.0.1:8888`.
- [x] Dashboard remains healthy.
- [x] Frontend visibility confirmed by live HTTP/HTML proof.
- [x] `PHASE15_LIVE_CORPUS|PASS`.
- [x] `PHASE15_AUTHORITY_BOUNDARY|PASS`.
- [x] `PHASE15_15I|PASS`.
- [x] Live gate shell exit `0`.

## 15J — Provider readiness decision

- [x] Final thresholds were frozen before live result review.
- [x] Exactly one final posture recorded.
- [x] Final posture: `manual-research-provider-degraded`.
- [x] Success target failed (`0.30` vs `>= 0.95`).
- [x] No-candidate target failed (`0.70` vs `<= 0.05`).
- [x] Unique-source-family target passed (`0.963` vs `>= 0.80`).
- [x] Duplicate-content target passed (`0.0` vs `<= 0.20`).
- [x] Retrieval p95 target failed (`7648.376 ms` vs `<= 1500 ms`).
- [x] Zero authority-boundary regressions.
- [x] Smart-routing remains disabled regardless of Phase 15 posture.
- [x] Phase 15 live evidence document created.
- [x] Final documentation CI green on checkpoint `ef7bc9d830f54fe8405e97b8535d2482bc39a10c` across all nine repository workflows.
- [ ] Merge requires explicit owner authorization.

## Final state

Phase 15 engineering, Acer live evidence, empirical posture selection, and final documentation CI are complete. The only remaining gate is explicit owner merge authorization. The provider remains deliberately manual and degraded; no authority expansion is implied by completing Phase 15.
