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
- [ ] Dashboard lint/build pass on Phase 15 branch.
- [ ] Acer serves the expected Phase 15 dashboard checkpoint.
- [ ] Owner confirms Research and Research Ops are visible from normal landing page.

## 15B — No-candidate diagnosis and bounded provider scanning

- [ ] Provider raw result count recorded.
- [ ] Provider considered-result count recorded.
- [ ] Invalid/malformed result count recorded.
- [ ] Destination-policy rejection count recorded.
- [ ] Provider-zero and filtering-zero outcomes are distinguishable.
- [ ] Provider scans beyond rejected top entries without exceeding bounded response/result limits.
- [ ] Accepted candidate count never exceeds requested count.
- [ ] Destination policy remains unchanged.
- [ ] Unit tests cover safe result after rejected entries.
- [ ] Guardian boundary covers no authority expansion.

## 15C — Deterministic query fallback contract

- [ ] Original query always attempted first.
- [ ] Fallback occurs only after zero admissible candidates.
- [ ] Maximum fallback attempt count frozen.
- [ ] Fallback variants derived deterministically from owner-supplied query.
- [ ] No model-generated autonomous expansion.
- [ ] Same fixed local provider used for every attempt.
- [ ] Attempt/query identity persisted in telemetry.

## 15D — Candidate diversity and duplicate suppression v2

- [ ] Canonical URL duplicate handling strengthened.
- [ ] Tracking/query-fragment duplicates handled deterministically.
- [ ] Unique source families preferred.
- [ ] Duplicate-family fallback remains explicit.
- [ ] Selected URL ceiling <= 3 preserved.
- [ ] Selection quality remains explicitly non-credibility.

## 15E — Duplicate-content reduction

- [ ] Immutable normalized-content hashes retained.
- [ ] Duplicate-content rate included in provider readiness.
- [ ] No evidence deletion/rewrite introduced.
- [ ] Duplicate-content groups remain owner-visible.

## 15F — Tail-latency remediation

- [ ] Provider latency separated from retrieval latency.
- [ ] Retry/timeout limits documented and frozen.
- [ ] Policy/cancellation failures never retried.
- [ ] Maximum wall-clock budget deterministic.

## 15G — Provider readiness model and owner dashboard

- [ ] Provider readiness state exposes reason codes.
- [ ] Query coverage shown read-only.
- [ ] Diversity shown read-only.
- [ ] Duplicate rate shown read-only.
- [ ] Latency shown read-only.
- [ ] No provider restart/reconfiguration action exposed.

## 15H — Expanded deterministic benchmark corpus

- [ ] Frozen corpus contains at least 30 cases.
- [ ] Corpus categories documented.
- [ ] CI fixture benchmark deterministic.
- [ ] Live Acer benchmark separated from offline CI.
- [ ] Success/no-candidate/diversity/duplicate/latency distributions emitted.
- [ ] Machine-readable report hash emitted.

## 15I — Acer live reliability burn-in

- [ ] Exact source checkpoint recorded.
- [ ] Live provider corpus executed.
- [ ] Success rate recorded.
- [ ] No-candidate rate recorded.
- [ ] Unique-source-family rate recorded.
- [ ] Duplicate-content rate recorded.
- [ ] p50/p95 latency recorded.
- [ ] Resource snapshot recorded.
- [ ] Guardian remains inactive.
- [ ] Telegram approvals remain false.
- [ ] SearXNG remains loopback-only.
- [ ] Frontend visibility confirmed.

## 15J — Provider readiness decision

- [ ] Exactly one final posture recorded.
- [ ] Final thresholds were frozen before live result review.
- [ ] Smart-routing remains disabled regardless of Phase 15 posture.
- [ ] Phase 15 live evidence document created.
- [ ] Final documentation CI green.
- [ ] Merge requires explicit owner authorization.
