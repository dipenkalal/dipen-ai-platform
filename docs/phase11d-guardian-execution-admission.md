# Phase 11D — Guardian Execution Admission

Status: implementation and dedicated CI complete; final Acer disposable smoke pending.

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

The Engineering Agent work-scope layer now rejects autonomous mutation of:

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

`.github/workflows/phase11-engineering-agent.yml` explicitly validates the new Engineering Agent surface with:

- Ruff;
- mypy;
- Python compilation;
- Phase 11 backend engineering tests;
- Phase 10 Guardian boundary regression;
- Phase 11 Guardian boundary regression.

The Phase 11 Guardian regression also proves that the existing privileged executor remains a fixed backend-service restart action and has no arbitrary Engineering Agent/Codex command parameters.

## Exit criteria

11D is sealed only after:

1. dedicated Phase 11 CI is green;
2. normal repository CI and Owner Channel checks are green;
3. an Acer disposable Codex smoke succeeds with a bound `EngineeringGuardianAdmission`;
4. smoke evidence reports Guardian contact not required/contacted and root authorization not required/granted;
5. no sandbox residue or Codex process remains;
6. live repository remains clean;
7. Guardian remains inactive and Telegram approvals remain false.
