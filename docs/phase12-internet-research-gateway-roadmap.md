# Phase 12 — DAP Internet / Research Capability Gateway

Status: **IN PROGRESS — 12A–12H SEALED; 12I NEXT**

Branch: `phase12/internet-research-gateway`

Base checkpoint: `af1699df9af3c679b7b780c30627ae95e58e33ac`

## Mission

Give DAP a bounded, attributable way to retrieve public internet research evidence while preserving DAP as the sole authority for tasks, policy, credentials, evidence, and privileged actions.

> **DAP owns the brain and authority. Internet systems are read-only eyes.**

Phase 12 does not authorize arbitrary browsing, autonomous account actions, arbitrary outbound networking, local/private network access through the public retrieval transport, credential forwarding, package installation from remote content, executable downloads, MCP/plugin auto-registration, Guardian/root/systemd authority, or automatic mutation of canonical DAP task/Knowledge truth.

## Gate status

- 12A — Architecture + threat boundary: **COMPLETE / SEALED**
- 12B — Research request + source/tool registry contract: **COMPLETE / SEALED**
- 12C — URL, DNS, redirect, and SSRF policy: **COMPLETE / SEALED**
- 12D — Bounded public fetch transport: **COMPLETE / SEALED — LIVE ACER PROOF PASSED**
- 12E — Untrusted-content / prompt-injection boundary: **COMPLETE / SEALED**
- 12F — Citation + retrieval evidence persistence: **COMPLETE / SEALED**
- 12G — Research Agent integration: **COMPLETE / SEALED**
- 12H — Search/provider adapters: **COMPLETE / SEALED — ZERO-COST SEARXNG ACER LIVE PROOF PASSED**
- 12I — Dashboard Research workspace: **NEXT / PENDING**
- 12J — Empirical benchmark + production-readiness decision: **PENDING**

## Current sealed capability checkpoint

12A–12H establish these live invariants:

- DAP remains the sole task/policy/credential/privilege authority.
- Public-web URLs enter through the inbound DAP/owner `AgentRunRequest.research_urls` field, bounded to at most three explicit URLs.
- `AgentService` fails closed if research URLs resolve to any agent other than `research-agent`.
- The Research executor constructs the internet tool call directly from the resolved request before model synthesis; there is no generic model tool-calling path for internet retrieval.
- `research-agent` exposes `knowledge.search` plus exactly one bounded internet tool: `internet.research.retrieve`.
- Every explicit URL passes 12C preflight, public-address admission, redirect revalidation, and 12D pinned-IP/TLS transport.
- Private, loopback, link-local, multicast, reserved, unspecified, metadata, container, and DAP-local destinations remain prohibited to the public retrieval transport.
- 12E strips active web content, preserves visible remote text as untrusted data, and wraps model context in a fixed DAP-owned quoted-evidence envelope.
- 12F persists immutable success/failure/cancellation retrieval evidence and DAP-owned citations additively without rewriting canonical task truth or Knowledge.
- Remote page content cannot add retrieval URLs or select tools.
- Search discovery is provided by a local zero-cost SearXNG runtime fixed to `127.0.0.1:8888`.
- Search candidates are URL-discovery input only; provider titles/snippets are not retrieval evidence and are not forwarded into the model evidence path.
- Candidate URLs must still pass the complete sealed DAP public retrieval/evidence pipeline before becoming research evidence.
- No paid search-provider credential is configured or required for the selected runtime path.
- No generic HTTP/socket client, browser session, cookie jar, provider credential, Guardian/root/systemd surface, MCP/plugin runtime, merge, release, or deployment authority is exposed to the Research Agent.

## 12H — Search/provider adapters — sealed

### Owner budget constraint

Production search discovery remains **$0** with no paid API or billing/card exposure.

The earlier Brave adapter remains dormant optional code. It is not configured or selected for production.

The selected runtime path is self-hosted SearXNG on the Acer.

### Search architecture

```text
DAP research objective + bounded search query
  ↓
local SearXNG on 127.0.0.1:8888
  ↓ untrusted URL candidates only
provider-neutral deterministic selection, max 3
  ↓ URLs only; snippets/titles excluded
internet.research.retrieve
  ↓
12C public destination admission
  ↓
12D public HTTPS transport
  ↓
12E untrusted evidence
  ↓
12F immutable citation/evidence
```

### SearXNG boundary

