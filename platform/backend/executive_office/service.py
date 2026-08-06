import hashlib
import re
from dataclasses import dataclass

from company.catalog import company_registry
from company.schemas import RoleDefinition
from executive_office.schemas import (
    AuditDecision,
    AuditEntry,
    ChiefOfStaffDecision,
    ChiefOfStaffTask,
    DecisionDisposition,
    ExecutiveOfficeCapability,
    ExecutiveOfficeStatusResponse,
    ExecutivePlanRequest,
    ExecutivePlanResponse,
    ProjectPlanDecision,
    ProjectWorkItem,
    RiskFinding,
    RiskLevel,
    RiskPolicyDecision,
)


@dataclass(frozen=True)
class RoutingRule:
    terms: tuple[str, ...]
    role_id: str


ROUTING_RULES = (
    RoutingRule(
        ("code", "program", "software", "python", "javascript", " c "),
        "software-engineer",
    ),
    RoutingRule(
        ("deploy", "docker", "server", "infrastructure", "service"),
        "site-reliability-engineer",
    ),
    RoutingRule(
        ("system", "linux", "network", "storage", "hardware"),
        "systems-engineer",
    ),
    RoutingRule(
        ("research", "compare", "investigate", "paper"),
        "research-analyst",
    ),
    RoutingRule(
        ("document", "report", "summary", "runbook", "progress"),
        "technical-writer",
    ),
    RoutingRule(
        ("knowledge", "retrieve", "files", "archive"),
        "knowledge-specialist",
    ),
)

HIGH_RISK_TERMS = (
    "delete",
    "destroy",
    "production deploy",
    "restart production",
    "permission",
    "credential",
    "secret",
    "payment",
    "purchase",
    "send email",
    "publish",
)
BLOCKED_TERMS = (
    "disable safety",
    "bypass approval",
    "unrestricted shell",
    "activate broker",
)
EXTERNAL_ACTION_TERMS = (
    "send",
    "publish",
    "purchase",
    "deploy",
    "restart",
    "delete",
    "modify account",
)


