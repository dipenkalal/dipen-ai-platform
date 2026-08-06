# Executive Office Foundation

## Purpose

The Executive Office Foundation adds a deterministic, non-executing management layer between Guardian and specialist workers.

It solves the first coordination problem: one user request may contain multiple independent objectives, and each objective must become a bounded work item rather than being sent blindly to one specialist.

## Current capabilities

The service exposes:

- `GET /api/v1/executive-office/status`
- `POST /api/v1/executive-office/plan`

A plan response contains four distinct evidence sections:

1. **Chief of Staff** — decomposes explicit objectives into bounded tasks and suggests registered specialist roles.
2. **Risk and Policy** — classifies low, high, approval-required, and blocked work.
3. **Project Management** — creates work items, assignments, execution mode, and acceptance evidence.
4. **Audit and Compliance** — records the advisory decision and immutable safety claims.

## Truthful runtime semantics

The Executive Office acts in `deterministic_advisory` mode.

The registry roles remain planned roles. The API does not claim that Chief of Staff, Risk Officer, Project Manager, or Audit Officer are active runtime employees.

## Safety boundary

The foundation:

- does not start agents;
- does not write to the task ledger;
- does not activate the broker;
- does not run shell commands;
- does not deploy or restart services;
- does not perform email, calendar, purchasing, payment, or other external mutations;
- never treats a generated plan as approval to execute.

The plan endpoint is computational only. Any later delegation endpoint must preserve owner approval, policy, evidence, concurrency, and capacity controls.

## Next phase

A later PR may add controlled delegation that converts an approved advisory plan into parent and child task-ledger records. That phase must include idempotency, resource admission control, explicit approval records, specialist availability checks, independent verification, and rollback-safe execution boundaries.
