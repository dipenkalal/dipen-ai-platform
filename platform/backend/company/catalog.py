from company.registry import OrganizationRegistry
from company.schemas import DepartmentDefinition, RoleDefinition


CONSTITUTION = "docs/dap-company-operating-constitution.md"
EXECUTIVE_CHARTERS = "docs/dap-initial-executive-role-charters.md"
OWNER_RATIFICATION = "docs/dap-company-owner-ratification.md"


def _department(
    department_id: str,
    name: str,
    mission: str,
    head_role_id: str,
    *,
    independent_control: bool = False,
    leads_cross_department_projects: bool = False,
) -> DepartmentDefinition:
    return DepartmentDefinition(
        id=department_id,
        name=name,
        mission=mission,
        head_role_id=head_role_id,
        independent_control=independent_control,
        leads_cross_department_projects=(
            leads_cross_department_projects
        ),
        source_document=CONSTITUTION,
    )


def _manager(
    role_id: str,
    title: str,
    department_id: str,
    reports_to_role_id: str,
    mission: str,
    *,
    role_kind: str = "manager",
    career_level: str = "director",
    employment_status: str = "planned",
    authority: tuple[str, ...] = (),
    prohibited_actions: tuple[str, ...] = (),
    approved_systems: tuple[str, ...] = (),
    evidence_requirements: tuple[str, ...] = (),
    approval_requirements: tuple[str, ...] = (),
    escalation_role_ids: tuple[str, ...] = ("guardian-ceo",),
    autonomy_ceiling: str = "assist",
    source_document: str = EXECUTIVE_CHARTERS,
) -> RoleDefinition:
    return RoleDefinition(
        id=role_id,
        title=title,
        department_id=department_id,
        reports_to_role_id=reports_to_role_id,
        role_kind=role_kind,
        career_level=career_level,
        runtime_kind="deterministic_service",
        employment_status=employment_status,
        permanent=True,
        manager_only=True,
        mission=mission,
        responsibilities=[
            "Plan and assign work within the role's authority.",
            "Monitor evidence, progress, risk, and escalation conditions.",
            "Review outcomes without performing specialist labour.",
        ],
        authority=list(authority),
        prohibited_actions=[
            "Perform specialist labour assigned to a qualified employee.",
            "Bypass company approval, privacy, or evidence policy.",
            *prohibited_actions,
        ],
        approved_systems=list(approved_systems),
        evidence_requirements=[
            "Use machine-verifiable records for material decisions.",
            *evidence_requirements,
        ],
        approval_requirements=list(approval_requirements),
        escalation_role_ids=list(escalation_role_ids),
        autonomy_ceiling=autonomy_ceiling,
        source_document=source_document,
    )


def _specialist(
    role_id: str,
    title: str,
    department_id: str,
    reports_to_role_id: str,
    mission: str,
    *,
    employment_status: str = "planned",
    machine_agent_id: str | None = None,
    career_level: str = "specialist",
    responsibilities: tuple[str, ...] = (),
    approved_systems: tuple[str, ...] = (),
    prohibited_actions: tuple[str, ...] = (),
    evidence_requirements: tuple[str, ...] = (),
    escalation_role_ids: tuple[str, ...] = (),
) -> RoleDefinition:
    return RoleDefinition(
        id=role_id,
        title=title,
        department_id=department_id,
        reports_to_role_id=reports_to_role_id,
        role_kind="specialist",
        career_level=career_level,
        runtime_kind="model_agent",
        employment_status=employment_status,
        permanent=True,
        manager_only=False,
        machine_agent_id=machine_agent_id,
        mission=mission,
        responsibilities=list(responsibilities),
        authority=[
            "Perform bounded cognitive work within the employment charter."
        ],
        prohibited_actions=[
            "Approve the role's own high-impact work.",
            "Invent evidence, progress, access, or completion state.",
            "Use tools outside the approved role charter.",
            *prohibited_actions,
        ],
        approved_systems=list(approved_systems),
        evidence_requirements=[
            "Return assumptions, limitations, and supporting evidence.",
            *evidence_requirements,
        ],
        approval_requirements=[
            "External or destructive actions require the applicable preview "
            "and approval workflow."
        ],
        escalation_role_ids=list(
            escalation_role_ids or (reports_to_role_id,)
        ),
        autonomy_ceiling="assist",
        source_document=CONSTITUTION,
    )


