# Phase 11E.3 — DAP-Owned Remote Git Publication

## Status

**LIVE GATE PASSED.** Implementation, CI, Acer runtime publication, independent GitHub verification, and temporary PR closure are complete. The temporary engineering branch remains only because the available GitHub connector does not expose ref deletion; it must be deleted with one exact host Git command after evidence capture.

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
- observed Git version during live smoke: `2.53.0`;
- fixed GitHub CLI binary: `/usr/bin/gh`;
- GitHub CLI semantic version: `2.97.0`;
- observed GitHub CLI first line: `gh version 2.97.0 (2026-07-31)`;
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

## Live smoke evidence — 2026-08-17

The Acer live smoke ran from exact Phase 11 source commit:

- source commit: `e098c5f3f5fb68517cdd6662a3735db7c0597676`;
- ticket: `codex-ticket-db675698216b5dcd7bdffbf6`;
- Guardian admission: `guardian-admission-ff7a36e0ad534a58b3c04041`;
- delivery: `git-delivery-fcba068d8c95863940368f28`;
- delivery plan SHA256: `50949759b371dbdf21cce32c0805cc9a8aeb075c452f27420dee224e58cbb1e3`;
- publication: `git-publication-5d7b0ddf25cb61b00fd72d70`;
- publication plan SHA256: `50083d16aced667a3098d702d817d69b85acc8e6ed1358d1951001328e33e3d9`;
- deterministic branch: `engineering/phase11c2-live-smoke-child-a4e40037cb3b`;
- engineering commit: `54fc021e312d12b8a7bc3fd6ff04c7c6940cdb9a`;
- exact parent: `e098c5f3f5fb68517cdd6662a3735db7c0597676`;
- draft pull request: `#63`;
- PR base: `phase11/autonomous-engineering-agent`;
- PR head: `engineering/phase11c2-live-smoke-child-a4e40037cb3b`;
- publication disposition: `succeeded`.

Runtime safety evidence:

- `github_credentials_exposed_to_codex=false`;
- `github_credentials_exposed_to_ruflo=false`;
- `codex_git_authority=false`;
- `ruflo_git_authority=false`;
- `force_push_performed=false`;
- `protected_branch_updated=false`;
- `pull_request_auto_merge_enabled=false`;
- `main_merge_performed=false`;
- `tag_created=false`;
- `release_created=false`;
- `deployment_performed=false`;
- `owner_review_required=true`;
- local workspace removed;
- no sandbox residue;
- no Codex executor residue;
- source repository clean;
- Guardian broker inactive;
- Telegram approvals disabled.

## Independent GitHub verification

After the Acer smoke, GitHub was queried independently from the runtime receipt.

The verification confirmed:

- PR #63 was open, draft, and unmerged at inspection time;
- base SHA was exactly `e098c5f3f5fb68517cdd6662a3735db7c0597676`;
- head SHA was exactly `54fc021e312d12b8a7bc3fd6ff04c7c6940cdb9a`;
- the engineering branch was exactly one commit ahead and zero commits behind the source commit;
- the one commit changed exactly one file: `platform/backend/engineering/phase11c2_smoke_artifact.txt`;
- that file contained exactly the expected one-line smoke payload `PHASE11C_CODEX_SMOKE_OK`;
- PR-triggered repository CI passed;
- PR-triggered Phase 11 Engineering Agent passed;
- PR-triggered Phase 10 Ruflo Evaluation passed.

PR #63 was then closed as disposable test evidence. It was **not merged**.

## Cleanup state

Completed remotely:

- PR #63 closed;
- PR #63 remains unmerged;
- evidence comment recorded before closure.

Remaining disposable artifact:

- branch `engineering/phase11c2-live-smoke-child-a4e40037cb3b`.

The current GitHub connector does not expose branch/ref deletion. Do not rewrite the branch to simulate deletion. Delete only this exact branch from the host after evidence capture.

## Exit criteria

11E.3 functional and safety gates are passed:

- dedicated Phase 11 Ruff, mypy, compile, engineering tests and Guardian regression pass;
- repository-wide CI and Owner Channel checks remain green;
- the Acer smoke published the exact local commit to the deterministic branch;
- the resulting pull request was independently verified as draft with exact base/head;
- Codex/Ruflo credential and Git authority flags remained false;
- no force push, protected-branch update, main merge, tag, release or deployment occurred;
- local workspaces were removed and the source repository remained clean;
- the disposable PR was closed without merge.

Formal remote cleanup is complete once the single temporary engineering branch above is deleted.