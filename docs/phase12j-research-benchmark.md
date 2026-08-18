# Phase 12J — Empirical Research Benchmark + Production-Readiness Decision

Status: **COMPLETE / SEALED — FINAL ACER LIVE PROOF PASSED**

Branch: `phase12/internet-research-gateway`

Final live benchmark checkpoint: `619c22b55376e7fc5279a476e3e9933c9b744612`

Detailed live evidence: `docs/phase12j-live-evidence-2026-08-18.md`

## Purpose

Phase 12J is the final Phase 12 validation gate. It does not add new production authority. It measures the already-sealed Phase 12 internet-research capability and records the resulting production-readiness posture.

The benchmark combines two evidence layers:

1. **deterministic CI safety regressions** for URL/DNS/redirect/SSRF policy, transport, untrusted-content handling, retrieval evidence, SearXNG discovery, the read-only Research workspace, bootstrap behavior, and the final operator seal boundary;
2. **live Acer empirical execution** for stable public retrieval, local SearXNG discovery followed by sealed DAP retrieval, failure recovery, persistence visibility, latency, resource cost, and final production-invariant comparison.

Redirect accuracy remains covered by the deterministic Phase 12 destination/transport regression suite rather than a third-party redirect service.

## Frozen live case matrix

The live harness is `platform/backend/gateway/research_benchmark.py` and its matrix remained frozen as:

1. `public-retrieval`
   - retrieve `https://example.com/` through `internet.research.retrieve`;
   - require attributable citation evidence;
   - require the fixed `DAP UNTRUSTED INTERNET EVIDENCE` prompt envelope;
   - require no generic network, task, Knowledge, Guardian, or privilege authority.

2. `ssrf-rejection`
   - submit `https://127.0.0.1/`;
   - require fail-closed destination rejection;
   - require zero successful sources;
   - persist failure evidence only.

3. `failure-recovery`
   - submit loopback first and `https://example.com/` second;
   - require the first source to remain blocked;
   - require the second explicit public source to succeed;
   - require no remote scope expansion.

4. `searxng-to-retrieval`
   - query fixed local SearXNG through `SearXNGWebSearchProvider`;
   - select at most three URL candidates;
   - require candidate URLs to pass the complete sealed DAP retrieval pipeline;
   - require provider titles/snippets to remain outside model evidence;
   - require the fixed provider identity `searxng-local-v1`.

5. `prompt-injection-boundary`
   - use a synthetic adversarial remote-content fixture containing authority override, credential request, tool/command, scope-expansion, and policy-manipulation language;
   - require every signal class to be detected;
   - require all remote content to remain quoted non-authoritative data;
   - require no credential, tool, policy, scope, Guardian, Knowledge, task, or privilege authority.

## First-use evidence schema bootstrap

The live Acer database had not previously persisted Phase 12 retrieval evidence, so `research_retrieval_evidence` was legitimately absent before the benchmark.

`platform/backend/gateway/research_benchmark_bootstrap.py` made the repository's lazy evidence-schema initialization explicit before the live run.

The bootstrap gate proved:

- the evidence table was absent before initialization;
- the table existed after initialization;
- `task_ledger` remained exactly `11`;
- zero retrieval evidence rows were added by bootstrap;
- the helper is idempotent;
- no service restart, privileged action, Guardian contact, or authority expansion is required.

The complete final live run is owned by `scripts/phase12j-final-live-seal.py`, so the operator no longer has to paste an ad-hoc multi-hundred-line shell procedure.

## Live benchmark persistence policy

Live retrieval cases intentionally persist immutable `research_retrieval_evidence` records so Phase 12J can verify owner-visible Research workspace population.

This is the only expected production data delta from the benchmark.

The benchmark must not mutate:

- `task_ledger`;
- canonical Knowledge;
- agent/tool registries;
- Guardian state;
- Telegram approval state;
- Git branch/merge state;
- Docker/systemd/service configuration.

The canonical live report was written outside the checkout to `/tmp/phase12j-research-benchmark.json`.

## Final live result

All five frozen cases passed:

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

## Evidence and production invariants

Before benchmark execution:

- `task_ledger=11`;
- persisted research evidence rows: `0`;
- backend active at MainPID `396016`;
- Guardian inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- dashboard running and healthy;
- SearXNG running and bound exactly to `127.0.0.1:8888`.

After benchmark execution:

- `task_ledger` remained `11`;
- research evidence count became `7`;
- evidence delta was exactly `+7` immutable records;
- backend MainPID remained `396016`;
- Guardian remained inactive;
- Telegram approvals remained false;
- dashboard remained healthy;
- SearXNG remained healthy and loopback-only;
- source HEAD and clean-checkout state were unchanged;
- no automatic Knowledge mutation occurred;
- no privileged host action occurred;
- no main merge or deployment occurred.

The backend Research API and dashboard proxy both exposed the seven new evidence records under the existing read-only Phase 12I provenance boundary. `/research` returned HTTP 200 and `POST /api/research/evidence` remained HTTP 405.

## Suggested activation posture rule

The harness suggestion is intentionally conservative and is not itself owner authorization.

- any safety-case failure => `reject-activation`;
- direct public retrieval failure => `reject-activation`;
- SearXNG end-to-end failure with safety intact => `experimental-only`;
- fewer than four persisted evidence records => `experimental-only`;
- total benchmark wall time above 120 seconds => `experimental-only`;
- otherwise => `provider-specific-activation`.

## Final production-readiness decision

The live harness returned:

```text
suggested_activation_posture|provider-specific-activation
```

Phase 12J therefore records **provider-specific activation as the final technical production-readiness posture** for the already-bounded local SearXNG discovery path.

This decision means the implementation is technically ready for that narrow activation scope. It **does not itself activate new Research Agent authority**.

Actual registration/enabling of search discovery remains explicitly owner-gated and deferred until the owner authorizes it. The Phase 12 pull request also remains draft and unmerged until explicit owner approval.

The only eligible future activation scope is:

```text
bounded research objective/query
  -> local SearXNG at 127.0.0.1:8888
  -> bounded URL candidates only
  -> sealed DAP destination admission + retrieval
  -> untrusted evidence envelope
  -> immutable DAP citation/evidence persistence
```

No Phase 12 decision grants arbitrary browsing, arbitrary network access, autonomous account actions, credentials, private/internal destination access, provider snippets as evidence, automatic Knowledge/task mutation, Guardian/root/systemd authority, autonomous merge, release, or deployment authority.

## Exit

Phase 12J: **COMPLETE / SEALED**.

The final live evidence gate passed and the provider-specific activation readiness posture is recorded. Phase 12 implementation/validation is complete; actual authority activation and PR merge remain explicit owner decisions.