DEPARTMENTS: tuple[DepartmentDefinition, ...] = (
    _department(
        "executive-office",
        "Executive Office",
        "Own executive supervision, planning, policy, audit, and escalation.",
        "guardian-ceo",
    ),
    _department(
        "product-programs",
        "Product and Program Management",
        "Own requirements, roadmap, projects, milestones, and progress truth.",
        "director-product-programs",
        leads_cross_department_projects=True,
    ),
    _department(
        "engineering",
        "Engineering",
        "Own architecture, implementation, code quality, and release readiness.",
        "director-engineering",
    ),
    _department(
        "infrastructure-operations",
        "Infrastructure and Operations",
        "Own homelab, services, reliability, deployments, and recovery.",
        "director-infrastructure-operations",
    ),
    _department(
        "data-knowledge-intelligence",
        "Data, Knowledge and Intelligence",
        "Own knowledge retrieval, research, analytics, and structured data work.",
        "director-data-intelligence",
    ),
    _department(
        "documentation-communications",
        "Documentation and Communications",
        "Own technical documentation, reports, applications, and communication.",
        "director-documentation-communications",
    ),
    _department(
        "quality-verification",
        "Quality Assurance and Verification",
        "Independently verify requirements, evidence, tests, and acceptance.",
        "director-quality-verification",
        independent_control=True,
    ),
    _department(
        "security-risk-governance",
        "Security, Risk and Governance",
        "Own access, privacy, risk controls, and authority to pause unsafe work.",
        "chief-security-governance",
        independent_control=True,
    ),
    _department(
        "strategy-innovation",
        "Strategy and Innovation",
        "Own long-term strategy, experimentation, and capability development.",
        "director-strategy-innovation",
    ),
    _department(
        "personal-corporate-services",
        "Personal and Corporate Services",
        "Own personal administration, career, expense, and support workflows.",
        "director-personal-corporate-services",
    ),
)


