# Phase 12 — DAP Internet / Research Capability Gateway

Status: **COMPLETE / SEALED — 12A–12J PASSED**

Branch: `phase12/internet-research-gateway`

Base checkpoint: `af1699df9af3c679b7b780c30627ae95e58e33ac`

Final live-validation checkpoint: `619c22b55376e7fc5279a476e3e9933c9b744612`

## Mission

Give DAP a bounded, attributable way to retrieve public internet research evidence while preserving DAP as the sole authority for tasks, policy, credentials, evidence, and privileged actions.

> **DAP owns the brain and authority. Internet systems are read-only eyes.**

Phase 12 does not authorize arbitrary browsing, autonomous account actions, arbitrary outbound networking, private/internal network access through the public retrieval transport, credential forwarding, executable remote content, MCP/plugin auto-registration, Guardian/root/systemd authority, or automatic mutation of canonical DAP task/Knowledge truth.

## Final gate status

- 12A — Architecture + threat boundary: **COMPLETE / SEALED**
- 12B — Research request + source/tool registry contract: **COMPLETE / SEALED**
- 12C — URL, DNS, redirect, and SSRF policy: **COMPLETE / SEALED**
- 12D — Bounded public fetch transport: **COMPLETE / SEALED — LIVE ACER PROOF PASSED**
- 12E — Untrusted-content / prompt-injection boundary: **COMPLETE / SEALED**
- 12F — Citation + retrieval evidence persistence: **COMPLETE / SEALED**
- 12G — Research Agent integration: **COMPLETE / SEALED**
- 12H — Search/provider adapters: **COMPLETE / SEALED — ZERO-COST SEARXNG ACER LIVE PROOF PASSED**
- 12I — Dashboard Research workspace: **COMPLETE / SEALED — ACER LIVE PROOF PASSED**
- 12J — Empirical benchmark + production-readiness decision: **COMPLETE / SEALED — FINAL ACER LIVE PROOF PASSED**

## Final sealed capability checkpoint

Phase 12 establishes these invariants:

- DAP remains the sole task/policy/credential/privilege authority.
- Public-web URLs enter through bounded DAP/owner research inputs.
- Research URLs are rejected if resolved to any agent other than `research-agent`.
- The Research executor constructs bounded retrieval calls deterministically; there is no generic model-controlled internet tool-calling path.
- `research-agent` exposes Knowledge search plus exactly one bounded public internet retrieval tool.
- Every explicit URL passes URL/DNS admission, public-address policy, redirect revalidation, and the sealed HTTPS transport.
- Private, loopback, link-local, multicast, reserved, unspecified, metadata, container, and DAP-local destinations remain prohibited to the public retrieval transport.
- Active web content is stripped; visible remote content is preserved only as untrusted evidence inside a fixed DAP-owned prompt envelope.
- Immutable success/failure/cancellation retrieval evidence and DAP-owned citations are persisted additively without rewriting task truth or Knowledge.
- Remote page content cannot add retrieval URLs, select tools, change policy, request credentials, or expand scope.
- Search discovery is provided by a local zero-cost SearXNG runtime fixed to `127.0.0.1:8888`.
- Search candidates are URL-discovery input only; provider titles/snippets are not evidence and are not forwarded into the model evidence path.
- Search-selected URLs still pass the complete sealed DAP destination/retrieval/evidence pipeline.
- No paid search-provider credential is configured or required for the selected runtime path.
- The owner dashboard exposes read-only Research evidence through `/research` and GET-only API proxies.
- Dashboard provenance explicitly distinguishes **Internet Evidence** from Knowledge.
- Dashboard-side network authority, Knowledge mutation, task mutation, arbitrary URL fetching, Guardian/root/systemd action, and provider credentials remain disabled.
- No generic HTTP/socket client, browser session, cookie jar, provider credential, Guardian/root/systemd surface, MCP/plugin runtime, merge, release, or deployment authority is exposed to the Research Agent.

## 12H — Search/provider adapters

Production search discovery remains **$0** and local-first.

The selected path is self-hosted SearXNG:

```text
DAP research objective + bounded search query
  -> local SearXNG on 127.0.0.1:8888
  -> untrusted URL candidates only
  -> deterministic max-3 selection
  -> sealed internet.research.retrieve
  -> public destination admission
  -> public HTTPS transport
  -> untrusted evidence envelope
  -> immutable citation/evidence
```

The SearXNG boundary fixes:

- provider identity `searxng-local-v1`;
- endpoint `http://127.0.0.1:8888/search`;
- no provider credential;
- numeric loopback peer validation;
- JSON-only output;
- URL candidates remain non-evidence until DAP retrieval succeeds;
- provider snippets/titles cannot become model evidence.

The deployment template pins the image, publishes only `127.0.0.1:8888`, disables privileged mode/host networking/Docker socket use, drops capabilities, enables no-new-privileges, and bounds resources.

Detailed live evidence: `docs/phase12h-searxng-live-evidence-2026-08-18.md`.

## 12I — Dashboard Research workspace

