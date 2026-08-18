# Phase 12H — Search/provider adapters

Status: **IMPLEMENTATION / CI COMPLETE — LIVE PROVIDER ACTIVATION PENDING**

Phase 12H adds a provider-specific search discovery layer without giving the Research Agent a generic search client, provider credential, or authority to treat search snippets as evidence.

## Governing rule

> Search may discover candidate URLs. Only the sealed DAP public-web pipeline may turn a candidate URL into research evidence.

## 12H.1 — Brave Search provider adapter

The initial approved adapter is `brave-web-search-v1`.

DAP fixes the provider destination and credential scope:

- hostname: `api.search.brave.com`;
- endpoint path: `/res/v1/web/search`;
- method: GET;
- credential env name: `DAP_BRAVE_SEARCH_API_KEY`;
- provider redirects: rejected;
- request encoding: identity;
- TLS: system trust with minimum TLS 1.2;
- transport: exact DAP-admitted numeric IP with `AI_NUMERICHOST` and SNI for the fixed Brave hostname.

The provider token is DAP-owned. It is accepted only from the backend environment, sent only to the fixed Brave endpoint, and is never included in discovery models, model context, candidate URLs, citations, task truth, Knowledge, or retrieval evidence.

The adapter is fail-closed when the credential is absent or malformed.

## Search query ceiling

The adapter currently enforces:

- query length: at most 400 characters;
- query words: at most 50;
- result count: 1–10;
- SafeSearch: strict.

No arbitrary provider endpoint or arbitrary request-header surface is accepted from the model or caller.

## Search candidates are not evidence

Provider results are converted into `WebSearchCandidate` values with explicit fail-closed flags:

- `candidate_is_untrusted=True`;
- `candidate_is_retrieval_evidence=False`;
- `candidate_url_requires_dap_retrieval=True`;
- `remote_instructions_are_authority=False`;
- `tool_selection_allowed=False`.

Search discovery performs URL preflight only. Any candidate selected for use must still pass the full 12C/12D address admission, DNS, pinned TLS transport, redirect, content-type, timeout, and byte-limit pipeline. A candidate IP literal that survives URL syntax/preflight remains inert data and is rejected later if the address is non-public.

## 12H.2 — Search discovery → sealed retrieval orchestration

`WebSearchRetrievalPipeline` is provider-neutral at its orchestration boundary.

Flow:

```text
DAP research objective + bounded search query
  ↓
credential-gated search provider
  ↓ untrusted URL candidates only
rank-order deterministic selection, max 3
  ↓ URLs only — no provider snippets/titles
internet.research.retrieve
  ↓
12C destination admission
  ↓
12D pinned public HTTPS
  ↓
12E untrusted-content normalization
  ↓
12F immutable evidence + citation
```

The pipeline:

- selects at most three unique candidate URLs in rank order;
- ignores provider snippets and titles when constructing retrieval arguments;
- never treats provider candidates as retrieval evidence;
- invokes only the already sealed `internet.research.retrieve` tool;
- binds its deterministic identity to the research objective SHA-256, discovery identity, selected URLs, and retrieval tool ID;
- preserves bounded retrieval failure instead of promoting a failed candidate;
- exposes no provider credential or generic network client;
- performs no automatic Knowledge/task-ledger mutation and no Guardian/privileged host action.

## Live activation state

The Search Agent / Research Agent does **not** currently expose a `web.search` tool.

`web_search` in the research source registry remains execution-disabled and has no tool ID. The Brave adapter and orchestration pipeline are internal DAP components only until the owner explicitly activates a configured provider.

No Brave credential has been stored or used during implementation/CI.

## Live smoke helper

`gateway/web_search_provider_smoke.py` is a credential-safe runtime proof prepared for provider activation. It:

- uses one hardcoded query (`Example Domain`);
- performs one bounded Brave search request;
- prints no provider credential or search snippets;
- makes no model call;
- writes no task, Knowledge, or retrieval evidence;
- verifies the provider-connected address is public;
- verifies candidate URLs remain untrusted non-evidence requiring full DAP retrieval;
- verifies the credential does not appear in serialized output.

The helper itself is included in Phase 12 Ruff, mypy, and compile gates before any live run.

## CI evidence

At the 12H.1 implementation checkpoint `eb0dc8a5f3c89926e270e9d33b0f99c862581dc9`, the dedicated Phase 12 workflow passed Ruff, mypy, compile, 133 Phase 12 behavior tests, and Guardian 12A–12H provider regressions, with repository CI plus Phase 10/11 regressions also green.

12H.2 then added the search-to-retrieval orchestration, objective-bound pipeline identity, provider-snippet exclusion tests, and Guardian discovery-boundary regression. The final credential-safe live-smoke helper is also statically gated.

## Still prohibited

Phase 12H does not authorize:

- provider activation without owner configuration;
- provider credentials in model context, task truth, Knowledge, citations, or result URLs;
- provider snippets as source evidence;
- using a candidate URL without full DAP retrieval admission;
- arbitrary search endpoints or arbitrary HTTP headers;
- arbitrary sockets/HTTP clients for the Research Agent;
- search-result-driven tool selection or scope expansion;
- private/internal/metadata network access;
- Guardian/root/systemd/Docker;
- full Agent-Reach runtime adoption;
- MCP/plugin auto-registration;
- merge, release, or deployment authority.

## Exit state

**Code/CI exit is satisfied.** Search discovery can deterministically feed candidate URLs into the same sealed DAP retrieval/evidence pipeline without exposing snippets, provider credentials, or generic network authority.

**Live provider activation is intentionally pending owner choice and local credential configuration.** A successful credential-safe Brave smoke is required before calling the external provider activated.
