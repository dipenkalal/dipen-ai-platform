import unittest

from agents.router import AgentRouter
from agents.schemas import AgentRunRequest


class AgentRouterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.router = AgentRouter()

    def test_c_program_routes_to_coding_agent(self) -> None:
        route = self.router.route(
            AgentRunRequest(
                mode="smart",
                objective=(
                    "Write a minimal C program that prints Hello World."
                ),
            )
        )

        self.assertEqual(
            route.agent_id,
            "coding-agent",
        )
        self.assertEqual(
            route.candidate_scores["system-agent"],
            0,
        )
        self.assertGreater(
            route.candidate_scores["coding-agent"],
            0,
        )
        self.assertIn(
            "program",
            route.matched_terms,
        )
        self.assertIn(
            "c",
            route.matched_terms,
        )
        self.assertNotIn(
            "ram",
            route.matched_terms,
        )

    def test_ram_status_routes_to_system_agent(self) -> None:
        route = self.router.route(
            AgentRunRequest(
                mode="smart",
                objective="Show current RAM usage.",
            )
        )

        self.assertEqual(
            route.agent_id,
            "system-agent",
        )
        self.assertIn(
            "ram",
            route.matched_terms,
        )

    def test_next_js_keyword_matches_coding_agent(self) -> None:
        route = self.router.route(
            AgentRunRequest(
                mode="smart",
                objective="Create a Next.js API.",
            )
        )

        self.assertEqual(
            route.agent_id,
            "coding-agent",
        )
        self.assertIn(
            "next.js",
            route.matched_terms,
        )
        self.assertIn(
            "api",
            route.matched_terms,
        )

    def test_ci_cd_keyword_matches_devops_agent(self) -> None:
        route = self.router.route(
            AgentRunRequest(
                mode="smart",
                objective="Review the CI/CD pipeline.",
            )
        )

        self.assertEqual(
            route.agent_id,
            "devops-agent",
        )
        self.assertIn(
            "ci/cd",
            route.matched_terms,
        )
        self.assertIn(
            "pipeline",
            route.matched_terms,
        )

    def test_combined_request_scores_both_agents(self) -> None:
        route = self.router.route(
            AgentRunRequest(
                mode="smart",
                objective=(
                    "Create a Next.js API and review the CI/CD pipeline."
                ),
            )
        )

        self.assertEqual(
            route.agent_id,
            "devops-agent",
        )
        self.assertGreater(
            route.candidate_scores["coding-agent"],
            0,
        )
        self.assertGreater(
            route.candidate_scores["devops-agent"],
            route.candidate_scores["coding-agent"],
        )
        self.assertEqual(
            route.matched_terms,
            ["ci/cd", "pipeline"],
        )


if __name__ == "__main__":
    unittest.main()

def test_dap_system_health_routes_to_system_agent() -> None:
    router = AgentRouter()

    route = router.route(
        AgentRunRequest(
            mode="smart",
            objective="Check the DAP system health.",
        )
    )

    assert route.agent_id == "system-agent"
    assert "system health" in route.matched_terms
