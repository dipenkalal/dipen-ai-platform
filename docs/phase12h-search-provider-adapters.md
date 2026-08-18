# Phase 12H — Search/provider adapters

Status: **COMPLETE / SEALED — ZERO-COST SEARXNG ACER LIVE PROOF PASSED**

Phase 12H gives DAP bounded search discovery without giving the Research Agent a generic search client, provider credential, or authority to treat search snippets as evidence.

## Governing rule

> Search may discover candidate URLs. Only the sealed DAP public-web pipeline may turn a candidate URL into research evidence.

## Owner budget decision

The production search path must have **zero paid API cost and no billing/card exposure**.

Therefore:

- the earlier Brave adapter remains dormant optional code only;
- no Brave credential is configured or required;
- the selected production discovery provider is self-hosted SearXNG on the Acer;
- SearXNG is bound only to `127.0.0.1:8888`;
- no provider credential is used by the DAP SearXNG adapter;
- search-result URLs remain untrusted candidates and must still pass the full DAP retrieval/evidence pipeline.

## Provider-neutral search → retrieval pipeline

`WebSearchRetrievalPipeline` accepts a bounded provider protocol and performs deterministic max-three URL selection.

Flow:

```text
DAP research objective + bounded search query
  ↓
local SearXNG discovery
  ↓ untrusted candidate URLs only
rank-order deterministic selection, max 3
  ↓ URLs only — snippets/titles excluded
internet.research.retrieve
  ↓
12C URL/DNS/address/redirect admission
  ↓
12D pinned public HTTPS transport
  ↓
12E untrusted-content normalization
  ↓
12F immutable evidence + citation
```

The pipeline identity binds objective SHA-256, provider/discovery identity, selected URLs, and the sealed retrieval tool ID.

## SearXNG adapter

Provider identity: `searxng-local-v1`.

The DAP adapter is fixed to:

- host: `127.0.0.1`;
- port: `8888`;
- path: `/search`;
- method: GET;
- response: JSON;
- no DNS resolution for the provider hop;
- no credential/header/token surface;
- no configurable endpoint;
- exact peer check requiring `127.0.0.1`.

Search candidates retain fail-closed semantics:

- `candidate_is_untrusted=True`;
- `candidate_is_retrieval_evidence=False`;
- `candidate_url_requires_dap_retrieval=True`;
- `remote_instructions_are_authority=False`;
- `tool_selection_allowed=False`.

Provider snippets and titles are not forwarded into retrieval arguments or the model evidence path.

## Local deployment boundary

Tracked deployment templates live under `deploy/phase12h-searxng/`.

The deployment is constrained to:

- an exact pinned SearXNG image tag + digest;
- `linux/amd64`;
- host publication only on `127.0.0.1:8888`;
- no host networking;
- no privileged mode;
- no Docker socket;
- `cap_drop: ALL`;
- `no-new-privileges`;
- bounded CPU/memory/PID resources;
- JSON output enabled;
- strict safe search;
- a small no-paid-key engine allowlist;
- a locally generated SearXNG application secret only.

The SearXNG application secret is local instance hardening and is not a paid provider/API credential.

## Live smoke helper

`gateway/searxng_search_provider_smoke.py` is a DB-free, model-free live proof. It:

- uses the hardcoded query `Example Domain`;
- connects only to the fixed local SearXNG endpoint;
- requires at least one candidate;
- selects at most three URLs;
- verifies selected URLs are HTTPS;
- captures the downstream sealed-retrieval invocation without actually fetching public pages;
- verifies provider snippets/titles are excluded from provider evidence;
- performs no model call, database write, Knowledge mutation, task mutation, Guardian contact, or privileged action;
- uses no paid provider or provider credential.

## CI evidence

At code checkpoint `63bff214ffe04703e46fd5784f1089ee61207e41`, all relevant workflows passed:

- Phase 12 Internet Research Gateway;
- repository CI;
- Phase 11 regression;
- Phase 10 regression.

The dedicated Phase 12 gate passed both `backend-boundary` and `guardian-boundary`, including Ruff, mypy, compile, behavior tests, Guardian SearXNG provider isolation, deployment-template isolation, and live-smoke helper checks.

## Acer live proof

The pinned SearXNG image was deployed successfully on the Acer:

`ghcr.io/searxng/searxng:2026.7.28-c01178d03@sha256:80622959f0f3512e6623d6bdbcea9f13c8d22c8d9715c498d0ae2be1c8535930`

Live runtime checks passed:

- container `dap-searxng` started successfully;
- publication is exactly `127.0.0.1:8888->8080/tcp`;
- loopback-only check passed;
- privileged mode is false;
- host networking is not used;
- all Linux capabilities are dropped;
- `no-new-privileges:true` is enabled;
- JSON API returned HTTP `200` and valid JSON;
- final SearXNG root HTTP check returned `200`.

The final zero-cost DAP search smoke returned four candidate URLs, selected three HTTPS URLs, and passed every provider/search/retrieval boundary assertion with `smoke_disposition|succeeded` and `smoke_exit|0`.

Production safety remained unchanged across the final smoke:

- `task_ledger`: `11` before and `11` after;
- backend MainPID: `2856` before and `2856` after;
- task-ledger mutation: false;
- backend restart: false;
- backend: active;
- Guardian broker: inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`.

Detailed live evidence is recorded in `docs/phase12h-searxng-live-evidence-2026-08-18.md`.

## Activation state

Search discovery is **not registered as live Research Agent authority yet**.

The zero-cost local provider and search-to-retrieval boundary are now proven. The deliberate Phase 12H exit decision is to keep search discovery internal while Phase 12I adds owner-visible research inspection and Phase 12J performs empirical benchmarking and the final production-readiness decision.

This is a least-authority decision, not a runtime limitation.

## Still prohibited

Phase 12H does not authorize:

- paid provider activation;
- provider credentials in model context or evidence;
- provider snippets as evidence;
- using a candidate URL without full DAP retrieval admission;
- arbitrary search endpoints or arbitrary HTTP headers;
- arbitrary sockets/HTTP clients for the Research Agent;
- search-result-driven tool selection or scope expansion;
- private/internal/metadata public-retrieval destinations;
- exposing SearXNG beyond Acer loopback;
- Guardian/root/systemd authority;
- Docker socket/privileged container access;
- full Agent-Reach runtime adoption;
- MCP/plugin auto-registration;
- merge, release, or deployment authority.

## Exit state

**Phase 12H is complete and sealed.**

Runtime exit evidence:

1. deploy pinned SearXNG locally on Acer — **PASS**;
2. prove it is reachable only on `127.0.0.1:8888` — **PASS**;
3. run the credential-free SearXNG live smoke successfully — **PASS**;
4. verify source/task/Guardian/Telegram safety invariants — **PASS**;
5. record live evidence — **PASS**;
6. activation decision — **DEFER LIVE RESEARCH-AGENT REGISTRATION UNTIL 12I/12J**.

Next gate: **12I — Dashboard Research workspace**.