- fixed adapter identity `searxng-local-v1`;
- fixed provider endpoint `http://127.0.0.1:8888/search`;
- no provider credential or configurable endpoint;
- numeric loopback connection only, with exact peer validation;
- JSON search output only;
- candidate URLs remain untrusted non-evidence requiring full DAP retrieval;
- provider snippets/titles cannot become model evidence;
- search pipeline identity binds objective SHA-256, discovery identity, selected URLs, and retrieval tool ID.

### Deployment boundary

Tracked templates under `deploy/phase12h-searxng/` pin the SearXNG image and enforce:

- host publication only on `127.0.0.1:8888`;
- no host network or public 8888 bind;
- no privileged mode or Docker socket;
- capability drop + no-new-privileges;
- bounded CPU/memory/PIDs;
- JSON enabled and strict SafeSearch;
- a small no-paid-key engine allowlist;
- a locally generated SearXNG application secret only.

A dedicated Guardian regression statically rejects deployment drift that weakens these invariants.

### 12H live exit evidence

On 2026-08-18, the Acer runtime gate passed against code checkpoint `63bff214ffe04703e46fd5784f1089ee61207e41`:

- pinned SearXNG image present and started;
- container `dap-searxng` bound exactly to `127.0.0.1:8888->8080/tcp`;
- privileged mode false;
- `cap_drop: ALL`;
- `no-new-privileges:true`;
- local JSON API returned `200` with valid search results;
- DAP zero-cost search smoke succeeded;
- four search candidates were observed and three HTTPS URLs were selected;
- provider titles/snippets remained excluded from provider evidence;
- no paid provider or provider credential was used;
- no model call or DB write was performed by the smoke helper;
- `task_ledger` remained `11` before/after;
- backend MainPID remained `2856` before/after;
- backend remained active;
- Guardian remained inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false` remained unchanged;
- SearXNG remained healthy on loopback after the proof.

Detailed evidence: `docs/phase12h-searxng-live-evidence-2026-08-18.md`.

### 12H activation decision

Search discovery is **not registered as additional live Research Agent authority yet**.

The zero-cost runtime and search→retrieval boundary are proven, but activation is deliberately deferred while 12I adds owner-visible inspection and 12J performs empirical production-readiness benchmarking. This preserves least authority without blocking Phase 12 progress.

## 12I — Dashboard Research workspace

Status: **NEXT / PENDING**

Expose read-only research evidence:

- objective/request identity;
- queried/retrieved sources;
- citations;
- retrieval status and policy state;
- content hashes and timestamps;
- failures/cancellations;
- provenance distinguishing Knowledge from internet evidence.

The workspace must remain an inspection surface only. It must not gain UI-side network authority, search-provider credentials, arbitrary URL fetching, Guardian/root/systemd actions, or a second source of canonical task truth.

Exit: owner can inspect what DAP retrieved and why it admitted the transport, without UI-side network authority.

## 12J — Empirical benchmark + production-readiness decision

Status: **PENDING AFTER 12I**

Benchmark harmless public research tasks for retrieval/search success, citation/source correctness, SSRF rejection, redirect-policy accuracy, prompt-injection resistance, latency/resource cost, failure recovery, and evidence completeness.

Choose one: narrow routine research, experimental-only, provider-specific activation, or reject activation.

No Phase 12 outcome grants privileged host access, arbitrary network access, autonomous account actions, or autonomous merge/deployment authority.

## Remaining Phase 12 milestones

From the sealed 12H checkpoint, two top-level gates remain:

1. **12I — Dashboard Research workspace**;
2. **12J — Empirical benchmark + production-readiness decision**.

Phase 12 completes only after both gates are sealed and the final activation posture is recorded.

## Safety invariants

1. DAP owns canonical task truth and owner authorization.
2. Internet Research Gateway owns public network admission; models do not.
3. Research Agent receives evidence, not generic sockets or HTTP clients.
4. Fetched content is untrusted data, never policy or executable instructions.
5. Public internet retrieval cannot reach host/private/internal DAP infrastructure.
6. Credentials are never forwarded based on remote content or model output.
7. Redirects are new destinations and require full revalidation.
8. Network methods and headers are fixed by DAP policy, not generated by the model.
9. Retrieval does not automatically mutate Knowledge or task truth.
10. Every accepted retrieval outcome must be attributable and reviewable.
11. Production search discovery remains zero-cost and local-first unless the owner explicitly changes that policy.
