from __future__ import annotations

import ast
import unittest
from pathlib import Path


class Phase12HSearchDiscoveryBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.pipeline_source = (
            cls.repo_root / "platform/backend/gateway/web_search_discovery.py"
        ).read_text(encoding="utf-8")
        cls.pipeline_tree = ast.parse(cls.pipeline_source)
        cls.agent_registry_source = (
            cls.repo_root / "platform/backend/agents/registry.py"
        ).read_text(encoding="utf-8")
        cls.tool_registry_source = (
            cls.repo_root / "platform/backend/tools/registry.py"
        ).read_text(encoding="utf-8")

    def test_pipeline_selects_at_most_three_and_uses_only_sealed_retrieval_tool(self) -> None:
        self.assertIn("MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL = 3", self.pipeline_source)
        self.assertIn("InternetResearchRetrieveTool", self.pipeline_source)
        self.assertIn('retrieval_tool_id: Literal["internet.research.retrieve"]', self.pipeline_source)
        self.assertIn('"urls": list(selected_urls)', self.pipeline_source)
        self.assertNotIn("BoundedInternetRetriever", self.pipeline_source)
        self.assertNotIn("asyncio.open_connection", self.pipeline_source)
        self.assertNotIn("socket.", self.pipeline_source)

    def test_provider_snippets_and_titles_are_not_model_evidence(self) -> None:
        self.assertIn("provider_snippets_are_evidence: Literal[False] = False", self.pipeline_source)
        self.assertIn("provider_snippets_exposed_to_model: Literal[False] = False", self.pipeline_source)
        self.assertIn("provider_titles_exposed_to_model: Literal[False] = False", self.pipeline_source)
        self.assertIn("search_candidates_are_retrieval_evidence: Literal[False] = False", self.pipeline_source)
        self.assertIn(
            "candidate_urls_require_full_dap_retrieval: Literal[True] = True",
            self.pipeline_source,
        )
        self.assertNotIn("candidate.snippet", self.pipeline_source)
        self.assertNotIn("candidate.title", self.pipeline_source)

    def test_pipeline_cannot_expose_provider_credentials_or_expand_scope(self) -> None:
        self.assertIn("provider_credential_exposed_to_model: Literal[False] = False", self.pipeline_source)
        self.assertIn(
            "provider_credential_forwarded_to_result_url: Literal[False] = False",
            self.pipeline_source,
        )
        self.assertIn("generic_network_client_exposed: Literal[False] = False", self.pipeline_source)
        self.assertIn("remote_scope_expansion_allowed: Literal[False] = False", self.pipeline_source)
        self.assertNotIn("subscription_token", self.pipeline_source)
        self.assertNotIn("DAP_BRAVE_SEARCH_API_KEY", self.pipeline_source)

    def test_pipeline_has_no_privileged_or_process_execution_surface(self) -> None:
        imported_roots: set[str] = set()
        for node in ast.walk(self.pipeline_tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue({"guardian", "docker", "subprocess", "socket"}.isdisjoint(imported_roots))

        lower = self.pipeline_source.lower()
        for token in (
            "guardian_broker",
            "guardian_client",
            "systemctl",
            "/var/run/docker.sock",
            "docker.sock",
            "sudo ",
            "os.system(",
            "subprocess.",
            "mcp",
            "plugin",
            "agent_registry.register",
            "tool_registry.register",
        ):
            self.assertNotIn(token, lower)

    def test_search_discovery_is_not_registered_live_during_12h2(self) -> None:
        research_block = self.agent_registry_source.split(
            'id="research-agent"', maxsplit=1
        )[1].split("agent_registry.register(", maxsplit=1)[0]
        self.assertNotIn('"web.search"', research_block)
        self.assertNotIn("WebSearch", self.tool_registry_source)
        self.assertNotIn("Brave", self.tool_registry_source)


if __name__ == "__main__":
    unittest.main()
