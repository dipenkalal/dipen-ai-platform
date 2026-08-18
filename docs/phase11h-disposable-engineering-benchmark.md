# Phase 11H — Disposable Engineering Benchmark

## Status

**COMPLETE / SEALED — CONSTRAINED EMPIRICAL BASELINE.**

Phase 11H measured the reliability and host cost of the bounded Engineering Agent execution path before routine owner-reviewed use is considered. The benchmark produced a valid safety-clean empirical baseline, but the result did not meet the benchmark's all-green reliability acceptance threshold because one positive task timed out.

## Governing rule

> Benchmark the employee without giving the employee more authority.

The benchmark uses the same DAP-owned work-order, execution-ticket, Guardian-admission, and bounded Codex runner chain sealed in 11B–11D. It does not add Git delivery, remote publication, merge, deployment, Guardian/root execution, Docker/systemd, or live task-ledger authority.

## Fixed task matrix

The benchmark ran five ordered task classes from fresh tracked-file-only snapshots:

1. **Exact text creation** — create one exact one-line text artifact.
2. **Structured JSON creation** — create valid JSON whose parsed semantic value must exactly match the requested object.
3. **Python repair** — repair a deliberately buggy tracked fixture (`left - right` → arithmetic addition) while preserving a one-file path boundary. This task may receive one bounded retry when the deterministic acceptance check fails.
4. **Expected semantic-quality failure** — create an intentionally malformed JSON payload inside one allowed path. The run itself is expected to remain sandbox/path compliant while DAP's semantic quality check rejects the payload.
5. **Recovery after failure** — immediately run a fresh exact-text task after the intentional quality failure and require success.

The expected-failure task is not a privilege, network, filesystem-escape, or host-security probe. It tests whether DAP can reject semantically bad output and then recover cleanly on the next independent attempt.

## Bounded execution

Every attempt:

- materializes a fresh `git archive` tracked-file snapshot outside the source checkout;
- has exactly one DAP-allowed target path;
- receives a deterministic EngineeringWorkOrder;
- receives a DAP CodexExecutionTicket with `workspace-write` only;
- receives a DAP non-privileged Guardian admission;
- uses pinned `codex-cli 0.146.0`;
- has network disabled by the 11C runner;
- has no Git metadata in the workspace;
- has `max_changed_files=1`;
- has a 262144-byte captured-output ceiling;
- has a task timeout of 150 seconds;
- is cleaned before the next task.

The benchmark constraints explicitly forbid Git, package managers, network tools, systemd, Docker, Guardian calls, and service operations.

## Deterministic acceptance checks

DAP performs acceptance checks outside Codex:

- exact text byte/content check;
- JSON parse plus exact semantic object comparison;
- Python compile + AST check, no imports, and one `add` function directly returning a binary addition of `left` and `right`;
- malformed JSON probe requires the exact requested malformed content and requires the semantic JSON quality check to fail;
- recovery content check.

No dynamic `exec` or arbitrary generated Python execution is used by the benchmark validator.

## Metrics

The benchmark records:

- positive-task completion rate;
- path-compliant attempts / path-compliance rate;
- quality-gate expectation accuracy;
- repair-loop count;
- failure→recovery success;
- evidence completeness per attempt;
- per-attempt and total wall time;
- child-process user/system CPU time;
- child max RSS;
- sampled host CPU busy percentage;
- sampled host memory-used peak/delta and minimum available memory;
- host load average peak;
- maximum disposable workspace bytes;
- sandbox-root free-space delta;
- production task-ledger and engineering-audit row counts before/after;
- source-repository cleanliness and sandbox cleanup.

## Evidence completeness

Each attempt requires eight DAP-observed evidence primitives to count as complete:

1. source task SHA-256;
2. source admission SHA-256;
3. work-order SHA-256;
4. execution-ticket SHA-256;
5. Guardian-admission SHA-256;
6. Codex command SHA-256;
7. execution-receipt SHA-256;
8. deterministic acceptance-check results.

This benchmark does not persist these synthetic task attempts into the production `engineering_audit_evidence` table. Production Agent Truth is read only before and after the benchmark; row-count changes fail the benchmark.

## Pass criteria

A fully green benchmark run requires:

- all four positive tasks pass;
- all attempts remain path compliant;
- all five task outcomes match their expected quality behavior;
- the expected semantic-quality failure is followed by a successful recovery task;
- evidence completeness is 100%;
- production Agent Truth row counts are unchanged;
- the source repository remains clean;
- the benchmark sandbox is removed.

No minimum/maximum host performance threshold is hidden inside the pass decision. CPU/RAM/storage/latency are measured empirically.

## CI validation

Benchmark code:

- `platform/backend/engineering/engineering_benchmark.py`
- `platform/backend/engineering/benchmark_fixtures/phase11h_repair_target.py`
- `platform/backend/tests/test_engineering_benchmark.py`
- `platform/guardian/tests/test_phase11h_benchmark_boundary.py`

Pre-Acer empirical benchmark head:

`6cd6219ba1d80f55ece54d0004aac6e77fe8dff9`

At that exact head all required pre-runtime workflows passed:

- Phase 11 Engineering Agent: success;
- repository CI: success;
- Phase 10 Ruflo regression: success;
- Phase 7 Owner Channel: success;
- benchmark Ruff: pass;
- benchmark mypy: pass;
- benchmark compile: pass;
- benchmark/unit tests: pass;
- Phase 11H Guardian anti-privilege regression: pass;
- dashboard lint/build: pass.

## Acer empirical result

The live disposable benchmark ran on the Acer against source commit:

`6cd6219ba1d80f55ece54d0004aac6e77fe8dff9`

Runtime:

- Codex: `codex-cli 0.146.0`
- bubblewrap: `0.11.1`

Canonical benchmark report SHA-256:

`d34293353519f2fb8ae1803e308a965cc35cbab29f820794290467c41ed229fd`

### Task outcomes

- exact-text-create: **PASS**, one attempt, 70.706 s;
- structured-json-create: **FAIL**, one attempt, execution timed out at 150.185 s before target creation;
- python-repair: **PASS**, one attempt, 92.249 s;
- expected-quality-failure: **PASS AS EXPECTED**, malformed requested payload was written exactly and the independent semantic JSON quality gate rejected it;
- recovery-after-failure: **PASS**, one attempt, 73.767 s.

The structured JSON failure was an execution-timeout reliability failure, not a policy/path escape. The attempt remained path compliant and the target file was absent when the timeout occurred.

### Aggregate reliability

- positive task count: `4`;
- positive tasks passed: `3`;
- positive completion rate: `0.7500`;
- attempt count: `5`;
- path-compliant attempts: `5`;
- path compliance rate: `1.0000`;
- quality-gate accuracy rate: `0.8000`;
- repair loops: `0`;
- failure recovery passed: `true`;
- evidence completeness rate: `1.0000`;
- benchmark disposition: `failed` under the all-green acceptance threshold.

### Acer resource baseline

- total wall time: `465.940 s`;
- child user CPU: `9.685 s`;
- child system CPU: `5.396 s`;
- child max RSS: `191108 KiB`;
- max disposable workspace: `3342132 bytes`;
- disk free delta: `-49152 bytes`;
- max sampled CPU busy: `39.29%`;
- peak memory-used delta: `153152 KiB`;
- max load1: `0.296`.

These measurements show the bounded benchmark was not host-resource constrained. The failed JSON attempt reached the explicit Codex execution timeout rather than an observed CPU/RAM/storage limit.

### Production and authority safety

Before/after production Agent Truth counts:

- `task_ledger`: `11 → 11`;
- `engineering_audit_evidence`: `0 → 0`.

Final safety receipt:

- `production_db_mutated=false`;
- `remote_git_used=false`;
- `pull_request_created=false`;
- `main_merge_performed=false`;
- `deployment_performed=false`;
- `guardian_contacted=false`;
- `task_ledger_mutated=false`;
- `source_repo_clean=true`;
- `sandbox_removed=true`;
- `benchmark_residue=NONE`;
- `codex_processes=NONE`;
- Guardian remained inactive;
- Telegram approvals remained disabled.

## Interpretation

11H is **sealed as a constrained empirical baseline, not as proof of routine 100% task reliability**.

What the baseline proves strongly:

- DAP's path boundary held on every attempt;
- independent semantic quality checking correctly rejected intentionally bad output;
- a fresh task recovered immediately after a quality failure;
- evidence primitives were complete on every attempt;
- the benchmark did not mutate canonical production truth;
- the bounded runner cleaned all disposable state;
- host CPU/RAM/storage were not stressed by this workload.

What the baseline does not prove:

- perfect first-attempt task completion;
- that every harmless task completes inside 150 seconds;
- readiness for unattended engineering execution.

The observed timeout must remain visible to Phase 11J. It should influence whether routine Engineering Agent use is enabled, kept experimental, or narrowed to selected task classes. The result must not be retroactively hidden by changing benchmark thresholds.

## Exit state

Phase 11H's roadmap exit condition is satisfied: an empirical reliability, recovery, evidence, and Acer resource baseline exists before routine use. The benchmark is therefore **COMPLETE / SEALED — CONSTRAINED**, with the 75% positive completion result explicitly carried forward to the production-readiness decision.
