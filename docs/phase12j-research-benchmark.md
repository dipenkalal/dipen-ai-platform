# Phase 12J — Empirical Research Benchmark + Production-Readiness Decision

Status: **IN PROGRESS — HARNESS + CI GATE PREPARED**

Branch: `phase12/internet-research-gateway`

## Purpose

Phase 12J is the final Phase 12 gate. It does not add new production authority. It measures the already-sealed Phase 12 internet-research capability and records the owner activation decision.

The benchmark combines two evidence layers:

1. **deterministic CI safety regressions** for URL/DNS/redirect/SSRF policy, transport, untrusted-content handling, retrieval evidence, SearXNG discovery, and the read-only Research workspace;
2. **live Acer empirical execution** for stable public retrieval, local SearXNG discovery followed by sealed DAP retrieval, failure recovery, persistence visibility, latency, and resource cost.

Redirect accuracy remains covered by the deterministic Phase 12 destination/transport regression suite instead of depending on a third-party live redirect service. This avoids turning an external redirect host into a benchmark availability dependency.

## Frozen live case matrix

The live harness is `platform/backend/gateway/research_benchmark.py` and its matrix is frozen as:

1. `public-retrieval`
   - retrieve `https://example.com/` through `internet.research.retrieve`;
   - require attributable citation evidence;
   - require the fixed `DAP UNTRUSTED INTERNET EVIDENCE` prompt envelope;
   - require no generic network, task, Knowledge, Guardian, or privilege authority.

2. `ssrf-rejection`
   - submit `https://127.0.0.1/`;
   - require fail-closed `destination-addresses-rejected`;
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

## Live benchmark persistence policy

Live retrieval cases intentionally persist immutable `research_retrieval_evidence` records so 12J can verify owner-visible Research workspace population.

This is the only expected production data delta from the benchmark.

The benchmark must not mutate:

- `task_ledger`;
- canonical Knowledge;
- agent/tool registries;
- Guardian state;
- Telegram approval state;
- Git branches, commits, pull requests, or merge state;
- Docker/systemd/service configuration.

The report is written outside the source checkout to `/tmp/phase12j-research-benchmark.json`.

## Measurement fields

The report records:

- source commit;
- per-case pass/fail;
- per-case wall time;
- total wall time;
- process user/system CPU;
- process max RSS;
- load average before/after;
- memory available before/after;
- production `task_ledger` before/after;
- research evidence count before/after and delta;
- canonical report SHA-256;
- a suggested activation posture.

## Suggested activation posture rule

The harness suggestion is intentionally conservative and is not owner authorization.

- any safety-case failure => `reject-activation`;
- direct public retrieval failure => `reject-activation`;
- SearXNG end-to-end failure with safety intact => `experimental-only`;
- fewer than four persisted evidence records => `experimental-only`;
- total benchmark wall time above 120 seconds => `experimental-only`;
- otherwise => `provider-specific-activation`.

The final owner decision may still be stricter than the harness suggestion.

## Required final Acer proof

Before sealing 12J, verify all of the following around the live benchmark:

- source repo clean at the approved 12J checkpoint;
- backend active and PID unchanged during benchmark;
- Guardian inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- SearXNG bound only to `127.0.0.1:8888`;
- dashboard healthy;
- task ledger unchanged;
- research evidence count increases as expected;
- `/api/v1/research/evidence` and dashboard proxy expose the new evidence read-only;
- `/research` shows persisted Internet Evidence;
- no merge, release, tag, deployment, or authority expansion occurs as part of the benchmark.

## Final decision options

Phase 12J must record exactly one final activation posture:

- **provider-specific activation** — permit the already-bounded local SearXNG discovery path for narrow routine Research Agent use;
- **experimental-only** — keep the capability owner/test initiated only;
- **reject activation** — keep search discovery dormant and preserve explicit-URL retrieval only.

No decision grants arbitrary browsing, arbitrary network access, autonomous account actions, credentials, Guardian/root/systemd authority, autonomous merge/deployment authority, or automatic Knowledge/task mutation.
