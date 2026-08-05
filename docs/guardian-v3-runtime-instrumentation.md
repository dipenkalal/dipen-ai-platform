# Guardian v3.0B Runtime Instrumentation

Status: implementation slice

## Purpose

Guardian v3.0A added the authoritative registry, heartbeat store, durable task ledger, and read-only truth APIs. Phase v3.0B connects those stores to the execution paths that already run agents and orchestrations.

The goal is to make runtime answers evidence-based:

- which agent is active
- which task it is handling
- which model is in use
- whether the worker is busy or available
- when the observation was refreshed
- whether a task completed, failed, or was cancelled

## Instrumented paths

### Direct agent execution

Both synchronous and streamed agent requests use the same instrumented executor wrapper.

Lifecycle writes:

1. `created`
2. `assigned`
3. `running`
4. `completed`, `failed`, or `cancelled`

The final ledger record links to the existing agent `run_id`.

### Orchestration execution

Each orchestration creates a parent ledger task assigned to the selected agents.

Each child orchestration task:

- uses its orchestration task objective
- records the assigned agent
- links to the parent ledger task
- links to the child agent `run_id`
- follows the same lifecycle as a direct agent run

The parent record links to the final `orchestration_run_id`.

## Runtime heartbeat contract

The backend process reports:

- worker id
- process id
- agent id
- busy or available status
- selected current task
- active task count
- active task ids
- model used by the selected active task
- observation timestamp

Busy heartbeats refresh every 30 seconds while work remains active. The refresh interval is shorter than the 90-second truth TTL, preventing a legitimate long-running task from being classified as offline.

When concurrent work uses the same agent in the same backend process, the coordinator keeps the agent busy until the final active task ends. The heartbeat details report the complete active-task count and ids, while `current_task_id` identifies the most recently started active task.

## Failure isolation

Runtime instrumentation is observability, not execution authority.

A task-ledger or heartbeat write failure:

- is logged
- does not alter the agent answer
- does not activate the broker
- does not invoke shell commands
- does not grant Guardian a mutation endpoint

The original execution exception is preserved and re-raised after a failed task record is attempted.

## Evidence boundaries

The instrumentation reports only data observed inside the backend process.

- Process id comes from the running backend process.
- Container id is reported only when `DAP_RUNTIME_CONTAINER_ID` is explicitly configured.
- Model comes from the resolved request.
- Agent identity comes from the authoritative registry-selected request.
- Task relationships come from the orchestration plan and runtime-created ledger ids.

No process-name or container-name guessing is used.

## Current-state limitation

The v3.0A task ledger stores the latest durable state for each task. v3.0B performs each lifecycle transition as a real upsert, but it does not yet expose an immutable event-history endpoint.

An append-only task event log can be added in a later audit phase without changing the runtime contract introduced here.

## Safety boundary

This phase does not add:

- public heartbeat writes
- public task mutation
- automatic Guardian delegation
- broker activation
- privileged execution
- arbitrary commands
- production deployment by CI

Deployment remains a separate guarded backend restart.
