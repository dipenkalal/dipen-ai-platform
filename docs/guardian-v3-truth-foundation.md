# Guardian v3 Truth Foundation

Status: design baseline

## Existing platform capabilities

The platform already contains:

- a static Agent Registry with seven registered agents
- enabled/disabled agent state
- capability, tool, category, model, and safety metadata
- agent execution and orchestration paths
- persisted completed run and orchestration history

Guardian v3 extends these existing systems rather than replacing them.

## Missing authoritative runtime truth

The current registry describes what an agent *is*, but not what it is doing now. Guardian needs distinct sources of truth for:

1. Agent definition
2. Runtime worker availability
3. Task assignment and lifecycle
4. Infrastructure correlation
5. Evidence freshness

## Phase 3.0A scope: read-only truth model

### Agent definition

Persistent identity and declared capabilities:

- id, name, version
- category and description
- capabilities and tools
- permissions and risk tier
- preferred provider/model
- enabled state

### Runtime state

Live, expiring worker observations:

- runtime id
- supported agent ids
- status: available, busy, degraded, offline
- current task id
- process/container/model identifiers when known
- CPU and memory observations when known
- heartbeat timestamp and expiry

### Task ledger

Durable task lifecycle:

- task id and owner
- original objective
- selected agent(s)
- selection reason
- status: created, planned, queued, assigned, running, waiting, completed, failed, cancelled, manual_review
- progress and current step
- timestamps
- artifacts, errors, validation state
- parent/dependency relationships

### Evidence contract

Every Guardian answer about agents or tasks must identify whether the claim is:

- registry fact
- live runtime observation
- task-ledger fact
- historical record
- inference
- unavailable

No process-name guessing may be presented as confirmed agent identity.

## Safety boundary

Phase 3.0A is read-only:

- no broker activation
- no privileged execution
- no arbitrary shell commands
- no automatic task assignment
- no service changes

Task submission and controlled delegation are deferred to Phase 3.1 after the truth model is tested.

## Initial acceptance questions

- How many agents are registered?
- How many are enabled?
- Which agents are available now?
- Which agents are busy or offline?
- What is each active agent doing?
- Which task is using a given model or runtime?
- When was this status last observed?
- Is this a live fact, registry fact, history, or inference?
