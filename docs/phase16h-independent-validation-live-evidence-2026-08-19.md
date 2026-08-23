# Phase 16H — Independent Validation Live Evidence — 2026-08-19

## Result

Phase 16H completed its independent 24-case live validation on Acer using exact all-CI-green source head:

`4c12910d013df75e0db43a28ed9dc1c857e9f158`

The validation runner itself completed successfully and all production/runtime/authority invariants remained intact, but the frozen Phase 16 readiness target set did **not** pass because successful retrieval-source P95 was above the sealed `1500 ms` ceiling.

Decision markers:

- `PHASE16_H_LIVE_VALIDATION|METRIC_FAIL`
- `PHASE16_H_FROZEN_TARGETS|FAIL`
- `PHASE16_H_PRODUCTION_TRUTH_UNCHANGED|PASS`
- `PHASE16_H_RUNTIME_UNCHANGED|PASS`
- `PHASE16_H_AUTHORITY_BOUNDARY|PASS`
- `PHASE16_H_READY_FOR_16I|NO`
- shell exit: `2`

Phase 16 therefore remains unsealed and must not advance to 16I readiness burn-in until the latency miss is diagnosed.

## Corpus integrity

Corpus: `phase16-validation-corpus-v1`

- total cases: `24`
- official-documentation: `6`
- standards: `6`
- general-factual: `6`
- multi-source-technical: `6`
- Phase 15 case-ID overlap: `0`
- Phase 15 exact-query overlap: `0`

The corpus was not modified after the live result.

## Independent validation metrics

- success: `24/24`
- success/query coverage rate: `1.0000`
- no-candidate count: `0`
- no-candidate rate: `0.0000`
- fallback cases: `0`
- selected sources: `72`
- successful sources: `72`
- selected unique-source-family rate: `0.9861`
- duplicate-content count: `13`
- duplicate-content rate: `0.1806`
- provider search P50: `320.731 ms`
- provider search P95: `614.669 ms`
- successful retrieval-source P50: `399.014 ms`
- successful retrieval-source P95: `1731.707 ms`
- pipeline P95: `3952.765 ms`

Category success was `1.0000` for all four categories.

Canonical report SHA-256:

`05c5417abdbbf2d13c75ec464ff4afd5fee733316cea68bbe288010a8e583cc1`

## Frozen target evaluation

- success/query coverage `>=0.95`: **PASS**
- no-candidate `<=0.05`: **PASS**
- unique source-family rate `>=0.80`: **PASS**
- duplicate-content rate `<=0.20`: **PASS**
- successful retrieval-source P95 `<=1500 ms`: **FAIL**
- authority/runtime boundary regressions: **PASS / zero regressions observed**

Recommended posture from the validation runner:

`manual-research-experimental-only`

The latency gap was `231.707 ms` above the frozen threshold.

## Slow-tail evidence

The 12 slowest successful source durations reported by the independent run were:

1. `2175.582 ms` — `p16-usgs-earthquake-magnitude` — general-factual
2. `1745.357 ms` — `p16-overlay-filesystems` — multi-source-technical
3. `1734.131 ms` — `p16-overlay-filesystems` — multi-source-technical
4. `1731.707 ms` — `p16-rfc9293-tcp` — standards
5. `1379.574 ms` — `p16-dns-over-https` — multi-source-technical
6. `1291.006 ms` — `p16-usgs-earthquake-magnitude` — general-factual
7. `1205.854 ms` — `p16-eia-electricity-generation` — general-factual
8. `1121.214 ms` — `p16-rfc9000-quic` — standards
9. `1118.913 ms` — `p16-w3c-csp3` — standards
10. `905.245 ms` — `p16-noaa-el-nino` — general-factual
11. `889.234 ms` — `p16-overlay-filesystems` — multi-source-technical
12. `865.836 ms` — `p16-lfp-battery` — multi-source-technical

Exactly four of the 72 successful source durations exceeded the `1500 ms` target. With the sealed nearest-rank P95 calculation, the fourth-largest value (`1731.707 ms`) became the run P95.

No failed cases occurred.

## Isolation and production invariants

Before and after the run, production remained:

- task ledger: `15 -> 15`
- research evidence: `16 -> 16`
- research operations: `6 -> 6`
- backend PID: `677911 -> 677911`
- Guardian: `inactive -> inactive`
- Telegram approvals: `DAP_TELEGRAM_APPROVALS_ENABLED=false`
- SearXNG state: `running -> running`
- SearXNG container ID: `812e687cf8d0b34f176271997a173756c7b77a8bd59bb785206495a31706e52d`
- SearXNG StartedAt: `2026-08-19T22:38:52.906924074Z`
- SearXNG binding: `127.0.0.1:8888`
- tracked SearXNG settings SHA-256: `cc2008ceb13c22e11da874921832fe1c702d7afc8b5bc1335a94831f7b37c0c1`
- production transport SHA-256: `d218e3a59b55e09b0b6f1269b7350c37808da3c0443818f02b0dbf0075139d13`
- production transport remained identity-only
- working tree remained clean on the exact validated source head

The isolated validation DB contained:

- task ledger: `0`
- research evidence: `72`
- research operations: `72`

## Next gate

Do not change the 24-case independent corpus and do not weaken the `1500 ms` readiness threshold.

Run a diagnostic-only Phase 16H.1 targeted replay of the cases implicated in the slow tail, using the existing sealed Phase 16E.2 timing decomposition. Repeat each target case three times so the project can distinguish persistent DAP-side latency from variable upstream DNS/connect/TLS/header/body latency before choosing any remediation.

16I remains blocked pending that evidence.
