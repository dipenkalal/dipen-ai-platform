# Changelog

## [0.18.1] - 2026-08-08

### Fixed

- Hardened the Telegram owner-approval confirmation state machine.
- Allowed an owner to reject a proposal after the initial approval step while it is awaiting confirmation.
- Kept rejected approval proposals terminal so later confirmation cannot delegate them.
- Corrected owner-approval audit wording so it records that Telegram approval itself did not start runtime execution.
- Removed the hardcoded five-minute approval duration from Telegram plan responses.

### Validation

- Telegram owner-channel test suite: 56 passed.
- Full backend test suite: 173 passed.
- Live owner-channel direct Reject flow verified.
- Live Approve → awaiting confirmation → Reject flow verified.
- No tested approval decision reached executive delegation, task-ledger mutation, execution admission, execution reservation, or execution start.

### Safety

- Telegram approvals remain disabled after validation.
- Guardian broker remains inactive.
- Guardian broker socket remains disabled.
- Broker activation remains disabled by Executive Office policy.
