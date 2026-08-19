# Phase 14 Status

Status: **IN PROGRESS — 14A–14I GREEN; 14J LIVE BURN-IN RECOVERY IN PROGRESS**

Base: Phase 13 final merged seal `5f4afa1869497aafee3d1cba3de9b96cdad2e8dd`.

Branch: `phase14/research-operations-reliability`.

## Implemented scope

- deterministic source-family diversity and exact URL duplicate suppression;
- source-selection quality metadata explicitly separated from factual/source credibility;
- one bounded retry for clearly transient GET retrieval failures only;
- append-only research operations telemetry;
- exact duplicate-content visibility using immutable normalized-text SHA-256;
- GET-only reliability summary, provider-health, resource-snapshot and retention-plan APIs;
- non-destructive evidence-retention dry-run policy;
- fixed-loopback SearXNG health telemetry with no service-control authority;
- read-only backend CPU/RSS and host utilization snapshot;
- owner-facing `/research/operations` dashboard;
- deterministic five-case reliability benchmark with resource snapshots and report hash;
- weekly scheduled deterministic regression benchmark;
- Phase 14 Guardian/browser authority boundaries;
- resumable Acer live burn-in/deployment operator;
- bounded provider-failure recovery bridge for a valid no-candidate SearXNG result.

## Preserved authority boundary

Phase 14 does not activate smart-routing research, generic model network tools, arbitrary provider access, automatic Knowledge mutation, destructive evidence cleanup, Guardian/root/systemd authority, Docker privilege, or autonomous merge/release/deployment authority.

The production research scope remains manual `research-agent` + explicit bounded search query + fixed local `searxng-local-v1` + sealed Phase 12 retrieval/evidence.

## Deterministic gate

14A–14I are green across the Phase 14 backend, Guardian and dashboard gates, including the deterministic 5/5 reliability benchmark, production dashboard image build, and sealed Phase 12/13 regression matrix.

## 14J first live observation

The first Acer burn-in query (`IANA example domains RFC 2606`) reached the fixed local SearXNG provider successfully but returned no URL candidate eligible for bounded DAP retrieval. The Research Agent failed closed with no public-web evidence and no retrieval-operations event. Smart-routing research remained rejected and the read-only operations APIs remained GET-only.

The original operator then exposed an operator-only assumption bug: HTTP 200 was treated as equivalent to an agent `status=completed`, causing the shell to stop before persisting the failed attempt into resume state.

The recovery path is intentionally narrow:

- reconcile exactly one failed instrumented `research-agent` task by its `source_run_id`;
- require no evidence or retrieval-operations delta from that failed search;
- permit only operator/test/workflow/docs source changes since the already-loaded backend checkpoint;
- run bounded manual fallback research queries until at least two successful runs and five retrieval-operation events are obtained, with at most three fallback attempts;
- then mark the existing resumable burn-in state complete and delegate back to the guarded Phase 14 live operator for operations visibility, deterministic benchmark, offline dashboard deployment and final safety checks.

The recovery bridge cannot restart services, operate Docker, expand network authority, merge/release, or enable approvals.

## Remaining gate

14J still requires the controlled Acer burn-in and dashboard deployment proof to finish. The live evidence must leave Guardian inactive, Telegram approvals disabled, SearXNG loopback-only, retention non-destructive, and smart-routing research disabled.

14J then records one empirical posture:

- `manual-research-production-ready`;
- `manual-research-experimental-only`;
- `manual-research-provider-degraded`.

The observed no-candidate provider failure will be included in the final posture decision even if the bounded fallback recovery succeeds. No 14J posture activates smart-routing research.
