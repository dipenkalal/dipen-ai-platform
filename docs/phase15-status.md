# Phase 15 Status

Status: **IN PROGRESS — 15A FRONTEND VISIBILITY IMPLEMENTED IN SOURCE; PROVIDER REMEDIATION NEXT**

Base: Phase 14 final merged documentation seal `512c03aaab6c49f7c7ec4c351dcd82e35f36b4bc`.

Branch: `phase15/research-provider-reliability`.

## Why Phase 15 exists

Phase 14 proved the reliability/operations layer and exposed a provider-quality problem rather than an authority problem. The final Phase 14 posture remained `manual-research-provider-degraded` after a real no-candidate provider failure, 0.8125 success rate, 0.5 unique-source-family rate, 0.4615 duplicate-content rate and 2370.666 ms retrieval p95.

Phase 15 remediates those empirical weaknesses while preserving manual-only research authority.

## 15A — frontend visibility

Repository inspection confirmed that `/research` and `/research/operations` already existed on `main`, and the Research page already linked to Operations. The discoverability issue was the global `AppNavigation`: it intentionally returned no navigation on the normal `/` Guardian landing page.

15A changes the dashboard so:

- primary navigation is visible on the normal Guardian landing page;
- `Research` is a primary navigation item;
- `Research Ops` is a direct primary navigation item;
- chat routes retain their intentionally isolated navigation behavior;
- existing read-only/no-network browser authority remains unchanged.

The dashboard boundary test now freezes those visibility requirements.

## Current authority boundary

- smart-routing research: disabled;
- autonomous search discovery: disabled;
- provider endpoint: fixed local `127.0.0.1:8888`;
- selected retrieval URLs: <= 3;
- provider titles/snippets: non-evidence;
- Knowledge mutation from research: disabled;
- destructive evidence cleanup: disabled;
- agent Guardian/root/systemd/Docker authority: absent.

## Next engineering gate

15B will add no-candidate diagnostics and bounded provider-result scanning so DAP can distinguish true provider-zero results from malformed/unsafe/policy-rejected candidates and can continue scanning a fixed provider response after rejected entries instead of stopping at the first `query.count` raw items.

No Acer runtime mutation is required until source/CI gates are green enough to justify a controlled dashboard/backend deployment proof.
