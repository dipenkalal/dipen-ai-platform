# Phase 16 — Research Provider Coverage & Latency Remediation

Status: **IN PROGRESS — EXISTING-ISSUE REMEDIATION ONLY**

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

SearXNG safe search is set to `2`. This may contribute to low coverage, but Phase 16 will not change provider configuration until the failure population is classified empirically.

## Phase gates

### 16A — failure taxonomy and diagnostic contract

Goal: classify every provider attempt without exposing provider text.

Required categories include:

- provider zero raw results;
- raw results returned but invalid candidate shape;
- raw results returned but rejected by DAP destination policy;
- candidate selection succeeded but retrieval failed;
- benchmark case timeout;
- provider transport/error condition.

The diagnostic record must preserve per-attempt counts, fallback usage and safe timing metadata while continuing to exclude provider titles/snippets.

### 16B — frozen baseline replay

Re-run the same 30-case Phase 15 corpus with the new diagnostic contract in an isolated `/tmp` truth database. No production task/evidence/operations mutation.

The purpose is diagnosis, not to move thresholds or change queries.

### 16C — SearXNG engine/configuration remediation

Only after 16B identifies the dominant failure class, make the smallest deterministic provider-side correction justified by evidence.

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

Implement 16A diagnostics first, then run 16B against the unchanged live provider configuration. Do not tune SearXNG before the failure distribution is captured.
