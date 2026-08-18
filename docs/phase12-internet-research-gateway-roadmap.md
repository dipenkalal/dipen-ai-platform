# Phase 12 — DAP Internet / Research Capability Gateway

Status: **IN PROGRESS — 12A–12G SEALED; 12H NEXT**

Branch: `phase12/internet-research-gateway`

Base checkpoint: `af1699df9af3c679b7b780c30627ae95e58e33ac`

## Mission

Give DAP a bounded, attributable way to retrieve public internet research evidence while preserving DAP as the sole authority for tasks, policy, credentials, evidence, and privileged actions.

The governing rule is:

> **DAP owns the brain and authority. Internet systems are read-only eyes.**

Phase 12 does not authorize arbitrary browsing, autonomous account actions, arbitrary outbound networking, local/private network access, credential forwarding, package installation, executable downloads, MCP/plugin auto-registration, Guardian/root/systemd/Docker access, or automatic mutation of canonical DAP task/Knowledge truth.

## Target flow

```text
Owner / DAP task
  ↓
Executive Office / Research Agent
  ↓
DAP tool registry
  ↓
Internet Research Gateway admission
  ↓
URL / DNS / redirect / content policy
  ↓
bounded public HTTP transport or approved search provider
  ↓
untrusted-content normalization
  ↓
source + citation + retrieval evidence
  ↓
Research Agent synthesis
  ↓
owner-visible result
```

Fetched content is always evidence, never instructions or authority.

## Gate status

- 12A — Architecture + threat boundary: **COMPLETE / SEALED**
- 12B — Research request + source/tool registry contract: **COMPLETE / SEALED**
- 12C — URL, DNS, redirect, and SSRF policy: **COMPLETE / SEALED**
- 12D — Bounded public fetch transport: **COMPLETE / SEALED — LIVE ACER PROOF PASSED**
- 12E — Untrusted-content / prompt-injection boundary: **COMPLETE / SEALED**
- 12F — Citation + retrieval evidence persistence: **COMPLETE / SEALED**
- 12G — Research Agent integration: **COMPLETE / SEALED**
- 12H — Search/provider adapters + optional Agent-Reach-inspired components: **NEXT / IN PROGRESS**
- 12I — Dashboard Research workspace: **PENDING**
- 12J — Empirical benchmark + production-readiness decision: **PENDING**

## Current sealed capability checkpoint

12A–12G establish these live invariants:

- DAP remains the sole task/policy/credential/privilege authority.
- Public-web URLs enter through the inbound DAP/owner `AgentRunRequest.research_urls` field, bounded to at most three explicit URLs.
- `AgentService` fails closed if research URLs resolve to any agent other than `research-agent`.
- The Research executor constructs the internet tool call directly from the resolved request before model synthesis; there is no generic model tool-calling path for internet retrieval.
- `research-agent` exposes `knowledge.search` plus exactly one bounded internet tool: `internet.research.retrieve`.
- Search discovery remains disabled and unconfigured.
- Every explicit URL passes 12C preflight, public-address admission, redirect revalidation, and 12D pinned-IP/TLS transport.
- Private, loopback, link-local, multicast, reserved, unspecified, metadata, container, and DAP-local destinations remain prohibited.
- The live 12D Acer smoke retrieved `https://example.com/` through an admitted public address while `localhost` and `127.0.0.1` were blocked by the expected SSRF layers.
- 12E strips active web content, preserves visible remote text as untrusted data, and wraps model context in a fixed DAP-owned quoted-evidence envelope.
- Remote instructions, role changes, policy claims, credential requests, tool requests, or URL-expansion requests never become authority.
- 12F persists immutable success/failure/cancellation retrieval evidence and DAP-owned citations additively without rewriting canonical task truth or Knowledge.
- Remote page content cannot add retrieval URLs or select tools.
- No generic HTTP/socket client, browser session, cookie jar, provider credential, Guardian/root/systemd/Docker surface, MCP/plugin runtime, merge, release, or deployment authority is exposed to the Research Agent.

Historical tests for earlier gates remain stage-local. For example, 12A still proves its policy grants no live network/tool authority and 12D still proves its transport does not self-register. Separate 12G regressions prove the later explicit bounded tool registration.

## 12A — Architecture + threat boundary

Define a machine-readable fail-closed boundary before any network tool exists.

Required invariants:

- Research Agent remains knowledge-only during 12A.
- No internet/network tool is registered during 12A.
- No transport is executed by the 12A policy object.
- Only future read-only public research retrieval is eligible for promotion.
- Page text, HTML, metadata, robots text, search snippets, PDFs, and downloaded content are untrusted evidence.
- Remote content cannot grant tool, credential, policy, task, Git, Guardian, or host authority.
- Credentials, cookies, owner tokens, browser sessions, and DAP secrets cannot be forwarded to arbitrary destinations.
- Private, loopback, link-local, multicast, reserved, unspecified, metadata, container, and DAP-local destinations remain prohibited.
- Every redirect must be independently revalidated before a future transport follows it.
- Initial future transport is limited to read-only retrieval methods; POST/PUT/PATCH/DELETE and uploads remain prohibited.
- File/data/javascript schemes remain prohibited.
- Executable/package/plugin/MCP downloads or installation remain prohibited.
- Automatic Knowledge/task-ledger mutation remains prohibited.
- Guardian/root/systemd/Docker access remains prohibited.

Exit: DAP can prove exactly what future internet capability may be wired and what remains impossible before a network call is implemented.

## 12B — Research request + source/tool registry contract

