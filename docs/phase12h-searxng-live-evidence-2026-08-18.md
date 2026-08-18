# Phase 12H — SearXNG Acer Live Evidence

Date: **2026-08-18**

Status: **PASS / SEALED RUNTIME EVIDENCE**

Branch at live proof: `phase12/internet-research-gateway`

Code checkpoint used for final retest: `63bff214ffe04703e46fd5784f1089ee61207e41`

## Purpose

Record the live Acer deployment and safety evidence that closes the Phase 12H zero-cost SearXNG runtime gate.

This proof does not grant new Research Agent authority. It proves that the selected local search-discovery runtime can operate inside the existing DAP boundary without mutating task truth, restarting production backend state, contacting Guardian, using paid-provider credentials, or exposing SearXNG beyond Acer loopback.

## Runtime deployment

Local runtime directory:

`/home/dipen/dap/compose/phase12h-searxng`

Pinned image:

`ghcr.io/searxng/searxng:2026.7.28-c01178d03@sha256:80622959f0f3512e6623d6bdbcea9f13c8d22c8d9715c498d0ae2be1c8535930`

Verified local image ID:

`sha256:80622959f0f3512e6623d6bdbcea9f13c8d22c8d9715c498d0ae2be1c8535930`

Container:

`dap-searxng`

Compose project:

`dap-searxng`

## Isolation proof

The live container passed all deployment-boundary checks:

- host publication: `127.0.0.1:8888->8080/tcp`;
- loopback-only binding: **true**;
- privileged mode: **false**;
- host networking: **not used**;
- network mode: `dap-searxng_default`;
- Linux capabilities dropped: `ALL`;
- `no-new-privileges:true` enabled;
- pinned image reference retained exactly;
- HTTP root health check returned `200`;
- JSON search API returned `200` and valid JSON.

The initial JSON API proof returned 10 raw results for the harmless `Example Domain` query.

## Zero-cost DAP search smoke

Final live command:

`python -m gateway.searxng_search_provider_smoke`

Provider identity:

`searxng-local-v1`

Provider endpoint:

`http://127.0.0.1:8888/search`

Query:

`Example Domain`

Observed live discovery:

- candidate count: `4`;
- selected URL count: `3`;
- all selected URLs used HTTPS;
- selected hosts were `en.wikipedia.org`, `domainwheel.com`, and `www.iana.org`;
- pipeline ID: `web-search-pipeline-463d963d423992ee472aa626`;
- pipeline SHA-256: `463d963d423992ee472aa6266230ed61af4e65cd08ad314b38c4a265212c99b6`.

All smoke boundary checks passed, including:

- provider ID exact;
- endpoint exact;
- query exact;
- non-zero candidate count;
- bounded selected count;
- HTTPS-only selected URLs;
- sealed retrieval capture invoked exactly once;
- retrieval URLs/objective matched exactly;
- provider snippets not exposed to the model;
- provider titles not exposed to the model;
- search candidates not treated as retrieval evidence;
- candidate URLs still require full DAP retrieval;
- no provider credential exposure;
- no generic network client exposure;
- no remote scope expansion;
- no Knowledge mutation;
- no task-ledger mutation;
- no Guardian contact;
- no privileged host action;
- provider titles not serialized as provider evidence;
- provider snippets not serialized as provider evidence.

Final smoke disposition:

`smoke_disposition|succeeded`

Final smoke exit:

`smoke_exit|0`

No paid provider was used. No provider credential was required. No model call was made. No database write was performed by the smoke. No public-page retrieval was performed by the smoke capture helper.

## Production safety proof

Before final live smoke:

- `task_ledger` count: `11`;
- `dap-backend.service` MainPID: `2856`.

After final live smoke:

- `task_ledger` count: `11`;
- `dap-backend.service` MainPID: `2856`.

Therefore:

- task ledger mutated: **false**;
- backend restarted: **false**.

Final production guards:

- backend: **active**;
- Guardian broker: **inactive**;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- SearXNG root HTTP status: `200`;
- SearXNG remained bound only to `127.0.0.1:8888`.

## Deployment incident and closure

The initial GHCR image pull was interrupted repeatedly by outbound IPv6 timeouts while downloading GitHub-hosted container layers. Existing downloaded layers remained cached. A narrowly scoped temporary IPv6 reject rule was used only to force fallback away from the failing GitHub IPv6 path long enough to complete the pinned image pull.

The temporary rule was subsequently removed and verified absent before SearXNG startup:

`temporary_rule_remaining|false`

No Docker daemon restart, DAP backend restart, production task mutation, or SearXNG secret regeneration was required.

## Smoke-test defect corrected

The first live smoke reached the provider successfully but failed one assertion because the smoke searched the serialized result for the generic substring `snippet`. The result intentionally contains safety-field names such as `provider_snippets_exposed_to_model`, so the assertion was semantically over-broad.

The smoke was corrected to test for actual provider content rather than the safety-field name. The corrected code checkpoint was:

`63bff214ffe04703e46fd5784f1089ee61207e41`

All repository workflows for that checkpoint completed successfully, including the Phase 12 backend and Guardian boundary jobs.

## Activation decision

**Do not register search discovery as live Research Agent authority yet.**

Phase 12H proves the zero-cost SearXNG runtime and search-to-retrieval boundary. Search discovery remains an internal DAP component while Phase 12I adds owner-visible research inspection and Phase 12J performs the empirical benchmark and production-readiness decision.

This preserves the existing least-authority posture while allowing Phase 12 to continue.

## Exit

Phase 12H runtime exit is satisfied:

1. pinned SearXNG deployed locally on Acer — **PASS**;
2. loopback-only publication proved — **PASS**;
3. credential-free live SearXNG smoke succeeded — **PASS**;
4. source/task/Guardian/Telegram safety invariants verified — **PASS**;
5. live evidence recorded — **PASS**;
6. activation decision recorded: defer live Research Agent registration pending 12I/12J — **PASS**.

**Phase 12H is sealed.**
