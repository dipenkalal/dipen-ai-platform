# NAS Project Dipen / DAP — Master Progress Ledger

**Canonical project:** `dipenkalal/dipen-ai-platform`  
**Coverage:** Day 1 through Phase 15.1 verified continuation  
**Ledger date:** 2026-08-19  
**Purpose:** Permanent progress-tracking companion to every future handover.

> Evidence rule: VERIFIED means supported by repository/PR/CI/runtime evidence available during reconstruction. RECONSTRUCTED means supported by prior handovers but exact early repository metadata was not recovered. UNVERIFIED means missing metadata is intentionally not invented.
>
> The historical body below preserves the original Phase 11-era reconstruction. Verified later milestones are recorded in `DAP_MASTER_PROJECT_LEDGER_PHASE12_14_APPENDIX.md` and `DAP_MASTER_PROJECT_LEDGER_PHASE15_15_1_APPENDIX.md`. The **Current continuation checkpoint** at the end of this file is the authoritative latest project position.

## Executive status

DAP progressed from an initial frontend/backend `fetch failed` recovery into a governed local AI control plane with multi-agent orchestration, durable task truth, bounded owner-triggered execution, cooperative cancellation, Guardian security controls, Telegram owner-channel functionality, Unified Chat with attachment/Knowledge isolation, a completed Ruflo evaluation, bounded Engineering Agent integration, and a sealed owner-supervised public-web research path with operational reliability telemetry and frontend evidence controls.

- Completed through: **Phase 15.1**
- Current repository baseline: `main` after PR #70 merge commit `d47c11166f5e52b2067f8804deeb75ffa048c1fb`
- Current production research posture: **manual owner-supervised research; provider degraded**
- Smart-routing research: **DISABLED**
- Guardian broker: **INACTIVE**
- Telegram approvals: **DISABLED**
- Next milestone: **Phase 16 — Research Provider Coverage & Latency Remediation**
- Ruflo decision: **ADAPT SELECTED COMPONENTS ONLY / REJECT FULL RUNTIME**

## Permanent architectural rules

1. Owner remains final approver for privileged, destructive, externally binding, costly, or privacy-sensitive actions.
2. DAP owns canonical task truth, policy, orchestration, audit evidence, local-model routing, and production decisions.
3. Guardian privileged execution is allowlisted/fail-closed and is not an arbitrary shell.
4. Agent work is bounded, registered, evidence-producing, and DAP-routed.
5. Ambiguous outcomes enter `manual_review`; they are not automatically replayed.
6. Running cancellation is cooperative; force-kill is not the normal owner cancellation primitive.
7. Telegram is an owner channel, not an independent authority plane; approvals remain separately controlled.
8. Knowledge/chat attachments are isolated by ownership/policy boundaries.
9. Ruflo never becomes a peer control plane and receives no root/systemd/Docker/Guardian/task-ledger/direct-Ollama authority.
10. Evaluation-only branches/PRs are not merged merely to prove a concept.
11. Codex/Ruflo do not receive GitHub credentials, remote Git authority, main-merge authority, release authority, or deployment authority.

## Master milestone timeline

