# Phase 11E — Controlled Git Delivery

Status: **11E.1 delivery contract and 11E.2 isolated local commit builder implemented; CI and Acer end-to-end smoke are the current gates. Remote publication is not enabled.**

## Purpose

Phase 11E moves a successful bounded Codex result into Git review without transferring Git or GitHub authority to Codex or Ruflo.

The authority chain is:

```text
EngineeringWorkOrder
      ↓
CodexExecutionTicket
      ↓
EngineeringGuardianAdmission
      ↓
CodexRunResult / successful execution receipt
      ↓
DAP GitDeliveryPlan
      ↓
DAP LocalGitDeliveryBuilder
      ↓
isolated local development branch + commit
```

The first two sub-gates are deliberately network-free. Remote branch push and draft pull-request creation remain separately disabled until the local delivery boundary is proven on the Acer host.

## 11E.1 — immutable delivery authorization

`GitDeliveryPlan` binds the complete post-execution chain:

- repository identity fixed to `dipenkalal/dipen-ai-platform`;
- non-main base development branch;
- exact source commit;
- work-order ID and SHA-256;
- Codex ticket ID and SHA-256;
- Guardian admission ID and SHA-256;
- execution-receipt SHA-256;
- exact changed-file allowlist;
- deterministic DAP-derived `engineering/...` delivery branch;
- deterministic commit message;
- owner review required.

11E.1 grants only local commit authority. These remain fixed false:

- remote branch push;
- draft pull-request creation;
- GitHub credentials exposure to Codex;
- Codex Git authority;
- Ruflo Git authority;
- force push;
- main merge;
- tag/release;
- deployment.

Delivery is rejected when any upstream binding changes, the Codex receipt is not successful/delivery-eligible, findings exist, changed paths escape the work-order allowlist, Codex already performed Git side effects, or Guardian/root authority appears in the chain.

## 11E.2 — isolated local Git commit builder

`LocalGitDeliveryBuilder` creates a new isolated repository beneath a DAP-controlled delivery root using only the exact committed source revision.

Safety properties:

1. it clones only from the local DAP repository with `--no-hardlinks --no-checkout`;
2. it immediately removes `origin`, leaving the delivery repository with **zero remotes**;
3. it checks out the exact source commit detached, then creates only the DAP-derived delivery branch;
4. it copies/deletes only the exact changed-file allowlist from the Codex disposable workspace;
5. changed, staged, and committed paths must independently equal the DAP plan;
6. symlinks, path escapes, directory-level changes through a file scope, and rename observations are rejected;
7. the commit parent must equal the exact source commit;
8. Git identity is provided per-command and no global Git config is required;
9. Git runs with a reduced environment, `GIT_CONFIG_NOSYSTEM=1`, terminal prompts disabled, and no shell;
10. any failure deletes the isolated delivery repository.

The post-delivery observation is rejected if any remote push, draft PR, force push, main merge, tag, release, or deployment is observed.

## Acer smoke

`python -m engineering.git_delivery_smoke` performs one end-to-end disposable flow:

1. verify the live Phase 11 checkout is clean;
2. run the existing one-file Codex smoke through the 11D Guardian admission;
3. verify exact artifact content;
4. derive a DAP `GitDeliveryPlan`;
5. create an isolated local development branch and one commit;
6. prove the commit parent is the Phase 11 source commit;
7. prove the commit contains exactly the single allowed smoke artifact;
8. prove the isolated Git repository has zero remotes;
9. prove remote push/PR/merge/tag/release/deployment authority remains false;
10. delete both Codex and Git-delivery workspaces;
11. prove the live DAP source checkout remains clean.

## Remote publication boundary

Remote publication is explicitly **not** part of 11E.1/11E.2. A later 11E sub-gate may authorize a DAP-owned publisher to push only the deterministic `engineering/...` branch and create only a draft PR against an explicitly allowed non-main development branch. That publisher must not expose credentials or remote authority to Codex/Ruflo and must still prohibit force push, main merge, release, and deployment.
