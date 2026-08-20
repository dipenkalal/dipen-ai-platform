# Phase 16 — Research Provider Coverage & Latency Remediation

Status: **IN PROGRESS — 16A–16G CLOSED; 16H LIVE METRIC FAIL; 16H.1 LATENCY DIAGNOSIS NEXT; 16I–16J BLOCKED**

Base main checkpoint: `69d51ebaaf017c8c44be71f22e77209c42a8ba6b`.

Active PR branch: `phase16/research-provider-coverage-latency-canary`.

## Why Phase 16 exists

Phase 15 and Phase 15.1 were complete, sealed and merged, but their live provider baseline was not useful enough for readiness:

- frozen 30-case corpus success: `9/30` = `0.30`;
- no-candidate rate: `21/30` = `0.70`;
- provider search p95: `2117.782 ms`;
- retrieval-source p95: `7648.376 ms`;
- pipeline p95: `23413.71 ms`;
- selected unique-source-family rate: `0.963`;
- duplicate-content rate: `0.0`;
- final posture: `manual-research-provider-degraded`.

Phase 16 is an existing-defect remediation milestone. It must not expand research authority. Phase 16 does **not** activate smart-routing research.

## Frozen authority boundary

Preserved throughout Phase 16:

- manual owner-supervised `research-agent` remains the maximum research authority;
- provider remains `searxng-local-v1` on fixed loopback `127.0.0.1:8888`;
- selected retrieval ceiling remains at most three URLs;
- every selected URL still uses sealed DAP destination admission, pinned HTTPS retrieval, untrusted-content handling and immutable evidence;
- provider titles/snippets never become evidence or model context;
- no model-callable generic HTTP/socket/browser authority;
- no provider switching or arbitrary remote endpoint;
- no automatic Knowledge mutation;
- no destructive evidence cleanup;
- no Guardian/root/systemd/Docker authority granted to agents;
- Telegram approvals remain disabled;
- no autonomous merge/release/deployment authority;
- smart-routing research remains disabled.

Any future authority expansion requires a separate owner-approved milestone.

## Phase gates

### 16A — failure taxonomy and diagnostic contract — PASS

Implemented an isolated diagnostic contract distinguishing provider-zero-results, DAP-filtered-zero, provider transport errors, retrieval failures, benchmark timeouts and success while excluding provider titles/snippets.

Source/CI checkpoint: `70dfee5b76c9ed5ad06221a3ec0b448d689cc43c`.

### 16B — frozen baseline replay — PASS

The unchanged 30-case Phase 15 corpus was replayed in an isolated `/tmp` truth DB.

Canonical diagnostic SHA-256:

`d497d4a4cca4451b3bcef3e0a4fd16d81932645fa28d28ef883ddb686d88baed`

Observed:

- success: `9`;
- provider-zero-results: `21`;
- every other failure class: `0`.

The first nine cases succeeded; all remaining 21 returned zero raw provider results across all bounded attempts. Production truth and runtime remained unchanged.

Evidence: `docs/phase16a-live-evidence-2026-08-19.md`.

### 16C — SearXNG engine/configuration remediation — PASS

#### 16C.1 — engine failure telemetry — PASS

Live engine-health telemetry proved the original DuckDuckGo/Brave/Startpage-only pool was upstream-blocked:

- all 6/6 probes zero-result;
- Brave: repeated `too-many-requests`;
- DuckDuckGo: repeated `captcha`;
- Startpage: repeated `captcha` and suspension;
- contributing engines: `0`.

Canonical probe SHA-256:

`6b2578d231e7f43f8dcc032b4764adbc749efb827f4120990473b6fd68ddf962`

Evidence: `docs/phase16c1-engine-health-live-evidence-2026-08-19.md`.

#### 16C.2 — bounded replacement engine pool — PASS

The tracked provider pool was changed to credential-free diversified engines while keeping the same local provider and SafeSearch value:

- Google;
- Bing;
- Qwant;
- Mojeek;
- Wikipedia;
- Wiby.

DuckDuckGo, Brave and Startpage were removed from the bounded pool. Provider endpoint, loopback topology, JSON format, DAP query semantics, URL admission and at-most-three retrieval ceiling remained unchanged.

