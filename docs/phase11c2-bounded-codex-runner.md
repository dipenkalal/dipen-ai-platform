# Phase 11C.2 — Bounded Codex Runner

Status: COMPLETE and sealed by CI plus Acer disposable smoke.

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

## Acer smoke evidence

The first live bounded smoke ran on the Phase 11 branch at source commit:

`80093b824d106a89f53024f88691e76cb2eda0aa`

Observed platform prerequisites:

- Codex `/home/dipen/.local/bin/codex` — `codex-cli 0.146.0`;
- Bubblewrap `/usr/bin/bwrap` — `bubblewrap 0.11.1`.

The synthetic task allowed exactly one new disposable file:

`platform/backend/engineering/phase11c2_smoke_artifact.txt`

with exact content:

`PHASE11C_CODEX_SMOKE_OK\n`

Observed result:

- disposition `succeeded`;
- delivery allowed true;
- exit code `0`;
- no timeout;
- exactly the allowlisted file changed;
- exact artifact content matched;
- no Git commit created;
- no pull request created;
- no main merge performed;
- no deployment performed;
- disposable workspace removed;
- no residual Codex process;
- live source repository remained clean;
- Guardian remained inactive;
- Telegram approvals remained false.

## Phase 11D evolution

After 11C sealed, Phase 11D added an additional required `EngineeringGuardianAdmission` before this runner can start. That later admission does not contact Guardian for ordinary non-privileged engineering work; it proves that the execution remains below the privileged boundary. See `docs/phase11d-guardian-execution-admission.md`.