| Milestone | Status | Confidence | Outcome |
|---|---|---|---|
| Day-1 recovery / platform foundation | COMPLETE | RECONSTRUCTED | Recovered frontend/backend connectivity and health baseline. |
| Phase 2.x orchestration platform | COMPLETE | RECONSTRUCTED + partial repo evidence | Orchestration, validation, persistence, REST/history UI and detail/DAG work. |
| Phase 2.8 safe development baseline | COMPLETE | VERIFIED | PR-based workflow and validation baseline; PR #5. |
| Guardian foundation/action engine | COMPLETE | VERIFIED | Read-only/planning Guardian, then tightly allowlisted backend restart boundary. |
| Guardian voice/UI evolution | COMPLETE / ITERATED | VERIFIED | Local voice, DAP-owned STT/TTS, Guardian-first UI; 3D direction rejected. |
| Guardian v3 truth + delegation | COMPLETE | VERIFIED | Task ledger, heartbeats, truth APIs, instrumentation, supervisor/delegation. |
| DAP company/governance | COMPLETE | VERIFIED | Owner/CEO hierarchy, departments/roles, Operations Center and governance docs. |
| Executive Office advisory | COMPLETE | VERIFIED | Deterministic non-executing planning/routing. |
| Phase 3 controlled delegation | COMPLETE | VERIFIED | Owner-gated parent/child task persistence; PR #44. |
| Phase 4 owner-triggered execution | COMPLETE | VERIFIED | Reservation/start/evidence/recovery; PR #45. |
| Phase 5 cooperative running cancellation | COMPLETE | VERIFIED | Durable cancellation and safe-boundary reconciliation; PR #46. |
| Phase 6 in-child cooperative cancellation | COMPLETE | VERIFIED from project history | Safe cancellation probes; PR #47 introduced the phase. |
| Phase 7 Telegram Owner Channel | COMPLETE for deployed scope | VERIFIED + handover | Authenticated ingress, polling stabilization, notification delivery; approvals disabled. |
| Phase 8 hardening/release baseline | COMPLETE | RECONSTRUCTED | Security/runtime hardening leading to deployed 0.18.1. |
| Phase 9 Unified Chat Interface | COMPLETE | VERIFIED + handover | Chat persistence/history, attachments, Knowledge context and isolation gates. |
| Phase 10 Ruflo Evaluation | COMPLETE — PASS | VERIFIED | Narrow adapter accepted; full Ruflo runtime rejected. |
| Phase 11A–11C Engineering Agent + bounded Codex | COMPLETE | VERIFIED | DAP-owned work order, execution ticket, bounded Codex runner, Acer live smoke. |
| Phase 11D Guardian execution admission | COMPLETE — PASS | VERIFIED | Non-privileged admission bound to Codex execution; Acer smoke passed without Guardian/root contact. |
| Phase 11E controlled Git delivery | HISTORICAL CHECKPOINT | VERIFIED to recorded code/CI gate | DAP-owned delivery contract + isolated local commit builder; historical reconstruction retained below. |
| Phase 12 Internet Research Gateway | COMPLETE / SEALED / MERGED | VERIFIED | Bounded retrieval, SSRF/untrusted-content controls, immutable evidence, local SearXNG, Research Workspace. |
| Phase 13 Provider-Specific Research Activation | COMPLETE / SEALED / MERGED | VERIFIED | Manual Research Agent query path activated through fixed loopback SearXNG; smart routing remained disabled. |
| Phase 14 Research Operations & Reliability | COMPLETE / SEALED / MERGED | VERIFIED | Operations telemetry, source-family/duplicate visibility, retention dry-run, provider health and reliability dashboard. |
| Phase 15 Provider Reliability Remediation | COMPLETE / SEALED / MERGED | VERIFIED | 30-case isolated provider corpus, fallback/diagnostics/timing, readiness projection; provider remained degraded. |
| Phase 15.1 Research UI + Data Hygiene | COMPLETE / SEALED / MERGED | VERIFIED | Metric-scope clarity, successful-only source-family analytics, workspace evidence scoping, navigation hygiene. |

## Day-1 recovery and early Phase 2

Earliest handovers describe the starting point as frontend/backend `fetch failed`. Recovery established a working local runtime, health/monitoring, multi-agent orchestration, evidence validation, persistent run/history storage, REST APIs and frontend orchestration history/detail work. Phase 2.7.x included orchestration-detail/DAG work.

Exact Day-1 SHA and the complete early Phase-2 PR map remain **UNVERIFIED** and are not invented here.

## Phase 2.8 — safe development baseline

PR #5 (`docs: add safe development workflow`) records the Phase 2.8 baseline: PR-based development, runtime/backend/dashboard validation, safe synchronization and recovery checks. Recorded validation: dashboard lint/build PASS; backend Ruff/Mypy/compile/tests PASS; runtime health returned HTTP 200 for five checks.

## Guardian foundation and privileged boundary

A prior checkpoint records PR #9 merged to `main` at `8264b4e`, followed by Guardian MVP work.

### PR #12 — non-executing Guardian action engine

Planning-only allowlisted restart plans, authenticated plan creation, SQLite lifecycle/audit, explicit approval, root-only authorization, single-use reservation, dry-run Unix-socket broker, hardened unit definitions and safety CI. No system command execution.

### PR #13 — authorized backend restart

First real Guardian privileged action, fixed to `/usr/bin/systemctl restart dap-backend.service`, with bounded verification. No arbitrary command/unit/shell/environment. Evidence records 29 Guardian tests passing locally.

### PR #23 — read-only action audit

Owner-authenticated, redacted action/audit history with no mutation path.

## Guardian local voice and UI evolution

- PR #25: local-only Guardian voice avatar, `Hey Guardian`, secure/local-processing boundary.
- PR #26: DAP-owned localhost voice service with WebRTC VAD + local whisper.cpp; no audio/transcript persistence.
- PR #27: improved local STT and Piper neural TTS while preserving privacy boundary.
- PR #32: Guardian Control Core landing experience with truthful health/agent data.
- PR #33: spatial 3D direction **rejected/closed by design** after visual review.
- PR #34: minimal central-orb Guardian voice interface.

