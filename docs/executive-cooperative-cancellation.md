# Executive Cooperative Cancellation

## Phase 5 purpose

Phase 5 adds cooperative cancellation to the bounded owner-triggered Executive
Office execution lifecycle.

Phase 4 deliberately refuses to force-kill a running execution. Its recovery
path reconciles durable evidence after interruption, but it does not provide a
safe way for an owner to request that currently running bounded work stop.

Phase 5 closes that gap without introducing an unrestricted process manager.

## Dependency

Phase 5 is stacked on the exact green Phase 4 head:

- Phase 4 PR: `#45`
- Phase 4 head: `cd30b7d1123f4a43ff9db8da952b437f85d2eba5`
- Phase 5 branch: `feat/executive-cooperative-cancellation`

Production remains unchanged until the dependency stack is merged and deployed
through the normal guarded process.

## Safety model

Cancellation is cooperative, not destructive.

A cancellation request must never:

- kill an operating-system process;
- send arbitrary signals to a PID;
- terminate a container;
- invoke a shell command;
- restart a service;
- activate the Guardian broker;
- replay completed work;
- mark an execution cancelled before runtime acknowledgement.

The system stores cancellation **intent** separately from execution terminal
state. Runtime code must explicitly observe that intent before a running task can
transition toward cancellation.

## Phase 5.1 — durable cancellation intent

The first slice introduces a durable cancellation-request ledger and a narrow
repository API.

A request records:

- execution ID;
- owner authorization identity;
- canonical request hash;
- request state;
- requested timestamp;
- observed timestamp, when a runtime acknowledges the request;
- resolved timestamp, when terminal reconciliation is complete.

Initial request states are:

- `requested` — owner cancellation intent is durable but not yet observed by a
  running executor;
- `observed` — the bounded runtime has acknowledged the cancellation intent;
- `resolved` — execution reconciliation has reached a durable terminal or
  manual-review state.

The same idempotency key and same canonical request returns the stored request.
The same key with different content conflicts.

Phase 5.1 does **not** cancel an asyncio task or change task-ledger execution state.
It only establishes the durable control-plane truth required by later slices.

## Phase 5.2 — cooperative runtime observation

The bounded execution runtime will gain an execution-scoped cancellation signal.

The runtime must check for cancellation:

1. before invoking each selected child task;
2. at bounded checkpoints exposed by the existing instrumented executor;
3. immediately after an awaited child result returns;
4. before starting the next child in a sequential execution.

A runtime observation updates the durable cancellation request to `observed`.

Cancellation must use normal coroutine cancellation/checkpoint semantics only.
There is no PID, process, container, service, or broker kill path.

## Phase 5.3 — cancellation reconciliation

When cooperative cancellation is observed:

- no additional child task may start;
- the currently cooperating child may finish as `cancelled` when the executor
  confirms cancellation;
- untouched queued children remain distinguishable from work that actually ran;
- active execution reservations are released through an atomic repository path;
- the execution moves to `cancelled` only when durable task/runtime evidence is
  consistent;
- otherwise it moves to `manual_review`;
- the parent orchestration task moves to `manual_review` unless all required
  child work has independently satisfied accepted completion evidence.

Cancellation acknowledgement never fabricates completion evidence.

## Phase 5.4 — status and recovery integration

Execution status will expose cancellation-request truth independently from task
state:

- cancellation requested;
- cancellation observed;
- cancellation resolved;
- owner authorization ID;
- relevant timestamps.

Recovery must recognize unresolved cancellation requests. It may reconcile stale
or interrupted cancellation state, but it must never replay work automatically.

## Owner authorization

Running cancellation requires a dedicated authorization scope distinct from:

- delegation approval;
- execution admission;
- execution start;
- pre-start reserved cancellation;
- interrupted-run recovery.

The scope is:

`request_running_execution_cancellation`

The authorization must be issued by `dipen-owner` and bound to the exact:

- execution ID;
- delegation ID;
- parent task ID;
- selected child task set.

## Broker boundary

The Guardian broker remains inactive throughout Phase 5. Cooperative cancellation
is an Executive Office/runtime concern and does not authorize privileged restart,
deploy, shell, email, purchase, publication, or other external mutation.

## Delivery sequence

Phase 5 will be delivered in bounded slices:

1. durable cancellation-request schema/repository and idempotency tests;
2. owner-authorized cancellation-request API;
3. runtime cancellation signal and checkpoint observation;
4. atomic cancellation reconciliation and reservation release;
5. execution status/recovery integration and end-to-end tests.
