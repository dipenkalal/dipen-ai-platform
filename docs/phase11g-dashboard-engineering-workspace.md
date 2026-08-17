# Phase 11G — Dashboard Engineering Workspace

## Status

**COMPLETE / SEALED.**

Phase 11G exposes Engineering Agent work as a read-only DAP projection over canonical task truth plus immutable Phase 11F evidence. The dashboard does not gain execution, Guardian, merge, release, deployment, or task-authority capabilities.

## Governing rule

> The dashboard observes engineering authority; it does not create engineering authority.

Canonical `task_ledger` status remains authoritative. Engineering audit evidence enriches the owner view but never overwrites task truth. If terminal evidence disagrees with canonical task lifecycle state, the workspace reports `requires_reconciliation` instead of silently resolving the conflict.

## Backend and API boundary

`platform/backend/engineering/engineering_workspace.py` projects only canonical `agent` tasks assigned to `engineering-agent` into `queued`, `active`, `completed`, or `failed` owner-facing states. Evidence provenance is reported as `evidence_unavailable`, `consistent`, or `requires_reconciliation`.

Every response preserves hard false authority flags:

- `ui_execution_authority=false`
- `ui_guardian_authority=false`
- `ui_merge_authority=false`
- `ui_deployment_authority=false`
- `execution_controls_exposed=false`
- `read_only=true`

The backend exposes only:

- `GET /api/v1/engineering/workspace`
- `GET /api/v1/engineering/workspace/{task_id}`

POST, PUT, PATCH, and DELETE are not registered and return HTTP 405.

## Dashboard surface

Phase 11G adds the `/engineering` workspace and a read-only GET proxy. The owner can inspect summary counts, task/admission provenance, evidence IDs/hashes, executor runtime, Guardian risk class, allowed and changed files, diff SHA-256, check results, policy state, commit/draft-PR metadata, and failure/cancellation information.

The only interactive action is **Refresh**. There is no Run, Approve, Guardian, Merge, Release, Deploy, Retry, Cancel, or authority-escalation control.

## CI validation

The implementation and runtime helper slices passed the dedicated Phase 11 backend/Guardian/dashboard jobs plus repository CI, Phase 10 regression, and Owner Channel checks.

The final no-npm runtime head was:

`e783175f19cbb7cc3eafe95e73de8bb56385495c`

At that head the dedicated `Phase 11G Dashboard Runtime Artifact` workflow also passed:

- bundle-smoke helper Ruff: pass;
- bundle-smoke helper mypy: pass;
- bundle-smoke helper compile: pass;
- dashboard dependency install in GitHub CI: pass;
- dashboard lint: pass;
- Next.js standalone production build: pass;
- standalone runtime packaging: pass;
- artifact upload: pass.

GitHub artifact run: `32076950188`.

Artifact ID: `9303786086`.

Artifact name: `phase11g-dashboard-standalone`.

GitHub artifact archive digest:

`sha256:65145f137ae5bddaa31c83af24dc7d18d40762b1db2eb70b483788b396b44bb7`

The artifact manifest binds the standalone dashboard to the same Phase 11 source commit. The artifact was independently downloaded and its outer GitHub digest, inner tarball SHA-256, manifest, `server.js`, static assets, public assets, and standalone runtime were inspected before Acer execution. It was also started successfully under Node 22 with a mock read-only backend before the host gate.

## Acer runtime history

Two earlier disposable-preview attempts proved the backend/read-only API boundary but failed while installing dashboard dependencies because the Acer experienced npm registry `ERR_SOCKET_TIMEOUT`. Those failures did not mutate production data or services.

The final gate therefore removed npm-registry access from the Acer entirely. GitHub CI built the already-linted standalone dashboard and the Acer downloaded that immutable workflow artifact with `gh run download`.

## Final Acer receipt

The final no-npm runtime smoke completed successfully against the real Agent Truth database through SQLite read-only backup semantics:

```text
source_commit|e783175f19cbb7cc3eafe95e73de8bb56385495c
artifact_source_commit|e783175f19cbb7cc3eafe95e73de8bb56385495c
artifact_schema|phase11g-dashboard-standalone-v1
artifact_node_version|v24.19.0
artifact_next_version|16.2.11
artifact_sha256|5ca01fe9a0f1714609aa59a97e887ae482acb507a8d384c35926c85ffddf4910
task_ledger_before|11
task_ledger_after|11
engineering_audit_before|0
engineering_audit_after|0
workspace_get|200
workspace_read_only|true
execution_controls_exposed|false
workspace_post|405
workspace_put|405
workspace_patch|405
workspace_delete|405
dashboard_engineering|200
dashboard_proxy|200
npm_registry_used_on_acer|false
production_db_mutated|false
live_services_restarted|false
docker_used|false
guardian_contacted|false
telegram_enabled|false
smoke_disposition|succeeded
smoke_exit|0
status|clean
artifact_residue|NONE
sandbox_residue|NONE
guardian|inactive
telegram|DAP_TELEGRAM_APPROVALS_ENABLED=false
```

## Exit state

Phase 11G exit criteria are satisfied:

- owner can inspect Engineering Agent work from DAP;
- canonical task truth remains authoritative;
- immutable engineering evidence is observable without becoming authority;
- API and dashboard are read-only;
- production Agent Truth row counts remain unchanged by observation;
- no live services were restarted;
- no Docker or Guardian authority was used;
- Telegram approvals stayed disabled;
- the host gate required no npm registry access;
- all disposable runtime/artifact directories were removed.

**Phase 11G is sealed.**
