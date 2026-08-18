# Phase 12I — Dashboard Research Workspace Live Evidence

Date: 2026-08-18

Branch: `phase12/internet-research-gateway`

Code checkpoint deployed: `83d5367667c822f0c5a7a52d28d5aa4ce2eb3b95`

Status: **COMPLETE / SEALED — ACER LIVE PROOF PASSED**

## Scope

Phase 12I adds an owner-facing, read-only Research workspace for inspection of DAP-owned internet retrieval evidence. It does not add browser-side network authority, arbitrary URL fetching, search-provider credentials, task mutation, Knowledge mutation, Guardian/root/systemd control, or a second source of canonical task truth.

## CI evidence

All relevant workflows completed successfully on checkpoint `83d5367667c822f0c5a7a52d28d5aa4ce2eb3b95`:

- normal CI;
- Phase 12 Internet Research Gateway;
- Phase 12I Research Workspace Dashboard;
- Phase 11 Engineering Agent regression;
- Phase 10 Ruflo Evaluation regression;
- Phase 7 Owner Channel regression.

The dedicated Phase 12I workflow passed:

- Research workspace authority boundary;
- dashboard lint;
- Next.js build;
- production dashboard Docker image build.

## Build incident and durable fix

The first Acer dashboard image builds failed only during `npm ci` because of unstable outbound package-registry transfers (`ETIMEDOUT`, then `ECONNRESET`). Production was not recreated during either failure.

The build context was also found to be unnecessarily large:

- dashboard directory: about 909 MB;
- local `node_modules`: about 714 MB;
- local `.next`: about 194 MB;
- initial Docker context transfer: about 840.56 MB.

A tracked `apps/dashboard/.dockerignore` reduced the Docker build context to about 11.58 KB. The Dockerfile was also hardened with a persistent BuildKit npm cache and `--prefer-offline` behavior.

Because Acer-to-registry bulk transfer remained unreliable, the final dashboard application build was performed with `--network none` using the already-present local dependency tree. Next.js compiled successfully offline and produced standalone runtime output. A minimal runtime image was then packaged with no npm install.

Offline build evidence:

- Node `v24.19.0`;
- npm `11.17.0`;
- network explicitly disabled;
- Next.js `16.2.11` production build succeeded;
- `/research` static route present;
- `/research/[evidenceId]` dynamic route present;
- `/api/research/evidence` proxy route present;
- `/api/research/evidence/[evidenceId]` proxy route present;
- standalone output verified;
- tracked source remained clean;
- runtime image built successfully as `sha256:9ea830efac2a47a277963fa47c29a28ad6e3127163288a290bafe0da767deef2`;
- rollback image saved as `dap-dashboard-phase12i-rollback:20260818T195336Z`.

## Backend activation

The Phase 12I backend code was activated with one controlled restart of `dap-backend.service`.

Before activation:

- backend MainPID: `2856`;
- `/api/v1/research/evidence`: HTTP 404;
- task ledger: `11`.

After activation:

- backend MainPID: `396016`;
- backend health: HTTP 200;
- `/api/v1/research/evidence?limit=100`: HTTP 200;
- workspace mode: `read_only`;
- `network_authority_granted=false`;
- `mutation_authority_granted=false`;
- `search_candidate_metadata_included=false`;
- task ledger remained `11`;
- Guardian remained inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false` remained unchanged;
- SearXNG remained healthy on `127.0.0.1:8888`.

The production evidence table contained zero records at activation time, which is valid; the workspace correctly rendered its empty state.

## Final dashboard deployment proof

The new runtime image was deployed by recreating only `dap-dashboard`, with no backend restart and no SearXNG restart.

Final live checks passed:

- dashboard recreation succeeded;
- new dashboard container is healthy;
- running image is `sha256:9ea830efac2a47a277963fa47c29a28ad6e3127163288a290bafe0da767deef2`;
- `GET /research`: HTTP 200;
- Research page marker check: PASS;
- `GET /api/research/evidence?limit=100`: HTTP 200;
- proxy JSON valid;
- proxy workspace mode: `read_only`;
- proxy totals: total 0, succeeded 0, failed 0, cancelled 0;
- `network_authority_granted=false`;
- `mutation_authority_granted=false`;
- `search_candidate_metadata_included=false`;
- proxy boundary check: PASS;
- `POST /api/research/evidence`: HTTP 405;
- GET-only boundary check: PASS;
- task ledger remained `11`;
- backend MainPID remained `396016` during dashboard deployment;
- backend remained active;
- Guardian remained inactive;
- `DAP_TELEGRAM_APPROVALS_ENABLED=false` remained unchanged;
- SearXNG remained healthy on `127.0.0.1:8888` with HTTP 200;
- final deployment exit: `0`.

## Browser proof

Owner browser verification showed the live Research workspace at `/research` with:

- `Research Workspace` / `Internet research evidence` heading;
- explicit `Read only` state;
- Total / Succeeded / Failed / Cancelled counters;
- `Provenance: Internet Evidence`;
- `Knowledge mutation: disabled`;
- `UI network authority: disabled`;
- correct zero-evidence empty state: `No persisted internet retrieval evidence is available yet.`

## Exit decision

Phase 12I is **SEALED**.

The owner can inspect DAP-owned internet evidence through the dashboard while the UI remains read-only and non-authoritative. No production authority expansion is authorized by this gate.

Search discovery remains deferred as additional live Research Agent authority until Phase 12J completes the empirical benchmark and records the production-readiness decision.
