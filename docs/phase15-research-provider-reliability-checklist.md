# Phase 15 — Research Provider Reliability Remediation Checklist

## Authority baseline

- [x] Phase 14 is COMPLETE / SEALED / MERGED.
- [x] Phase 15 starts from `main` merge seal `512c03aaab6c49f7c7ec4c351dcd82e35f36b4bc`.
- [x] Work is isolated on `phase15/research-provider-reliability`.
- [x] Smart-routing research remains disabled.
- [x] Manual Research Agent remains the maximum research authority.
- [x] SearXNG endpoint remains fixed to `127.0.0.1:8888`.
- [x] Selected retrieval URL ceiling remains `<= 3`.
- [x] Provider titles/snippets remain non-evidence and excluded from model context.
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
- [x] Production dashboard image build passes in CI.
- [ ] Acer serves the expected Phase 15 dashboard checkpoint.
- [ ] Owner-visible Research and Research Ops links proven from normal landing page.

## 15B — No-candidate diagnosis and bounded provider scanning

- [x] Provider raw result count recorded.
- [x] Provider considered-result count recorded.
- [x] Invalid/malformed result count recorded.
- [x] Destination-policy rejection count recorded.
- [x] Provider-zero and filtering-zero outcomes are distinguishable.
- [x] Provider scans beyond rejected top entries within fixed 20-result limit.
- [x] Accepted candidate count never exceeds requested count.
- [x] Downstream selected retrieval URL ceiling remains `<= 3`.
- [x] Destination policy remains unchanged.
- [x] Unit tests cover safe result after rejected entries.
- [x] Guardian boundary covers no authority expansion.

## 15C — Deterministic query fallback contract

- [x] Original query always attempted first.
- [x] Fallback occurs only after zero admissible candidates.
- [x] Maximum fallback attempt count frozen at 3.
- [x] Fallback variants derived deterministically from owner-supplied query.
- [x] Fallback variants cannot add query terms.
- [x] No model-generated autonomous expansion.
- [x] Same fixed local provider used for every attempt.
- [x] Provider switching disabled.
- [x] Attempt/query identity persisted in safe Research Agent step metadata.
- [x] Failed-search diagnostics exclude provider titles/snippets.
- [x] Successful-search diagnostics exclude provider titles/snippets.

## 15D — Candidate diversity and duplicate suppression v2

- [x] Canonical URL duplicate handling strengthened.
- [x] Tracking/query-fragment duplicates handled deterministically.
- [x] Duplicate normalization does not rewrite selected retrieval URLs.
- [x] Unique source families preferred.
- [x] Duplicate-family fallback remains explicit.
- [x] Selected URL ceiling `<= 3` preserved.
- [x] Selection quality remains explicitly non-credibility.
- [x] Provider titles/snippets remain non-evidence.

## 15E — Duplicate-content readiness measurement

- [x] Immutable normalized-content hashes retained.
- [x] Duplicate-content rate included in provider readiness.
- [x] No evidence deletion/rewrite introduced.
- [x] Duplicate-content groups remain owner-visible.
- [ ] Final live duplicate-content rate recorded in 15I.

## 15F — Tail-latency remediation

- [x] Provider-search latency separated from retrieval latency.
- [x] Total pipeline latency separately recorded.
- [x] Existing bounded retry/timeout rules preserved.
- [x] Policy/cancellation failures remain non-retryable.
- [x] Live retrieval p95 target frozen at `1500 ms`.
- [x] Maximum live corpus case wall clock frozen at `60 s`.
- [ ] Final live p50/p95 distributions recorded in 15I.

## 15G — Provider readiness model and owner dashboard

- [x] Provider readiness state exposes stable reason codes.
- [x] Query coverage shown read-only.
- [x] No-candidate rate shown read-only.
- [x] Diversity shown read-only.
- [x] Duplicate rate shown read-only.
- [x] Retrieval p95 shown read-only.
- [x] Missing live report shows insufficient-data/pending rather than fabricated readiness.
- [x] Hashed live report is validated before use.
- [x] No provider restart/reconfiguration action exposed.
- [x] Direct Research Ops navigation present.
- [ ] Deployed Acer dashboard reads live Phase 15 report after 15I.

## 15H — Expanded deterministic benchmark corpus

- [x] Frozen corpus contains exactly 30 cases.
- [x] Corpus categories documented.
- [x] CI fixture benchmark deterministic.
- [x] Deterministic benchmark passes `30/30`.
- [x] Live Acer benchmark separated from offline CI.
- [x] Live benchmark requires isolated `/tmp` truth DB.
- [x] Production task/evidence mutation flags are false.
- [x] Success/no-candidate/diversity/duplicate/latency distributions emitted.
- [x] Machine-readable report hash emitted.
- [x] Per-case live timeout is bounded.

## Pre-live source/CI gate

- [x] Phase 15 Ruff passes.
- [x] Phase 15 Mypy passes.
- [x] Phase 15 compile passes.
- [x] Phase 15 deterministic tests pass.
- [x] Sealed search/retrieval regression matrix passes.
- [x] Phase 15 Guardian boundary passes.
- [x] Dashboard authority/navigation checks pass.
- [x] Dashboard lint/build passes.
- [x] Production dashboard image build passes.
- [x] All nine repository workflows green on pre-live code checkpoint `d3c6289cc7a32da14a18552937826d8f81a99da2`.

## 15I — Acer live reliability burn-in

- [ ] Exact final pre-live source checkpoint recorded.
- [ ] Controlled backend activation loads Phase 15 code.
- [ ] Controlled dashboard deployment loads Phase 15 frontend.
- [ ] Normal `/` landing page exposes Research and Research Ops.
- [ ] Readiness endpoint shows live-corpus-pending before corpus execution.
- [ ] Frozen 30-case live provider corpus executed.
- [ ] Isolated benchmark truth DB used.
- [ ] Production task ledger unchanged by corpus.
- [ ] Production research evidence unchanged by corpus.
- [ ] Production research operations events unchanged by corpus.
- [ ] Success rate recorded.
- [ ] No-candidate rate recorded.
- [ ] Unique-source-family rate recorded.
- [ ] Duplicate-content rate recorded.
- [ ] Provider and retrieval p50/p95 recorded.
- [ ] Hashed durable live report written.
- [ ] Readiness endpoint loads valid live report.
- [ ] Resource snapshot recorded.
- [ ] Guardian remains inactive.
- [ ] Telegram approvals remain false.
- [ ] SearXNG remains loopback-only.
- [ ] Dashboard remains healthy.
- [ ] Source checkout remains clean.

## 15J — Provider readiness decision

- [x] Final numeric thresholds frozen before live result review.
- [x] Smart-routing remains disabled regardless of Phase 15 posture.
- [ ] Exactly one final posture recorded.
- [ ] Phase 15 live evidence document created.
- [ ] Final status/roadmap/checklist updated with empirical result.
- [ ] Final documentation CI green.
- [ ] PR #69 remains unmerged until explicit owner authorization.
