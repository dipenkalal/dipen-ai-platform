# Phase 11E.3 — DAP-Owned Remote Git Publication

## Status

Implementation and CI complete. Live Acer publication smoke is the final runtime gate.

## Purpose

Phase 11E.3 promotes one already-validated, isolated local Engineering Agent commit into a remote review artifact without transferring GitHub authority to Codex or Ruflo.

The authority chain is:

1. Executive Office engineering work order.
2. Bounded Codex execution ticket.
3. DAP Guardian admission.
4. Successful Codex execution receipt.
5. Local-only `GitDeliveryPlan` and isolated commit with zero remotes.
6. Separate immutable `RemoteGitPublicationPlan`.
7. DAP-owned remote publisher.
8. Exact `engineering/...` branch plus draft pull request for owner review.

## Remote publication authority

The remote publication plan grants only:

- publication to repository `dipenkalal/dipen-ai-platform`;
- one deterministic `engineering/...` branch;
- one exact local commit SHA;
- one exact non-protected development base branch;
- one draft pull request;
- DAP-managed network and GitHub credentials for the publication step.

It explicitly does not grant:

- GitHub credentials to Codex;
- GitHub credentials to Ruflo;
- Git authority to Codex or Ruflo;
- force push;
- updates to protected branches;
- pull-request auto-merge;
- merge to `main`;
- tags;
- releases;
- deployment.

## Transport boundary

The Acer preflight established the host transport used by the publisher:

- Git remote: `git@github.com:dipenkalal/dipen-ai-platform.git`;
- fixed Git binary: `/usr/bin/git`;
- fixed GitHub CLI binary: `/usr/bin/gh`;
- GitHub CLI semantic version: `2.97.0`;
- SSH authentication is non-interactive and succeeds for the repository owner;
- `git push --dry-run` can create an `engineering/...` branch;
- GitHub CLI has an active host-managed authenticated account.

The publisher does not read or emit a raw GitHub token. It builds a reduced environment and deliberately does not inherit `GH_TOKEN` or `GITHUB_TOKEN`. Git publication uses the host SSH credential. Draft-PR publication uses the host `~/.config/gh` authentication context.

## Fixed command surface

The publisher has no generic command interface. It uses only bounded forms of:

- `git remote`;
- `git branch --show-current`;
- `git rev-parse HEAD`;
- `git ls-remote --heads` for the exact deterministic branch;
- `git push --porcelain` from the exact local commit to a previously absent deterministic `engineering/...` ref;
- `gh --version`;
- `gh auth status --active --hostname github.com`;
- `gh pr list` for the exact head branch;
- `gh pr create --draft` for the exact base/head/title/body.

All subprocesses use `shell=False`.

## No remote branch mutation after creation

The publisher does not update an existing remote engineering branch. If the deterministic branch does not exist, it may create it. If it already points to the exact expected commit, it may reuse it. If it points anywhere else, publication fails closed.

This removes both force-push and ordinary branch-rewrite authority from Phase 11E.3.

## Draft PR idempotency

An existing open pull request may be reused only when it is exactly one pull request for the deterministic head, remains draft, and has the exact expected base/head. A ready-for-review or mismatched pull request is rejected rather than modified.

## Guardian boundary

Remote Git publication is non-privileged DAP work. It does not contact the Guardian broker, request root authorization, invoke systemd, use the Docker socket, or inherit privileged execution authority. Phase 11 Guardian regression tests explicitly enforce this boundary.

## Live smoke

`python -m engineering.remote_git_publication_smoke` performs one disposable end-to-end proof:

1. bounded Codex changes the single Phase 11 smoke artifact;
2. DAP validates Guardian admission;
3. DAP creates an isolated local engineering commit with zero remotes;
4. DAP prepares the immutable remote publication plan;
5. the DAP publisher creates/reuses the exact remote engineering branch;
6. the DAP publisher creates/reuses the exact draft PR;
7. the local Codex and Git workspaces are removed;
8. the live source repository must remain clean.

The smoke deliberately leaves the remote branch and draft PR in place for independent GitHub verification. Cleanup is performed only after evidence has been checked. It never merges the PR.

## Exit criteria

11E.3 is complete only when:

- dedicated Phase 11 Ruff, mypy, compile, engineering tests and Guardian regression pass;
- repository-wide CI and Owner Channel checks remain green;
- the Acer smoke publishes the exact local commit to the deterministic branch;
- the resulting pull request is independently verified as draft with the exact base/head;
- Codex/Ruflo credential and Git authority flags remain false;
- no force push, protected-branch update, main merge, tag, release or deployment occurs;
- local workspaces are removed and the source repository remains clean;
- temporary remote review artifacts are closed/deleted after evidence capture, without merge.
