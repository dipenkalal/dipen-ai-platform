from __future__ import annotations

import unittest
from pathlib import Path


class Phase15ProviderReliabilityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.provider_source = (
            cls.repo_root / "platform/backend/gateway/searxng_search_provider.py"
        ).read_text(encoding="utf-8")
        cls.discovery_source = (
            cls.repo_root / "platform/backend/gateway/web_search_discovery.py"
        ).read_text(encoding="utf-8")
        cls.navigation_source = (
            cls.repo_root / "apps/dashboard/src/app/components/AppNavigation.tsx"
        ).read_text(encoding="utf-8")
        cls.roadmap_source = (
            cls.repo_root / "docs/phase15-research-provider-reliability-roadmap.md"
        ).read_text(encoding="utf-8")

    def test_provider_endpoint_remains_fixed_loopback(self) -> None:
        self.assertIn('SEARXNG_HOST: Literal["127.0.0.1"] = "127.0.0.1"', self.provider_source)
        self.assertIn("SEARXNG_PORT = 8888", self.provider_source)
        self.assertIn("socket.AI_NUMERICHOST", self.provider_source)
        self.assertIn("MAX_SEARXNG_PROVIDER_RESULT_SCAN = 20", self.provider_source)
        for token in (
            "os.getenv",
            "os.environ",
            "DAP_SEARXNG_URL",
            "SEARXNG_URL",
        ):
            self.assertNotIn(token, self.provider_source)

    def test_result_scanning_is_bounded_and_cannot_expand_retrieval_count(self) -> None:
        self.assertIn(
            "provider_results[:MAX_SEARXNG_PROVIDER_RESULT_SCAN]",
            self.provider_source,
        )
        self.assertIn("if len(candidates) >= query.count", self.provider_source)
        self.assertIn("MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL = 3", self.discovery_source)
        self.assertIn(
            "limit=MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL",
            self.discovery_source,
        )

    def test_no_candidate_diagnostics_do_not_change_stable_error_code(self) -> None:
        self.assertIn('"no-search-candidates"', self.discovery_source)
        for token in (
            '"provider_result_count"',
            '"considered_result_count"',
            '"invalid_candidate_count"',
            '"policy_rejected_candidate_count"',
            '"provider_zero_results"',
            '"admissible_candidate_zero_after_filtering"',
        ):
            self.assertIn(token, self.discovery_source)

    def test_phase15_adds_no_privileged_or_service_control_authority(self) -> None:
        combined = f"{self.provider_source}\n{self.discovery_source}".lower()
        for token in (
            "systemctl",
            "docker.sock",
            "/var/run/docker.sock",
            "subprocess",
            "os.system",
            "sudo ",
            "telegram",
            "guardianclient",
        ):
            self.assertNotIn(token, combined)

    def test_frontend_visibility_does_not_embed_provider_network_authority(self) -> None:
        self.assertIn('label: "Research"', self.navigation_source)
        self.assertIn('label: "Research Ops"', self.navigation_source)
        self.assertNotIn("127.0.0.1:8888", self.navigation_source)
        self.assertNotIn("/search?q=", self.navigation_source)

    def test_smart_routing_remains_explicitly_out_of_scope(self) -> None:
        self.assertIn("does **not** activate smart-routing research", self.roadmap_source)
        self.assertIn(
            "Any future authority expansion requires a separate owner-approved milestone.",
            self.roadmap_source,
        )


if __name__ == "__main__":
    unittest.main()
