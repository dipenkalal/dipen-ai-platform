# Phase 16 — Research Provider Coverage & Latency Remediation

Status: **IN PROGRESS — 16A–16G CLOSED; 16H INITIAL LIVE LATENCY FAIL DIAGNOSED; 16H.2 SOURCE-SELECTION RESILIENCE IMPLEMENTED; FULL 24-CASE REVALIDATION NEXT; 16I–16J BLOCKED**

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

### 16F — latency remediation — PASS / NO PRODUCTION TRANSPORT CHANGE REQUIRED

#### 16F.1 — bounded gzip shadow A/B — PASS

Exact source head: `be03a2eebc2c38503ffe3f60a0efb0b42612db4b`.

Same-session unchanged identity control:

- `30/30` successful;
- frozen successful per-source P50/P95: `364.027 / 1223.962 ms`;
- frozen `<=1500 ms` target: **PASS**;
- identity report SHA-256: `7a9392c9a8f2b60857ee8b61c40b280e3fe49b6f522071c73b24b536e83a60cc`.

Bounded gzip shadow:

- `30/30` successful;
- actual gzip responses observed: `68`;
- frozen successful per-source P50/P95: `285.725 / 1047.676 ms`;
- same-session improvement: `176.286 ms`;
- frozen target: **PASS**;
- gzip report SHA-256: `97a1ffed0a17d2a539c254a0eb5fd26a9c2dd8821989ba947dd219ee403930b3`.

Decision:

`PHASE16_F1_AB_DECISION|IDENTITY_ALREADY_MEETS_TARGET`

Production transport remains unchanged and identity-only. Gzip was not promoted because the existing production transport already clears the frozen latency target in the same-session control.

Evidence: `docs/phase16f1-gzip-shadow-live-evidence-2026-08-19.md`.

### 16G — Research Operations diagnostics — PASS / NO CHANGE REQUIRED

The sealed read-only Research Operations surfaces already satisfy the Phase 16 observability requirement:

- `/api/v1/research/operations` exposes success/failure rate, P50/P95 source duration, retry/recovery counts, normalized error codes, source-family distribution, duplicate rate and reliability posture;
- `/api/v1/research/operations/provider-health` exposes fixed-provider reachability/latency;
- `/api/v1/research/operations/provider-readiness` exposes query coverage, no-candidate rate, source diversity, duplicate-content rate, retrieval-source P95 and machine-readable reason codes;
- the `/research/operations` dashboard renders these read-only metric scopes for the owner.

No mutation, service-control or provider-reconfiguration authority is exposed. No Phase 16 API/dashboard change is required.

### 16H — independent validation corpus — INITIAL LIVE COMPLETE / LATENCY METRIC FAIL

The frozen Phase 15 30-case corpus remains untouched. A separate Phase 16 corpus was validated with:

- version `phase16-validation-corpus-v1`;
- `24` independent cases;
- exactly `6` cases in each frozen category;
- no Phase 15 case IDs reused;
- no Phase 15 query strings reused.

Exact initial validation head:

`4c12910d013df75e0db43a28ed9dc1c857e9f158`

Initial live metrics:

- success/query coverage: `24/24` = `1.0000` — PASS;
- no-candidate: `0.0000` — PASS;
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

Evidence: `docs/phase16h-independent-validation-live-evidence-2026-08-19.md`.

#### 16H.1 — targeted slow-tail latency diagnosis — PASS

Exact source head:

`c4457ae394f6f835f7e2aa03fdf443a676b9fa24`

The four cases implicated in the initial tail were replayed three times each using E2 timing decomposition under isolated truth:

- `12/12` runs successful;
- `36/36` source records successful;
- source P50/P95: `298.305 / 1628.755 ms`;
- max: `1953.731 ms`;
- four sources above `1500 ms`;
- dominant fetch component: response-header;
- retry/backoff was not the cause.

