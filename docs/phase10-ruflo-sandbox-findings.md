# Phase 10B — Ruflo Sandbox Findings

## Status

Phase 10B isolated Ruflo sandbox evaluation is complete with a constrained-runtime verdict.

## Environment

- DAP Phase 10 branch: `phase10/ruflo-evaluation`
- Sandbox root: `/home/dipen/dap/sandboxes/ruflo-eval`
- Host Node.js: `v22.22.1`
- Ruflo wrapper tested: `3.38.12`
- DAP runtime, databases, Guardian controls, and production source tree were not modified by Ruflo.

## Findings

### Package structure

- `ruflo@3.38.12` wrapper tarball is approximately 4.4 MB compressed and 8.18 MB unpacked.
- The wrapper exposes `bin/ruflo.js` and has one direct dependency: `@claude-flow/cli`.
- The wrapper has no `preinstall`, `install`, `postinstall`, or `prepare` lifecycle scripts.

### CLI dependency surface

`@claude-flow/cli@3.38.12` carries the large runtime surface. It includes required Codex, MCP, neural, federation, security, and shared packages plus a substantial optional native/vector ecosystem.

The CLI `postinstall` was statically inspected. It only patches reachable `agentdb` installations inside the Node dependency tree for compatibility. It does not invoke shell commands, Docker, systemd, sudo, Codex registration, or DAP paths.

### Controlled execution

The extracted Ruflo CLI `--version` fast path was executed under an isolated HOME and returned:

```text
ruflo v3.38.12
exit_code|0
```

No project state, processes, or listeners were created. DAP remained clean and protected controls remained unchanged.

### Provisioning feasibility

Two npm provisioning attempts were intentionally bounded:

1. Full Ruflo install with lifecycle scripts disabled stalled on network/dependency resolution and was aborted.
2. Minimal direct CLI install using `--omit=optional --ignore-scripts` exceeded a hard 180-second timeout and was terminated.

Therefore the full Ruflo CLI runtime is classified as **impractical to provision on the current Acer host via npm for this evaluation**. Further repeated full/minimal CLI install attempts are prohibited unless the evaluation plan is explicitly changed.

### Codex adapter publication drift

The Ruflo GitHub `main` source currently declares `@claude-flow/codex` version `3.0.3`, while the npm registry currently publishes `3.0.2` as the available package version. A controlled install attempt pinned to `3.0.3` failed immediately with `ETARGET` and created no project state. This is recorded as upstream source/registry release drift rather than a DAP or Acer failure.

For runtime evaluation, use the explicitly published npm version after verifying it with `npm view @claude-flow/codex version` instead of assuming the version declared on upstream `main` has been published.

## 10B Decision

Phase 10B passes as an isolation and feasibility evaluation, with the following constraint:

- Do not install the full Ruflo CLI runtime on the DAP Acer host at this stage.
- Continue Phase 10 by evaluating smaller Ruflo components independently.
- The Codex adapter is the next candidate because its CLI peer dependency is optional and its own direct dependency set is comparatively small.

## Safety baseline

Throughout 10B:

- no Ruflo initialization was performed;
- no Codex MCP registration was performed;
- no `.claude-flow`, `.codex`, or `.agents` project state was created;
- DAP Guardian broker remained inactive;
- Telegram approvals remained disabled;
- no Docker or systemd integration was granted to Ruflo.