class ExecutiveOfficeService:
    version = "0.1.0"

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip()).lower()

    def _decision_id(self, request: ExecutivePlanRequest) -> str:
        canonical = "|".join(
            [request.requested_by, *request.objectives, *request.constraints]
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
        return f"executive-decision-{digest}"

    def _route_role(self, objective: str) -> RoleDefinition:
        normalized = f" {self._normalize(objective)} "

        for rule in ROUTING_RULES:
            if any(term in normalized for term in rule.terms):
                return company_registry.get_role(rule.role_id)

        return company_registry.get_role("research-analyst")

    def _risk_for_task(
        self,
        task_id: str,
        objective: str,
        allow_external_actions: bool,
    ) -> RiskFinding:
        normalized = self._normalize(objective)
        blocked_matches = [term for term in BLOCKED_TERMS if term in normalized]
        high_matches = [term for term in HIGH_RISK_TERMS if term in normalized]
        external_matches = [
            term for term in EXTERNAL_ACTION_TERMS if term in normalized
        ]

        if blocked_matches:
            return RiskFinding(
                task_id=task_id,
                risk_level="blocked",
                approval_required=True,
                reasons=[
                    "Objective requests a prohibited control-plane action.",
                    *[f"Matched prohibited term: {term}" for term in blocked_matches],
                ],
                prohibited_actions=blocked_matches,
            )

        approval_required = bool(high_matches) or (
            bool(external_matches) and not allow_external_actions
        )
        risk_level: RiskLevel = "high" if approval_required else "low"
        reasons = ["No privileged or external mutation was detected."]

        if high_matches:
            reasons = [
                "Objective may change production, access, money, or external state.",
                *[f"Matched controlled term: {term}" for term in high_matches],
            ]
        elif external_matches:
            reasons = [
                "Objective contains an external action and execution permission is absent.",
                *[f"Matched external term: {term}" for term in external_matches],
            ]

        return RiskFinding(
            task_id=task_id,
            risk_level=risk_level,
            approval_required=approval_required,
            reasons=reasons,
        )

    def status(self) -> ExecutiveOfficeStatusResponse:
        definitions = (
            (
                "chief-of-staff-planning",
                "chief-of-staff",
                "Decompose owner objectives into bounded tasks and dependencies.",
            ),
            (
                "risk-policy-review",
                "chief-risk-policy",
                "Classify risk and identify owner approval requirements.",
            ),
            (
                "project-plan-construction",
                "senior-project-manager",
                "Create work items, assignments, and acceptance evidence.",
            ),
            (
                "independent-audit-record",
                "chief-audit-compliance",
                "Record decision evidence without executing work.",
            ),
        )
        capabilities = []

        for service_id, role_id, description in definitions:
            role = company_registry.get_role(role_id)
            capabilities.append(
                ExecutiveOfficeCapability(
                    service_id=service_id,
                    acting_role_id=role_id,
                    registry_employment_status=role.employment_status,
                    description=description,
                )
            )

        return ExecutiveOfficeStatusResponse(
            version=self.version,
            capabilities=capabilities,
        )

    def plan(self, request: ExecutivePlanRequest) -> ExecutivePlanResponse:
        decision_id = self._decision_id(request)
        chief_tasks: list[ChiefOfStaffTask] = []
        risk_findings: list[RiskFinding] = []
        work_items: list[ProjectWorkItem] = []

        for index, objective in enumerate(request.objectives, start=1):
            normalized_objective = objective.strip()
            task_id = f"{decision_id}-task-{index}"
            role = self._route_role(normalized_objective)
            finding = self._risk_for_task(
                task_id,
                normalized_objective,
                request.allow_external_actions,
            )
            status = (
                "blocked"
                if finding.risk_level == "blocked"
                else "approval_required"
                if finding.approval_required
                else "planned"
            )

            chief_tasks.append(
                ChiefOfStaffTask(
                    task_id=task_id,
                    objective=normalized_objective,
                    sequence=index,
                    suggested_role_id=role.id,
                    suggested_machine_agent_id=role.machine_agent_id,
                    rationale=(
                        f"Matched objective to {role.title}; no runtime execution "
                        "has started."
                    ),
                )
            )
            risk_findings.append(finding)
            work_items.append(
                ProjectWorkItem(
                    work_item_id=f"{decision_id}-work-{index}",
                    task_id=task_id,
                    department_id=role.department_id,
                    assigned_role_id=role.id,
                    assigned_machine_agent_id=role.machine_agent_id,
                    status=status,
                    acceptance_evidence=[
                        "Specialist output is attached to the task record.",
                        "Claims are traceable to tool, model, or source evidence.",
                        "Guardian performs final synthesis before user delivery.",
                    ],
                )
            )

        blocked = any(item.risk_level == "blocked" for item in risk_findings)
        approval_required = any(item.approval_required for item in risk_findings)
        overall_risk: RiskLevel = (
            "blocked"
            if blocked
            else "high"
            if approval_required
            else "low"
        )
        disposition: DecisionDisposition = (
            "blocked"
            if blocked
            else "approval_required"
            if approval_required
            else "ready_for_delegation"
        )
        execution_mode = "parallel" if len(chief_tasks) > 1 else "sequential"

        chief_decision = ChiefOfStaffDecision(
            objective_count=len(chief_tasks),
            tasks=chief_tasks,
            parallelizable_task_ids=[task.task_id for task in chief_tasks],
            notes=[
                "Each supplied objective becomes an independent bounded task.",
                "Dependencies remain empty unless explicitly supplied in a later phase.",
            ],
        )
        risk_decision = RiskPolicyDecision(
            overall_risk=overall_risk,
            findings=risk_findings,
            owner_approval_required=approval_required,
            execution_allowed=False,
        )
        project_decision = ProjectPlanDecision(
            parent_plan_id=f"{decision_id}-plan",
            work_items=work_items,
            execution_mode=execution_mode,
            completion_definition=[
                "Every work item reaches an evidence-backed terminal state.",
                "Blocked or approval-required work is not silently executed.",
                "Guardian returns one synthesized outcome to the owner.",
            ],
        )
        audit_decision = AuditDecision(
            entries=[
                AuditEntry(
                    sequence=1,
                    actor_role_id="chief-of-staff",
                    action="decomposed objectives",
                    evidence=f"{len(chief_tasks)} bounded task(s) created",
                ),
                AuditEntry(
                    sequence=2,
                    actor_role_id="chief-risk-policy",
                    action="classified risk and approvals",
                    evidence=f"overall risk={overall_risk}",
                ),
                AuditEntry(
                    sequence=3,
                    actor_role_id="senior-project-manager",
                    action="constructed non-executing project plan",
                    evidence=f"execution mode={execution_mode}",
                ),
                AuditEntry(
                    sequence=4,
                    actor_role_id="chief-audit-compliance",
                    action="sealed advisory decision record",
                    evidence=decision_id,
                ),
            ],
            immutable_claims=[
                "No worker was started by this endpoint.",
                "No broker, shell, deployment, or external mutation was invoked.",
                "Planned executive roles remain planned registry entries.",
            ],
        )

        return ExecutivePlanResponse(
            decision_id=decision_id,
            requested_by=request.requested_by,
            disposition=disposition,
            chief_of_staff=chief_decision,
            risk_policy=risk_decision,
            project_plan=project_decision,
            audit=audit_decision,
            message=(
                "Executive advisory plan created. Explicit delegation or owner "
                "approval is required before any runtime work begins."
            ),
        )


executive_office_service = ExecutiveOfficeService()
