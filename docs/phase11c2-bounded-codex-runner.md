# Phase 11C.2 — Bounded Codex Runner

Status: implementation and CI complete; Acer disposable smoke pending.

## Purpose

Phase 11C.2 introduces the first DAP-owned subprocess boundary capable of invoking the locally installed Codex CLI. It does not grant Codex Git delivery, Guardian, merge, deployment, privileged host, or production-secret authority.

The runner is pinned to the Acer-observed CLI surface `codex-cli 0.146.0` and requires Linux `bubblewrap` before execution.

## Execution boundary

The runner materializes a tracked-file-only snapshot with `git archive` from an exact source commit. The snapshot is outside the live DAP checkout and contains no `.git` directory and no untracked production files.

Codex receives the following fixed policy:

- `exec`
- `--sandbox workspace-write`
- `--ephemeral`
- `--ignore-user-config`
- `--strict-config`
- `--ignore-rules`
- `--skip-git-repo-check`
- network disabled for workspace shell execution
- `/tmp` and `$TMPDIR` excluded from writable roots
- inherited shell environment set to none
- web search disabled
- automatic skill MCP dependency installation disabled
- feedback disabled
- approval policy `on-request`

The dangerous bypass flags, `danger-full-access`, extra writable directories, persistent sessions, MCP/plugin installation, and full Ruflo runtime are not admitted.

## DAP outer controls

DAP independently:

1. binds the execution ticket to the immutable Engineering Agent work-order hash;
2. limits mutation to the exact repository-relative allowlist;
3. limits runtime, output size, and number of changed files;
4. supplies only a reduced parent environment plus a dedicated Codex auth home;
5. snapshots every file before and after execution and computes changed paths itself;
6. rejects any path escape, Guardian mutation, Git metadata write, network/privilege observation, external repository write, or production-secret access observation;
7. produces a typed execution receipt with Git commit, PR, merge, and deployment flags fixed to false.

Codex sandboxing is defense-in-depth. DAP policy remains authoritative.

## Acer smoke

The smoke harness is `python -m engineering.codex_smoke` from `platform/backend` using the backend virtual environment. It requires the Phase 11 branch to be clean and creates a temporary workspace beneath `/home/dipen/dap/sandboxes`.

The synthetic task allows exactly one new disposable file:

`platform/backend/engineering/phase11c2_smoke_artifact.txt`

with exact content:

`PHASE11C_CODEX_SMOKE_OK\n`

The live repository is used only as the read source for `git archive`. The smoke removes its temporary workspace before returning and verifies that the source repository remains clean.

## Exit criteria

Phase 11C.2 is sealed only after the Acer smoke demonstrates:

- correct pinned Codex version;
- Bubblewrap present;
- disposition `succeeded`;
- exactly one allowlisted changed file;
- exact expected artifact content;
- no timeout;
- no Git commit or PR;
- no merge or deployment;
- disposable workspace removed;
- live source repository still clean.
