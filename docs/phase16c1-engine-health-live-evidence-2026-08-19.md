# Phase 16C.1 — SearXNG Engine Health Live Evidence — 2026-08-19

Status: **PASS — UPSTREAM ENGINE BLOCKING CONFIRMED**

Source checkpoint tested: `4e9e9f3fab4a13b96278fa8a8bb84bc2edeb53ca`.

Provider: `searxng-local-v1` on fixed loopback `127.0.0.1:8888`.

## Purpose

Phase 16A/16B proved that all 21 failed frozen-corpus cases were provider-zero-result failures, but did not identify the upstream engine failure mode. Phase 16C.1 added safe engine-health telemetry and a six-query control probe without changing SearXNG configuration.

## Live probe result

All six probes returned zero results, including the known-good Python documentation control at the beginning, middle and end of the sequence.

Probe report SHA-256:

`6b2578d231e7f43f8dcc032b4764adbc749efb827f4120990473b6fd68ddf962`

Suspected failure mode:

`upstream-engine-blocking`

Outcome totals:

- zero-results: `6/6`;
- contributing engines: `0`.

Normalized engine failure classes:

- CAPTCHA: `12`;
- too-many-requests: `6`.

Unresponsive engine counts:

- Brave: `6/6`;
- DuckDuckGo: `6/6`;
- Startpage: `6/6`.

Observed behavior:

- Brave: `too-many-requests`; active on the first probe, then reported suspended on subsequent probes;
- DuckDuckGo: `captcha` on every probe;
- Startpage: `captcha` and reported suspended on every probe.

The repeated Python controls also returned zero results, so the failure is not explained by the standards/general/technical query content itself.

## Runtime and truth isolation

Production truth before and after remained exactly:

- task ledger: `15`;
- research retrieval evidence: `16`;
- research operations events: `6`.

Runtime invariants remained unchanged:

- backend PID: `677911` before and after;
- Guardian: `inactive`;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false`;
- SearXNG container remained running;
- SearXNG binding remained `127.0.0.1:8888`;
- SearXNG container ID remained unchanged;
- SearXNG `StartedAt` remained unchanged;
- tracked SearXNG settings SHA remained `ed62d55f458aa1ac064bee392d1d639095d76ef55ea0000a8de545c2ffbb4730`.

No backend restart, SearXNG restart, provider configuration mutation, production truth mutation, Guardian contact, privilege expansion, provider switching, smart-routing activation, or automatic Knowledge mutation occurred.

## Empirical conclusion

The dominant coverage defect is the current three-engine SearXNG pool itself. All configured engines are simultaneously blocked by upstream anti-bot/rate-limit behavior. DAP candidate validation, destination policy, retrieval, and benchmark timeout behavior are not the cause of the 70% no-candidate baseline.

The next justified action is a bounded provider-engine-pool remediation while preserving the same fixed local SearXNG provider and all DAP authority boundaries. SafeSearch is not implicated by this evidence and should remain unchanged during the engine-pool correction so that variables are isolated.

## 16C.2 source remediation selected

The tracked candidate replacement pool is:

- Google;
- Bing;
- Qwant;
- Mojeek;
- Wikipedia;
- Wiby.

The original blocked Brave/DuckDuckGo/Startpage pool is removed from the candidate configuration. All six replacement engines are credential-free in the tracked DAP configuration and explicitly enabled. SafeSearch remains `2`.

The source boundary test freezes the exact pool and rejects credential fields or authority changes before any Acer deployment is allowed.
