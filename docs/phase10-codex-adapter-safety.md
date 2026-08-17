# Phase 10C.4 — Codex Adapter Safety Boundary

## Verdict

The standalone `@claude-flow/codex` adapter is lightweight and its read-only commands are safe in the evaluation sandbox, but its ordinary `init` workflow is not permitted under DAP's current safety model.

## Installed-artifact evidence

- Installed package metadata: `3.0.2`.
- Installed compiled version constant: `3.0.1`.
- Installed CLI SHA-256: `1df00b5aa26c6d76b354bbf2d80042c9c91e83b877c7bacc22f96ee098bea096`.
- Installed initializer SHA-256: `c1694616eecf1b8b91b10378bb5862e70a110c425212bb968b1ca904f419227c`.

The `init` command exposes only template, skills, force, dual, path, and quiet options. It does not expose a supported flag to disable MCP registration, plugin installation, Codex-local config generation, or `.claude-flow` state creation.

A previous grep reported a `--dry-run` match, but that flag belongs to another command / internal dry-run text and is not an `init` safety bypass. `init --help` is authoritative for the installed CLI surface.

## Prohibited initializer behavior

The installed initializer contains code to:

- create `.agents`, `.codex`, `.claude-flow`, `.claude-flow/data`, and `.claude-flow/logs`;
- write `AGENTS.md`, `.agents/config.toml`, `.codex/AGENTS.override.md`, and `.codex/config.toml`;
- invoke the host `codex` CLI through `execSync`;
- register a Ruflo MCP server;
- add the Ruflo plugin marketplace and install `ruflo-core@ruflo` at user scope;
- generate local Codex settings containing `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, and `web_search = "live"`.

Direct `claude-flow-codex init` is therefore blocked for Phase 10.

## Generator-level finding

The exported generator API is a better integration seam than the initializer, but generated configuration must still be treated as untrusted data. Upstream `generateConfigToml()` defaults to safer top-level approval/sandbox values, yet it also unconditionally includes a Ruflo MCP server in its generated TOML and emits `network_access = true` in the workspace-write section. DAP must not consume that output verbatim.

### Phase 10C.5 generator-only PoC

The adapter's pure generator and validator exports were executed without invoking the initializer or Codex CLI.

Observed results:

- generated minimal `AGENTS.md` candidate: 947 bytes;
- `validateAgentsMd()` returned `valid=true`, zero errors, and three warnings;
- generated configuration candidate: 7,724 bytes;
- `validateConfigToml()` returned `valid=true`, zero errors, and one warning;
- the requested conservative top-level settings were present: `approval_policy="untrusted"`, `sandbox_mode="read-only"`, and `web_search="disabled"`;
- despite those inputs, the same generated configuration also contained `approval_policy="never"`, `sandbox_mode="danger-full-access"`, `web_search="live"`, `network_access=true`, a Ruflo MCP server, and an `npx` invocation using `@claude-flow/cli@latest`;
- the disposable project workspace remained unchanged;
- no `.agents`, `.codex`, `.claude-flow`, or `AGENTS.md` project state was created;
- no adapter process or listener remained;
- no initializer, Codex CLI, MCP registration, plugin installation, or real Codex configuration access occurred.

This proves that upstream validation success is not equivalent to DAP policy approval. Ruflo validators may be used as syntax/shape checks, but DAP must perform an independent policy gate.

## DAP-owned integration rule

The allowed Phase 10C direction is therefore:

1. call selected pure generator / validator functions only;
2. pin the npm package version and verify the installed artifact hash before import;
3. treat every returned string as untrusted candidate data;
4. apply DAP-owned deny/allow policy checks independently of Ruflo validators;
5. never accept upstream-generated Codex configuration verbatim;
6. let DAP render its own Codex execution policy/configuration;
7. never allow Ruflo to register MCP, install plugins, modify real Codex user state, or choose privileged execution policy;
8. keep Codex execution, auditing, and privileged actions behind DAP/Guardian-owned boundaries.

## Phase 10C.6 wrapper

A Phase 10 evaluation gate is maintained at `scripts/phase10-codex-adapter-gate.mjs`.

The gate is intentionally limited to pure adapter exports. It:

- requires the evaluated package metadata to equal `3.0.2`;
- requires the installed adapter CLI SHA-256 to equal `1df00b5aa26c6d76b354bbf2d80042c9c91e83b877c7bacc22f96ee098bea096`;
- generates and validates a minimal AGENTS candidate;
- applies a DAP-owned policy scan before accepting that candidate;
- generates upstream configuration only as a negative control and requires DAP policy to reject it;
- never writes the rejected upstream configuration as a usable `.toml` artifact;
- never calls `CodexInitializer`, the adapter CLI, `child_process`, MCP registration, plugin installation, or Codex execution.

## Current decision

Proceed with the DAP-owned adapter gate and verify it on the Acer sandbox. Continue to block `init`, `dual`, `loop`, direct MCP registration, plugin installation, and any command that mutates real Codex state.