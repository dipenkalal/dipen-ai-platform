# Phase 16F.1 — Bounded Gzip Shadow A/B Live Evidence

Date: 2026-08-19

Status: **PASS — NO PRODUCTION TRANSPORT CHANGE REQUIRED**

Exact source head:

`be03a2eebc2c38503ffe3f60a0efb0b42612db4b`

The Phase 16F.1 experiment was run on the Acer against the unchanged local `searxng-local-v1` provider using the frozen 30-case Phase 15 corpus. The production transport remained `dap-pinned-https-http1-v1`, identity-only, and unchanged throughout the run.

## Source and runtime gate

- source branch: `phase16/research-provider-coverage-latency-canary`
- source HEAD: `be03a2eebc2c38503ffe3f60a0efb0b42612db4b`
- source state before/after: clean
- tracked SearXNG settings SHA-256: `cc2008ceb13c22e11da874921832fe1c702d7afc8b5bc1335a94831f7b37c0c1`
- production transport SHA-256 before/after: `d218e3a59b55e09b0b6f1269b7350c37808da3c0443818f02b0dbf0075139d13`
- production transport identity-only marker: PASS
- validated Acer network: `COGECO-9F8330-5G-ext`

## Production baseline frozen

- task ledger: `15`
- research retrieval evidence: `16`
- research operations events: `6`
- backend PID: `677911`
- Guardian broker: `inactive`
- Telegram approvals: `DAP_TELEGRAM_APPROVALS_ENABLED=false`
- SearXNG state: `running`
- SearXNG container ID: `812e687cf8d0b34f176271997a173756c7b77a8bd59bb785206495a31706e52d`
- SearXNG StartedAt: `2026-08-19T22:38:52.906924074Z`
- SearXNG binding: `127.0.0.1:8888`

## A — unchanged identity transport control

Probe version: `phase16e2.1`

Result:

- cases: `30/30` successful
- retrieval traces: `93`
- source records: `90`
- retriever P95: `1116.204 ms`
- DNS P95: `253.943 ms`
- fetch P95: `945.701 ms`
- connect/TLS P95: `283.805 ms`
- response-header P95: `259.454 ms`
- response-body P95: `391.661 ms`
- frozen successful per-source P50: `364.027 ms`
- frozen successful per-source P95: `1223.962 ms`
- frozen target `<=1500 ms`: **PASS**
- retrying source count: `3`
- retry backoff total: `750.000 ms`
- report SHA-256: `7a9392c9a8f2b60857ee8b61c40b280e3fe49b6f522071c73b24b536e83a60cc`

This is the decisive Phase 16F result: the unchanged production identity transport already meets the frozen Phase 15 retrieval-source latency target in the same-session control.

## B — bounded gzip shadow transport

Experiment version: `phase16f1.1`

Result:

- cases: `30/30` successful
- gzip responses observed: `68`
- identity responses observed inside shadow run: `18`
- frozen successful per-source P50: `285.725 ms`
- frozen successful per-source P95: `1047.676 ms`
- same-session improvement vs identity: `-176.286 ms`
- improvement vs prior E2 live P95 `1698.145 ms`: `-650.469 ms`
- frozen target `<=1500 ms`: **PASS**
- connect/TLS P95: `331.706 ms`
- response-header P95: `468.347 ms`
- response-body P95: `274.481 ms`
- dominant shadow fetch component: `response-header`
- report SHA-256: `97a1ffed0a17d2a539c254a0eb5fd26a9c2dd8821989ba947dd219ee403930b3`

The shadow run proves gzip is materially used and can reduce transfer-tail latency, but it does not justify a production transport change because the unchanged identity control already meets the frozen target.

## Decision

`PHASE16_F1_AB_DECISION|IDENTITY_ALREADY_MEETS_TARGET`

Phase 16F therefore closes as **PASS / NO CHANGE REQUIRED**.

Do not promote the gzip shadow transport into production during Phase 16. Preserve the original production request semantics (`Accept-Encoding: identity`) and the sealed production transport ID. Any future compression support must be a separately justified versioned transport change, not an implicit Phase 16 expansion.

## Isolation and authority evidence

Identity isolated DB:

- task ledger: `0`
- evidence: `90`
- operations: `90`

Gzip isolated DB:

- task ledger: `0`
- evidence: `90`
- operations: `90`

Production after the experiment remained:

- task ledger: `15`
- research evidence: `16`
- research operations: `6`
- backend PID: `677911`
- Guardian: `inactive`
- Telegram approvals: `false`
- SearXNG state/container/start/binding: unchanged
- production transport SHA-256: unchanged
- source: clean at the exact F1 head

Final markers:

- `PHASE16_F1_GZIP_SHADOW_AB|PASS`
- `PHASE16_F1_PRODUCTION_TRANSPORT_UNCHANGED|PASS`
- `PHASE16_F1_PRODUCTION_TRUTH_UNCHANGED|PASS`
- `PHASE16_F1_PROVIDER_RUNTIME_UNCHANGED|PASS`
- `PHASE16_F1_AUTHORITY_BOUNDARY|PASS`
- `phase16_f1_shell_exit|0`

## Phase 16 consequence

The two original Phase 16 defects are now empirically remediated without expanding research authority:

1. provider coverage/no-candidate failure was fixed by the bounded SearXNG engine-pool remediation;
2. retrieval-source latency now meets the frozen target on the unchanged production identity transport.

Remaining Phase 16 work is validation/observability/sealing: 16G diagnostics review, 16H independent validation corpus, 16I live burn-in and 16J readiness decision.