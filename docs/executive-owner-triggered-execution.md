# Executive Office Owner-Triggered Execution

## Milestone purpose

Phase 4 converts an already persisted Executive Office delegation into a bounded,
explicitly owner-triggered execution request. It must reuse the platform's existing
agent executor, orchestration validator, Guardian reservation, authorization,
recovery, task-ledger, and runtime-heartbeat foundations.

Phase 4 does not create an unrestricted command runner and does not silently move
assigned work into execution.

## Dependency and stacked-development strategy

This work is developed on top of the exact Phase 3 controlled-delegation head:

- dependency PR: `#44`
- dependency head: `36857904f759a420ac472d616138fa213d2e8b2c`
- Phase 4 branch: `feat/executive-owner-triggered-execution`

Development, review, and local verification may continue while GitHub Actions is
unavailable. After PR #44 merges, the Phase 4 branch will be rebased or retargeted
to the resulting `main` commit before its own merge.

## Required API boundary

The first endpoint is expected to be:

- `POST /api/v1/executive-office/execute`

The request must identify:

- the existing delegation ID;
- the exact parent task ID;
- the child task IDs selected for this bounded execution;
- a unique execution idempotency key;
- an explicit `dipen-owner` execution authorization;
- whether the request is validation-only or execution-enabled.

A request must not accept arbitrary shell text, service names, filesystem paths,
URLs, purchase instructions, publication instructions, or unbounded external
actions.

## Execution admission rules

Execution admission must fail before mutation unless all of the following hold:

1. The delegation exists and its stored response matches the supplied task IDs.
2. The parent task remains `planned`.
3. Every selected child task remains `assigned`.
4. Every selected task belongs to the same delegation and parent.
5. The owner authorization is affirmative, single-purpose, and tied to the exact
   delegation and selected task set.
6. The mapped machine agents remain enabled and available in Agent Truth.
7. The orchestration validator accepts the bounded plan.
8. Resource and concurrency reservations can be acquired deterministically.
9. The execution idempotency key has not been reused for different content.
10. No selected objective crosses a prohibited policy boundary.

Stale, completed, failed, cancelled, manual-review, unknown, mismatched, or
already-running tasks must be rejected without starting any worker.

## Initial execution scope

The first Phase 4 release is intentionally narrow:

- owner-triggered only;
- delegated tasks only;
- low-risk internal agent work only;
- one active task per machine agent;
- bounded task count per request;
- existing on-demand backend agent executor only;
- no broker activation;
- no root command execution;
- no service restart;
- no deployment;
- no email, purchase, publication, or other external mutation;
- no automatic retry after an ambiguous failure.

Existing Guardian root-authorized service actions remain a separate privileged
control path and are not implicitly exposed through this endpoint.

## Durable execution record

Execution admission must atomically persist an execution record containing:

- execution ID;
- delegation ID;
- parent and child task IDs;
- authorization identity and statement;
- canonical request hash;
- selected machine agents;
- reservation identifiers;
- requested and admitted timestamps;
- current execution state;
- validation evidence;
- terminal outcome and acceptance evidence when available.

The execution state machine is:

`requested -> validated -> reserved -> running -> completed`

with bounded alternate terminal or intervention states:

- `rejected`
- `failed`
- `cancelled`
- `manual_review`

No transition may skip directly from `requested` to `running`.

## Task-ledger transitions

After successful admission and reservation:

- selected child tasks transition from `assigned` to `queued`;
- a child transitions from `queued` to `running` only immediately before its
  executor invocation;
- `started_at`, `current_step`, and progress are recorded;
- success transitions the child to `completed` with acceptance evidence;
- deterministic failure transitions the child to `failed`;
- ambiguous or authorization/recovery failure transitions it to `manual_review`;
- the parent remains `planned` while any child is pending;
- the parent becomes `completed` only when every delegated child is completed;
- mixed terminal child outcomes place the parent in `manual_review`.

