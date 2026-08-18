# Phase 13 — Live Activation Proof Plan

The Acer proof is intentionally one controlled deployment after CI is green.

Required proof:

1. exact Phase 13 source checkpoint and clean checkout;
2. current task-ledger, research-evidence, backend PID, Guardian, Telegram, dashboard, and SearXNG baselines;
3. one controlled `dap-backend.service` restart to load the activation code;
4. dashboard application rebuilt offline from the already-present local `node_modules` and packaged as standalone runtime, avoiding Acer-to-npm bulk dependency downloads;
5. recreate only `dap-dashboard` from the locally built image;
6. verify dashboard health and Agents page local-search control;
7. verify API rejects `research_search_query` in smart mode;
8. verify API rejects `research_search_query` for a non-Research agent;
9. execute one harmless manual Research Agent search query through local `searxng-local-v1`;
10. verify search step provider identity, candidate count, selected URL count <= 3, retrieval success, snippets/titles excluded, no generic network client, and no remote scope expansion;
11. verify immutable research evidence increases and appears through the read-only Research workspace/backend/dashboard APIs;
12. verify Research workspace POST remains HTTP 405;
13. verify task ledger unchanged, backend stable after the controlled restart, Guardian inactive, Telegram approvals false, SearXNG loopback-only, dashboard healthy, and checkout clean.

No Docker daemon restart, Guardian activation, Telegram approval activation, paid provider, main merge, release, tag, or privileged host action is part of the proof.
