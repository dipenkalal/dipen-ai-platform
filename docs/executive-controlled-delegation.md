# Executive Office Controlled Delegation

## Purpose

Controlled delegation converts an Executive Office advisory plan into durable
parent and child task-ledger records without starting workers or activating the
Guardian broker.

The endpoint is:

- `POST /api/v1/executive-office/delegate`

## Safety boundary

A delegation request is evaluated in this order:

1. Recompute the advisory plan from the supplied objectives.
2. Reject prohibited work before any database mutation.
3. Require a matching affirmative `dipen-owner` approval record when the plan
   contains high-impact or external action.
4. Check the live Agent Truth state for every mapped worker.
5. Apply deterministic per-delegation capacity admission.
6. Write the parent task, child tasks, approval record, and idempotency result in
   one SQLite transaction.

The delegation endpoint:

- writes tasks only in `planned` or `assigned` state;
- does not invoke an agent executor;
- does not queue work to the broker;
- does not activate the broker service or socket;
- does not run a shell command;
- does not deploy, restart, email, purchase, publish, or mutate external state.

## Idempotency

Every request requires an idempotency key.

- Repeating the same key with the same request returns the stored delegation.
- Repeating the same key with different request content returns HTTP `409`.
- A successful replay does not duplicate tasks or approvals.

The request hash includes the advisory plan and approval identity, decision,
affirmation, and statement. The approval timestamp is excluded so transport
retries remain stable.

## Task model

A successful delegation writes:

- one parent `orchestration` task in `planned` state;
- one child `agent` task per admitted objective in `assigned` state;
- `parent_task_id` links from every child to the parent;
- `source_run_id` set to the deterministic delegation ID.

These records describe accountable work allocation only. `execution_started` and
`broker_activated` remain `false`.

## Approval records

Approval-required work needs an `OwnerApprovalRecord` with:

- a unique approval ID;
- the exact recomputed Executive Office decision ID;
- `approved_by` equal to `dipen-owner`;
- an affirmative approval value;
- a statement describing the bounded approved action.

Approval cannot override blocked policy terms.

## Worker admission

The service uses Agent Truth rather than static registry claims.

A mapped worker must be reported `available`. Busy, degraded, offline, disabled,
unreported, unmapped, or capacity-exhausted work is deferred with no task write.

The first release permits one admitted task per machine agent in one delegation.
This prevents an advisory plan from oversubscribing a worker while execution
scheduling remains a later phase.

## Persistence and rollback

Executive delegation metadata and approvals are stored alongside the existing
Agent Truth task ledger. `BEGIN IMMEDIATE` protects the write transaction.

Any parent-task, child-task, approval, or idempotency collision rolls back the
entire new delegation. Existing unrelated records remain unchanged.

## Next phase

A later phase may add explicit owner-triggered execution of already delegated
tasks. That phase must preserve:

- Guardian validation;
- broker isolation;
- concurrency and resource reservations;
- progress heartbeats;
- independent acceptance evidence;
- cancellation and recovery;
- no silent elevation from assignment to execution.