## Guardian v3 truth and delegation

### PR #36 — truth foundation

Authoritative runtime schemas, heartbeat repository, durable task ledger, fleet-state service and read-only truth APIs. Missing evidence is not fabricated.

### PR #37 — runtime instrumentation

Agent/orchestration lifecycle instrumentation, busy/available heartbeats, long-run refresh, process/model evidence and telemetry failure isolation.

### PR #38 — truth console + delegation

Live truth UI and Guardian supervisor behavior. Cognitive work can be delegated to bounded registered agents; privileged operations remain separate.

## DAP company/governance model

### PR #40

Established owner/CEO hierarchy, 10 departments, 37 roles, manager/specialist separation, QA/Security controls, Audit independence, evidence/escalation rules. CI run `31069060119` recorded fully passing.

### PR #41

Read-only Company Operations Center combining organization, truth/task, monitoring and infrastructure data. CI run `31070207063` recorded fully passing.

### PR #43

Simplified Operations Center into a compact executive view while retaining detailed read-only tabs.

## Executive Office advisory foundation — PR #42

Added deterministic decomposition/routing, risk classification and independent evidence through `/api/v1/executive-office/status` and `/api/v1/executive-office/plan`. Advisory only: no task writes, execution, broker activation or production mutation.

## Phase 3 — controlled delegation — PR #44

Recomputes plans server-side; blocks prohibited work; requires matching owner approval when required; checks Agent Truth/capacity; atomically creates parent/child tasks; persists approval/idempotency; stable replay and changed-content conflict behavior. No execution or broker activation.

## Phase 4 — owner-triggered execution — PR #45

- 4.1 admission: exact controlled delegation/tasks, owner authorization and live rechecks.
- 4.2 reservation: durable execution/reservations; one active reservation per machine agent; atomic `assigned -> queued`.
- 4.3 start: second owner authorization; exact queued task/agent pairs only; instrumented executor.
- 4.4 evidence/status: SHA-256 acceptance evidence; uncertainty -> `manual_review`.
- 4.5 cancellation/recovery: pre-start cancellation; heartbeat-aware interrupted recovery; no force-kill or automatic replay.

## Phase 5 — cooperative running cancellation — PR #46

Durable cancellation intent, safe runtime checkpoints, atomic reconciliation preserving completed child outcomes, reservation release, parent `manual_review`, heartbeat/grace-aware recovery. No PID/task/container kill, shell/root, broker activation or uncertain replay.

## Phase 6 — in-child cooperative cancellation — PR #47

PR #47 introduced typed `CancellationCheck`, `CooperativeCancellationRequested` and explicit safe checkpoints. Project handover history records Phase 6 as completed through bounded child execution. Exact final Phase-6 merge/head metadata was not recovered in this reconstruction and remains **UNVERIFIED**.

## Phase 7 — Telegram Owner Channel — PRs #48/#49

PR #48 introduced exact owner/chat binding, constant-time secret validation, deterministic update idempotency and bounded `/status`, `/cancel`, `/help` ingress. PR #49 stabilized long polling and sanitized transport errors.

Recorded PR #49 validation: 17 Telegram transport tests passed; full backend suite 171 passed with 2 non-blocking dependency deprecation warnings; `git diff --check` passed.

By 2026-08-09, DAP `0.18.0` was deployed healthy, Guardian broker inactive, Telegram polling/notifications enabled, approvals disabled and `broker_activation_enabled=false`. `/status` was proven and event-driven notification delivery was subsequently verified through the authoritative SQLite/outbox/delivery path.

## Phase 8 — hardening/release baseline

Available handovers show the move from deployed `0.18.0` in Phase 7 to healthy `0.18.1` by Phase 9, including Telegram/security/runtime hardening. A separately named Phase-8 PR/sub-phase map was not recovered and is not fabricated.

## Phase 9 — Unified Chat Interface

Branch: `phase9/unified-chat`.

Completed capabilities include employee-aware chat, conversation persistence/history, attachment ingestion, Knowledge context, lifecycle/status handling, bounded uploads, per-conversation quotas, metadata sanitization, client-safe errors, invalid-extension rejection before durable metadata, ownership isolation and live security/executor acceptance.

Validation/documentation PRs:

- #53 Phase 9.4J checkpoint;
- #55 Phase 9.4K.1 bounded uploads;
- #56 Phase 9.4K.1b dashboard upload proxy;
- #57 Phase 9.4K.2 attachment quotas;
- #58 Phase 9.4K.3 metadata hardening;
- #59 Phase 9.4K.3 policy-invalid rejection;
- #60 Phase 9.4L attachment isolation gate.

