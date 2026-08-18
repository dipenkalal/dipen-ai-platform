# Phase 11C — Controlled Codex Executor

Status: **11C.1 CONTRACT IMPLEMENTED — LIVE RUNNER PENDING**

## Principle

Codex is an executor inside a DAP-owned boundary. Codex does not receive authority to decide its own filesystem scope, network access, Git delivery, privileged access, or deployment.

The executor uses layered controls:

1. canonical Executive Office task/admission;
2. immutable Engineering Agent work order;
3. DAP-issued Codex execution ticket;
4. disposable workspace/worktree;
5. Codex workspace sandbox;
6. DAP post-run observation and diff validation;
7. later Git-delivery and Guardian gates.

## 11C.1 execution ticket

A `CodexExecutionTicket` authorizes only one narrow capability expansion from the non-executing 11B work order:

```text
workspace_file_write_allowed=true
codex_execution_allowed=true
shell_execution_inside_sandbox_allowed=true
```

Everything outside the disposable workspace remains denied:

```text
network_access_allowed=false
privileged_access_allowed=false
git_metadata_write_allowed=false
external_repository_write_allowed=false
guardian_access_allowed=false
production_secret_access_allowed=false
main_merge_allowed=false
deployment_allowed=false
owner_review_required=true
```

The default limits are:

- timeout: 600 seconds;
- maximum changed files: 20;
- maximum captured output: 1 MiB.

Limits are bounded by the contract and cannot be expanded beyond the Phase 11 ceilings without changing DAP code and tests.

## Post-run validation

The executor harness must report observable facts to `CodexExecutionValidator`, including:

- process exit code;
- changed repository files;
- captured output size;
- whether a subprocess actually started;
- network attempts;
- privileged-access attempts;
- `.git`/Git metadata mutation;
- external-repository mutation;
- Guardian access attempts;
- production-secret access attempts.

Any prohibited observation produces a rejected receipt and blocks Git delivery even when Codex exits successfully.

A non-zero Codex exit without a policy violation is recorded as `failed`, not `rejected`.

Only a zero-exit observation with no policy violations is marked `succeeded`, and that status means only **eligible for the later Git-delivery gate**. It does not create a commit or PR by itself.

## Why the actual subprocess runner is deferred

The DAP Acer has an already-installed Codex CLI whose exact `exec` option surface must be verified before the runner hard-codes arguments. Phase 11 will not guess version-specific CLI flags or inherit the Phase 10 upstream-generated unsafe configuration.

Before implementing the live runner, DAP will capture read-only local evidence for:

```text
codex --version
codex exec --help
```

The runner will then pin the accepted executable/version behavior and use a DAP-rendered, isolated configuration rather than an upstream Ruflo config.

## Live runner requirements

The future `SubprocessCodexRunner` must:

- use `shell=False` / fixed argv construction;
- use a dedicated disposable workspace;
- use a sanitized environment;
- avoid normal user MCP/plugin configuration;
- disable network in the workspace sandbox;
- avoid production DAP secrets/config/data;
- enforce timeout and captured-output limits;
- inspect repository state independently after Codex exits;
- reject any changed path not listed in the ticket;
- never perform `git commit`, `git push`, PR creation, merge, tag, release, deployment, systemd, Docker, or Guardian operations.

Those actions, where allowed at all, belong to later DAP-owned gates.
