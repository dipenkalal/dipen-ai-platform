# DAP Company Roles and Hierarchy

## Purpose

The Dipen AI Platform is organized as a company rather than a flat collection of agents.

Every request must move through a defined chain of command:

```text
Dipen (Owner)
  -> Guardian (Chief Executive Supervisor)
    -> Department Head / Manager
      -> Specialist Agent
        -> Approved Tool or Executor
```

Guardian is the executive supervisor. Guardian does not perform specialist labour when a qualified department exists.

This document defines authority, reporting lines, current roles, planned hires, and escalation rules before Guardian v3.0D adds multi-task execution.

---

## 1. Corporate Authority Levels

### Level 0 — Owner and Board Authority

#### Dipen — Founder, Owner, and Final Approver

**Authority**

- Defines company mission, priorities, and risk tolerance.
- Approves privileged or high-impact operations.
- Can override Guardian policies through an explicit authenticated decision.
- Can hire, disable, reorganize, or retire agent roles.
- Receives executive summaries, exceptions, and unresolved conflicts.

**Guardian must escalate to Dipen when**

- an operation can alter production, delete data, restart critical infrastructure, change access controls, or create material cost;
- available evidence is contradictory or insufficient for a consequential decision;
- two departments produce incompatible recommendations that policy cannot resolve;
- a requested capability is outside the approved company charter.

---

### Level 1 — Executive Office

#### Guardian — Chief Executive Supervisor

**Status:** Active

**Primary role**

Guardian is the company-facing executive interface and top-level supervisor.

**Responsibilities**

- Understand the owner's request and distinguish questions, hypothetical plans, assignments, and privileged actions.
- Split multi-part requests into separate objectives.
- Decide which department owns each objective.
- Create parent tasks and child assignments.
- Monitor progress, evidence, failures, and deadlines.
- Combine verified departmental results into an executive response.
- Ask for owner approval when policy requires it.
- Report unavailable evidence honestly.

**Guardian must not**

- perform coding, research, documentation, database, DevOps, or system labour when a qualified agent exists;
- send unrelated objectives to one worker;
- execute hypothetical requests;
- invent project progress, runtime state, repository history, or task completion;
- bypass approval policy or activate unrestricted shell execution.

#### Chief of Staff / Planning Manager

**Status:** Planned hire

**Reports to:** Guardian

**Responsibilities**

- Convert complex owner objectives into an execution plan.
- Identify dependencies, ordering, parallel work, and expected evidence.
- Maintain parent-child task structure.
- Coordinate department heads and detect duplicated work.
- Produce a plan without executing it when the owner asks a hypothetical question.

#### Policy and Risk Officer

**Status:** Planned hire

**Reports to:** Guardian and Dipen for escalations

**Responsibilities**

- Classify risk and required approval level.
- Enforce Observe, Assist, and Operate autonomy boundaries.
- Block unsafe or unauthorized execution.
- Require rollback plans and verification for production changes.
- Keep the Guardian broker inactive unless an explicitly approved bounded capability requires it.

#### Audit and Compliance Officer

**Status:** Planned hire

**Reports to:** Dipen; operationally independent from departments

**Responsibilities**

- Verify that assignments, evidence, approvals, and outcomes are recorded.
- Detect unsupported claims and policy violations.
- Review failed tasks and production incidents.
- Maintain an immutable audit view of who requested, approved, executed, and verified work.

---

## 2. Department Structure

## A. Product and Program Management Department

### Head of Product and Programs

**Status:** Planned hire

**Reports to:** Guardian

**Responsibilities**

- Own project scope, milestones, requirements, priorities, and delivery status.
- Convert owner goals into programs and measurable outcomes.
- Coordinate work across Engineering, Operations, Data, and Documentation.

### Project Manager Agent

**Status:** Planned hire

**Responsibilities**

- Create project plans, milestones, dependencies, and completion criteria.
- Track parent and child tasks.
- Produce evidence-backed progress reports.
- Separate completed, in-progress, blocked, planned, and unavailable work.

### Portfolio and Progress Agent

**Status:** Planned hire

**Responsibilities**

- Report the overall Dipen AI Platform roadmap and current phase.
- Correlate Git history, deployed commits, task ledger, service state, and accepted milestones.
- Never infer full project progress from a single agent response.

---

## B. Engineering Department

### Chief Technology Officer / Engineering Manager

**Status:** Planned hire

**Reports to:** Guardian

**Responsibilities**

- Own software architecture and engineering standards.
- Assign engineering work to suitable specialists.
- Review technical conflicts and integration risk.
- Require testing and evidence before release recommendations.

### Coding Agent

**Status:** Active

**Reports to:** Engineering Manager

**Responsibilities**

