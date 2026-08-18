# Phase 11J — Production Readiness Decision

## Decision

**NARROW SUPPORTED TASK CLASSES / LIMITED OWNER-REVIEWED PILOT.**

Phase 11 is complete as a bounded engineering capability, but it is **not** approved for broad autonomous engineering, automatic company routing, autonomous merge, release, deployment, or privileged host administration.

The machine-readable decision is implemented in:

- `platform/backend/engineering/production_readiness.py`
- `platform/backend/tests/test_production_readiness.py`
- `platform/guardian/tests/test_phase11j_production_readiness_boundary.py`

## Why the decision is constrained

The Phase 11H fixed empirical benchmark produced a mixed reliability result while preserving the safety boundary:

- four positive tasks were defined;
- three positive tasks passed;
- positive completion rate: **0.75**;
- path compliance rate: **1.00**;
- evidence completeness rate: **1.00**;
- failure recovery: **passed**;
- production Agent Truth mutation: **none**;
- source repository remained clean;
- disposable sandbox cleanup passed;
- the only positive-task failure was `structured-json-create`, which timed out at the fixed 150-second execution ceiling before creating its target file.

Canonical benchmark report SHA-256:

`d34293353519f2fb8ae1803e308a965cc35cbab29f820794290467c41ed229fd`

This means the safety architecture is substantially stronger than the observed first-pass task reliability. Phase 11J therefore does not upgrade the 75% result into a claim of general production autonomy.

## Phase 11I owner-review evidence

The final disposable owner-review smoke ran on Acer from source commit:

`9d55ef80d4764758c94fb37c8d474f0218734b4f`

Observed runtime evidence:

- dashboard review page: HTTP 200;
- review list: HTTP 200;
- one pending disposable review before decision;
- approve POST: HTTP 200;
- approval effect: `record_review_only`;
- separate owner merge action still required: true;
- conflicting reject after approval: HTTP 409;
- immutable first decision preserved;
- disposable canonical task unchanged;
- production `task_ledger`: 11 → 11;
- production `engineering_audit_evidence`: 0 → 0;
- production `engineering_owner_review_decisions`: 0 → 0;
- production DB mutated: false;
- Git write performed: false;
- pull request merged: false;
- main merge performed: false;
- deployment performed: false;
- Guardian contacted: false;
- task ledger mutated: false;
- live services restarted: false;
- Docker used: false;
- npm registry used on Acer: false;
- source repository clean: true;
- smoke disposition: succeeded;
- sandbox removed: true;
- artifact residue: none;
- preview processes: none;
- Guardian remained inactive;
- Telegram approvals remained disabled.

This proves owner review can be recorded without converting review approval into execution, merge, deployment, or canonical task authority.

## Routine pilot task classes

Only the following classes are approved for routine owner-reviewed pilot use:

1. `exact_text_one_file`
   - exactly one changed file;
   - exact deterministic expected content;
   - no network or package installation;
   - draft PR delivery;
   - owner review required.

2. `deterministic_one_file_repair`
   - exactly one changed file;
   - simple repair of an existing tracked file;
   - deterministic machine-verifiable acceptance;
   - no network or package installation;
   - draft PR delivery;
   - owner review required.

These are the task shapes that demonstrated successful bounded behavior in the empirical Phase 11 benchmark.

## Not approved for routine use

The following remain outside the routine Phase 11 pilot:

- structured JSON generation;
- multi-file general engineering work;
- network-required engineering;
- dependency/package installation;
- protected control-plane changes;
- privileged host or runtime administration;
- Guardian/root/systemd/Docker operations;
- production-secret access;
- automatic routing to `engineering-agent`;
- automatic Git publication beyond the already bounded draft-PR delivery path;
- automatic merge;
- merge to `main`;
- release/tag creation;
- deployment.

The observed structured-JSON timeout is specifically preserved as negative evidence. That class must be re-benchmarked before it can be promoted.

## Company routing remains unchanged

The live company role `software-engineer` remains mapped to:

`coding-agent`

It is **not** remapped to `engineering-agent` in Phase 11J.

This is intentional. The Engineering Agent capability is available only behind the bounded Phase 11 workflow and is not made the default company software-engineering worker by this milestone.

## Hard routine ceiling

The machine-readable Phase 11J ceiling requires:

- maximum changed files: **1**;
- deterministic acceptance: required;
- draft PR: required;
- owner review: required;
- network access: false;
- package installation: false;
- privileged host access: false;
- direct Guardian access: false;
- Docker/systemd access: false;
- production-secret access: false;
- automatic routing: false;
- automatic merge: false;
- main merge: false;
- release: false;
- deployment: false.

## Expansion rule

Any expansion beyond the two routine task classes requires both:

1. a new empirical benchmark demonstrating the proposed task class under the same bounded DAP execution path; and
2. a new explicit owner milestone/decision.

A future milestone may improve reliability, add task classes, or intentionally activate company routing. Phase 11 itself does not grant that authority.

## Final interpretation

Phase 11 succeeded in building the **hands** of DAP without giving those hands control of the company.

The Engineering Agent can now prepare bounded work, execute inside a disposable workspace, produce evidence, deliver a draft PR, and receive an immutable owner review decision. However, the first empirical reliability benchmark does not justify broad autonomy.

Therefore the final Phase 11 production-readiness disposition is:

> **LIMITED OWNER-REVIEWED PILOT — NARROW TASK CLASSES ONLY.**

No Phase 11 outcome authorizes autonomous merge or deployment.
