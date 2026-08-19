# Phase 15 — Research Provider Reliability Live Evidence — 2026-08-19

Status: **COMPLETE / SEALED — LIVE POSTURE: `manual-research-provider-degraded`**

Live source checkpoint: `6fae0c2a6de7413bb093607c8558eced9877cd0f`

Branch: `phase15/research-provider-reliability`

PR: #69 — remains draft/open/unmerged pending explicit owner merge authorization.

## Purpose

Phase 15 remediated the provider-quality weaknesses measured in Phase 14 without widening DAP research authority, then ran a frozen 30-case live corpus on the Acer to make an empirical provider-readiness decision.

The live gate completed successfully as an execution/safety gate. The provider-quality targets did not pass, so the correct Phase 15 readiness posture is `manual-research-provider-degraded`.

## Final pre-live CI seal

All nine repository workflows passed on the exact live source checkpoint `6fae0c2a6de7413bb093607c8558eced9877cd0f` before the Acer corpus was run:

- CI — run `32208030799` — SUCCESS;
- Phase 10 Ruflo Evaluation — run `32208030686` — SUCCESS;
- Phase 11 Engineering Agent — run `32208030744` — SUCCESS;
- Phase 12 Internet Research Gateway — run `32208030683` — SUCCESS;
- Phase 12I Research Workspace Dashboard — run `32208030678` — SUCCESS;
- Phase 12J Research Benchmark — run `32208030702` — SUCCESS;
- Phase 13 Provider-Specific Research Activation — run `32208030833` — SUCCESS;
- Phase 14 Research Operations Reliability — run `32208030673` — SUCCESS;
- Phase 15 Research Provider Reliability — run `32208030711` — SUCCESS.

The dedicated Phase 15 workflow proved Ruff, Mypy, compile, Phase 15 tests, the deterministic 30/30 offline corpus, the sealed Phase 12–14 regression matrix, Guardian boundaries, dashboard navigation tests, dashboard build, and production dashboard-image build.

## Acer source and runtime baseline

The live gate synchronized the Acer to the exact expected branch and commit:

- branch: `phase15/research-provider-reliability`;
- HEAD: `6fae0c2a6de7413bb093607c8558eced9877cd0f`;
- source state: clean.

Production baseline before the Phase 15 deployment/corpus:

- task ledger rows: `15`;
- immutable research evidence rows: `16`;
- research operations rows: `6`;
- backend: active, PID `487274`;
- Guardian broker: inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- dashboard: healthy;
- SearXNG: running;
- SearXNG binding: exactly `127.0.0.1:8888`.

## Phase 15 frontend deployment proof

The backend was loaded with one controlled restart. Its new PID was `510720`, and it remained that PID through the final safety gate.

The Phase 15 dashboard was rebuilt and recreated successfully. Live HTTP/frontend proof:

- `/research` -> HTTP `200`;
- `/research/operations` -> HTTP `200`;
- the normal Guardian landing page contained links to both `/research` and `/research/operations`;
- dashboard readiness endpoint loaded successfully;
- `PHASE15_FRONTEND_VISIBILITY|PASS`.

This closes the original frontend-discoverability defect: Research and Research Ops are now exposed from the normal DAP landing navigation rather than requiring a manually typed route.

## Frozen live corpus

Benchmark version: `phase15i.1`

Corpus size: `30` cases.

The benchmark used the fixed local `searxng-local-v1` provider and the sealed DAP retrieval/evidence path. Each case was hard-bounded to 60 seconds. The corpus used an isolated benchmark truth database under `/tmp`, not the production DAP truth database.

Canonical report SHA-256:

`ade3a36bd60382cad33529af465d8f08f0c5e9feac71c1d823ed2f9af214ac7d`

The validated live report was published read-only at:

`/home/dipen/dap/data/research/phase15-provider-live-report.json`

## Empirical results

| Metric | Frozen target | Live result | Result |
|---|---:|---:|---|
| Query success rate | >= 0.95 | `0.30` (`9/30`) | FAIL |
| No-candidate rate | <= 0.05 | `0.70` (`21/30`) | FAIL |
| Unique-source-family rate | >= 0.80 | `0.963` | PASS |
| Duplicate-content rate | <= 0.20 | `0.0` | PASS |
| Retrieval-source p95 | <= 1500 ms | `7648.376 ms` | FAIL |
| Authority-boundary regressions | `0` | `0` | PASS |