The replacement pool passed source/CI, shadow canary and controlled live one-container SearXNG promotion. The unchanged frozen 30-case corpus then reached:

- success/query coverage: `30/30` = `1.00`;
- no-candidate: `0/30` = `0.00`;
- canonical post-remediation diagnostic SHA-256: `55f5864899248d6bf266ab3d39c0efaac36f85e7ec5b8031c5bc2ca4f5cd375d`.

Coverage/no-candidate provider defects are resolved.

### 16D — deterministic query-coverage remediation — PASS / NO CHANGE REQUIRED

No query semantic expansion was justified after 16C.2. The unchanged frozen corpus already achieved 100% coverage with the corrected engine pool.

Decision:

- do not add model-generated search expansion;
- do not add new deterministic semantic terms merely to optimize the benchmark;
- preserve the existing bounded owner-query fallback contract.

### 16E — retrieval latency stage instrumentation — PASS

#### 16E.1 — live bounded stage instrumentation — PASS

Exact source head: `78e72acf917487b0296bfa91eef51815caf61581`.

Acer result:

- cases: `30/30` successful;
- retriever traces: `92` total / `84` successful;
- bounded retriever P50/P95: `363.489 / 1311.186 ms`;
- fetch P50/P95: `246.082 / 1029.870 ms`;
- DNS P50/P95: `37.175 / 258.355 ms`;
- report SHA-256: `1703569a7e691e683adbc02159272b59334b45a2001c2cbe399eea8019545ab9`.

#### 16E.2 — detailed decomposition — PASS

Exact source head: `39ef70ab17582a295ada926e9ec3a43b3fec291c`.

Acer result:

- cases: `30/30` successful;
- retriever traces: `93`;
- source records: `90` / `86` successful;
- frozen successful per-source P50/P95: `329.377 / 1698.145 ms`;
- frozen target: `<=1500 ms` — FAIL in that sample by `198.145 ms`;
- retriever P95: `1432.904 ms`;
- fetch P95: `1008.358 ms`;
- DNS P95: `207.958 ms`;
- fetch component P95: connect/TLS `329.803 ms`, response-header `301.919 ms`, response-body `375.469 ms`;
- successful sources with retries: `0`;
- report SHA-256: `9f93d2c9ccf61c1a21c44b3d6cf8a5bc95c5b5d2992823c188aae3d7c2f58c1b`.

The slow tail was heterogeneous and upstream-driven rather than a single DAP subsystem defect.

### 16F — latency remediation — PASS / NO PRODUCTION CHANGE REQUIRED

#### 16F.1 — bounded gzip shadow A/B — PASS

Exact source head: `be03a2eebc2c38503ffe3f60a0efb0b42612db4b`.

All 11 pull-request workflows passed on that head before Acer execution.

Same-session unchanged identity control:

- `30/30` successful;
- frozen successful per-source P50/P95: `364.027 / 1223.962 ms`;
- frozen `<=1500 ms` target: **PASS**;
- identity report SHA-256: `7a9392c9a8f2b60857ee8b61c40b280e3fe49b6f522071c73b24b536e83a60cc`.

Bounded gzip shadow:

- `30/30` successful;
- actual gzip responses observed: `68`;
- identity responses: `18`;
- frozen successful per-source P50/P95: `285.725 / 1047.676 ms`;
- same-session improvement: `176.286 ms`;
- frozen target: **PASS**;
- gzip report SHA-256: `97a1ffed0a17d2a539c254a0eb5fd26a9c2dd8821989ba947dd219ee403930b3`.

Decision:

`PHASE16_F1_AB_DECISION|IDENTITY_ALREADY_MEETS_TARGET`

Production transport therefore remains unchanged and identity-only. Gzip is not promoted during Phase 16 because the existing production transport already clears the frozen latency target. This is the minimum-change outcome required by the Phase 16 authority boundary.

Evidence: `docs/phase16f1-gzip-shadow-live-evidence-2026-08-19.md`.

### 16G — Research Operations diagnostics — PASS / NO CHANGE REQUIRED

The sealed read-only Research Operations surfaces already satisfy the Phase 16 observability requirement:

