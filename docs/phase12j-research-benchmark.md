# Phase 12J — Empirical Research Benchmark + Production-Readiness Decision

Status: **COMPLETE / SEALED — FINAL ACER LIVE PROOF PASSED**

Branch: `phase12/internet-research-gateway`

Final live benchmark checkpoint: `619c22b55376e7fc5279a476e3e9933c9b744612`

Detailed live evidence: `docs/phase12j-live-evidence-2026-08-18.md`

## Purpose

Phase 12J is the final Phase 12 validation gate. It does not add new production authority. It measures the already-sealed Phase 12 internet-research capability and records the resulting production-readiness posture.

The benchmark combines two evidence layers:

1. deterministic CI safety regressions for URL/DNS/redirect/SSRF policy, transport, untrusted-content handling, retrieval evidence, SearXNG discovery, the read-only Research workspace, bootstrap behavior, and the final operator seal boundary;
2. live Acer empirical execution for stable public retrieval, local SearXNG discovery followed by sealed DAP retrieval, failure recovery, persistence visibility, latency, resource cost, and final production-invariant comparison.

## Frozen live case matrix

The live harness `platform/backend/gateway/research_benchmark.py` remained frozen to five cases:

1. public HTTPS retrieval;
2. SSRF / loopback rejection;
3. failure recovery from blocked source to explicit public source;
4. local SearXNG discovery followed by the sealed DAP retrieval pipeline;
5. prompt-injection boundary resistance.

Redirect-policy accuracy remains covered by deterministic Phase 12 destination/transport regressions instead of a third-party live redirect dependency.

## First-use evidence schema bootstrap

The Acer database had not previously persisted retrieval evidence, so `research_retrieval_evidence` was legitimately absent before the final run. `research_benchmark_bootstrap.py` made the repository's lazy schema initialization explicit.

The bootstrap proved:

- evidence table absent before initialization;
- evidence table present afterward;
- task ledger stayed exactly `11`;
- zero retrieval evidence rows were added by bootstrap;
- no service restart, privileged action, Guardian contact, or authority expansion occurred.

The final operator proof is owned by `scripts/phase12j-final-live-seal.py`.

## Final live result

All five cases passed:

```text
case_count|5
cases_passed|5
completion_rate|1.000
all_safety_cases_passed|true
total_wall_seconds|3.084
```

Observed case wall times were approximately:

- public retrieval: `0.248s`;
- SSRF rejection: `0.008s`;
- failure recovery: `0.169s`;
- SearXNG-to-retrieval: `2.659s`;
- prompt-injection boundary: `0.001s`.

Canonical report observations:

- process user CPU: approximately `0.21492s`;
- process system CPU: approximately `0.026807s`;
- process max RSS: `45452 KiB`;
- report SHA-256: `dfadf7dbac09434070dcac4c22e5d5dc61b5f9c26afdc267415d426a2ae7acb3`.

## Evidence and safety invariants

Before benchmark execution:

- `task_ledger=11`;
- research evidence rows: `0`;
- backend active at MainPID `396016`;
- Guardian inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- dashboard healthy;
- SearXNG bound exactly to `127.0.0.1:8888`.

After benchmark execution:

- task ledger remained `11`;
- research evidence rows became `7`, exact delta `+7`;
- backend MainPID remained `396016`;
- Guardian remained inactive;
- Telegram approvals remained false;
- dashboard remained healthy;
- SearXNG remained healthy and loopback-only;
- source HEAD and clean-checkout state remained unchanged;
- no automatic Knowledge mutation occurred;
- no privileged host action occurred;
- no main merge or deployment occurred.

The backend Research API and dashboard proxy exposed all new evidence under the read-only Phase 12I boundary; `/research` returned HTTP 200 and POST remained HTTP 405.

## Final production-readiness decision

The frozen rule returned:

```text
suggested_activation_posture|provider-specific-activation
```

Phase 12J records **provider-specific activation as the final technical production-readiness posture** for the already-bounded local SearXNG discovery path.

This is a readiness decision, not an authority change. Actual registration/enabling of search discovery remains explicitly owner-gated and deferred until owner authorization. PR #64 remains draft and unmerged until explicit owner approval.

No Phase 12 decision grants arbitrary browsing, arbitrary network access, autonomous account actions, credentials, private/internal destination access, provider snippets as evidence, automatic Knowledge/task mutation, Guardian/root/systemd authority, autonomous merge, release, or deployment authority.

## Exit

Phase 12J: **COMPLETE / SEALED**.

Phase 12 implementation and validation are complete. Actual search-authority activation and PR merge remain explicit owner decisions.
