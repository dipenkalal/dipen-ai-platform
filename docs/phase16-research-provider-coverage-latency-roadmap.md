# Phase 16 — Research Provider Coverage & Latency Remediation

Status: **IN PROGRESS — 16A/16B PASS; 16C.1 LIVE ENGINE BLOCKING CONFIRMED; 16C.2 SOURCE REMEDIATION IN PROGRESS**

Base main checkpoint: `69d51ebaaf017c8c44be71f22e77209c42a8ba6b`.

Branch: `phase16/research-provider-coverage-latency`.

## Why Phase 16 exists

Phase 15 and Phase 15.1 are complete, sealed, merged and deployed. Their safety, UI, data-hygiene, provenance-diversity and duplicate-suppression gates passed. The remaining known defect is provider usefulness/retrieval performance, not authority or frontend hygiene.

Frozen Phase 15 live baseline:

- 30-case corpus;
- success `9/30` = `0.30`;
- no-candidate `21/30` = `0.70`;
- provider search p50 `964.589 ms`;
- provider search p95 `2117.782 ms`;
- retrieval source p50 `2202.51 ms`;
- retrieval source p95 `7648.376 ms`;
- pipeline p95 `23413.71 ms`;
- selected unique-source-family rate `0.963`;
- duplicate-content rate `0.0`;
- final posture `manual-research-provider-degraded`.

## Frozen authority boundary

Phase 16 must not expand research authority. It does **not** activate smart-routing research.

Preserved invariants:

- manual owner-supervised `research-agent` remains the maximum research authority;
- provider remains `searxng-local-v1` on fixed loopback `127.0.0.1:8888`;
- selected retrieval ceiling remains at most three URLs;
- every selected URL still goes through sealed DAP destination admission, HTTPS retrieval, untrusted-content handling and immutable evidence;
- no provider titles/snippets become evidence or model context;
- no model-callable generic HTTP/socket/browser tool;
- no provider switching or arbitrary remote endpoint;
- no automatic Knowledge mutation;
- no destructive evidence cleanup;
- no Guardian/root/systemd/Docker authority granted to agents;
- Telegram approvals remain disabled;
- no autonomous merge/release/deployment authority.

Any future authority expansion requires a separate owner-approved milestone.

## Current configuration observation

The original Phase 15/16 deployment kept only three engines:

- DuckDuckGo;
- Brave;
- Startpage.

SearXNG safe search is set to `2`.

Phase 16C.1 proved that all three configured engines are currently blocked upstream under the live DAP workload. SafeSearch is not implicated by the captured failure metadata and remains unchanged during 16C.2 so the engine-pool variable is isolated.

## Phase gates

### 16A — failure taxonomy and diagnostic contract — PASS

Implemented a safe isolated diagnostic contract that distinguishes provider zero raw results, DAP-filtered raw results, retrieval failures, case timeouts and provider transport/error conditions while excluding provider titles/snippets.

Source/CI checkpoint before live replay: `70dfee5b76c9ed5ad06221a3ec0b448d689cc43c`.

All 11 repository pull-request workflows passed on that exact checkpoint.

### 16B — frozen baseline replay — PASS

The unchanged 30-case Phase 15 corpus was replayed on the Acer with the original provider configuration in an isolated `/tmp` truth database.

Canonical diagnostic report SHA-256:

`d497d4a4cca4451b3bcef3e0a4fd16d81932645fa28d28ef883ddb686d88baed`

Observed failure population:

- success: `9`;
- provider-zero-results: `21`;
- DAP-filtered-zero: `0`;
- provider transport errors: `0`;
- retrieval failures: `0`;
- benchmark timeouts: `0`;
- unclassified no-candidate: `0`.

Category result:

- official documentation: `9` success, `1` provider-zero-results;
- standards: `10` provider-zero-results;
- general factual: `5` provider-zero-results;
- multi-source technical: `5` provider-zero-results.

Sequence observation: the first nine cases succeeded, then every remaining 21 case returned zero raw results across all three bounded attempts.

Production task/evidence/operations counts were unchanged and the SearXNG settings SHA remained unchanged.

