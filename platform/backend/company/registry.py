from collections.abc import Iterable

from company.schemas import (
    DepartmentDefinition,
    DepartmentListResponse,
    DepartmentStatus,
    EmploymentStatus,
    OrganizationSnapshot,
    OrganizationSummary,
    ReportingChainResponse,
    RoleDefinition,
    RoleKind,
    RoleListResponse,
)


class OrganizationRegistryError(ValueError):
    """Raised when the deterministic company directory is invalid."""


class OrganizationRegistry:
    def __init__(
        self,
        departments: Iterable[DepartmentDefinition],
        roles: Iterable[RoleDefinition],
        *,
        organization_id: str = "dipen-ai-platform",
        organization_name: str = "Dipen AI Platform",
        registry_version: str = "1.0.0",
        owner_role_id: str = "dipen-owner",
        ceo_role_id: str = "guardian-ceo",
    ) -> None:
        department_items = tuple(departments)
        role_items = tuple(roles)

        self._ensure_unique_ids(
            "department",
            [department.id for department in department_items],
        )
        self._ensure_unique_ids(
            "role",
            [role.id for role in role_items],
        )

        self.organization_id = organization_id
        self.organization_name = organization_name
        self.registry_version = registry_version
        self.owner_role_id = owner_role_id
        self.ceo_role_id = ceo_role_id

        self._departments = {
            department.id: department
            for department in department_items
        }
        self._roles = {
            role.id: role
            for role in role_items
        }

        self._validate()

    @staticmethod
    def _ensure_unique_ids(
        item_type: str,
        identifiers: list[str],
    ) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()

        for identifier in identifiers:
            if identifier in seen:
                duplicates.add(identifier)
            seen.add(identifier)

        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise OrganizationRegistryError(
                f"Duplicate {item_type} identifiers: {duplicate_list}"
            )

    def _validate(self) -> None:
        owner = self._roles.get(self.owner_role_id)
        if owner is None:
            raise OrganizationRegistryError(
                f"Owner role is missing: {self.owner_role_id}"
            )
        if owner.role_kind != "owner":
            raise OrganizationRegistryError(
                "The configured owner role must use role_kind='owner'."
            )
        if owner.reports_to_role_id is not None:
            raise OrganizationRegistryError(
                "The owner role cannot report to another role."
            )

        ceo = self._roles.get(self.ceo_role_id)
        if ceo is None:
            raise OrganizationRegistryError(
                f"CEO role is missing: {self.ceo_role_id}"
            )
        if ceo.role_kind != "executive":
            raise OrganizationRegistryError(
                "The configured CEO role must use role_kind='executive'."
            )
        if ceo.reports_to_role_id != self.owner_role_id:
            raise OrganizationRegistryError(
                "The CEO must report directly to the owner."
            )

        machine_agent_roles: dict[str, str] = {}

        for role in self._roles.values():
            self._validate_role_references(role)

            if role.manager_only and role.machine_agent_id is not None:
                raise OrganizationRegistryError(
                    f"Manager-only role {role.id} cannot map to a worker agent."
                )

            if (
                role.runtime_kind == "model_agent"
                and role.employment_status in {"active", "disabled"}
                and role.machine_agent_id is None
            ):
                raise OrganizationRegistryError(
                    f"Model-agent role {role.id} requires machine_agent_id."
                )

            if role.machine_agent_id is not None:
                existing_role_id = machine_agent_roles.get(
                    role.machine_agent_id
                )
                if existing_role_id is not None:
                    raise OrganizationRegistryError(
                        "Machine agent is assigned to multiple roles: "
                        f"{role.machine_agent_id} -> "
                        f"{existing_role_id}, {role.id}"
                    )
                machine_agent_roles[role.machine_agent_id] = role.id

        for department in self._departments.values():
            head = self._roles.get(department.head_role_id)
            if head is None:
                raise OrganizationRegistryError(
                    f"Department {department.id} references missing head "
                    f"role {department.head_role_id}."
                )
            if head.department_id != department.id:
                raise OrganizationRegistryError(
                    f"Department head {head.id} is not assigned to "
                    f"department {department.id}."
                )
            if not head.manager_only:
                raise OrganizationRegistryError(
                    f"Department head {head.id} must be manager-only."
                )

        self._validate_reporting_cycles()

    def _validate_role_references(
        self,
        role: RoleDefinition,
    ) -> None:
        if (
            role.department_id is not None
            and role.department_id not in self._departments
        ):
            raise OrganizationRegistryError(
                f"Role {role.id} references unknown department "
                f"{role.department_id}."
            )

        if role.id != self.owner_role_id:
            if role.reports_to_role_id is None:
                raise OrganizationRegistryError(
                    f"Role {role.id} must have a reporting manager."
                )
            if role.reports_to_role_id not in self._roles:
                raise OrganizationRegistryError(
                    f"Role {role.id} reports to unknown role "
                    f"{role.reports_to_role_id}."
                )
            if role.reports_to_role_id == role.id:
                raise OrganizationRegistryError(
                    f"Role {role.id} cannot report to itself."
                )

        for escalation_role_id in role.escalation_role_ids:
            if escalation_role_id not in self._roles:
                raise OrganizationRegistryError(
                    f"Role {role.id} references unknown escalation role "
                    f"{escalation_role_id}."
                )

    def _validate_reporting_cycles(self) -> None:
        for role in self._roles.values():
            visited: set[str] = set()
            current = role

            while current.reports_to_role_id is not None:
                if current.id in visited:
                    chain = " -> ".join([*visited, current.id])
                    raise OrganizationRegistryError(
                        f"Reporting cycle detected: {chain}"
                    )

                visited.add(current.id)
                current = self._roles[current.reports_to_role_id]

    def get_department(
        self,
        department_id: str,
    ) -> DepartmentDefinition:
        department = self._departments.get(department_id)
        if department is None:
            raise KeyError(f"Unknown department: {department_id}")
        return department

    def list_departments(
        self,
        *,
        status: DepartmentStatus | None = None,
    ) -> DepartmentListResponse:
        departments = [
            department
            for department in self._departments.values()
            if status is None or department.status == status
        ]
        return DepartmentListResponse(
            total=len(departments),
            departments=departments,
        )

    def get_role(
        self,
        role_id: str,
    ) -> RoleDefinition:
        role = self._roles.get(role_id)
        if role is None:
            raise KeyError(f"Unknown company role: {role_id}")
        return role

    def list_roles(
        self,
        *,
        department_id: str | None = None,
        status: EmploymentStatus | None = None,
        role_kind: RoleKind | None = None,
    ) -> RoleListResponse:
        if (
            department_id is not None
            and department_id not in self._departments
        ):
            raise KeyError(f"Unknown department: {department_id}")

        roles = [
            role
            for role in self._roles.values()
            if (
                (department_id is None or role.department_id == department_id)
                and (status is None or role.employment_status == status)
                and (role_kind is None or role.role_kind == role_kind)
            )
        ]
        return RoleListResponse(
            total=len(roles),
            roles=roles,
        )

    def direct_reports(
        self,
        role_id: str,
    ) -> RoleListResponse:
        self.get_role(role_id)
        reports = [
            role
            for role in self._roles.values()
            if role.reports_to_role_id == role_id
        ]
        return RoleListResponse(
            total=len(reports),
            roles=reports,
        )

    def reporting_chain(
        self,
        role_id: str,
    ) -> ReportingChainResponse:
        role = self.get_role(role_id)
        chain: list[RoleDefinition] = []
        current = role

        while current.reports_to_role_id is not None:
            current = self._roles[current.reports_to_role_id]
            chain.append(current)

        return ReportingChainResponse(
            role=role,
            chain=chain,
        )

    def snapshot(self) -> OrganizationSnapshot:
        roles = list(self._roles.values())
        departments = list(self._departments.values())

        summary = OrganizationSummary(
            department_count=len(departments),
            role_count=len(roles),
            active_roles=sum(
                role.employment_status == "active"
                for role in roles
            ),
            planned_roles=sum(
                role.employment_status == "planned"
                for role in roles
            ),
            disabled_roles=sum(
                role.employment_status == "disabled"
                for role in roles
            ),
            active_specialists=sum(
                role.role_kind == "specialist"
                and role.employment_status == "active"
                for role in roles
            ),
            manager_roles=sum(
                role.manager_only
                for role in roles
            ),
            mapped_agent_roles=sum(
                role.machine_agent_id is not None
                for role in roles
            ),
        )

        return OrganizationSnapshot(
            organization_id=self.organization_id,
            organization_name=self.organization_name,
            registry_version=self.registry_version,
            owner_role_id=self.owner_role_id,
            ceo_role_id=self.ceo_role_id,
            summary=summary,
            departments=departments,
            roles=roles,
        )