ROLES: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        id="dipen-owner",
        title="Founder, Owner and Final Approver",
        department_id=None,
        reports_to_role_id=None,
        role_kind="owner",
        career_level="owner",
        runtime_kind="human_authority",
        employment_status="active",
        permanent=True,
        manager_only=True,
        mission="Define company purpose and retain final authority over DAP.",
        responsibilities=[
            "Set company goals and risk tolerance.",
            "Approve destructive, externally binding, or critical actions.",
            "Approve permanent headcount and constitutional changes.",
        ],
        authority=[
            "Final authority over company policy, roles, and critical actions."
        ],
        prohibited_actions=[],
        approved_systems=["owner approval interface", "audit records"],
        evidence_requirements=[
            "Material approvals must identify the proposed action and impact."
        ],
        approval_requirements=[],
        escalation_role_ids=[],
        autonomy_ceiling="operate",
        source_document=OWNER_RATIFICATION,
    ),
    RoleDefinition(
        id="guardian-ceo",
        title="Chief Executive Officer",
        department_id="executive-office",
        reports_to_role_id="dipen-owner",
        role_kind="executive",
        career_level="executive",
        runtime_kind="executive_service",
        employment_status="active",
        permanent=True,
        manager_only=True,
        mission=(
            "Interpret owner objectives, supervise the company, delegate work, "
            "and return evidence-backed executive outcomes."
        ),
        responsibilities=[
            "Classify questions, plans, assignments, and privileged actions.",
            "Split multi-part objectives and assign accountable departments.",
            "Monitor progress, evidence, failure, capacity, and escalation.",
            "Create temporary teams within deterministic capacity policy.",
        ],
        authority=[
            "Set per-task autonomy within company policy.",
            "Reassign work, request independent review, and retry cognitive work.",
            "Reject requests that would destructively damage the platform.",
        ],
        prohibited_actions=[
            "Perform specialist labour when a qualified department exists.",
            "Execute hypothetical questions.",
            "Bypass owner approval for critical or destructive actions.",
        ],
        approved_systems=[
            "company registry",
            "task ledger",
            "agent truth",
            "planning and delegation services",
        ],
        evidence_requirements=[
            "Executive claims must cite authoritative company evidence."
        ],
        approval_requirements=[
            "Escalate destructive, critical, privacy-sensitive, costly, or "
            "externally binding actions to the owner."
        ],
        escalation_role_ids=["dipen-owner"],
        autonomy_ceiling="operate",
        source_document=EXECUTIVE_CHARTERS,
    ),
    _manager(
        "chief-of-staff",
        "Chief of Staff and Planning Director",
        "executive-office",
        "guardian-ceo",
        "Convert complex objectives into deterministic, non-executing plans.",
        career_level="director",
        authority=(
            "Create proposed parent and child objective structures.",
            "Identify dependencies, sequencing, and accountable departments.",
        ),
        approved_systems=("company registry", "planning service"),
    ),
    _manager(
        "chief-risk-policy",
        "Chief Risk and Policy Officer",
        "executive-office",
        "guardian-ceo",
        "Classify risk, autonomy, approval, and policy boundaries.",
        role_kind="control",
        career_level="executive",
        authority=(
            "Pause or reject work that violates ratified policy.",
            "Require approval, rollback, or independent verification.",
        ),
        approved_systems=("policy engine", "approval records"),
        escalation_role_ids=("guardian-ceo", "dipen-owner"),
    ),
    _manager(
        "chief-audit-compliance",
        "Chief Audit and Compliance Officer",
        "executive-office",
        "dipen-owner",
        "Independently audit authority, evidence, approvals, and outcomes.",
        role_kind="control",
        career_level="executive",
        authority=(
            "Inspect company audit records independently from management.",
            "Report unsupported claims or policy violations to the owner.",
        ),
        approved_systems=("read-only audit ledger", "evidence records"),
        escalation_role_ids=("dipen-owner",),
        autonomy_ceiling="observe",
    ),
    _manager(
        "director-product-programs",
        "Director of Product and Programs",
        "product-programs",
        "guardian-ceo",
        "Own portfolio priorities, requirements, roadmap, and delivery truth.",
        authority=(
            "Set project ownership and program priorities within CEO direction.",
        ),
        approved_systems=("project registry", "portfolio evidence"),
    ),
    _manager(
        "senior-project-manager",
        "Senior Project Manager",
        "product-programs",
        "director-product-programs",
        "Lead cross-department projects and maintain accountable execution plans.",
        career_level="manager",
        authority=(
            "Create and coordinate parent-child project work structures.",
            "Choose parallel or sequential work from dependencies and capacity.",
        ),
        approved_systems=("task ledger", "company registry", "project registry"),
    ),
    _specialist(
        "portfolio-progress-analyst",
        "Portfolio and Progress Analyst",
        "product-programs",
        "senior-project-manager",
        "Produce evidence-backed DAP roadmap and progress reporting.",
        responsibilities=(
            "Correlate deployed versions, Git evidence, CI, tasks, and acceptance.",
            "Separate planned, developed, tested, merged, deployed, and accepted.",
        ),
        approved_systems=(
            "read-only project registry",
            "read-only repository evidence",
            "read-only task and deployment evidence",
        ),
        evidence_requirements=(
            "Never infer complete project history from one worker response.",
        ),
    ),
    _manager(
        "director-engineering",
        "Director of Engineering",
        "engineering",
        "guardian-ceo",
        "Own software architecture, engineering standards, and delivery quality.",
        approved_systems=("engineering work queue", "repository evidence"),
    ),
    _specialist(
        "software-engineer",
        "Software Engineer",
        "engineering",
        "director-engineering",
        "Design, generate, review, refactor, and troubleshoot software.",
        employment_status="active",
        machine_agent_id="coding-agent",
        responsibilities=(
            "Produce maintainable code and implementation guidance.",
            "Report assumptions, test limitations, and integration risk.",
        ),
        approved_systems=("bounded coding tools",),
    ),
    _specialist(
        "solutions-architect",
        "Solutions Architect",
        "engineering",
        "director-engineering",
        "Design service, application, data, and integration architecture.",
        career_level="senior",
    ),
    _specialist(
        "release-engineer",
        "Release Engineer",
        "engineering",
        "director-engineering",
        "Prepare versioned releases, manifests, rollback, and release evidence.",
        career_level="senior",
    ),
    _manager(
        "director-infrastructure-operations",
        "Director of Infrastructure and Operations",
        "infrastructure-operations",
        "guardian-ceo",
        "Own infrastructure reliability, operations, deployment, and recovery.",
        approved_systems=("operations work queue", "runtime truth"),
    ),
    _specialist(
        "site-reliability-engineer",
        "Site Reliability Engineer",
        "infrastructure-operations",
        "director-infrastructure-operations",
        "Analyse infrastructure, deployment health, and operational risk.",
        employment_status="active",
        machine_agent_id="devops-agent",
        responsibilities=(
            "Provide Docker, service, deployment, and remediation guidance.",
        ),
        approved_systems=("system.status",),
    ),
    _specialist(
        "systems-engineer",
        "Systems Engineer",
        "infrastructure-operations",
        "director-infrastructure-operations",
        "Inspect host resources, service health, and system warnings.",
        employment_status="active",
        machine_agent_id="system-agent",
        responsibilities=(
            "Report CPU, memory, disk, uptime, and bounded health evidence.",
        ),
        approved_systems=("system.status",),
    ),
    _specialist(
        "backup-recovery-engineer",
        "Backup and Recovery Engineer",
        "infrastructure-operations",
        "director-infrastructure-operations",
        "Design, verify, and report backup and recovery readiness.",
        career_level="senior",
    ),
    _manager(
        "director-data-intelligence",
        "Director of Data and Intelligence",
        "data-knowledge-intelligence",
        "guardian-ceo",
        "Own knowledge, research, analytics, and structured-data standards.",
        approved_systems=("knowledge registry", "data work queue"),
    ),
    _specialist(
        "knowledge-specialist",
        "Knowledge Specialist",
        "data-knowledge-intelligence",
        "director-data-intelligence",
        "Answer questions from indexed documents with grounded sources.",
        employment_status="active",
        machine_agent_id="knowledge-agent",
        approved_systems=("knowledge.search", "knowledge.ask"),
    ),
    _specialist(
        "research-analyst",
        "Research Analyst",
        "data-knowledge-intelligence",
        "director-data-intelligence",
        "Investigate topics and synthesize available evidence.",
        employment_status="active",
        machine_agent_id="research-agent",
        approved_systems=("knowledge.search",),
    ),
    _specialist(
        "sql-specialist",
        "Data Analyst and SQL Specialist",
        "data-knowledge-intelligence",
        "director-data-intelligence",
        "Design safe SQL and structured-data analysis plans.",
        employment_status="disabled",
        machine_agent_id="sql-agent",
        prohibited_actions=(
            "Execute database changes before database policy is activated.",
        ),
    ),
    _manager(
        "director-documentation-communications",
        "Director of Documentation and Communications",
        "documentation-communications",
        "guardian-ceo",
        "Own technical writing, company documentation, and communication quality.",
        approved_systems=("documentation work queue",),
    ),
    _specialist(
        "technical-writer",
        "Technical Writer",
        "documentation-communications",
        "director-documentation-communications",
        "Create technical documents, runbooks, reports, and release notes.",
        employment_status="active",
        machine_agent_id="documentation-agent",
    ),
    _specialist(
        "career-communications-specialist",
        "Career Communications Specialist",
        "documentation-communications",
        "director-documentation-communications",
        "Prepare resumes, applications, letters, and professional communication.",
    ),
    _manager(
        "director-quality-verification",
        "Director of Quality and Verification",
        "quality-verification",
        "guardian-ceo",
        "Independently own verification, acceptance, and release confidence.",
        role_kind="control",
        authority=(
            "Block acceptance when required evidence or tests are missing.",
        ),
        approved_systems=("test evidence", "acceptance records"),
        escalation_role_ids=("guardian-ceo", "dipen-owner"),
    ),
    _specialist(
        "qa-engineer",
        "Quality Assurance Engineer",
        "quality-verification",
        "director-quality-verification",
        "Create and execute independent test and regression plans.",
    ),
    _specialist(
        "evidence-verification-analyst",
        "Evidence Verification Analyst",
        "quality-verification",
        "director-quality-verification",
        "Validate that claims, completion, and acceptance match evidence.",
    ),
    _manager(
        "chief-security-governance",
        "Chief Security and Governance Officer",
        "security-risk-governance",
        "guardian-ceo",
        "Own access, privacy, security controls, and unsafe-work stoppage.",
        role_kind="control",
        career_level="executive",
        authority=(
            "Immediately pause unsafe or unauthorized work.",
            "Require privacy, access, or threat review before activation.",
        ),
        approved_systems=("policy engine", "access metadata", "security audit"),
        escalation_role_ids=("guardian-ceo", "dipen-owner"),
    ),
    _specialist(
        "security-engineer",
        "Security Engineer",
        "security-risk-governance",
        "chief-security-governance",
        "Assess technical security, secrets, boundaries, and threat controls.",
    ),
    _specialist(
        "privacy-access-officer",
        "Privacy and Access Officer",
        "security-risk-governance",
        "chief-security-governance",
        "Review identity, data boundaries, permissions, and privacy compliance.",
    ),
    _manager(
        "director-strategy-innovation",
        "Director of Strategy and Innovation",
        "strategy-innovation",
        "guardian-ceo",
        "Own long-term direction, experimentation, and capability investments.",
        approved_systems=("strategy portfolio", "capability proposals"),
    ),
    _specialist(
        "innovation-architect",
        "Innovation Architect",
        "strategy-innovation",
        "director-strategy-innovation",
        "Design experiments and future platform capability concepts.",
        career_level="senior",
    ),
    _specialist(
        "capability-research-analyst",
        "Capability Research Analyst",
        "strategy-innovation",
        "director-strategy-innovation",
        "Identify capability gaps and compare implementation approaches.",
    ),
    _manager(
        "director-personal-corporate-services",
        "Director of Personal and Corporate Services",
        "personal-corporate-services",
        "guardian-ceo",
        "Own personal administration and lightweight corporate service delivery.",
        approved_systems=("personal service queue", "user permission metadata"),
    ),
    _specialist(
        "executive-assistant",
        "Executive Assistant",
        "personal-corporate-services",
        "director-personal-corporate-services",
        "Coordinate authorized email, calendar, reminders, and personal records.",
    ),
    _specialist(
        "career-applications-specialist",
        "Career and Applications Specialist",
        "personal-corporate-services",
        "director-personal-corporate-services",
        "Coordinate evidence-backed job application workflows.",
    ),
    _specialist(
        "expense-budget-analyst",
        "Expense and Budget Analyst",
        "personal-corporate-services",
        "director-personal-corporate-services",
        "Track expenses and provide budgeting and decision support.",
        prohibited_actions=(
            "Transfer funds, trade, purchase, or modify financial accounts.",
        ),
    ),
    _specialist(
        "procurement-administration-specialist",
        "Procurement and Administration Specialist",
        "personal-corporate-services",
        "director-personal-corporate-services",
        "Compare purchases and coordinate approved administrative workflows.",
        prohibited_actions=(
            "Complete purchases without exact preview and user approval.",
        ),
    ),
)


company_registry = OrganizationRegistry(
    DEPARTMENTS,
    ROLES,
    registry_version="1.0.0",
)