Additional measurements:

- fallback cases: `21`;
- provider search p50: `964.589 ms`;
- provider search p95: `2117.782 ms`;
- retrieval-source p50: `2202.51 ms`;
- retrieval-source p95: `7648.376 ms`;
- total pipeline p95: `23413.71 ms`;
- benchmark target aggregate: `meets_phase15_targets=false`.

The strongest Phase 15 improvements are source-family diversity and duplicate-content suppression. The remaining limiting factors are provider query coverage/no-candidate frequency and remote retrieval tail latency.

## Readiness projection

The published report was loaded by both the direct backend and dashboard read-only readiness projections.

Final state: `degraded`

Final reason codes:

- `operations-reliability-degraded`;
- `query-coverage-below-target`;
- `no-candidate-rate-above-target`;
- `retrieval-p95-above-target`.

Final live posture:

`manual-research-provider-degraded`

This is an empirical outcome, not a failed safety gate and not an authorization to expand research authority.

## Production-truth isolation proof

Production counts before and after the 30-case corpus were identical:

| Production table | Before | After | Delta |
|---|---:|---:|---:|
| `task_ledger` | 15 | 15 | 0 |
| `research_retrieval_evidence` | 16 | 16 | 0 |
| `research_operations_events` | 6 | 6 | 0 |

The isolated benchmark database contained:

- task ledger: `0`;
- research evidence: `27`;
- research operations events: `27`.

Therefore the live provider corpus produced benchmark evidence only inside its isolated truth database and did not mutate production task truth, production research evidence, or production research operations telemetry.

## Resource snapshot

At the post-corpus resource check:

- backend RSS: `140.88 MiB`;
- backend user CPU: `4.28 s`;
- backend system CPU: `0.58 s`;
- host memory: `18.5%`;
- host CPU: `3.4%`.

No Acer resource-safety issue was observed in the live gate.

## Final authority/runtime safety proof

At the end of the live gate:

- backend: active;
- backend PID: `510720` (unchanged after the single controlled restart);
- Guardian broker: inactive;
- Telegram approvals: false;
- dashboard: healthy;
- SearXNG: running;
- SearXNG binding: exactly `127.0.0.1:8888`;
- branch: `phase15/research-provider-reliability`;
- source HEAD: `6fae0c2a6de7413bb093607c8558eced9877cd0f`;
- source state: clean;
- `PHASE15_LIVE_CORPUS|PASS`;
- `PHASE15_AUTHORITY_BOUNDARY|PASS`;
- `PHASE15_15I|PASS`;
- shell exit: `0`.

No smart-routing research was enabled. No provider switching or generic network authority was granted. No automatic Knowledge mutation or destructive evidence cleanup was introduced. No Guardian/root/systemd/Docker authority was granted to agents.

## Phase 15J decision

**Chosen posture: `manual-research-provider-degraded`.**

Phase 15 is complete and sealed at this posture. Manual owner-supervised Research Agent execution remains the maximum research authority. The correct next engineering direction is provider coverage/reliability work, not authority expansion.

Any merge of PR #69 remains an explicit owner decision. Any future smart-routing research or broader provider/network authority must be a separate owner-approved milestone with its own safety and live-evidence gates.

## Post-live documentation CI seal

The corrected post-live documentation checkpoint `ef7bc9d830f54fe8405e97b8535d2482bc39a10c` passed all nine repository workflows after restoring both frozen Phase 15 Guardian roadmap assertions:

- CI — run `32209579699` — SUCCESS;
- Phase 10 Ruflo Evaluation — run `32209579696` — SUCCESS;
- Phase 11 Engineering Agent — run `32209579680` — SUCCESS;
- Phase 12 Internet Research Gateway — run `32209579676` — SUCCESS;
- Phase 12I Research Workspace Dashboard — run `32209579684` — SUCCESS;
- Phase 12J Research Benchmark — run `32209579693` — SUCCESS;
- Phase 13 Provider-Specific Research Activation — run `32209579674` — SUCCESS;
- Phase 14 Research Operations Reliability — run `32209579697` — SUCCESS;
- Phase 15 Research Provider Reliability — run `32209579672` — SUCCESS.

The earlier post-live documentation attempts failed only because the roadmap wording no longer matched two intentionally frozen Guardian text assertions. The final roadmap restores both exact safety statements; no runtime implementation, empirical result, provider authority, or safety policy was weakened to obtain the green seal.