Live evidence: `docs/phase16a-live-evidence-2026-08-19.md`.

### 16C — SearXNG engine/configuration remediation

#### 16C.1 — engine failure telemetry — PASS

A six-query low-volume control probe captured only safe engine metadata already exposed by the local SearXNG JSON response.

Canonical probe SHA-256:

`6b2578d231e7f43f8dcc032b4764adbc749efb827f4120990473b6fd68ddf962`

Observed result:

- all six probes returned zero results;
- all three known-good Python controls also returned zero results;
- Brave: `too-many-requests` on every probe and reported suspended after the first probe;
- DuckDuckGo: `captcha` on every probe;
- Startpage: `captcha` on every probe and reported suspended;
- total normalized CAPTCHA failures: `12`;
- total normalized rate-limit failures: `6`;
- contributing engines: `0`.

This proves `upstream-engine-blocking` as the dominant current coverage defect rather than DAP filtering or query-specific zero results.

Production truth, backend PID, SearXNG container identity/start time, loopback binding and tracked configuration remained unchanged.

Live evidence: `docs/phase16c1-engine-health-live-evidence-2026-08-19.md`.

#### 16C.2 — minimal configuration correction — SOURCE CHECKPOINT

The tracked candidate configuration replaces the blocked three-engine-only pool with a credential-free diversified pool while preserving the same local SearXNG provider:

- Google;
- Bing;
- Qwant;
- Mojeek;
- Wikipedia;
- Wiby.

The removed pool is:

- DuckDuckGo;
- Brave;
- Startpage.

All six replacement engines are explicitly enabled in the tracked settings. The provider endpoint, local-only topology, SafeSearch value `2`, JSON search format, DAP query semantics, URL admission path and at-most-three retrieval ceiling remain unchanged.

The source boundary is frozen by `test_phase16_engine_pool_remediation_boundary.py`, which verifies the exact engine set, removal of the blocked pool, absence of credential fields, unchanged SafeSearch, fixed loopback provider endpoint and frozen Phase 16 authority language.

Current source checkpoint: `15ccdce88466cafa234556f4cc10daaae94f0da9`.

The engine-pool change must pass the complete repository CI matrix before any Acer configuration mutation. Acer deployment must use a reversible one-container SearXNG recreation with exact pre/post configuration hashes, runtime safety checks and an immediate low-volume canary before any 30-case replay.

No provider endpoint change and no provider switching.

### 16D — deterministic query-coverage remediation

Improve bounded owner-query normalization/fallback only where evidence supports it. No model-generated search expansion and no added semantic terms outside deterministic rules.

### 16E — retrieval latency stage instrumentation

Separate retrieval tail latency into bounded stages where practical, including connection/TLS/read/body processing/retry costs, without adding network authority.

### 16F — latency remediation

Make only the transport/retry/timeout changes justified by 16E evidence. Preserve fail-closed destination and content-size/time budgets.

### 16G — Research Operations diagnostics

Expose read-only owner-visible root-cause and latency summaries. No mutation/service-control controls.

### 16H — regression corpus

Preserve the frozen 30-case Phase 15 corpus for comparability and add an independent Phase 16 validation corpus rather than modifying cases to fit the implementation.

### 16I — Acer live burn-in

Run isolated live validation with production-truth counts frozen and all authority/runtime invariants rechecked.

### 16J — empirical readiness decision

Targets remain at least:

- success/query coverage `>= 0.95`;
- no-candidate rate `<= 0.05`;
- unique source-family rate `>= 0.80`;
- duplicate-content rate `<= 0.20`;
- retrieval-source p95 `<= 1500 ms`;
- zero authority-boundary regressions.

A green Phase 16 engineering gate does not itself activate smart-routing research.

## Immediate next gate

Run the complete CI matrix on source checkpoint `15ccdce88466cafa234556f4cc10daaae94f0da9`. Only after that exact source checkpoint is green may the Acer SearXNG container be recreated with the new tracked settings. The first live action after recreation is a bounded engine-health canary; do not run the 30-case corpus until the replacement pool proves it can return candidates without immediately entering a blocked state.