These were validation-only where stated and not intended for merge to `main`.

Repository-history maintenance: #52 restored an Aug-9 contribution using replay + immediate revert while preserving the final main tree; #54 backfilled Aug 12–16 documentation checkpoints without runtime changes.

## Phase 10 — Ruflo evaluation

Branch: `phase10/ruflo-evaluation`  
Final SHA: `7bf3a68218ffaab934ffa980a3f6abbddd09a66a`  
Temporary PR #61: closed without merge.  
Status: **COMPLETE — OWNER ACCEPTANCE PASS**.

### Final gate ledger

| Gate | Result | Conclusion |
|---|---|---|
| 10A Architecture/security audit | COMPLETE | Full Ruflo authority too broad; strict subordinate boundary. |
| 10B Isolated sandbox | COMPLETE | Full provisioning unreliable; standalone Codex adapter provisionable. |
| 10C Codex adapter PoC | COMPLETE | Pure generator/validator works; ordinary initializer blocked due mutation risk. |
| 10D DAP ↔ Ruflo adapter | COMPLETE | Typed contract/bridge/handoff/evidence; execution authority false. |
| 10E Guardian boundary | COMPLETE | Non-root fails before privilege; no arbitrary Ruflo command surface. |
| 10F Audit/task integration | COMPLETE | Immutable additive evidence; canonical task truth not mutated. |
| 10G Ollama compatibility | COMPLETE | DAP remains sole local-model boundary; no direct Ruflo Ollama. |
| 10H Engineering benchmark | COMPLETE — CONSTRAINED | No justified full-runtime coding race; no demonstrated advantage sufficient for adoption. |
| 10I Acer resource/performance | COMPLETE — CONSTRAINED | Narrow adapter acceptable; full runtime unacceptable on current host; no fabricated CPU/RSS. |
| 10J Adoption decision | COMPLETE | Adapt/cherry-pick selected pieces only; reject full runtime. |

### CI evidence

Focused Guardian boundary PASS; Phase-10 Ruff PASS; Mypy PASS across six source files; compile PASS; backend tests **63 passed, 1 existing pytest-asyncio deprecation warning**; general backend/Guardian CI PASS; dashboard lint/voice safety/build PASS; Owner Channel workflow PASS.

### Acer/resource evidence

Audit checkpoint: ~11 GiB RAM total, ~9.3 GiB available, swap unused, ~54–55 GiB disk free. Full `ruflo@3.38.12` provisioning timed out/hung and was cleaned. Standalone `@claude-flow/codex@3.0.2` installed 59 packages in ~3 seconds and occupied ~18 MiB. No persistent Ruflo daemon/listener/MCP/memory/plugin retained.

### Owner-side Acer acceptance — 2026-08-17

- exact final SHA: PASS;
- Guardian boundary: **6/6 PASS**;
- DAP health: **OK**;
- Ollama operational and models visible;
- core containers up/healthy at check time;
- isolated backend Phase-10 suite: **63 passed, 1 warning in 0.27s**;
- temporary `.venv-phase10` removed; cleanup explicitly confirmed.

### Explicitly rejected/not performed

No full Ruflo production runtime/init/MCP/plugin; no direct Ruflo Ollama; no Ruflo canonical memory/task ownership; no arbitrary shell; no Docker/systemd/root/Guardian authority; no automatic merge/release/deployment; no fabricated peak CPU/RSS; no Phase-10 merge to `main` merely for evaluation.

## Phase 11 — Autonomous Engineering Agent adaptation

Branch: `phase11/autonomous-engineering-agent`  
Draft PR: #62, CI/review visibility only; do not merge without owner approval.

### 11A–11C — bounded Engineering Agent and live Codex

DAP owns immutable work-order and Codex-execution contracts, path scope, execution limits and post-run validation. Codex executes only in a disposable tracked-file snapshot with network disabled, no Git metadata, no remote repository access, no Guardian/root authority, no merge/deployment authority and owner review required.

Acer 11C live smoke passed with exactly one allowlisted disposable file changed; exact content matched; no Git commit/PR/main merge/deployment; workspace removed; source checkout clean.

### 11D — Guardian execution admission — COMPLETE

A DAP-owned `EngineeringGuardianAdmission` binds the work-order and Codex-ticket hashes. Non-privileged Engineering Agent execution is rejected rather than escalated if it requests network, privilege, Git metadata, external repository, Guardian, secrets, main merge or deployment.

