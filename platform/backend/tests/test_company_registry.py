import unittest

from fastapi.testclient import TestClient

from app import app
from company.catalog import DEPARTMENTS, ROLES, company_registry
from company.registry import (
    OrganizationRegistry,
    OrganizationRegistryError,
)


class CompanyRegistryTestCase(unittest.TestCase):
    def test_ratified_company_snapshot_is_complete(self) -> None:
        snapshot = company_registry.snapshot()

        self.assertEqual(snapshot.organization_id, "dipen-ai-platform")
        self.assertEqual(snapshot.owner_role_id, "dipen-owner")
        self.assertEqual(snapshot.ceo_role_id, "guardian-ceo")
        self.assertEqual(snapshot.summary.department_count, 10)
        self.assertEqual(snapshot.summary.role_count, 37)
        self.assertEqual(snapshot.summary.active_roles, 8)
        self.assertEqual(snapshot.summary.planned_roles, 28)
        self.assertEqual(snapshot.summary.disabled_roles, 1)
        self.assertEqual(snapshot.summary.active_specialists, 6)
        self.assertEqual(snapshot.summary.manager_roles, 15)
        self.assertEqual(snapshot.summary.mapped_agent_roles, 7)

    def test_every_department_has_non_working_head(self) -> None:
        for department in company_registry.list_departments().departments:
            head = company_registry.get_role(department.head_role_id)

            self.assertEqual(head.department_id, department.id)
            self.assertTrue(head.manager_only)
            self.assertIsNone(head.machine_agent_id)

    def test_current_agents_are_mapped_to_human_roles(self) -> None:
        mapped_roles = {
            role.machine_agent_id: role.id
            for role in company_registry.list_roles().roles
            if role.machine_agent_id is not None
        }

        self.assertEqual(
            mapped_roles,
            {
                "coding-agent": "software-engineer",
                "devops-agent": "site-reliability-engineer",
                "system-agent": "systems-engineer",
                "knowledge-agent": "knowledge-specialist",
                "research-agent": "research-analyst",
                "documentation-agent": "technical-writer",
                "sql-agent": "sql-specialist",
            },
        )

    def test_reporting_chain_reaches_owner(self) -> None:
        response = company_registry.reporting_chain("software-engineer")

        self.assertEqual(
            [role.id for role in response.chain],
            [
                "director-engineering",
                "guardian-ceo",
                "dipen-owner",
            ],
        )

    def test_audit_reports_directly_to_owner(self) -> None:
        audit = company_registry.get_role("chief-audit-compliance")
        self.assertEqual(audit.reports_to_role_id, "dipen-owner")
        self.assertEqual(audit.autonomy_ceiling, "observe")

    def test_role_filters_are_deterministic(self) -> None:
        engineering = company_registry.list_roles(
            department_id="engineering"
        )
        active_specialists = company_registry.list_roles(
            status="active",
            role_kind="specialist",
        )

        self.assertEqual(engineering.total, 4)
        self.assertEqual(active_specialists.total, 6)
        self.assertEqual(
            {role.id for role in active_specialists.roles},
            {
                "software-engineer",
                "site-reliability-engineer",
                "systems-engineer",
                "knowledge-specialist",
                "research-analyst",
                "technical-writer",
            },
        )

    def test_duplicate_role_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            OrganizationRegistryError,
            "Duplicate role identifiers",
        ):
            OrganizationRegistry(
                DEPARTMENTS,
                [*ROLES, ROLES[0]],
            )

    def test_manager_cannot_map_to_worker_agent(self) -> None:
        roles = list(ROLES)
        guardian_index = next(
            index
            for index, role in enumerate(roles)
            if role.id == "guardian-ceo"
        )
        roles[guardian_index] = roles[guardian_index].model_copy(
            update={"machine_agent_id": "guardian-worker"}
        )

        with self.assertRaisesRegex(
            OrganizationRegistryError,
            "Manager-only role guardian-ceo",
        ):
            OrganizationRegistry(DEPARTMENTS, roles)

    def test_reporting_cycles_are_rejected(self) -> None:
        roles = list(ROLES)
        director_index = next(
            index
            for index, role in enumerate(roles)
            if role.id == "director-engineering"
        )
        roles[director_index] = roles[director_index].model_copy(
            update={"reports_to_role_id": "software-engineer"}
        )

        with self.assertRaisesRegex(
            OrganizationRegistryError,
            "Reporting cycle detected",
        ):
            OrganizationRegistry(DEPARTMENTS, roles)


class CompanyRegistryRouteTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def test_organization_endpoint_is_read_only_directory(self) -> None:
        response = self.client.get("/api/v1/company/organization")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["department_count"], 10)
        self.assertEqual(payload["summary"]["role_count"], 37)
        self.assertEqual(payload["registry_version"], "1.0.0")

    def test_role_and_reporting_chain_endpoints(self) -> None:
        role_response = self.client.get(
            "/api/v1/company/roles/software-engineer"
        )
        chain_response = self.client.get(
            "/api/v1/company/roles/software-engineer/reporting-chain"
        )

        self.assertEqual(role_response.status_code, 200)
        self.assertEqual(
            role_response.json()["machine_agent_id"],
            "coding-agent",
        )
        self.assertEqual(chain_response.status_code, 200)
        self.assertEqual(
            [role["id"] for role in chain_response.json()["chain"]],
            [
                "director-engineering",
                "guardian-ceo",
                "dipen-owner",
            ],
        )

    def test_role_filters_and_unknown_department(self) -> None:
        response = self.client.get(
            "/api/v1/company/roles",
            params={
                "department_id": "engineering",
                "status": "active",
            },
        )
        missing = self.client.get(
            "/api/v1/company/roles",
            params={"department_id": "unknown"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(
            response.json()["roles"][0]["id"],
            "software-engineer",
        )
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