- Add deterministic, immutable research-request identity.
- Bind request to canonical DAP task/admission when applicable.
- Define source categories and provider identity.
- Define exact output/evidence contract.
- Keep research networking unavailable until the later transport gate.

Exit: research intent can be represented without performing network I/O.

## 12C — URL, DNS, redirect, and SSRF policy

- Parse and canonicalize destinations before DNS resolution is permitted.
- Allow only explicitly supported schemes and methods.
- Reject URL user-info and credential-bearing URLs.
- Reject local/internal/container/metadata hostname forms before DNS.
- Validate hostname syntax before DNS.
- Validate resolver-supplied addresses and reject every non-public address class.
- Fail closed if any DNS answer is non-public.
- Re-run preflight, resolution, and final admission for every redirect and cap redirect depth.
- Bind the approved address set to immutable destination admission.

Exit: a request cannot use DAP as an SSRF tunnel into host or private infrastructure.

## 12D — Bounded public fetch transport

- Fixed GET/HEAD-only surface.
- DNS only after 12C preflight.
- Exact admitted numeric-IP connection while validating TLS/SNI for the canonical hostname.
- `AI_NUMERICHOST` prevents silent hostname re-resolution after admission.
- Fixed connect/read/total timeouts, header/body ceilings, content types and encodings.
- Every redirect is independently re-admitted.
- No proxy/cookie/browser/session inheritance and no arbitrary model headers.
- Cancellation-aware.

Live Acer proof passed against `https://example.com/` with source repo clean, task ledger unchanged, Guardian inactive, and Telegram approvals disabled.

Exit: harmless public content can be retrieved without giving the Research Agent generic network authority.

## 12E — Untrusted-content / prompt-injection boundary

- Verify transport body hash/count before normalization.
- Normalize bounded textual content into immutable untrusted evidence.
- Strip executable/active HTML content and markup authority surfaces.
- Preserve visible remote claims as evidence rather than silently treating them as trusted.
- Add heuristic prompt-injection findings for audit, while keeping safety independent of detection quality.
- Wrap model context in a fixed DAP-owned quoted-data envelope.
- Treat remote instructions, role changes, tool calls, credential requests, policy claims, and URL-expansion requests as data only.
- Unsupported binary content such as PDF remains outside model context until a later bounded extractor exists.

Exit: remote content cannot become DAP authority through model context.

## 12F — Citation + retrieval evidence persistence

Persist immutable DAP-owned evidence for success, failure, and cancellation, including request identity, provider/transport identity, URLs, status/content metadata, hashes, redirects, timestamps, normalized-content identity, policy state, and DAP-owned citation identity.

Persistence is additive beside canonical task truth, idempotent for exact replay, and fails on conflicting reuse of an evidence ID. It does not mutate Knowledge or task truth.

Exit: research retrieval is attributable and replayable from DAP evidence.

## 12G — Research Agent integration

- Register exactly one bounded public-web tool: `internet.research.retrieve`.
- Preserve `knowledge.search` as a separate evidence source.
- Accept internet URLs only from the resolved inbound Research Agent request, max three explicit URLs.
- Reject research URLs for non-Research agents.
- Execute retrieval before model synthesis.
- Feed only 12E normalized evidence envelopes and 12F citations into synthesis.
- Never extract/follow new URLs from page content.
- Keep search discovery disabled.

Dedicated 12G tests prove bounded tool execution, failure/cancellation persistence, Knowledge + internet synthesis, no embedded-URL expansion, no generic network library in the agent layer, and no privileged/provider-credential surface.

Exit: Research Agent can combine Knowledge and bounded internet evidence without gaining generic network authority.

## 12H — Search/provider adapters

- Evaluate approved search APIs or safe provider abstractions.
- Agent-Reach-inspired ideas may be adapted only behind DAP contracts.
- Do not install or delegate control to a full external runtime by default.
- Provider secrets, if later needed, remain DAP-owned and destination-scoped.
- Search results must enter the same untrusted-content/citation/retrieval pipeline and cannot bypass 12C–12G.

Exit: search discovery can feed the same bounded retrieval/evidence pipeline.

## 12I — Dashboard Research workspace

Expose read-only research evidence:

- objective/request identity;
- queried/retrieved sources;
- citations;
- retrieval status and policy state;
- content hashes and timestamps;
- failures/cancellations;
- provenance distinguishing Knowledge from internet evidence.

Exit: owner can inspect what DAP retrieved and why it trusted the transport, without UI-side network authority.

## 12J — Empirical benchmark + production-readiness decision

Benchmark harmless public research tasks for retrieval success, citation/source correctness, SSRF rejection, redirect-policy accuracy, prompt-injection resistance, latency/resource cost, failure recovery, and evidence completeness.

Choose one: narrow routine research, experimental-only, provider-specific activation, or reject activation.

No Phase 12 outcome grants privileged host access, arbitrary network access, autonomous account actions, or autonomous merge/deployment authority.

## Safety invariants

1. DAP owns canonical task truth and owner authorization.
2. The Internet Research Gateway owns network admission; models do not.
3. Research Agent receives evidence, not generic sockets or HTTP clients.
4. Fetched content is untrusted data, never policy or executable instructions.
5. Public internet access cannot reach host/private/internal DAP infrastructure.
6. Credentials are never forwarded based on remote content or model output.
7. Redirects are new destinations and require full revalidation.
8. Network methods and headers are fixed by DAP policy, not generated by the model.
9. Retrieval does not automatically mutate Knowledge or task truth.
10. Every accepted retrieval outcome must be attributable and reviewable.
