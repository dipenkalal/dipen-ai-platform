# Phase 10E — Guardian Enforcement Boundary for Ruflo

## Purpose

Phase 10E proves that Ruflo cannot become a privileged execution path around DAP Guardian controls.

The Phase 10 architecture remains:

- Ruflo may generate bounded, non-executable engineering guidance;
- DAP owns task identity, policy, audit, and execution admission;
- Guardian remains the only privileged-action boundary;
- Ruflo has no direct Guardian credential, root authorization, systemd, Docker, or arbitrary shell authority.

## Existing Guardian enforcement

Guardian privileged backend execution already has several independent barriers:

1. `execute_authorized_backend_restart()` rejects non-root callers before validating plans or invoking the executor.
2. `restart_backend_service()` rejects non-root callers before any subprocess invocation.
3. root authorization issue/consume operations require effective UID 0.
4. the only executable backend action is the fixed restart of `dap-backend.service`.
5. root authorization validates the exact fixed command stored in the reserved Guardian plan.
6. authorization is bound to a plan ID and reservation ID and is single-use.
7. the executor does not accept an arbitrary command or shell parameter.

These controls are independent of Ruflo and therefore remain effective even if malformed or adversarial Ruflo output reaches a higher DAP layer.

## Phase 10E regression lock

`platform/guardian/tests/test_phase10_ruflo_boundary.py` adds Phase-10-specific tests that assert:

- Guardian's executor command remains exactly `/usr/bin/systemctl restart dap-backend.service`;
- the executor exposes no caller-supplied command argument;
- non-root callers fail before `subprocess.run()`;
- non-root callers fail before plan validation, execution-state entry, or executor invocation;
- non-root callers cannot issue root authorization;
- root authorization does not accept caller-supplied action, target, or command parameters;
- authorized execution exposes only Guardian database paths, plan/reservation IDs, and the existing dry-run flag.

## Ruflo-specific rule

Ruflo artifacts, adapter receipts, handoffs, or audit evidence are never accepted as Guardian authorization material.

The following remain prohibited:

- Ruflo-generated root tokens or approvals;
- Ruflo-selected systemd units;
- Ruflo-selected shell commands;
- Ruflo direct access to the Guardian broker/socket;
- Ruflo direct access to Guardian or root-authorization databases;
- Ruflo activation of the Guardian service;
- Ruflo bypass of DAP owner authorization or Executive Office admission.

## Acceptance criteria

Phase 10E can be considered complete when:

- the existing Guardian suite remains green;
- the Phase 10 Ruflo boundary regression tests pass;
- Guardian remains inactive in the production Acer baseline;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false` remains unchanged;
- no Ruflo process has Guardian/root credentials or privileged host access.

No production Guardian activation is required for this phase.
