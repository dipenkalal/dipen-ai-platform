# Phase 13 — Provider-Specific Research Activation

Status: **SEALED — LIVE ACER ACTIVATION GATE PASSED; MERGE READY**

Branch: `phase13/provider-specific-research-activation`

Base: Phase 12 merge `4ca48a1d68e3f90f43265017befe0ce7c263229c`

Final live-proof source checkpoint: `3f7dc4318abe165629e59cf45264c781d7a6784f`

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
- arbitrary task-truth mutation;
- Guardian/root/systemd authority;
- Docker socket or privileged container authority;
- autonomous account action;
- autonomous release/deployment authority.

Normal DAP runtime instrumentation still records one task-ledger row for a successfully executed manual agent run. That row is an audit/runtime truth record, not new model authority. The Phase 13 live proof required the ledger delta to be exactly one and correlated it to the completed Research Agent run by `source_run_id` and assigned agent.

The Research Agent registry remains model-tool limited to:

```text
knowledge.search
internet.research.retrieve
```

SearXNG discovery is a deterministic DAP executor path, not a generic model-callable tool.

## CI exit gate

The Phase 13 branch passed:

- Ruff and Mypy on the activation boundary;
- Phase 13 backend contract/integration tests;
- the sealed Phase 12 destination/transport/untrusted/evidence/search/workspace/benchmark regressions;
- post-activation SearXNG Guardian semantics;
- dedicated Phase 13 Guardian boundaries;
- dashboard lint/build;
- production dashboard Docker image build;
- normal repository CI/regression workflows.

The operator scripts were also hardened after live observations to prove:

- root-owned generated `.next` cleanup is limited to the fixed generated path;
- the application rebuild runs offline as the normal host UID;
- the resume path does not rerun the Research Agent;
- task-ledger growth must be exactly one and must correlate to the completed Research Agent run.

## Live Acer proof — PASSED

The final live proof established:

- exact approved Phase 13 source checkpoint;
- one controlled backend restart loaded the new request/executor path;
- smart-mode search request was rejected;
- non-Research-Agent search request was rejected;
- one manual Research Agent search succeeded through `searxng-local-v1`;
- selected URL count remained bounded to at most three;
- provider snippets/titles remained non-evidence and outside model context;
- three new immutable retrieval-evidence rows were created, increasing evidence from `7` to `10`;
- the normal instrumented agent run created exactly one new task-ledger row, increasing the ledger from `11` to `12`;
- that task was `completed`, requested by `agent-api`, assigned to `research-agent`, and linked to run `801daf77-af76-49bb-a45d-fb414cb2fc11`;
- Research workspace exposed the resulting Internet Evidence read-only;
- dashboard was rebuilt offline and recreated without disturbing unrelated services;
- backend remained active with PID `462906` after closure;
- Guardian remained inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false` remained unchanged;
- SearXNG remained loopback-only at `127.0.0.1:8888`;
- source checkout remained clean;
- resume closure did not rerun research or create duplicate evidence.

The complete evidence record is `docs/phase13-provider-specific-research-live-evidence-2026-08-18.md`.

Phase 13 is therefore sealed and ready for integration into `main` after this documentation checkpoint remains CI-green.
