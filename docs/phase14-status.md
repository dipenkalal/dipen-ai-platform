# Phase 14 Status

Status: **IN PROGRESS — 14A–14I IMPLEMENTED; FINAL CI + 14J ACER BURN-IN PENDING**

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
- resumable Acer live burn-in/deployment operator.

## Preserved authority boundary

Phase 14 does not activate smart-routing research, generic model network tools, arbitrary provider access, automatic Knowledge mutation, destructive evidence cleanup, Guardian/root/systemd authority, Docker privilege, or autonomous merge/release/deployment authority.

The production research scope remains manual `research-agent` + explicit bounded search query + fixed local `searxng-local-v1` + sealed Phase 12 retrieval/evidence.

## Current deterministic gate

The core Phase 14 implementation has already passed:

- Phase 14 backend tests;
- deterministic 5/5 reliability benchmark;
- Phase 14 Guardian boundary;
- dashboard authority/lint/build gates;
- sealed Phase 12/13 regression matrix (112 tests);
- repository-wide CI/regression workflows.

The final tracked operator and owner-visible selection metadata are now under the same full CI gate before Acer execution.

## Remaining gate

14J requires one controlled Acer burn-in and dashboard deployment proof. The burn-in is resumable and will run two bounded manual Research Agent searches, using a third only if necessary to obtain at least five retrieval-telemetry events. It must leave Guardian inactive, Telegram approvals disabled, SearXNG loopback-only, retention non-destructive, and smart-routing research disabled.

14J then records one empirical posture:

- `manual-research-production-ready`;
- `manual-research-experimental-only`;
- `manual-research-provider-degraded`.

No 14J posture activates smart-routing research.
