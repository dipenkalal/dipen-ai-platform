# Phase 11D — Guardian Execution Admission

Status: **SEALED — dedicated CI and Acer disposable admission smoke passed.**

## Purpose

Phase 11D places an explicit DAP-owned admission proof between a Phase 11 Engineering Agent execution ticket and the bounded Codex runner.

The central rule is deliberately narrow:

> Ordinary Engineering Agent work may execute only when it is proven to remain non-privileged. If the work needs Guardian, root, network, Git metadata, external-repository, production-secret, main-merge, or deployment authority, the request is rejected instead of escalated on Codex's behalf.

Codex and Ruflo never receive a Guardian client, Guardian socket, root authorization token, or arbitrary privileged command surface.

## Admission chain

```text
Canonical DAP child task
        ↓
Executive Office validation-only admission
        ↓
EngineeringWorkOrder
        ↓
CodexExecutionTicket
        ↓
EngineeringGuardianAdmission
        ↓
BoundedCodexRunner
        ↓
Disposable tracked-file snapshot
```

`EngineeringGuardianAdmission` is immutable and binds:

- work-order ID and stable authority SHA-256;
- Codex ticket ID and SHA-256;
- risk class `non_privileged_workspace`;
- the fact that Codex workspace execution is admitted;
- the fact that no Guardian service/broker contact is needed or allowed;
- the fact that no root authorization is needed or granted;
- all authority-expansion flags fixed false;
- owner review required.

## Fail-closed rules

Admission is rejected if any of the following is true:

- work-order or ticket identity/hash does not match;
- allowed repository paths drift after work-order creation;
- sandbox mode is not `workspace-write`;
- approval policy is not `on-request`;
- network access is requested;
- privileged access is requested;
- Git metadata writes are requested;
- external repository writes are requested;
- Guardian access is requested;
- production-secret access is requested;
- main merge is requested;
- deployment is requested;
- owner review is removed.

The bounded Codex runner refuses to start its preflight/subprocess unless the supplied Guardian admission independently matches the work order and ticket hashes.

## Protected repository regions

The Engineering Agent work-scope layer rejects autonomous mutation of:

- `.git`;
- `.github/workflows`;
- `platform/guardian`;
- legacy `platform/backend/guardian`;
- `deploy/systemd`.

This closes the gap discovered during 11D review where the earlier scope list named the legacy backend Guardian path but not the actual privileged `platform/guardian` tree.

## Stable authority identity

Canonical task and Executive Office models contain observation timestamps generated at construction time. Those timestamps are audit metadata, not execution authority. Phase 11 therefore hashes stable authority fields for work-order identity while excluding only task lifecycle timestamps and the Executive response generation timestamp.

Changing a meaningful field such as the task objective still changes the authority hash and work-order ID.

## Dedicated Phase 11 CI

`.github/workflows/phase11-engineering-agent.yml` explicitly validates the Engineering Agent surface with Ruff, mypy, Python compilation, Phase 11 backend engineering tests, and Phase 10/11 Guardian boundary regressions.

## Acer acceptance — 2026-08-17

Source head: `fe22d0b0aadb492f21768ad6d332df7a07cedbbe`.

The disposable smoke passed with:

- ticket ID `codex-ticket-30278e949ab90164892e42d0`;
- ticket SHA-256 `23c4181320887cfa11fc3f805468e3693abbb9eae7619484b6d291f5d5147326`;
- Guardian admission ID `guardian-admission-3d7cf87247d592dbed299513`;
- Guardian admission SHA-256 `2586576170eb4c7ed90ac53a0def7b280c987e7808c27ee0e3c8871ea1787af7`;
- Guardian contact required `false` and contacted `false`;
- root authorization required `false`;
- Codex disposition `succeeded`, delivery allowed `true`, exit code `0`, timeout `false`;
- exactly one changed file: `platform/backend/engineering/phase11c2_smoke_artifact.txt`;
- exact artifact content verified;
- Git commit/PR/main merge/deployment all `false`;
- disposable workspace removed, no sandbox or Codex-process residue;
- live source repository clean;
- Guardian broker inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`.

## Seal decision

All 11D exit criteria passed. Phase 11D is complete. The next boundary is Phase 11E controlled Git delivery, where Git authority belongs to a DAP-owned post-execution delivery component rather than Codex or Ruflo.
