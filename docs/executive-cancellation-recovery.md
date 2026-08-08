# Executive Execution Cancellation and Recovery

## Phase 4.5 purpose

Phase 4.5 completes the bounded owner-triggered execution lifecycle with two
explicit control operations:

- `POST /api/v1/executive-office/executions/{execution_id}/cancel`
- `POST /api/v1/executive-office/executions/{execution_id}/recover`

These controls do not create a general process manager. They preserve the existing
Executive Office, Agent Truth, instrumented executor, and broker-isolation
boundaries.

## Cancellation boundary

Cancellation is intentionally narrow.

A cancellation may mutate execution state only when all of the following are true:

1. the execution exists;
2. it is a durable, non-validation-only execution;
3. its state is exactly `reserved`;
4. no execution-start claim exists;
5. selected child tasks are still `queued`;
6. child task delegation, parent, and assigned-agent identity still match;
7. the active reservations still match the stored execution reservation set;
8. an affirmative `dipen-owner` authorization is bound to the exact execution.

The transaction then:

- moves selected queued children to `cancelled`;
- releases their execution reservations;
- moves the execution record to `cancelled`;
- moves the parent to `manual_review`;
- stores the idempotent control result.

A running execution is never force-killed by this endpoint. Once the start claim
exists, the caller must use recovery rather than crossing the execution boundary.

## Recovery boundary

Recovery reconciles durable evidence. It never invokes an agent.

The recovery service reads:

- the execution record;
- selected task and agent identity;
- active reservation ownership;
- the execution-start claim and stored terminal response, when present;
- current task-ledger states;
- current Agent Truth runtime state;
- acceptance evidence already stored by Phase 4.4.

Recovery is allowed for interrupted `running` or existing `manual_review`
executions. A `reserved` execution must use the separate start or cancel path.

## Recovery decisions

### Live work

A fresh `busy` heartbeat whose `current_task_id` matches a selected task defers
recovery. The execution remains `running`.

A newly claimed execution also receives a bounded grace window before stale-state
reconciliation.

### Proven completion

Recovery may finalize `completed` only when every selected child has:

- a stored completed task result;
- non-empty output;
- matching assigned agent;
- matching run ID;
- accepted completion evidence;
- matching terminal status; and
- an output SHA-256 matching the stored agent result.

Task status alone is not accepted as proof of completion.

### Proven failure

After the recovery grace window, if every selected child is terminal and at least
one is deterministically `failed`, recovery may finalize the execution as
`failed`. Reservations are released and the parent moves to `manual_review`.

### Ambiguous interruption

When no fresh matching runtime evidence exists and durable state is not sufficient
to prove completion or deterministic failure:

- nonterminal selected children move to `manual_review`;
- active reservations are released;
- the execution moves to `manual_review`;
- the parent moves to `manual_review`;
- no agent is replayed.

A completed task without complete acceptance evidence also goes to
`manual_review`, rather than being falsely accepted.

### Existing manual review

Recovery may:

- release stale reservations while preserving `manual_review`; or
- finalize `completed` when complete matching acceptance evidence later becomes
  available.

It never guesses that an ambiguous action should be repeated.

## Idempotency

Execution-control requests use a separate durable idempotency ledger.

The canonical request hash includes:

- action (`cancel` or `recover`);
- execution ID;
- owner authorization ID;
- delegation, parent, and selected child IDs;
- owner identity;
- approval value;
- authorization scope; and
- authorization statement.

Authorization timestamps are excluded so transport retries remain stable.

The same key plus the same request returns the stored result. The same key with
different content returns HTTP `409`.

A replay never:

- invokes an agent;
- acquires or releases a second reservation;
- starts a broker;
- repeats task mutations; or
- repeats a privileged action.

## Safety boundary

Phase 4.5 does not expose or invoke:

- arbitrary shell commands;
- root execution;
- service restarts;
- deployments;
- email;
- purchases;
- publication;
- external mutations;
- Guardian broker activation.

The existing synchronous bounded `/start` path is not converted into an unsafe
force-kill primitive. Cooperative mid-run cancellation can be added only in a
later milestone with a real cancellable worker/task runtime.

## Phase 4 lifecycle

The bounded lifecycle is now:

`delegated -> reserved -> running -> completed|failed`

with explicit side paths:

- `reserved -> cancelled`
- `running -> manual_review` through recovery
- `running -> completed|failed` through evidence-based recovery
- `manual_review -> completed` only with complete accepted evidence

No recovery transition calls the executor.
