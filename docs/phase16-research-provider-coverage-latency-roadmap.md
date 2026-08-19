# Phase 16 — Research Provider Coverage & Latency Remediation

Status: **IN PROGRESS — 16A/16B LIVE DIAGNOSTIC PASS; 16C.1 ENGINE TELEMETRY NEXT**

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

The merged SearXNG deployment currently keeps only three engines:

- DuckDuckGo;
- Brave;
- Startpage.

SearXNG safe search is set to `2`.

Phase 16A/16B proved that configuration/output behavior is the current coverage bottleneck population, but it did not yet prove whether the dominant mechanism is upstream engine suspension/throttling/CAPTCHA/access denial or genuinely empty engine results. Provider settings therefore remain unchanged until 16C.1 captures engine-level diagnostics.

## Phase gates

### 16A — failure taxonomy and diagnostic contract — PASS

Implemented a safe isolated diagnostic contract that distinguishes:

- provider zero raw results;
- raw results returned but invalid candidate shape;
- raw results returned but rejected by DAP destination policy;
- candidate selection succeeded but retrieval failed;
- benchmark case timeout;
- provider transport/error condition.

The diagnostic preserves per-attempt counts, fallback usage and safe timing metadata while excluding provider titles/snippets.

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

Sequence observation: the first nine cases succeeded, then every remaining 21 case returned zero raw results across all three bounded attempts. That is consistent with an order/burst-dependent upstream-engine problem, but Phase 16B intentionally did not capture engine error metadata and therefore does not yet prove the specific engine failure mechanism.

Production task/evidence/operations counts were unchanged and the SearXNG settings SHA remained unchanged.

Live evidence: `docs/phase16a-live-evidence-2026-08-19.md`.

### 16C — SearXNG engine/configuration remediation

#### 16C.1 — engine failure telemetry — NEXT

Before any configuration mutation, capture only safe engine-level metadata already present in the local SearXNG JSON response:

- engines that contributed returned results;
- unresponsive engine names;
- DAP-normalized failure classes such as rate limit, CAPTCHA, access denied, timeout, network/HTTP/proxy/SSL/parsing/API failure or unknown;
- whether SearXNG reports an engine suspended.

Do not persist raw engine error strings, titles, snippets, answers, corrections or suggestions.

Run a bounded control-probe/replay that can distinguish order-dependent upstream engine exhaustion from genuinely empty query results.

#### 16C.2 — minimal configuration correction

Only after 16C.1 identifies the dominant engine failure class, make the smallest deterministic SearXNG-side correction justified by live evidence.

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

Implement 16C.1 engine-level telemetry and a bounded control probe. Do not change SearXNG engine selection, SafeSearch, provider endpoint or query semantics until the upstream engine failure mode is proven.
