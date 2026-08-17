# Phase 11H — Disposable Engineering Benchmark

## Status

**IMPLEMENTATION + CI COMPLETE / ACER EMPIRICAL BENCHMARK PENDING.**

Phase 11H measures the reliability and host cost of the bounded Engineering Agent execution path before routine owner-reviewed use is considered.

## Governing rule

> Benchmark the employee without giving the employee more authority.

The benchmark uses the same DAP-owned work-order, execution-ticket, Guardian-admission, and bounded Codex runner chain sealed in 11B–11D. It does not add Git delivery, remote publication, merge, deployment, Guardian/root execution, Docker/systemd, or live task-ledger authority.

## Fixed task matrix

The benchmark runs five ordered task classes from fresh tracked-file-only snapshots:

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

A benchmark run is accepted only if all of the following are true:

- all four positive tasks pass;
- all attempts remain path compliant;
- all five task outcomes match their expected quality behavior;
- the expected semantic-quality failure is followed by a successful recovery task;
- evidence completeness is 100%;
- production Agent Truth row counts are unchanged;
- the source repository remains clean;
- the benchmark sandbox is removed.

No minimum/maximum host performance threshold is hidden inside the pass decision. CPU/RAM/storage/latency are measured empirically and will be interpreted after the Acer run rather than retrofitted to force a pass/fail outcome.

## Safety regression

`platform/guardian/tests/test_phase11h_benchmark_boundary.py` statically proves the benchmark does not import actual Guardian/root authorization surfaces or contain Guardian socket/service, systemd, Docker-socket, GitHub-token, Git push, `gh pr`, remote publisher, or local Git-delivery execution paths.

## CI validation

Benchmark code:

- `platform/backend/engineering/engineering_benchmark.py`
- `platform/backend/engineering/benchmark_fixtures/phase11h_repair_target.py`
- `platform/backend/tests/test_engineering_benchmark.py`
- `platform/guardian/tests/test_phase11h_benchmark_boundary.py`

The dedicated Phase 11 workflow explicitly includes the benchmark in Ruff, mypy, compile, pytest, and Guardian regression jobs.

Validation head before this documentation checkpoint:

`c7450a5f572603b87c3e05f50810894cae80941f`

At that head:

- Phase 11 benchmark/backend Ruff: pass;
- Phase 11 benchmark/backend mypy: pass;
- Phase 11 benchmark/backend compile: pass;
- Phase 11 engineering tests including benchmark unit tests: pass;
- Phase 11H Guardian anti-privilege regression: pass.

The ordinary repository CI, Phase 10 regression, Owner Channel, and dashboard regression are required to be green on the final pre-Acer benchmark head before the empirical run is authorized.

## Exit state

11H must not be marked **COMPLETE / SEALED** until the bounded multi-task benchmark has run on the Acer and its actual completion, quality, recovery, latency, CPU/RAM/storage, evidence, production-row-count, repository-cleanliness, and cleanup receipt has been recorded.
