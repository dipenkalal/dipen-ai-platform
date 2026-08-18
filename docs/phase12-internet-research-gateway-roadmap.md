# Phase 12 — DAP Internet / Research Capability Gateway

Status: **IN PROGRESS**

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
- 12D — Bounded public fetch transport: **NEXT / IN PROGRESS**
- 12E — Untrusted-content / prompt-injection boundary: **PENDING**
- 12F — Citation + retrieval evidence persistence: **PENDING**
- 12G — Research Agent integration: **PENDING**
- 12H — Search/provider adapters + optional Agent-Reach-inspired components: **PENDING**
- 12I — Dashboard Research workspace: **PENDING**
- 12J — Empirical benchmark + production-readiness decision: **PENDING**

## Sealed boundary checkpoint

12A–12C are sealed on the Phase 12 branch with the following invariants:

- `research-agent` still exposes only `knowledge.search`.
- `tools.registry` still registers no `internet.*` or `web.*` capability.
- The source registry can represent `public_web` and `web_search`, but both remain execution-disabled and have no tool IDs.
- A research request may express web intent without granting network authority.
- URL preflight occurs before DNS resolution is permitted.
- DNS resolution and HTTP transport are absent from the 12A–12C policy modules.
- Final destination admission requires every resolver-supplied IPv4/IPv6 address to be public.
- Mixed public/private DNS answers fail closed.
- Redirect depth is bounded and cryptographically bound into destination admission.
- The final destination admission binds the canonical URL, method, hostname, exact approved address set, and redirect depth by SHA-256.

Dedicated Phase 12, repository CI, Phase 10 regression, and Phase 11 regression all passed on the hardened 12C checkpoint.

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
- Reject localhost, private RFC1918, loopback, link-local, multicast, unspecified, reserved, metadata, container and DAP-local targets.
- Fail closed if any DNS answer is non-public.
- Re-run preflight, resolution, and final admission for every redirect and cap redirect depth.
- Bind the approved address set to the immutable destination admission so the chosen transport can connect only to validated IPs.
- Add IPv4/IPv6, mixed-answer, IP-literal, and DNS-rebinding-oriented tests.

Exit: a request cannot use DAP as an SSRF tunnel into host or private infrastructure, and unsafe URLs are rejected before the resolver is called.

## 12D — Bounded public fetch transport

- Fixed GET/HEAD-only command/API surface initially.
- Resolve only after a successful 12C preflight.
- Connect to an exact 12C-approved IP while validating TLS for the canonical hostname.
- Do not let the HTTP client silently re-resolve the hostname after admission.
- Fixed connect/read/total timeouts.
- Response-byte and header-size caps.
- Controlled content types and content encodings.
- No automatic redirects; return redirect metadata so each destination is re-admitted through 12C.
- No ambient proxy/cookie/browser/session inheritance.
- No arbitrary request headers supplied by model output.
- Cancellation-aware operation.
- Do not register the transport as an agent-visible tool during 12D.

Exit: harmless public content can be retrieved without giving the Research Agent generic network authority.

## 12E — Untrusted-content / prompt-injection boundary

- Normalize fetched content into evidence records.
- Strip active content and executable behavior.
- Label remote content as untrusted data in model prompts.
- Treat remote instructions, role changes, tool calls, credential requests, and policy claims as data only.
- Prevent page content from selecting tools or expanding retrieval scope.
- Add adversarial prompt-injection fixtures.

Exit: remote content cannot become DAP authority through the model context.

## 12F — Citation + retrieval evidence persistence

Persist immutable DAP-owned evidence for:

- canonical task/admission where applicable;
- research request hash;
- provider/transport identity;
- canonical requested and final URL;
- validated destination metadata without exposing secrets;
- redirects;
- HTTP status/content type/byte count;
- retrieval timestamps;
- content hash;
- source title/metadata;
- policy decisions;
- cancellation/failure information.

Exit: research retrieval is attributable and replayable from DAP evidence.

## 12G — Research Agent integration

- Add the new internet research tool only after 12A–12F are sealed.
- Preserve Knowledge search as a separate evidence source.
- Research Agent may synthesize retrieved evidence but may not expand authority from page instructions.
- Keep model-generated arbitrary networking impossible.

Exit: Research Agent can combine Knowledge and bounded internet evidence.

## 12H — Search/provider adapters

- Evaluate approved search APIs or safe provider abstractions.
- Agent-Reach-inspired ideas may be adapted only behind DAP contracts.
- Do not install or delegate control to a full external runtime by default.
- Provider secrets, if later needed, remain DAP-owned and destination-scoped.

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

Benchmark harmless public research tasks for:

- retrieval success rate;
- citation/source correctness;
- SSRF rejection accuracy;
- redirect-policy accuracy;
- prompt-injection resistance;
- latency and resource cost;
- failure recovery;
- evidence completeness.

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
