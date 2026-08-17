# Phase 11G — Dashboard Engineering Workspace

## Status

**IMPLEMENTATION + CI COMPLETE / ACER DISPOSABLE RUNTIME SMOKE PENDING.**

Phase 11G now exposes Engineering Agent work as a read-only DAP projection over canonical task truth plus immutable Phase 11F evidence. The dashboard does not gain execution, Guardian, merge, release, deployment, or task-authority capabilities.

## Governing rule

> The dashboard observes engineering authority; it does not create engineering authority.

Canonical `task_ledger` status remains authoritative. Engineering audit evidence enriches the owner view but never overwrites task truth. If terminal evidence disagrees with canonical task lifecycle state, the workspace reports `requires_reconciliation` instead of silently resolving the conflict.

## Backend read model

`platform/backend/engineering/engineering_workspace.py` provides a read-only projection with four owner-facing workspace states:

- `queued`
- `active`
- `completed`
- `failed`

Canonical task status maps into those states. Only canonical `agent` tasks assigned to `engineering-agent` are exposed.

Evidence provenance is reported as:

- `evidence_unavailable`
- `consistent`
- `requires_reconciliation`

The projection checks whether `engineering_audit_evidence` already exists and reads it when available. A GET request does not instantiate the Phase 11F persistence repository and therefore does not create the audit table as a side effect.

Every workspace response preserves hard false authority flags:

- `ui_execution_authority=false`
- `ui_guardian_authority=false`
- `ui_merge_authority=false`
- `ui_deployment_authority=false`
- `execution_controls_exposed=false`

The top-level projection reports `read_only=true`.

## API surface

`platform/backend/engineering/routes.py` exposes only:

- `GET /api/v1/engineering/workspace`
- `GET /api/v1/engineering/workspace/{task_id}`

POST, PUT, PATCH, and DELETE are not registered and return HTTP 405. Unknown or non-engineering task IDs return 404.

The router is registered in `platform/backend/app.py` without adding an execution service or mutation endpoint.

## Dashboard surface

Phase 11G adds:

- `apps/dashboard/src/app/engineering/types.ts`
- `apps/dashboard/src/app/engineering/api.ts`
- `apps/dashboard/src/app/api/engineering/workspace/route.ts`
- `apps/dashboard/src/app/engineering/page.tsx`
- an `Engineering` entry in `AppNavigation.tsx`

The dashboard page exposes:

- queued/active/completed/failed summary counts;
- reconciliation count;
- canonical task objective, status, progress, timestamps, delegation and parent provenance;
- evidence count and evidence ID;
- executor runtime identity;
- Guardian risk class;
- allowed/changed files;
- exact diff SHA-256 when available;
- lint/type-check/compile/test/CI/policy check results;
- policy decisions and authority source;
- work-order ID;
- commit SHA and delivery branch;
- draft pull-request metadata and owner-review requirement;
- explicit failure or cancellation information.

The only interactive action on the page is **Refresh**. There is no Run, Approve, Guardian, Merge, Release, Deploy, Retry, Cancel, or authority-escalation control.

## Dashboard proxy

`GET /api/engineering/workspace` proxies only the backend GET endpoint with `cache: no-store`. No dashboard mutation proxy exists.

## Test coverage

`platform/backend/tests/test_engineering_workspace.py` proves:

- only engineering-agent tasks are projected;
- canonical task state drives workspace state;
- terminal evidence enriches without changing task truth;
- inconsistent evidence is flagged for reconciliation;
- UI authority flags remain false;
- unknown/non-engineering tasks are not exposed.

`platform/backend/tests/test_engineering_routes.py` proves:

- list and detail GET routes work;
- POST/PUT/PATCH/DELETE return 405;
- missing tasks return 404.

The dedicated Phase 11 workflow now includes a separate dashboard job with `npm ci`, lint, and production build.

## Disposable Acer runtime smoke

`platform/backend/engineering/engineering_workspace_smoke.py` is the host validation entrypoint.

It is intentionally not a deployment script. It:

1. requires the Phase 11 branch and a clean source tree;
2. opens the production Agent Truth database using SQLite URI `mode=ro`;
3. records production task-ledger and engineering-audit row counts;
4. copies Agent Truth into a disposable sandbox through SQLite backup;
5. starts an ephemeral backend on `127.0.0.1:8112` against only that copied database;
6. explicitly disables Telegram polling, notifications, and approvals in the preview process;
7. verifies the Engineering workspace GET contract;
8. verifies POST/PUT/PATCH/DELETE all return 405;
9. builds the current dashboard source;
10. starts an ephemeral dashboard on `127.0.0.1:3112` pointing only to the ephemeral backend;
11. verifies `/engineering` renders the read-only shell;
12. verifies the dashboard GET proxy preserves the read-only flags;
13. re-reads the production DB through read-only mode and requires row counts to be unchanged;
14. requires the Git worktree to remain clean;
15. terminates both preview processes and deletes the sandbox in `finally` cleanup.

The smoke does **not** restart live systemd services, use Docker, contact Guardian, enable Telegram, create a canonical task, create an engineering audit row, merge code, or deploy the dashboard.

## CI seal before Acer runtime smoke

Validated application head:

`54e2d69ea3b2d9806858bef82a949d5dd81c7b4c`

At that head the dedicated Phase 11 gate passed:

- backend Ruff: pass;
- backend mypy: pass;
- backend compile: pass;
- Phase 11 engineering tests: pass;
- Guardian boundary: pass;
- dashboard lint: pass;
- dashboard production build: pass.

The ordinary repository CI and Owner Channel checks also passed on that implementation slice.

The disposable preview-smoke helper was subsequently added and lint-gated. Ruff first identified one `SIM117` style defect in the helper before Acer execution. That helper-only defect was corrected. Corrected smoke-helper head:

`5d0f80739a9278e6bb8df63987a147e616cb9727`

At the corrected head:

- Phase 11 backend Engineering gate: success;
- Phase 11 Guardian boundary: success;
- Phase 11 dashboard lint/build: success;
- Phase 10 Ruflo regression: success;
- Phase 7 Owner Channel: success;
- repository CI Guardian/backend/dashboard jobs: success.

## Exit state

Code and CI requirements for 11G are satisfied. The remaining gate is the disposable Acer runtime smoke proving the read-only API/proxy/rendering path against a temporary copy of the real Agent Truth database while leaving production counts and services unchanged.

11G must not be marked **COMPLETE / SEALED** until that runtime receipt is captured.
