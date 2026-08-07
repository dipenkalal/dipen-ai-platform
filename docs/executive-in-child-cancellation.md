# Executive Office In-Child Cooperative Cancellation

## Phase 6 purpose

Phase 5 safely stops launching additional child tasks after a running-cancellation
request is observed. Phase 6 narrows the cancellation latency further by allowing
a bounded child agent to observe the same durable cancellation intent at safe
internal execution boundaries.

This milestone remains cooperative. It does not kill an asyncio task, process,
PID, container, model server, HTTP request, or tool process.

## Phase 6.1 — cancellation probe transport

The first slice introduces a typed cancellation probe that can flow through:

`ExecutiveExistingTaskRunner -> InstrumentedAgentExecutor -> AgentExecutor`

The probe is optional. Existing agent API execution continues unchanged when no
probe is supplied.

The raw executor checks the probe only at explicit safe boundaries. A tripped
probe raises a dedicated cooperative-cancellation exception rather than a generic
runtime failure. Runtime instrumentation records that outcome as `cancelled` and
preserves normal heartbeat cleanup.

Phase 6.1 does not yet connect the probe to Executive Office durable cancellation
state. That connection belongs to the next slice after the transport contract is
validated independently.

## Planned safe boundaries

Later Phase 6 slices may check cancellation:

- before planning;
- before dispatching the selected agent handler;
- before starting a tool call;
- after a tool call returns and before model generation;
- before a model/gateway request;
- after a model/gateway response before further bounded work.

A currently blocking external operation is never force-terminated by this design.
Cancellation becomes effective at the next boundary controlled by DAP.

## Safety boundary

Phase 6 must not:

- use `Task.cancel()` as an owner-facing kill primitive;
- send OS signals;
- terminate containers;
- kill model-server requests;
- introduce shell or root execution;
- activate the Guardian broker;
- replay uncertain work;
- mark a task cancelled before the runtime has actually observed the probe.

## Stack

- dependency PR: #46
- dependency head: `845cd0da9dc3cb8a5afa36f9717aab5fc0f93d9c`
- Phase 6 branch: `feat/executive-in-child-cancellation`

Production remains unchanged.
