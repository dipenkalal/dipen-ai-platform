# Phase 15 Status

Status: **IN PROGRESS — 15A–15H SOURCE/CI GREEN; 15I ACER LIVE DEPLOYMENT + 30-CASE CORPUS NEXT**

Base: Phase 14 final merged documentation seal `512c03aaab6c49f7c7ec4c351dcd82e35f36b4bc`.

Branch: `phase15/research-provider-reliability`.

Draft PR: #69. Do not merge without explicit owner authorization after live evidence and final CI.

Pre-live code checkpoint: `d3c6289cc7a32da14a18552937826d8f81a99da2`.

## Why Phase 15 exists

Phase 14 proved the reliability/operations layer and exposed a provider-quality problem rather than an authority problem. Its final posture was `manual-research-provider-degraded`, with a real no-candidate failure, `0.8125` success rate, `0.5` unique-source-family rate, `0.4615` duplicate-content rate and `2370.666 ms` retrieval p95.

Phase 15 remediates those measured weaknesses while preserving manual-only research authority.

## 15A–15H implemented scope

### 15A — Frontend visibility

The Research routes were already present, but the global navigation was hidden on the normal `/` Guardian landing page. Phase 15 makes the primary navigation visible there and exposes direct `Research` and `Research Ops` entries while keeping chat navigation isolated. Dashboard boundary, lint, Next build and production-image build are green. Acer deployment/owner visual proof remains part of 15I.

### 15B — No-candidate diagnosis and bounded provider scanning

Local SearXNG scanning is bounded to at most 20 provider results while accepted candidate count remains bounded by the request and downstream retrieval remains `<= 3` URLs. DAP now distinguishes true provider-zero results from malformed/invalid/destination-policy-filtered results and records provider/considered/rejection counts without exposing provider titles or snippets.

### 15C — Deterministic query fallback

A fixed three-attempt maximum fallback policy is implemented only for the fixed local SearXNG path. The original owner query is always first; fallback variants may remove edge tokens but never add terms, switch providers or invoke model-generated query expansion. Successful and failed search steps expose safe attempt/query diagnostics in Research Agent run history while provider titles/snippets remain excluded.

### 15D — Candidate diversity and duplicate suppression v2

Canonical duplicate comparison drops fragments and known tracking parameters, normalizes host/default ports and sorts remaining query parameters. This affects duplicate comparison only; retrieval uses the original admitted URL. Unique source families are preferred before duplicate-family fallback, and the retrieval ceiling remains `<= 3`.

### 15E — Duplicate-content readiness measurement

Immutable normalized-text SHA-256 values remain the duplicate-content signal. Phase 15 includes duplicate-content rate in the live provider report/readiness view without deleting, rewriting or destructively consolidating evidence.

### 15F — Timing and bounded live execution

Provider-search duration, retrieval duration and total pipeline duration are separated. Existing sealed retry rules remain intact. The live 30-case benchmark adds a frozen `60 s` per-case wall-clock ceiling so an external stall becomes a case failure rather than an unbounded run.

### 15G — Read-only provider readiness

A GET-only `/api/v1/research/operations/provider-readiness` endpoint and dashboard proxy were added. The Research Ops page exposes provider state/reason codes, live query coverage, no-candidate rate, source-family rate, duplicate-content rate and retrieval p95. Before the hashed live report exists it deliberately reports `insufficient-data` / live corpus pending. It exposes no SearXNG restart/reconfiguration action and grants no new network/mutation authority.

### 15H — Frozen 30-case benchmark corpus

The corpus is frozen at exactly 30 cases across official documentation, standards, general factual and multi-source technical categories. CI uses deterministic fixtures; the Acer runner is separate and uses the real fixed local provider plus sealed retrieval. The live runner must use an isolated `/tmp` truth database and therefore must not mutate production task truth or production research evidence.

## Pre-live CI gate

All nine repository workflows were green on `d3c6289cc7a32da14a18552937826d8f81a99da2`:

- CI — `32207590532`;
- Phase 10 Ruflo Evaluation — `32207590572`;
- Phase 11 Engineering Agent — `32207590496`;
- Phase 12 Internet Research Gateway — `32207590516`;
- Phase 12I Research Workspace Dashboard — `32207590512`;
- Phase 12J Research Benchmark — `32207590450`;
- Phase 13 Provider-Specific Research Activation — `32207590653`;
- Phase 14 Research Operations Reliability — `32207590413`;
- Phase 15 Research Provider Reliability — `32207590460`.

The dedicated Phase 15 workflow passed Ruff, Mypy, compile, Phase 15 tests, the deterministic `30/30` provider benchmark, the sealed search/retrieval regression matrix, Guardian boundaries, dashboard authority tests, lint/build and the production dashboard image build.

## Frozen live targets

The live result must be measured against the thresholds frozen before 15I:

- query success rate `>= 0.95`;
- no-candidate rate `<= 0.05`;
- selected unique-source-family rate `>= 0.80`;
- duplicate-content rate `<= 0.20`;
- retrieval-source p95 `<= 1500 ms`;
- per-case wall-clock maximum `60 s`;
- zero authority-boundary regressions.

These thresholds are not changed after seeing the live result merely to force a pass.

## Current authority boundary

- smart-routing research: disabled;
- automatic research on unrelated agent requests: disabled;
- provider: fixed local `searxng-local-v1` at `127.0.0.1:8888`;
- selected retrieval URLs: `<= 3`;
- provider titles/snippets: non-evidence and excluded from model context;
- automatic Knowledge mutation: disabled;
- destructive evidence cleanup: disabled;
- agent Guardian/root/systemd/Docker authority: absent.

## Remaining gates

15I requires one controlled Acer deployment/live block that loads the Phase 15 backend/dashboard, proves the new navigation from the normal landing page, runs the frozen 30-case corpus against the real local provider using an isolated benchmark DB, writes the hashed live report, verifies the read-only readiness projection, and proves production task/evidence/operations truth was unchanged by the corpus.

15J then records exactly one empirical posture:

- `manual-research-production-ready`;
- `manual-research-experimental-only`;
- `manual-research-provider-degraded`.

No Phase 15 posture activates smart-routing research.