Acer acceptance on source head `fe22d0b0aadb492f21768ad6d332df7a07cedbbe` passed with Guardian contact required/contacted false, root authorization required false, Codex success, exact one-file mutation, no Git/PR/merge/deploy effects, no residue, clean source repo, Guardian inactive and Telegram approvals false.

### 11E — controlled Git delivery — HISTORICAL CHECKPOINT

11E.1 adds an immutable `GitDeliveryPlan` bound to the full work-order/ticket/Guardian-admission/execution-receipt chain. The repository is fixed, the base must be a non-main development branch, and the delivery branch is DAP-derived under `engineering/...`.

11E.2 adds a network-free `LocalGitDeliveryBuilder` which clones from the local source commit into an isolated delivery root, removes `origin`, creates the deterministic delivery branch, applies only the exact changed-file allowlist, creates one local commit, verifies its parent and file set, and rejects any remote push/PR/force-push/main-merge/tag/release/deployment observation.

The original reconstruction recorded remote publication as disabled at this point. Later milestones are tracked in the verified appendices rather than inferred from this historical checkpoint.

## PR index recovered for milestone history

#5, #9, #12, #13, #23, #25, #26, #27, #32, #33, #34, #36, #37, #38, #40, #41, #42, #43, #44, #45, #46, #47, #48, #49, #52, #53, #54, #55, #56, #57, #58, #59, #60, #61, #62.

This is not asserted to be every PR ever created; it is the positively recovered milestone-relevant set from this reconstruction. Verified later PRs are recorded in the Phase 12–14 and Phase 15–15.1 appendices.

## Known release/runtime checkpoints

| Period | Evidence |
|---|---|
| Early project | Local DAP recovered from frontend/backend connectivity failure; exact version UNVERIFIED. |
| 2026-08-09 | DAP `0.18.0` deployed healthy during Phase-7 work. |
| 2026-08-16 | DAP `0.18.1` healthy during Phase-9 completion/recovery. |
| 2026-08-17 | Phase 10 isolated and accepted; Phase 11 development/acceptance in progress. |
| 2026-08-19 | Phases 12–15.1 verified complete/sealed/merged; manual research provider remains degraded; smart routing disabled. |

## Current architecture

The historical Phase 11 architecture below is retained as reconstruction context:

```text
Owner
  -> DAP UI/API
       -> Company / Executive Office / canonical task truth
       -> DAP local-model provider -> Ollama
       -> Engineering Agent work-order
            -> bounded Codex ticket
            -> DAP Guardian admission
            -> disposable Codex snapshot
            -> validated Codex result
            -> DAP Git delivery plan
            -> isolated local Git commit (11E.2)
       -> Telegram owner channel (separately gated)
       -> Guardian privileged boundary -> fixed approved executor
```

Current verified research path added by Phases 12–15.1:

```text
Owner/manual Research Agent
  -> explicit research_search_query
  -> fixed local searxng-local-v1 on 127.0.0.1:8888
  -> bounded candidate selection (<= 3 retrieval URLs)
  -> sealed DAP admission/retrieval/untrusted-content boundary
  -> immutable Internet Evidence
  -> Research Agent synthesis
  -> read-only Research Workspace / Research Operations visibility
```

Ruflo is not a peer and is not in the privileged or Git authority chain. Smart-routing research is disabled.

## Honest metadata gaps

- exact Day-1 commit and early Phase-2.x PR mapping;
- exact standalone Phase-8 sub-phase/PR map;
- exact final Phase-6 merge/head metadata in this reconstruction.

Fill these only if new repository/handover evidence is recovered.

## Current continuation checkpoint

```text
Project: dipenkalal/dipen-ai-platform
Completed through: Phase 15.1
Current repository baseline: main
Latest completed merge: PR #70 -> d47c11166f5e52b2067f8804deeb75ffa048c1fb
Phase 15 posture: manual-research-provider-degraded
Phase 15.1 UI/data hygiene: COMPLETE / SEALED / MERGED
Production task ledger at live proof: 15
Production research evidence at live proof: 16
Production research operations at live proof: 6
Guardian broker: inactive
Telegram approvals: false
SearXNG: fixed local provider on 127.0.0.1:8888
Smart-routing research: disabled
Known remaining issue: provider query coverage/no-candidate reliability and retrieval tail latency
Next milestone: Phase 16 — Research Provider Coverage & Latency Remediation
Authority expansion in Phase 16: none planned
```

Verified continuation details:
- `docs/DAP_MASTER_PROJECT_LEDGER_PHASE12_14_APPENDIX.md`
- `docs/DAP_MASTER_PROJECT_LEDGER_PHASE15_15_1_APPENDIX.md`