A repeatable source-specific upstream TTFB pattern was isolated: `atscontainers.com` exceeded the target in all three overlay-filesystem iterations (`1556.426`, `1522.586`, `1628.755 ms`), dominated by response-header wait (`948.956`, `916.311`, `1045.895 ms`). A `github.com` RFC source had one transient `1953.731 ms` event but the next two iterations fell to `566.226` and `675.700 ms`.

H.1 therefore does not justify changing the threshold, corpus, transport, timeout/retry policy or adding a source blacklist.

Canonical report SHA-256:

`c9cfa723ef69ff554aadaeba8936b719352b12319e485d599c90a0b8355559f6`

Evidence: `docs/phase16h1-slow-tail-live-evidence-2026-08-19.md`.

#### 16H.2 — deterministic source-selection resilience — IMPLEMENTED / CI GATE

H.2 addresses the repeatable source-selection tail generically rather than special-casing observed domains or benchmark cases.

Implemented source-selection policy:

- `dap-source-family-diversity-url-resilience-v2`;
- `dap-url-retrieval-resilience-v1`;
- `dap-searxng-provider-support-reservoir-v1`.

The fixed local SearXNG request is unchanged. For the normal five-candidate research request, DAP may retain up to eight already-returned admissible candidates from the same provider JSON response, still within the existing maximum 20-result scan. No additional provider request is made. Small explicit requests below five retain their exact requested candidate count.

Candidate ordering may use only bounded non-content metadata:

- original provider rank;
- count of contributing SearXNG engines for that result, without persisting per-candidate engine names;
- URL-structure signals for documentation/standards/static-document/government/education paths and hosts.

The selection policy does not use provider title/snippet text, does not fetch or probe candidates before selection, does not assess factual credibility, contains no observed-domain or corpus-specific blacklist/allowlist, and does not change query semantics.

Source-family diversity and canonical URL duplicate suppression remain active. Final remote retrieval remains capped at exactly the existing at-most-three URL ceiling. Every selected URL still passes the same sealed DAP admission and identity-only pinned HTTPS retrieval path.

Dedicated backend tests and Guardian boundaries freeze:

- reservoir `<=8` and raw scan `<=20`;
- one fixed provider request only;
- final retrieval `<=3`;
- provider titles/snippets not used for selection or evidence;
- no per-candidate engine names persisted;
- no remote pre-probe;
- no provider switching;
- no timeout/retry/concurrency change;
- no production transport change;
- no source-specific exception;
- independent 24-case corpus and `1500 ms` target unchanged.

The source implementation passed Phase 16 Ruff, mypy, compile, H.2 tests, sealed Phase 15 regressions and Guardian boundary. A historical Phase 15 Guardian assertion that froze the old `query.count` admission implementation was updated to freeze the stronger current invariant: scan `<=20`, reservoir `<=8`, no extra provider request, final retrieval `<=3`.

The full unchanged 24-case Phase 16H corpus must now be rerun once against H.2. H.1 is not rerun and cannot substitute for this full validation.

### 16I — Acer live burn-in — BLOCKED

16I remains blocked until the unchanged full 24-case independent corpus passes every frozen Phase 16 target after H.2. No targeted subset may unblock 16I.

### 16J — empirical readiness decision — BLOCKED

Frozen minimum targets:

- success/query coverage `>= 0.95`;
- no-candidate rate `<= 0.05`;
- unique source-family rate `>= 0.80`;
- duplicate-content rate `<= 0.20`;
- retrieval-source P95 `<= 1500 ms`;
- zero authority-boundary regressions.

A future green Phase 16 readiness decision still does not activate smart-routing research.

## Immediate next gate

Complete the full pull-request CI matrix on the exact H.2 source/documentation head, then run exactly one unchanged `phase16-validation-corpus-v1` 24-case isolated validation on Acer. Do not rerun H.1, modify the independent corpus, lower any threshold, promote gzip, or change runtime/service configuration for this validation. If the full corpus passes every frozen target, proceed to 16I. If it fails, use that single full report to decide the next source change before asking the owner for another Acer action.
