# Phase 16H.1 — Targeted Slow-Tail Live Evidence

Date: 2026-08-19

Purpose: diagnose the four Phase 16H cases implicated in the independent-validation retrieval tail without changing the independent corpus, frozen threshold, provider, transport, timeout/retry/concurrency policy, production truth or authority boundary.

## Source and runtime baseline

- source head: `c4457ae394f6f835f7e2aa03fdf443a676b9fa24`
- branch: `phase16/research-provider-coverage-latency-canary`
- provider: `searxng-local-v1`
- provider bind: `127.0.0.1:8888`
- production transport: identity-only `dap-pinned-https-http1-v1`
- production truth before/after: task/evidence/ops `15/16/6`
- backend PID before/after: `677911`
- Guardian: inactive
- Telegram approvals: `DAP_TELEGRAM_APPROVALS_ENABLED=false`
- SearXNG container/start/binding unchanged
- source checkout clean

## Probe contract

Probe version: `phase16h1.1`

Four independent Phase 16H cases were replayed exactly three times each:

- `p16-usgs-earthquake-magnitude`
- `p16-overlay-filesystems`
- `p16-rfc9293-tcp`
- `p16-dns-over-https`

The probe used the same fixed provider, bounded query fallback, sealed retrieval path, at-most-three URL ceiling, identity production transport and 60-second case timeout. It wrote only to an isolated `/tmp` truth DB and recorded only safe source-family / hashed source-key identity plus timing decomposition.

## Result

- runs: `12/12` successful
- source records: `36/36` successful
- successful source P50: `298.305 ms`
- successful source P95: `1628.755 ms`
- successful source max: `1953.731 ms`
- successful sources above frozen `1500 ms` target: `4`
- run P95 values above target: `4`
- dominant fetch component by P95: `response-header`

Retriever P95 decomposition:

- preflight: `0.274 ms`
- DNS: `84.225 ms`
- admission: `0.749 ms`
- fetch: `1469.390 ms`
- retriever-uninstrumented: `6.988 ms`
- total: `1531.428 ms`

Fetch-component P95:

- connect/TLS: `274.966 ms`
- request-write: `0.011 ms`
- response-header: `973.191 ms`
- response-body: `563.905 ms`
- close-wait: `0.585 ms`
- fetch-uninstrumented: `29.702 ms`

## Case findings

### USGS earthquake magnitude

All three iterations stayed below the frozen threshold. Case P95/max: `1252.443 ms`.

### Overlay filesystems

One source family, `atscontainers.com`, was above `1500 ms` in all three iterations:

- `1556.426 ms`, response-header `948.956 ms`
- `1522.586 ms`, response-header `916.311 ms`
- `1628.755 ms`, response-header `1045.895 ms`

All three were single-attempt retrievals with zero retries. This is a reproducible upstream response-header / TTFB tail for that repeatedly selected source family, not a retry/backoff artifact.

### RFC 9293 TCP

One `github.com` retrieval measured `1953.731 ms`, dominated by response-header `1282.014 ms`. The next two iterations measured only `566.226 ms` and `675.700 ms`, so this source-family event was transient rather than repeatably slow in this probe.

### DNS over HTTPS

All three iterations stayed below the frozen threshold. Case P95/max: `977.192 ms`.

## Engineering conclusion

H.1 does not justify lowering the `1500 ms` target, changing the independent corpus, increasing timeout/retry/concurrency authority, promoting gzip, or adding source-specific blacklists. The repeatable tail is primarily caused by upstream response-header latency on a repeatedly selected source, while the remaining observed outlier is transient.

The justified next remediation is generic deterministic source-selection resilience: retain a bounded set of equally admissible alternatives already present in the same provider response, keep source-family diversity and the final three-URL retrieval ceiling, and prefer URL structures / cross-engine support that are more resilient for documentation and standards retrieval without using provider titles/snippets or remote latency probes.

## Integrity

Canonical H.1 report SHA-256:

`c9cfa723ef69ff554aadaeba8936b719352b12319e485d599c90a0b8355559f6`

H.1 is diagnostic evidence only. It does not itself satisfy or replace the full 24-case independent Phase 16H readiness gate.
