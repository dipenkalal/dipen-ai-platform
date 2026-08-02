# Contributing to Dipen AI Platform

DAP uses a pull-request workflow so that `main` stays stable and the running homelab services are not disturbed unnecessarily.

## Start from an updated `main`

```bash
cd ~/dap/source/dipen-ai-platform
git switch main
git fetch origin
git pull --ff-only origin main
git switch -c feature/describe-the-change
```

Use focused branch names such as `feature/...`, `fix/...`, `chore/...`, or `docs/...`. Do not commit directly to `main`.

## Check the running platform

```bash
./scripts/check-dev-health.sh
```

The backend API, backend monitoring, dashboard, execution history, and monitoring page should all return HTTP 200.

## Backend validation

```bash
cd platform/backend

.venv/bin/ruff check \
  agents/orchestration/validator.py \
  tests/test_orchestration_validator.py

.venv/bin/mypy \
  agents/orchestration/validator.py \
  --follow-imports=skip

.venv/bin/python -m compileall \
  -q \
  agents/orchestration/validator.py \
  tests/test_orchestration_validator.py

.venv/bin/python -m pytest \
  -q \
  tests/test_orchestration_validator.py
```

Backend development tools are pinned in `platform/backend/requirements-dev.txt`.

## Dashboard validation

```bash
cd ~/dap/source/dipen-ai-platform
npm --prefix apps/dashboard run lint
npm --prefix apps/dashboard run build
```

When the development dashboard is running, prefer a temporary worktree for production builds so its `.next` directory is not reused.

Do not run `npm audit fix` or `npm audit fix --force` as part of unrelated work.

## Review and commit

```bash
git diff --check
git status --short
GIT_PAGER=cat git diff
```

Stage only intended files, inspect them, and commit with a focused message:

```bash
git add <real-file-path>
git diff --cached --check
GIT_PAGER=cat git diff --cached
git commit -m "type: describe the change"
```

`<real-file-path>` is a placeholder and must be replaced with an actual file path.

## Push and open a pull request

```bash
git push --set-upstream origin "$(git branch --show-current)"
```

Open a pull request into `main`. Do not merge until both GitHub Actions jobs pass:

- `backend`
- `dashboard`

## Safely sync after a merge

Before switching branches, confirm the working tree is clean:

```bash
git status -sb
```

When the current branch and merged remote `main` should contain identical files, compare their trees first:

```bash
git fetch origin
CURRENT_TREE="$(git rev-parse 'HEAD^{tree}')"
REMOTE_MAIN_TREE="$(git rev-parse 'origin/main^{tree}')"

printf "Current tree: %s\n" "${CURRENT_TREE}"
printf "Remote tree:  %s\n" "${REMOTE_MAIN_TREE}"
```

Only switch when the state is understood. After syncing, run `./scripts/check-dev-health.sh` again.

## Safety rules

Avoid destructive commands unless the repository state and recovery plan are clear:

```text
git reset --hard
git clean -fd
git push --force
git branch -D
```

Use these commands first when diagnosing a mistake:

```bash
git status -sb
git branch --show-current
GIT_PAGER=cat git log --oneline --decorate -n 10
git reflog -n 20
```

Never delete persistent DAP data as part of a Git recovery operation.

## Phase 2.8 baseline

Phase 2.8 establishes:

- a LAN dashboard development command;
- a read-only runtime health check;
- pinned backend development tools;
- clean dashboard linting;
- backend and dashboard CI jobs;
- a pull-request-based development workflow.
