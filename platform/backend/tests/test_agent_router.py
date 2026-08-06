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

    def test_phrase_and_punctuation_keywords_still_match(self) -> None:
        route = self.router.route(
            AgentRunRequest(
                mode="smart",
                objective=(
                    "Create a Next.js API and review the CI/CD pipeline."
                ),
            )
        )

        self.assertIn(
            "next.js",
            route.matched_terms,
        )
        self.assertGreater(
            route.candidate_scores["coding-agent"],
            0,
        )
        self.assertGreater(
            route.candidate_scores["devops-agent"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
