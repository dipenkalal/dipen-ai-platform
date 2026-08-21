# Phase 16A — Provider Root-Cause Diagnostic Live Evidence — 2026-08-19

Status: **PASS — ROOT CAUSE LOCALIZED TO UPSTREAM PROVIDER ZERO-RESULT BEHAVIOR**

Source checkpoint: `70dfee5b76c9ed5ad06221a3ec0b448d689cc43c`

Branch: `phase16/research-provider-coverage-latency`

PR: #72

## Purpose

Phase 16A replayed the unchanged frozen Phase 15 30-case corpus with a new isolated diagnostic contract. The goal was to distinguish upstream provider zero-result behavior from DAP candidate filtering, provider transport failures, retrieval failures and benchmark timeouts before changing SearXNG configuration.

No provider configuration was changed for this run.

## Pre-live CI seal

All 11 pull-request workflows passed on source checkpoint `70dfee5b76c9ed5ad06221a3ec0b448d689cc43c`, including the dedicated Phase 16 workflow and the sealed Phase 10–15.1 regressions.

## Acer source and safety baseline

The Acer synchronized to the exact source checkpoint and remained clean:

- branch: `phase16/research-provider-coverage-latency`;
- HEAD: `70dfee5b76c9ed5ad06221a3ec0b448d689cc43c`;
- source: clean.

Production/runtime baseline:

- task ledger: `15`;
- research evidence: `16`;
- research operations: `6`;
- Guardian: inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- SearXNG: running;
- SearXNG binding: `127.0.0.1:8888`;
- repository SearXNG settings SHA-256: `ed62d55f458aa1ac064bee392d1d639095d76ef55ea0000a8de545c2ffbb4730`.

## Diagnostic result

Diagnostic version: `phase16a.1`

Corpus: `phase15-provider-corpus-v1`

Case count: `30`

Canonical diagnostic report SHA-256:

`d497d4a4cca4451b3bcef3e0a4fd16d81932645fa28d28ef883ddb686d88baed`

Failure taxonomy:

| Failure class | Count |
|---|---:|
| success | 9 |
| provider-zero-results | 21 |
| dap-filtered-zero | 0 |
| provider-transport-error | 0 |
| retrieval-failed | 0 |
| benchmark-case-timeout | 0 |
| unclassified-no-candidate | 0 |

This localizes the 70% no-candidate defect to SearXNG/upstream engine behavior before DAP destination-policy filtering or retrieval begins.

## Category distribution

- official documentation: `9` success, `1` provider-zero-results;
- standards: `10` provider-zero-results;
- general factual: `5` provider-zero-results;
- multi-source technical: `5` provider-zero-results.

## Sequence observation

The first nine corpus cases succeeded. Starting with `p15-nodejs-streams`, every remaining 21 case returned zero raw SearXNG results on all three bounded query attempts (`raw=[0,0,0]`).

This sequence is consistent with an order/burst-dependent upstream-engine failure mode such as engine suspension, throttling, CAPTCHA/access denial or rate limiting. It is not yet proof of which upstream-engine condition occurred because Phase 16A intentionally did not retain SearXNG engine-error metadata.

Therefore Phase 16 must capture engine-level health/error classes before changing engine selection, SafeSearch or query behavior.

## Successful-case timing observations

Search discovery remained roughly around one to two seconds on successful cases, while retrieval showed substantial tail latency. Examples from the replay include:

- Python docs: provider `2026.381 ms`, retrieval `1448.553 ms`;
- Kubernetes: provider `1031.459 ms`, retrieval `12806.738 ms`;
- PostgreSQL JSONB: provider `957.89 ms`, retrieval `13812.884 ms`;
- systemd service unit: provider `1047.238 ms`, retrieval `22498.959 ms`;
- Linux namespaces: provider `953.462 ms`, retrieval `2219.172 ms`.

The coverage defect and retrieval-latency defect remain separate remediation tracks.

## Isolation proof

Isolated diagnostic truth database:

- task ledger: `0`;
- research evidence: `27`;
- research operations: `27`.

Production counts were unchanged after the replay:

- task ledger: `15 -> 15`;
- research evidence: `16 -> 16`;
- research operations: `6 -> 6`.

The diagnostic did not mutate production truth.

## Provider/configuration proof

The repository SearXNG settings SHA-256 remained exactly:

`ed62d55f458aa1ac064bee392d1d639095d76ef55ea0000a8de545c2ffbb4730`

SearXNG remained running on exactly `127.0.0.1:8888`.

No provider switch, engine-set change, SafeSearch change or provider endpoint change occurred.

## Final authority proof

At the end of the diagnostic:

- Guardian remained inactive;
- Telegram approvals remained false;
- source branch/head remained exact and clean;
- provider configuration unchanged: PASS;
- production truth unchanged: PASS;
- authority boundary: PASS;
- failure taxonomy: PASS;
- `PHASE16_16A_LIVE_DIAGNOSTIC|PASS`;
- shell exit: `0`.

## Decision

**16A/16B diagnostic baseline: PASS.**

The next work is **16C.1 — SearXNG upstream-engine failure telemetry**. DAP will record only safe engine names, contributing-engine names and normalized engine failure classes from SearXNG's local JSON response. Raw engine error text, provider titles and provider snippets remain excluded.

No engine/configuration change is justified until that engine telemetry proves the dominant upstream failure mechanism.
