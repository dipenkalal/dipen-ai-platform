# Guardian v3.0D — Multi-Task Company Supervisor Contract

## Purpose

Guardian v3.0D introduces a company operating model before adding further multi-agent execution.

The authoritative organization design is defined in:

- `docs/dap-company-roles-and-hierarchy.md`

Guardian is the Chief Executive Supervisor. Guardian is not a general worker.

## Chain of command

```text
Dipen (Owner)
  -> Guardian (Chief Executive Supervisor)
    -> Department Head / Manager
      -> Specialist Agent
        -> Approved Tool or Executor
```

## Problem exposed in production

Guardian received the hypothetical question:

> What would Guardian do if I assigned two tasks: write complex C code and report the entire Dipen AI Platform progress?

The platform incorrectly:

1. executed a hypothetical question;
2. treated two unrelated objectives as one task;
3. assigned the combined objective to Coding Agent;
4. allowed Coding Agent to answer a project-progress question without authoritative project evidence.

## Mandatory v3.0D behavior

### Hypothetical planning

Questions such as these must never execute work:

- What would you do if…
- How would Guardian handle…
- Suppose I assigned…
- What plan would you make…

Guardian must explain the proposed organization, departments, child assignments, dependencies, evidence requirements, approval gates, and expected result structure.

No agent run, task-ledger mutation, tool call, or privileged action is permitted for a hypothetical plan.

### Real multi-task assignments

A real multi-task request must create:

- one parent supervisor objective;
- one child objective per independent deliverable;
- one accountable department per child;
- one independently routed specialist per child;
- separate task, run, evidence, and status records;
- one aggregated executive answer.

Unrelated objectives must never be sent to one worker merely because one keyword scores highest.

### Company progress reporting

A request for Dipen AI Platform progress must be owned by Product and Program Management, supported by the Repository and Project Evidence role.

The report may use only approved evidence such as:

- Git commits and merged pull requests;
- deployed commit and image identifiers;
- accepted phase milestones;
- task-ledger and orchestration history;
- runtime/service health;
- rollback and deployment records.

When repository or project-history evidence is unavailable, Guardian must say that the full progress report is unavailable. A Coding Agent, System Agent, or generic language model must not improvise it.

## Initial implementation slice

v3.0D will implement only:

1. Guardian as executive supervisor;
2. deterministic Chief of Staff planning;
3. hypothetical-plan detection;
4. explicit multi-task parsing;
5. parent and child ledger relationships;
6. separate routing and execution per child;
7. evidence-backed project-progress reporting;
8. partial-success, blocked, and failed child outcomes;
9. executive result aggregation.

## Safety boundaries

- Privileged actions remain approval-controlled.
- Guardian cannot approve its own privileged action.
- Specialist agents cannot broaden their own role or tool access.
- Tools remain fixed, bounded, and auditable.
- The Guardian broker remains inactive by default.
- No unrestricted shell execution is included.
- Missing evidence is reported as unavailable, never inferred.

## Acceptance scenarios

### Scenario A — hypothetical two-task question

Input:

> What would Guardian do if I assigned two tasks: write complex C code and report the entire Dipen AI Platform progress?

Expected:

- no execution;
- no ledger mutation;
- a two-child plan;
- Engineering/Coding ownership for the code;
- Product/Program plus Repository Evidence ownership for progress;
- explicit evidence requirements and unavailable-source handling.

### Scenario B — real two-task assignment

Input:

> Perform two tasks: 1. Write a complex C program for X. 2. Report the current Dipen AI Platform progress.

Expected:

- one parent task;
- separate child tasks;
- Coding Agent receives only the coding objective;
- project-progress path receives only the reporting objective;
- separate statuses and evidence;
- Guardian returns an executive summary with each child outcome.

### Scenario C — partial evidence

When coding succeeds but repository evidence is unavailable:

- coding child is completed;
- progress child is blocked or partial;
- Guardian does not mark the parent fully completed;
- Guardian explains exactly what evidence is missing.

### Scenario D — privileged child mixed with cognitive work

When one child requests code and another requests production deployment:

- coding may proceed through normal delegation;
- deployment remains pending approval;
- Guardian must not treat owner approval for one child as approval for all children.
