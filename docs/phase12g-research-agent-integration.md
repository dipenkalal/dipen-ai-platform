# Phase 12G — Research Agent integration

Status: **COMPLETE / SEALED**

Phase 12G promotes the sealed 12C–12F public-web pipeline into exactly one DAP-owned Research Agent execution path.

## Governing rule

> The Research Agent may synthesize bounded internet evidence, but it never receives a generic network client and remote content never chooses the next retrieval.

## Live capability surface

The Research Agent has exactly these research tools:

- `knowledge.search`
- `internet.research.retrieve`

Search discovery remains disabled in 12G. `web_search` remains unconfigured and execution-disabled.

## URL authority boundary

Public-web URLs do not come from model-generated tool calls. `research_urls` is an inbound `AgentRunRequest` field. `AgentService` fails closed if non-empty research URLs resolve to any agent other than `research-agent`. The Research executor constructs the internet tool call directly from the resolved request before model synthesis.

```text
owner / DAP request
  ↓ explicit research_urls (max 3)
AgentService scope check
  ↓
ResearchEnabledAgentExecutor
  ↓ exact request.research_urls
internet.research.retrieve
  ↓
12C destination policy
  ↓
12D pinned public HTTPS retrieval
  ↓
12E untrusted-content normalization
  ↓
12F immutable citation/evidence persistence
  ↓
DAP-owned untrusted evidence envelope
  ↓
local Research Agent synthesis
```

There is no generic model tool-calling loop for this capability and no generic tool-execution HTTP endpoint. `/tools` is list-only; agent execution is routed through `AgentRunRequest` and `AgentService`.

## Bounded behavior

`internet.research.retrieve` requires an objective, accepts only an explicit list/tuple of URLs, permits at most three explicit URLs, rejects empty/duplicate input, uses only the sealed bounded retriever, does not extract or follow URLs found inside page content, persists success/failure/cancellation evidence, returns citations plus normalized prompt envelopes rather than raw transport bodies, and keeps scope expansion, automatic Knowledge/task mutation, Guardian contact, and privileged host actions disabled.

Knowledge evidence remains a separate source. Internet evidence is supplied to synthesis only inside the fixed 12E DAP-owned untrusted-data envelope.

## Dedicated evidence

The dedicated Phase 12 workflow explicitly gates the internet research tool, registries, research executor, AgentRunRequest/service routing, tool tests, integration tests, and the Phase 12G Guardian boundary.

At implementation checkpoint `ec4f30f3e9f31abaa2ba333bdf2160f9c2d0be17`, the dedicated Phase 12 gate passed Ruff, mypy, compilation, **125 Phase 12 behavior tests**, and all Guardian 12A–12G boundary regressions.

12D already proved the real outbound pinned public HTTPS transport live on the Acer, including public-IP admission and localhost/loopback rejection. 12G adds deterministic DAP-owned request-to-evidence-to-synthesis wiring above that sealed transport, so no second unrestricted network smoke is needed for this gate.

## Historical stage-boundary note

Earlier 12A and 12D regressions remain stage-local: 12A proves its policy grants no live network/tool authority, and 12D proves its transport does not self-register. Separate 12G regressions prove the later explicit bounded registration is narrow and safe.

## Still prohibited

Model-generated arbitrary URLs, search discovery, arbitrary HTTP/socket access, mutating HTTP methods, credentials/cookies/browser sessions, provider-secret forwarding, automatic Knowledge/task mutation, Guardian/root/systemd/Docker, package installation, MCP/plugin registration, full Agent-Reach adoption, and Git/merge/release/deployment authority remain prohibited.

## Exit decision

**12G is complete and sealed.** The Research Agent can combine indexed Knowledge evidence with explicitly requested bounded public-web evidence while DAP retains URL authority and the model receives only normalized untrusted evidence.

Next: **12H — search/provider adapters**.
