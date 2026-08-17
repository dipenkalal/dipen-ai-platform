# Phase 10D.3 — Executive Office → Ruflo Handoff

## Purpose

Phase 10D.3 maps an already validated DAP Executive Office child task into the bounded `RufloAdapterRequest` contract. The handoff is a pure translation/evidence step. It does not invoke Ruflo, Codex, Guardian, MCP, plugins, Docker, systemd, or any executor.

## Source authority

The handoff accepts DAP-owned model objects only:

- a canonical `TaskLedgerRecord` child task;
- an `ExecutiveExecutionResponse` that has already passed Executive Office execution admission;
- a DAP-owned `RufloHandoffScope` containing acceptance criteria, repository-relative allowed paths, and optional constraints.

The handoff does not create a canonical task, owner approval, or execution authorization.

## Admission requirements

Before constructing a Ruflo request, the service requires:

- execution disposition `validated` or a validated `idempotent_replay`;
- execution state `validated`;
- `admission_validated=true`;
- `validation_only=true`;
- no task-ledger mutation;
- no durable reservation;
- no executor start;
- no broker activation;
- no reservation IDs;
- a canonical child task with `task_type=agent` and `status=assigned`;
- the task ID to be included in the admitted child-task set;
- exact delegation and parent-task identity match;
- exactly one assigned DAP agent;
- that assigned agent to appear in the Executive Office selected-agent set.

## Scope hardening

Allowed paths must be repository-relative POSIX paths. Absolute paths, home-relative paths, parent traversal, dot segments, empty segments, Windows-style paths, and duplicates are rejected.

Every generated Ruflo envelope adds DAP-owned non-negotiable constraints prohibiting:

- Codex execution through the handoff;
- network access;
- privileged execution;
- MCP registration;
- Codex/Ruflo plugin installation;
- work outside the explicitly listed repository paths.

## Evidence binding

The resulting `RufloExecutiveHandoff` records:

- source execution ID;
- source delegation ID;
- source parent task ID;
- source child task ID;
- SHA-256 of the canonical task snapshot;
- SHA-256 of the validated admission snapshot;
- the deterministic bounded `RufloAdapterRequest`;
- explicit `false` claims for canonical-task creation, owner-approval creation, and execution-authority transfer.

The Ruflo request ID is deterministic over the exact task snapshot, admission snapshot, execution/task identity, and DAP-owned handoff scope.

## Boundary

Phase 10D.3 does not wire this service into the production API. The next integration step may pass the resulting request into the already bounded `RufloCandidateBridge`, but execution authority remains entirely with DAP.
