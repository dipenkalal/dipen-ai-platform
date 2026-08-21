# Phase 16E.1 — Retrieval Stage Latency Live Evidence

Date: 2026-08-19 (Acer local runtime)

## Scope

Phase 16E.1 is diagnostic-only. It reused the sealed Phase 15 30-case corpus, fixed local `searxng-local-v1` provider, `WebSearchRetrievalPipeline`, `InternetResearchRetrieveTool`, and `BoundedInternetRetriever`. It did not alter provider configuration, transport behavior, transport timeouts, retry policy, production truth, smart routing, provider selection, generic network authority, evidence/model-content rules, Guardian state, Telegram approvals, or privileged actions.

Exact source head tested:

`78e72acf917487b0296bfa91eef51815caf61581`

Report SHA-256:

`1703569a7e691e683adbc02159272b59334b45a2001c2cbe399eea8019545ab9`

## Runtime gates

- Source checkout: clean
- Provider settings SHA-256: `cc2008ceb13c22e11da874921832fe1c702d7afc8b5bc1335a94831f7b37c0c1`
- Validated Wi-Fi path: `COGECO-9F8330-5G-ext`
- Production task ledger: 15 before / 15 after
- Production research evidence: 16 before / 16 after
- Production research operations: 6 before / 6 after
- Backend PID: 677911 before / 677911 after
- Guardian broker: inactive before / inactive after
- Telegram approvals: `DAP_TELEGRAM_APPROVALS_ENABLED=false` before / after
- SearXNG: running before / after
- SearXNG binding: `127.0.0.1:8888` before / after
- SearXNG container ID unchanged: `812e687cf8d0b34f176271997a173756c7b77a8bd59bb785206495a31706e52d`
- SearXNG StartedAt unchanged: `2026-08-19T22:38:52.906924074Z`
- Final source checkout: clean

All source/runtime/authority gates passed.

## Corpus result

- Cases: 30
- Successful cases: 30/30
- Retrieval attempts traced: 92
- Successful retriever traces: 84
- Successful retriever traces over 1500 ms: 2
- Isolated task ledger: 0
- Isolated evidence rows: 89
- Isolated operations rows: 89

## Bounded retriever stage timing

| Stage | P50 ms | P95 ms |
|---|---:|---:|
| Preflight policy | 0.099 | 0.268 |
| DNS resolution | 37.175 | 258.355 |
| Destination admission | 0.609 | 1.135 |
| Pinned HTTPS fetch | 246.082 | 1029.870 |
| Uninstrumented retriever overhead | 0.730 | 3.738 |
| Total bounded retriever | 363.489 | 1311.186 |

Dominant P95 stage: `fetch`.

Median fetch share of bounded-retriever time: `0.882` (88.2%).

Interpretation: policy/admission/local retriever overhead are negligible. DNS is secondary. The pinned HTTPS fetch is the dominant bounded-retriever stage.

## Slowest successful retriever traces

The two successful bounded-retriever traces above 1500 ms were:

1. `saeinc.com`: total 1979.861 ms; DNS 140.047 ms; fetch 1836.159 ms.
2. `bibliotecapleyades.net`: total 1759.168 ms; DNS 188.063 ms; fetch 1562.646 ms.

Additional high traces were dominated primarily by fetch, with a few cases showing material DNS contribution, including `freedesktop.org`, `nyaa.ee`, and `hackitu.de`.

## Case-level timing

- Provider case P50: 271.447 ms
- Provider case P95: 1556.711 ms
- Retrieval phase case P50: 1412.825 ms
- Retrieval phase case P95: 3128.600 ms
- Pipeline case P50: 1721.318 ms
- Pipeline case P95: 3886.016 ms

The Phase 16E.1 shell printed the case-level retrieval P95 against the 1500 ms threshold and therefore reported `FAIL`. That case-level comparison is diagnostic only: the frozen Phase 15 readiness threshold is defined against successful **per-source `duration_ms`** collected by `research_provider_live_benchmark.py`, not against aggregate case retrieval duration. Phase 16E.2 must therefore measure the exact frozen per-source metric while decomposing the dominant fetch stage and outer retry/backoff/tool overhead.

## Decision

Phase 16E.1: **PASS as instrumentation/evidence**.

The next gate is Phase 16E.2 diagnostic-only decomposition:

- connect + TLS setup
- request write/drain
- response header wait/read
- response body read
- connection close wait
- exact successful per-source end-to-end `duration_ms`
- retry count and bounded 250 ms retry-backoff contribution
- tool overhead excluding retry backoff

No timeout, retry, concurrency, provider, transport-authority, smart-routing, or deployment behavior should change before Phase 16E.2 evidence is collected.