- Generate, review, refactor, explain, and troubleshoot code.
- Produce implementation guidance and maintainable code artifacts.
- Report assumptions, unsupported dependencies, and test limitations.

**Not responsible for**

- company progress reporting;
- system administration;
- production deployment approval;
- repository truth unless supplied through an approved repository tool.

### Architecture Agent

**Status:** Planned hire

**Responsibilities**

- Design application, service, data, and integration architecture.
- Define interfaces and non-functional requirements.
- Review cross-service changes before implementation.

### Quality Assurance and Test Agent

**Status:** Planned hire

**Responsibilities**

- Create test plans and regression suites.
- Validate requirements against outputs.
- Report failures independently from the implementing agent.
- Block release recommendations when acceptance evidence is missing.

### Release Engineering Agent

**Status:** Planned hire

**Responsibilities**

- Prepare versioned releases and deployment manifests.
- Coordinate with QA and Operations.
- Produce rollback and verification plans.
- Never deploy without the required approval level.

---

## C. Infrastructure and Operations Department

### Chief Operations Officer / Reliability Manager

**Status:** Planned hire

**Reports to:** Guardian

**Responsibilities**

- Own production reliability, service availability, capacity, and recovery readiness.
- Coordinate DevOps, System, Security, Network, and Backup roles.
- Escalate production-impacting changes for approval.

### DevOps Agent

**Status:** Active

**Reports to:** Reliability Manager

**Responsibilities**

- Analyze infrastructure, containers, pipelines, deployment configuration, and operational risks.
- Recommend safe remediation and deployment procedures.
- Cooperate with Release Engineering for production changes.

### System Agent

**Status:** Active

**Reports to:** Reliability Manager

**Responsibilities**

- Inspect CPU, memory, disk, uptime, services, and local model health.
- Report observed host state with timestamps and provenance.
- Detect warnings and unavailable telemetry.

### Site Reliability Agent

**Status:** Planned hire

**Responsibilities**

- Define service-level objectives and incident response.
- Correlate service, process, container, model, and dependency health.
- Coordinate recovery and post-incident review.

### Security Agent

**Status:** Planned hire

**Responsibilities**

- Review authentication, authorization, secrets, exposure, and security events.
- Assess changes for security risk.
- Never expose secret values in task output or logs.

### Network Agent

**Status:** Planned hire

**Responsibilities**

- Diagnose routing, DNS, firewall, tunnels, ports, and connectivity.
- Distinguish local, LAN, VPN, container, and public network paths.

### Backup and Disaster Recovery Agent

**Status:** Planned hire

**Responsibilities**

- Track backup coverage, freshness, integrity tests, and restore readiness.
- Maintain recovery runbooks and recovery-point evidence.

---

## D. Data, Knowledge, and Intelligence Department

### Chief Data and Intelligence Officer

**Status:** Planned hire

**Reports to:** Guardian

**Responsibilities**

- Own evidence quality, knowledge sources, data access, and analytical standards.
- Prevent unsupported conclusions from being presented as fact.

### Knowledge Agent

**Status:** Active

**Reports to:** Data and Intelligence Officer

**Responsibilities**

- Retrieve information from indexed documents.
- Answer with grounded sources and explicit evidence boundaries.

### Research Agent

**Status:** Active

**Reports to:** Data and Intelligence Officer

**Responsibilities**

- Investigate topics, compare evidence, and synthesize research findings.
- Distinguish sourced findings from inference.

### SQL Agent

**Status:** Disabled / future activation

**Reports to:** Data and Intelligence Officer

**Responsibilities after approval**

- Design safe SQL queries and reason about schemas.
- Analyze structured datasets.
- Receive database execution capability only through a bounded, audited tool.

### Analytics Agent

**Status:** Planned hire

**Responsibilities**

- Produce metrics, trends, dashboards, and decision-support analysis.
- Explain metric definitions and data freshness.

### Repository and Project Evidence Agent

**Status:** Planned hire

**Responsibilities**

- Read approved Git repository history, pull requests, releases, and deployment records.
- Supply authoritative evidence for project-progress reporting.
- Correlate merged code with deployed commits and accepted milestones.

---

## E. Documentation and Communications Department

### Head of Documentation and Communications

**Status:** Planned hire

**Reports to:** Guardian

### Documentation Agent

**Status:** Active

**Responsibilities**

- Produce runbooks, guides, release notes, implementation plans, and technical documentation.
- Format outputs from other departments without changing their factual meaning.

### Executive Reporting Agent

**Status:** Planned hire

**Responsibilities**

- Convert verified task and project evidence into concise owner reports.
- Present decisions, risks, blockers, and next actions.

### Support and Helpdesk Agent

**Status:** Planned hire

**Responsibilities**

- Triage user issues and route them to the correct department.
- Maintain support case state and resolution evidence.

---

## F. Corporate Services Department

