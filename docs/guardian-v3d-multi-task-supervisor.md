# Guardian v3.0D — Multi-Task Supervisor

## Problem

Guardian v3.0C correctly delegates one cognitive objective to one agent, but it does not yet distinguish between:

1. a hypothetical planning question such as “What would Guardian do if I assigned two tasks?”; and
2. a real multi-task command containing several independent objectives.

As a result, a hypothetical question can be executed, and multiple objectives can be sent as one prompt to a single worker.

## Required behaviour

### Hypothetical planning questions

Questions framed as “what would Guardian do”, “how would Guardian handle”, “suppose I assigned”, or equivalent planning language must not execute any task.

Guardian must answer with the proposed plan, including:

- detected child objectives;
- intended agent or evidence path for each child;
- whether each child can currently be completed;
- required evidence and unavailable evidence;
- safety or approval boundaries.

No backend agent run, task-ledger write, privileged action, or broker call is allowed for a planning-only question.

### Real multi-task commands

A real command containing two or more explicit objectives must create one parent supervisor task and one child task per objective.

Each child must be independently classified and routed:

- code generation and debugging → Coding Agent;
- research and comparisons → Research Agent;
- documentation and reports → Documentation Agent;
- infrastructure analysis → DevOps Agent;
- current machine state → System Agent or direct truth path;
- current agent/task state → Guardian truth path;
- privileged operations → approval-controlled action path;
- unsupported evidence requests → unavailable, never guessed.

Guardian must not send the entire mixed request to a single worker.

### Project-progress requests

“Dipen AI Platform progress” must be evidence-backed. Agent runtime truth alone is insufficient to reconstruct the complete project history.

The response must distinguish:

- deployed commit and service state;
- fleet and task-ledger state;
- repository milestones or project-status records;
- unavailable historical evidence.

A worker may format or summarize verified project evidence, but it may not invent project progress from model memory.

## Result aggregation

Guardian must return a structured supervisor result containing:

- parent task identifier;
- one section per child objective;
- assigned agent or truth source;
- child task/run identifiers when executed;
- completed, failed, unavailable, or approval-required status;
- verified output for each child;
- partial-failure reporting without hiding successful children.

## Safety boundaries

- Hypothetical questions are read-only.
- Cognitive work uses bounded agent APIs.
- Privileged operations remain separate and approval-controlled.
- No arbitrary shell execution.
- No broker activation.
- A child failure must not trigger Guardian to perform that child itself.
- Missing evidence must remain unavailable.

## Acceptance scenario

Input:

> What would Guardian do if I assigned two tasks: 1. write complex code in C; 2. tell me the entire progress of the Dipen AI Platform?

Expected:

- classified as a planning-only question;
- no task or agent run created;
- proposed child 1 routes to Coding Agent;
- proposed child 2 routes to the project-progress evidence path;
- Guardian states that full project history requires repository/project-status evidence and must not be improvised;
- no generic Coding Agent disclaimer is returned.

A later imperative version of the same request must create one parent task and two separately tracked child outcomes.
