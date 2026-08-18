from __future__ import annotations

import ast
import unittest
from pathlib import Path


class Phase13ProviderSpecificResearchActivationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.schemas_source = (
            cls.repo_root / "platform/backend/agents/schemas.py"
        ).read_text(encoding="utf-8")
        cls.service_source = (
            cls.repo_root / "platform/backend/agents/service.py"
        ).read_text(encoding="utf-8")
        cls.executor_source = (
            cls.repo_root / "platform/backend/agents/research_executor.py"
        ).read_text(encoding="utf-8")
        cls.executor_tree = ast.parse(cls.executor_source)
        cls.agent_registry_source = (
            cls.repo_root / "platform/backend/agents/registry.py"
        ).read_text(encoding="utf-8")
        cls.tool_registry_source = (
            cls.repo_root / "platform/backend/tools/registry.py"
        ).read_text(encoding="utf-8")
        cls.dashboard_page = (
            cls.repo_root / "apps/dashboard/src/app/agents/page.tsx"
        ).read_text(encoding="utf-8")
        cls.dashboard_panel = (
            cls.repo_root / "apps/dashboard/src/app/agents/components/RunPanel.tsx"
        ).read_text(encoding="utf-8")

    def test_search_query_is_bounded_and_mutually_exclusive_with_explicit_urls(self) -> None:
        self.assertIn("research_search_query", self.schemas_source)
        self.assertIn("max_length=400", self.schemas_source)
        self.assertIn("at most 50 words", self.schemas_source)
        self.assertIn(
            "research_urls and research_search_query are mutually exclusive",
            self.schemas_source,
        )

    def test_search_activation_requires_manual_research_agent(self) -> None:
        self.assertIn(
            'request.agent_id != "research-agent"',
            self.service_source,
        )
        self.assertIn(
            'request.research_search_query and request.mode != "manual"',
            self.service_source,
        )
        self.assertIn(
            "research_search_query requires manual research-agent mode",
            self.service_source,
        )
        self.assertIn(
            "research_search_query cannot be combined with supplemental_context",
            self.service_source,
        )

    def test_executor_uses_only_fixed_local_searxng_pipeline(self) -> None:
        self.assertIn("WebSearchRetrievalPipeline.searxng_local()", self.executor_source)
        self.assertIn('"searxng-local-v1"', self.executor_source)
        self.assertNotIn("brave_from_environment", self.executor_source)
        self.assertNotIn("BraveWebSearchProvider", self.executor_source)
        self.assertNotIn("internet.research.search", self.executor_source)

        imported_roots: set[str] = set()
        for node in ast.walk(self.executor_tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

        self.assertTrue(
            {
                "socket",
                "requests",
                "httpx",
                "aiohttp",
                "subprocess",
                "guardian",
                "docker",
            }.isdisjoint(imported_roots)
        )

    def test_provider_discovery_metadata_never_becomes_evidence_or_model_content(self) -> None:
        self.assertIn(
            '"provider_snippets_exposed_to_model": (',
            self.executor_source,
        )
        self.assertIn(
            '"provider_titles_exposed_to_model": (',
            self.executor_source,
        )
        self.assertIn(
            '"search_candidates_are_retrieval_evidence": (',
            self.executor_source,
        )
        self.assertIn(
            '"candidate_urls_require_full_dap_retrieval": (',
            self.executor_source,
        )
        self.assertNotIn("search_result.candidates", self.executor_source)
        self.assertNotIn("candidate.snippet", self.executor_source)
        self.assertNotIn("candidate.title", self.executor_source)

    def test_activation_does_not_register_generic_search_tool(self) -> None:
        research_block = self.agent_registry_source.split(
            'id="research-agent"', maxsplit=1
        )[1].split("agent_registry.register(", maxsplit=1)[0]
        self.assertIn("Local SearXNG URL discovery", research_block)
        self.assertNotIn("internet.research.search", research_block)
        self.assertNotIn("internet.research.search", self.tool_registry_source)
        self.assertNotIn("SearXNG", self.tool_registry_source)

    def test_dashboard_control_is_manual_research_agent_only(self) -> None:
        self.assertIn(
            'mode === "manual" && selectedAgentId === "research-agent"',
            self.dashboard_panel,
        )
        self.assertIn("127.0.0.1:8888", self.dashboard_panel)
        self.assertIn("at most three candidate", self.dashboard_panel)
        self.assertIn("Provider titles and snippets never become", self.dashboard_panel)
        self.assertIn("research_search_query", self.dashboard_page)
        self.assertIn(
            'mode === "manual" && selectedAgentId === "research-agent"',
            self.dashboard_page,
        )

    def test_no_privileged_or_runtime_control_surface_was_added(self) -> None:
        combined = "\n".join(
            (
                self.schemas_source,
                self.service_source,
                self.executor_source,
                self.dashboard_page,
                self.dashboard_panel,
            )
        ).lower()
        for token in (
            "systemctl",
            "docker.sock",
            "/var/run/docker.sock",
            "sudo ",
            "os.system(",
            "subprocess.",
            "guardian_broker",
            "guardian_client",
        ):
            self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
