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

The allowed Phase 10C direction is therefore:

1. call pure generator / validator functions only;
2. treat returned strings as untrusted candidate artifacts;
3. apply DAP-owned policy filtering or construct DAP-owned configuration instead of accepting Ruflo's local Codex config;
4. never allow Ruflo to register MCP, install plugins, modify real Codex user state, or choose privileged execution policy;
5. keep Codex execution, auditing, and privileged actions behind DAP/Guardian-owned boundaries.

## Current decision

Proceed to a generator-only proof of concept. Do not execute `init`, `dual`, `loop`, MCP registration, plugin installation, or any command that mutates real Codex state.