- `/api/v1/research/operations` exposes success/failure rate, P50/P95 source duration, retry/recovery counts, normalized error codes, source-family distribution, duplicate rate and reliability posture;
- `/api/v1/research/operations/provider-health` exposes fixed-provider reachability/latency;
- `/api/v1/research/operations/provider-readiness` exposes query coverage, no-candidate rate, source diversity, duplicate-content rate, retrieval-source P95 and machine-readable reason codes;
- the `/research/operations` dashboard renders these read-only metric scopes for the owner.

No mutation, service-control or provider-reconfiguration authority is exposed. No Phase 16 API/dashboard change is required.

### 16H — independent validation corpus — LIVE COMPLETE / METRIC FAIL

The frozen Phase 15 30-case corpus remains untouched. A separate Phase 16 corpus was validated with:

- version `phase16-validation-corpus-v1`;
- `24` independent cases;
- exactly `6` cases in each frozen category;
- no Phase 15 case IDs reused;
- no Phase 15 query strings reused.

Exact all-CI-green Acer validation head:

`4c12910d013df75e0db43a28ed9dc1c857e9f158`

Live metrics:

- success/query coverage: `24/24` = `1.0000` — PASS;
- no-candidate: `0/24` = `0.0000` — PASS;
- selected unique-source-family rate: `0.9861` — PASS;
- duplicate-content rate: `0.1806` — PASS;
- retrieval-source P50: `399.014 ms`;
- retrieval-source P95: `1731.707 ms` — FAIL against frozen `<=1500 ms`;
- provider search P95: `614.669 ms`;
- pipeline P95: `3952.765 ms`;
- all four category success rates: `1.0000`;
- failed cases: none.

Canonical report SHA-256:

`05c5417abdbbf2d13c75ec464ff4afd5fee733316cea68bbe288010a8e583cc1`

Exactly four of 72 successful retrieval-source durations exceeded `1500 ms`. The nearest-rank P95 landed on the fourth-largest duration (`1731.707 ms`), a `231.707 ms` miss.

Production truth remained `15/16/6`, backend PID remained `677911`, Guardian remained inactive, Telegram approvals remained false, SearXNG runtime/container/binding remained unchanged, production transport remained identity-only, and the source checkout remained clean.

Evidence: `docs/phase16h-independent-validation-live-evidence-2026-08-19.md`.

#### 16H.1 — targeted slow-tail latency diagnosis — NEXT

Do not alter the independent corpus and do not lower the frozen threshold.

Replay the cases implicated in the slow tail using the existing Phase 16E.2 detailed timing instrumentation, three iterations per case, under isolated `/tmp` truth. Diagnose DNS, connect/TLS, response-header, response-body, retry/backoff and tool-overhead contributions while recording only bounded safe source identity metadata.

The initial target set is:

- `p16-usgs-earthquake-magnitude`;
- `p16-overlay-filesystems`;
- `p16-rfc9293-tcp`;
- `p16-dns-over-https`.

16H.1 is diagnostic-only and cannot modify provider configuration, production transport, timeout/retry/concurrency policy, production truth, Guardian state, smart-routing authority or host privileges.

### 16I — Acer live burn-in — BLOCKED

16I remains blocked because the independent 16H latency target failed. It may begin only after 16H.1 establishes a justified resolution and the full frozen target set is independently satisfied without weakening thresholds or authority boundaries.

### 16J — empirical readiness decision — BLOCKED

Frozen minimum targets:

- success/query coverage `>= 0.95`;
- no-candidate rate `<= 0.05`;
- unique source-family rate `>= 0.80`;
- duplicate-content rate `<= 0.20`;
- retrieval-source P95 `<= 1500 ms`;
- zero authority-boundary regressions.

The independent 16H corpus currently passes every frozen readiness target except retrieval-source P95. Phase 16 cannot be sealed and cannot move to a production-ready research posture while that target remains failed.

A future green Phase 16 readiness decision still does not activate smart-routing research.

## Immediate next gate

Implement and CI-gate the diagnostic-only Phase 16H.1 targeted slow-tail replay. Then run it on Acer using the exact all-CI-green source head. Preserve the 24-case corpus, all frozen thresholds, the identity-only production transport and the complete Phase 16 authority boundary. Do not advance to 16I unless the latency defect is empirically resolved.