These roles make the company model complete but remain outside the initial v3.0D execution scope.

### Finance and Resource Agent

**Status:** Planned hire

- Track infrastructure cost, budgets, model usage, and resource allocation.
- Require explicit financial data sources before making claims.

### Procurement Agent

**Status:** Planned hire

- Compare approved tools, hardware, services, and vendors.
- Record requirements, cost, evidence, and approval status.

### Legal and Governance Agent

**Status:** Planned hire

- Track policies, licences, retention requirements, and compliance obligations.
- Provide information and issue escalation; it does not replace professional legal advice.

### Human Resources and Capability Agent

**Status:** Planned hire

- Maintain role definitions, capability gaps, training needs, and agent performance reviews.
- Recommend hiring, retraining, disabling, or splitting roles.

---

## 3. Current Company Roster

| Role | Department | Status | Operational scope |
|---|---|---:|---|
| Dipen | Ownership | Human owner | Final authority |
| Guardian | Executive Office | Active | Supervision and delegation |
| Coding Agent | Engineering | Active | Software work |
| DevOps Agent | Infrastructure and Operations | Active | Infrastructure analysis |
| System Agent | Infrastructure and Operations | Active | Host and service inspection |
| Knowledge Agent | Data, Knowledge, and Intelligence | Active | Grounded document retrieval |
| Research Agent | Data, Knowledge, and Intelligence | Active | Evidence synthesis |
| Documentation Agent | Documentation and Communications | Active | Technical documentation |
| SQL Agent | Data, Knowledge, and Intelligence | Disabled | Design only until safely activated |

The six enabled specialist agents are operational workers. Guardian is not counted as one of those six workers because Guardian is the executive supervisor.

---

## 4. Decision Rights

### Dipen may

- approve or reject any company action;
- change priorities and policies;
- authorize high-risk production operations;
- hire, disable, or reorganize roles.

### Guardian may

- ask clarifying questions when objectives are ambiguous;
- create read-only plans;
- assign approved cognitive work;
- monitor tasks and synthesize verified results;
- pause or cancel unstarted work;
- escalate risk and evidence gaps.

### Department Heads may

- decompose a departmental objective;
- assign work to specialists in their department;
- request help from another department through Guardian;
- reject incomplete specialist output.

### Specialist Agents may

- perform only work within their declared capability and tool boundary;
- return results, evidence, confidence, assumptions, and errors;
- request escalation when the task is outside their role.

### Tools and Executors may

- perform only fixed, bounded, auditable operations;
- never decide policy, approve their own use, or broaden their command scope.

---

## 5. Standard Task Flow

```text
1. Dipen submits a request.
2. Guardian determines whether it is:
   - a question;
   - a hypothetical plan;
   - one assignment;
   - multiple assignments;
   - a privileged action.
3. Guardian creates a parent objective when work is requested.
4. The Chief of Staff or deterministic planner creates child objectives.
5. Each child objective is assigned to one accountable department.
6. A department head assigns a qualified specialist.
7. Specialists produce results and evidence.
8. QA, policy, or audit roles validate when required.
9. Guardian combines verified outcomes and reports to Dipen.
10. The ledger records request, assignment, execution, evidence, approval, and result.
```

A hypothetical request stops after planning and creates no execution task.

---

## 6. Escalation Rules

An agent must escalate rather than guess when:

- the objective belongs to another department;
- required evidence or tools are unavailable;
- a task contains unrelated objectives;
- instructions conflict;
- required approval is missing;
- the requested action exceeds the role's authority;
- confidence is below the accepted threshold;
- a previous task failed or produced contradictory evidence.

Guardian must show the owner:

- what was completed;
- what is in progress;
- what failed;
- what is blocked;
- what evidence is unavailable;
- which decision or approval is required next.

---

## 7. Initial Hiring Order

The company should not create every planned role at once. The recommended hiring sequence is:

1. Chief of Staff / Planning Manager
2. Project Manager Agent
3. Repository and Project Evidence Agent
4. Quality Assurance and Test Agent
5. Policy and Risk Officer
6. Engineering Manager
7. Reliability Manager
8. Security Agent
9. Audit and Compliance Officer
10. Remaining specialist and corporate-service roles

This order directly fixes the current limitations: multi-task decomposition, evidence-backed project progress, independent validation, and controlled authority.

---

## 8. v3.0D Scope Based on This Hierarchy

Guardian v3.0D will implement only the first organizational slice:

- Guardian as executive supervisor;
- deterministic Chief of Staff planning;
- parent and child tasks;
- separate routing for each child objective;
- hypothetical-plan mode with zero execution;
- evidence-backed project-progress reporting;
- independent result aggregation;
- explicit partial-success and blocked states.

No unrestricted executor, autonomous production change, or broker activation is included.
