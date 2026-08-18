from __future__ import annotations

import ast
import unittest
from pathlib import Path


class Phase12HSearXNGProviderBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.provider_source = (
            cls.repo_root / "platform/backend/gateway/searxng_search_provider.py"
        ).read_text(encoding="utf-8")
        cls.provider_tree = ast.parse(cls.provider_source)
        cls.agent_registry_source = (
            cls.repo_root / "platform/backend/agents/registry.py"
        ).read_text(encoding="utf-8")
        cls.tool_registry_source = (
            cls.repo_root / "platform/backend/tools/registry.py"
        ).read_text(encoding="utf-8")

    def test_searxng_transport_is_fixed_to_one_loopback_socket(self) -> None:
        self.assertIn('SEARXNG_HOST = "127.0.0.1"', self.provider_source)
        self.assertIn("SEARXNG_PORT = 8888", self.provider_source)
        self.assertIn('SEARXNG_PATH = "/search"', self.provider_source)
        self.assertIn("family=socket.AF_INET", self.provider_source)
        self.assertIn("flags=socket.AI_NUMERICHOST", self.provider_source)
        self.assertIn('peer[0] != SEARXNG_HOST', self.provider_source)

    def test_searxng_provider_has_no_credential_or_configurable_endpoint_surface(self) -> None:
        lower = self.provider_source.lower()
        for token in (
            "api_key",
            "subscription_token",
            "authorization:",
            "cookie:",
            "base_url=",
            "endpoint_url=",
            "host=arguments",
            "port=arguments",
            "os.environ",
            "getenv(",
        ):
            self.assertNotIn(token, lower)
        self.assertIn("provider_credential_required: Literal[False] = False", self.provider_source)
        self.assertIn("provider_is_local_only: Literal[True] = True", self.provider_source)

    def test_search_results_remain_untrusted_and_require_public_retrieval(self) -> None:
        self.assertIn("WebSearchCandidate", self.provider_source)
        self.assertIn("InternetDestinationPolicy", self.provider_source)
        self.assertIn("candidate_urls_require_full_dap_retrieval: Literal[True] = True", self.provider_source)
        self.assertIn("generic_network_client_exposed: Literal[False] = False", self.provider_source)

    def test_local_provider_has_no_privileged_or_runtime_control_dependency(self) -> None:
        imported_roots: set[str] = set()
        for node in ast.walk(self.provider_tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue({"guardian", "docker", "subprocess"}.isdisjoint(imported_roots))

        lower = self.provider_source.lower()
        for token in (
            "systemctl",
            "/var/run/docker.sock",
            "docker.sock",
            "sudo ",
            "os.system(",
            "subprocess.",
            "guardian_broker",
            "guardian_client",
            "tool_registry.register",
            "agent_registry.register",
            "mcp",
        ):
            self.assertNotIn(token, lower)

    def test_searxng_is_not_registered_live_before_runtime_smoke(self) -> None:
        research_block = self.agent_registry_source.split(
            'id="research-agent"', maxsplit=1
        )[1].split("agent_registry.register(", maxsplit=1)[0]
        self.assertNotIn("searxng", research_block.lower())
        self.assertNotIn("SearXNG", self.tool_registry_source)


if __name__ == "__main__":
    unittest.main()
