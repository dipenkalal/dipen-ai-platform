# Phase 13 — Provider-Specific Research Activation

Status: **IN PROGRESS — CODE/CI GATE, LIVE ACER PROOF PENDING**

Branch: `phase13/provider-specific-research-activation`

Base: Phase 12 merge `4ca48a1d68e3f90f43265017befe0ce7c263229c`

## Decision

Phase 12 is complete and sealed. Its final benchmark recommended `provider-specific-activation` for the already-bounded local SearXNG path.

The owner delegated the post-Phase-12 decision. DAP therefore adopts the recommendation with an intentionally stricter first activation:

- search discovery is **manual Research Agent only**;
- smart routing cannot invoke search discovery;
- the search query must be explicit owner/DAP input;
- the provider is fixed to local `searxng-local-v1` at `127.0.0.1:8888`;
- search discovery may select at most three URL candidates for retrieval;
- selected URLs must still pass the complete sealed Phase 12 destination, transport, untrusted-content, citation, and evidence pipeline;
- provider titles and snippets remain discovery metadata only and never become evidence or model context;
- no generic search tool is registered in the model-visible DAP tool registry.

This is a post-Phase-12 activation. It does not reopen or rewrite the sealed Phase 12 milestone.

## Owner request contract

`AgentRunRequest` adds one bounded optional field:

```text
research_search_query
```

Rules:

- maximum 400 characters;
- maximum 50 normalized words;
- whitespace normalized by DAP;
- mutually exclusive with `research_urls`;
- admitted only for `mode=manual` + `agent_id=research-agent`;
- rejected in smart routing mode even if smart routing would otherwise select Research Agent;
- rejected when combined with supplemental attachment/context input.

The dashboard exposes the field only while the owner has manually selected Research Agent.

## Runtime flow

```text
owner selects manual Research Agent
  ↓
explicit bounded research_search_query
  ↓
AgentService manual-only / research-agent-only admission
  ↓
WebSearchRetrievalPipeline.searxng_local()
  ↓
fixed local SearXNG 127.0.0.1:8888
  ↓
untrusted URL candidates only
  ↓
provider-neutral deterministic selection, max 3 URLs
  ↓
internet.research.retrieve
  ↓
sealed Phase 12 URL/DNS/SSRF admission
  ↓
sealed public HTTPS transport
  ↓
sealed untrusted-content normalization
  ↓
immutable Internet Evidence + DAP citations
  ↓
Research Agent synthesis
```

## Authority boundary

Phase 13 does **not** grant:

- model-generated arbitrary URL authority;
- a generic HTTP/socket/browser client;
- direct SearXNG access to the model;
- provider credential access;
- provider snippet/title evidence authority;
- smart-routing search activation;
- automatic Knowledge mutation;
- task-ledger mutation;
- Guardian/root/systemd authority;
- Docker socket or privileged container authority;
- autonomous account action;
- autonomous merge/release/deployment authority.

The Research Agent registry remains model-tool limited to:

```text
knowledge.search
internet.research.retrieve
```

SearXNG discovery is a deterministic DAP executor path, not a generic model-callable tool.

## CI exit gate

Before live activation, the Phase 13 branch must pass:

- Ruff and Mypy on the activation boundary;
- Phase 13 backend contract/integration tests;
- the sealed Phase 12 destination/transport/untrusted/evidence/search/workspace/benchmark regressions;
- Phase 12H SearXNG Guardian regression evolved for post-activation semantics;
- dedicated Phase 13 Guardian boundary;
- dashboard lint/build;
- production dashboard Docker image build;
- normal repository CI/regression workflows.

## Live Acer proof — pending

The live proof must verify, in one controlled deployment:

- exact approved Phase 13 source checkpoint;
- task ledger unchanged around activation;
- research evidence grows only through immutable retrieval evidence;
- one controlled backend restart loads the new request/executor path;
- dashboard is rebuilt/recreated without disturbing unrelated services;
- manual Research Agent search succeeds through `searxng-local-v1`;
- selected URL count is bounded to at most three;
- provider snippets/titles are not model evidence;
- Research workspace displays the resulting Internet Evidence;
- smart-mode search request is rejected;
- non-Research-Agent search request is rejected;
- backend remains active after deployment;
- Guardian remains inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false` remains unchanged;
- SearXNG remains loopback-only at `127.0.0.1:8888`;
- source checkout remains clean.

No merge of this activation branch should occur until the live Acer proof passes.