The owner-facing Research workspace exposes read-only retrieval evidence with:

- objective/request identity and correlated Research Agent history;
- queried/retrieved source URLs;
- DAP-owned citations;
- retrieval status and policy state;
- content hashes and timestamps;
- failures/cancellations;
- admission hops and prompt-injection findings;
- provenance explicitly distinguishing Internet Evidence from Knowledge.

The dashboard remains inspection-only:

- backend: `GET /api/v1/research/evidence` and `GET /api/v1/research/evidence/{evidence_id}`;
- dashboard proxies are GET-only;
- `POST /api/research/evidence` returns HTTP 405;
- UI network authority is disabled;
- UI mutation authority is disabled;
- search candidate metadata is not exposed as evidence;
- Knowledge mutation remains disabled.

The final Acer dashboard proof preserved task ledger `11`, kept the backend active, left Guardian inactive, kept Telegram approvals false, and left SearXNG loopback-only.

The dashboard build path was also hardened: `.dockerignore` reduced the Docker context from roughly 840 MB to roughly 11.58 KB, and the final application build was proven offline before runtime packaging.

Detailed live evidence: `docs/phase12i-research-workspace-live-evidence-2026-08-18.md`.

## 12J — Empirical benchmark + production-readiness decision

Phase 12J froze five live cases:

1. public HTTPS retrieval;
2. loopback/SSRF rejection;
3. failure recovery from blocked source to explicit public source;
4. local SearXNG discovery followed by sealed DAP retrieval;
5. prompt-injection resistance.

Redirect-policy accuracy remains covered by deterministic Phase 12 transport/destination regressions instead of a flaky third-party redirect service.

### First-use evidence schema bootstrap

The live production DB had never persisted Phase 12 retrieval evidence, so `research_retrieval_evidence` was absent before the final benchmark. A narrow bootstrap helper made the repository's lazy schema initialization explicit.

It proved:

- evidence table absent before bootstrap;
- evidence table present after bootstrap;
- task ledger remained `11`;
- bootstrap added zero evidence rows;
- no service restart or authority expansion occurred.

### Final live benchmark

The final operator seal ran against checkpoint `619c22b55376e7fc5279a476e3e9933c9b744612` and passed:

```text
PHASE12J_FINAL|PASS
PHASE12_LIVE_EVIDENCE_GATE|PASS
```

Aggregate result:

```text
case_count|5
cases_passed|5
completion_rate|1.000
all_safety_cases_passed|true
total_wall_seconds|3.084
```

All five cases passed, including SSRF rejection, SearXNG-to-retrieval, failure recovery, and prompt-injection handling.

Expected immutable evidence delta:

- research evidence before: `0`;
- research evidence after: `7`;
- exact delta: `+7`;
- task ledger before/after: `11` / `11`.

Final production invariants remained intact:

- backend MainPID remained `396016`;
- backend remained active;
- Guardian remained inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false` remained unchanged;
- dashboard remained healthy;
- SearXNG remained running and bound exactly to `127.0.0.1:8888`;
- source HEAD remained unchanged and checkout clean;
- no automatic Knowledge mutation occurred;
- no privileged host action occurred;
- no main merge or deployment occurred during the benchmark.

The owner workspace exposed all new evidence read-only and the POST boundary remained HTTP 405.

Detailed live evidence: `docs/phase12j-live-evidence-2026-08-18.md`.

## Final production-readiness posture

The frozen benchmark returned:

```text
suggested_activation_posture|provider-specific-activation
```

Phase 12 therefore records **provider-specific activation as the technical production-readiness posture** for the already-bounded local SearXNG discovery path.

This is a readiness decision only. It does **not** activate new Research Agent authority by itself.

Actual search-discovery registration/enabling remains explicitly owner-gated. Until the owner authorizes that change, search discovery stays unregistered as new live Research Agent authority.

Likewise, PR #64 remains draft and unmerged until explicit owner approval.

## Phase 12 exit state

Phase 12 implementation and validation are complete.

There are **no remaining Phase 12 engineering gates**.

What remains outside the sealed milestone is an owner decision about whether to execute the already-recorded provider-specific activation recommendation and whether to merge PR #64.

Neither action is implied by the Phase 12 seal.

## Safety invariants

1. DAP owns canonical task truth and owner authorization.
2. Internet Research Gateway owns public network admission; models do not.
3. Research Agent receives evidence, not generic sockets or HTTP clients.
4. Fetched content is untrusted data, never policy or executable instruction.
5. Public internet retrieval cannot reach host/private/internal DAP infrastructure.
6. Credentials are never forwarded based on remote content or model output.
7. Redirects are new destinations and require full revalidation.
8. Network methods and headers are fixed by DAP policy, not generated by the model.
9. Retrieval does not automatically mutate Knowledge or task truth.
10. Every accepted retrieval outcome is attributable and reviewable.
11. Production search discovery remains zero-cost and local-first unless the owner explicitly changes that policy.
12. Search-discovery activation remains a separate explicit owner authorization after this sealed readiness decision.
