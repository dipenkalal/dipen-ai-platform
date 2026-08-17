# Phase 11B — Engineering Agent Service

Status: **CODE COMPLETE — CI VALIDATION IN PROGRESS**

## Purpose

Introduce a dedicated DAP `engineering-agent` identity and a deterministic work-order service without enabling repository mutation or Codex execution.

The existing `coding-agent` remains an advisory model agent. Phase 11 does not silently turn that general chat/coding helper into a repository-changing worker.

## New identity

`engineering-agent` is registered as a coding-category DAP agent with no tools. Its current capabilities are limited to:

- bounded engineering work-order preparation;
- repository change planning;
- test and verification planning;
- owner-reviewed delivery preparation.

No executable tool is attached in 11B.

## Work-order source authority

`EngineeringAgentService.prepare()` accepts only:

1. a canonical `TaskLedgerRecord` child task;
2. a matching `ExecutiveExecutionResponse` whose admission is validated by DAP;
3. a DAP-owned `EngineeringWorkScope`.

The task must remain `assigned`, belong to the same delegation and parent task as the admission, and be selected for the `engineering-agent` only.

The admission must remain validation-only and must not already contain reservation, execution, broker, or task-ledger side effects.

## Repository scope

Allowed paths must be repository-relative POSIX paths. Absolute paths, parent traversal, Windows drive paths, duplicate paths, dot segments, and empty path segments are rejected.

The following sensitive regions are denied by default:

- `.git`;
- `.github/workflows`;
- `platform/backend/guardian`.

A future owner-approved policy may define a separate controlled path for sensitive engineering, but the ordinary Engineering Agent will not receive those paths implicitly.

## Work-order authority

Every 11B `EngineeringWorkOrder` is immutable and explicitly records:

```text
validation_only=true
owner_review_required=true
execution_authority_granted=false
repository_mutation_allowed=false
git_write_allowed=false
codex_execution_allowed=false
network_access_allowed=false
privileged_access_allowed=false
main_merge_allowed=false
deployment_allowed=false
```

The work-order ID and canonical SHA-256 are deterministic from the canonical task, Executive Office admission, and DAP scope.

## Routing activation intentionally deferred

The company `software-engineer` role is **not remapped to `engineering-agent` in 11B**. This prevents Executive Office from treating the Engineering Agent as an active repository-changing worker before Phase 11C has proven the controlled executor.

The activation sequence is therefore:

```text
11B identity + work-order contract
        ↓
11C controlled executor proven safe
        ↓
11D Guardian execution admission proven
        ↓
explicit software-engineer → engineering-agent routing activation
```

This sequencing prevents a partially implemented Engineering Agent from being admitted as if execution were already safe.