Task updates and execution-state updates must be transactionally consistent.

## Runtime truth and heartbeats

Each running child must emit task-specific Agent Truth heartbeats with:

- machine agent ID;
- worker identity;
- current task ID;
- `busy` runtime state;
- progress/current-step details;
- observation timestamp.

A terminal transition must clear the task-specific busy state or publish an
available/degraded terminal heartbeat. Stale busy heartbeats must not be treated
as successful completion.

## Validation-only mode

A validation-only request must execute the complete admission path through policy,
identity, task matching, worker state, orchestration validation, and reservation
simulation, but must not:

- mutate task status;
- acquire a durable execution reservation;
- call an executor;
- start the broker;
- perform an external action.

The response must clearly report `execution_started=false`.

## Idempotency and replay

- Same key and same canonical request returns the stored execution response.
- Same key and different canonical request returns HTTP `409`.
- A replay must be resolved before worker availability is checked again.
- A terminal execution must never run again through transport retry.
- An ambiguous interrupted execution must require recovery or manual review, not
  automatic replay.

## Cancellation and recovery

Cancellation is accepted only for `requested`, `validated`, `reserved`, `queued`,
or cooperatively cancellable `running` work.

Recovery must reconcile:

- execution record state;
- task-ledger state;
- latest agent heartbeat;
- orchestration history;
- reservation ownership;
- available acceptance evidence.

Recovery may finalize an objectively completed task, fail a deterministically
failed task, or move uncertainty to `manual_review`. It must not repeat an action
merely because the API response was lost.

## Acceptance evidence

A child task is not complete merely because an executor returned without raising.
Completion requires bounded evidence such as:

- validated structured agent result;
- expected artifact or stored output identifier;
- orchestration validation result;
- task-specific runtime timeline;
- independent postcondition check where the task definition requires one.

The API response must distinguish execution output from acceptance evidence.

## Implementation slices

### Phase 4.1 — Admission foundation

- execution schemas and endpoint;
- delegation/task matching;
- explicit owner execution authorization;
- policy and worker revalidation;
- validation-only response;
- idempotency conflicts;
- no executor invocation.

### Phase 4.2 — Atomic reservation and task transition

- durable execution repository;
- deterministic resource reservation;
- atomic execution record plus `assigned -> queued` transitions;
- replay-safe state machine.

### Phase 4.3 — Bounded agent execution

- invoke existing on-demand agent executor for allowed internal tasks;
- `queued -> running -> terminal` transitions;
- task-specific heartbeats and progress;
- preserve broker isolation.

### Phase 4.4 — Evidence and parent reconciliation

- acceptance-evidence validation;
- parent completion/manual-review reconciliation;
- query endpoint for execution status and evidence.

### Phase 4.5 — Cancellation and recovery

- cooperative cancellation;
- interrupted-run recovery;
- ambiguous outcome to manual review;
- tests proving actions are not silently replayed.

## Required tests

Tests must cover at least:

- successful validation-only admission;
- unknown delegation, parent, or child task;
- mismatched task ownership;
- stale task status;
- missing, false, wrong-owner, or mismatched authorization;
- unavailable, busy, disabled, or degraded worker;
- policy rejection;
- idempotent replay and idempotency conflict;
- reservation collision and transaction rollback;
- executor never called during rejected or validation-only requests;
- exact task state transitions during success and failure;
- heartbeat/progress evidence;
- parent completion and manual-review reconciliation;
- cancellation boundaries;
- interrupted execution recovery without duplicate execution;
- broker remains inactive unless a later separately approved milestone changes the
  architecture.

## Production boundary

Phase 4 development does not alter production. Deployment requires:

1. PR #44 merged and deployed successfully.
2. Phase 4 rebased onto the deployed source commit.
3. Complete backend and Guardian test evidence.
4. A database snapshot and rollback plan.
5. A validation-only production acceptance test before any real executor call.
6. Explicit owner approval for the first bounded production execution test.
