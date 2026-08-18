from __future__ import annotations

import ast
import unittest
from pathlib import Path


class Phase12HSearchProviderBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.provider_source = (
            cls.repo_root / "platform/backend/gateway/web_search_provider.py"
        ).read_text(encoding="utf-8")
        cls.provider_tree = ast.parse(cls.provider_source)
        cls.contract_source = (
            cls.repo_root / "platform/backend/gateway/research_contract.py"
        ).read_text(encoding="utf-8")
        cls.agent_registry_source = (
            cls.repo_root / "platform/backend/agents/registry.py"
        ).read_text(encoding="utf-8")
        cls.tool_registry_source = (
            cls.repo_root / "platform/backend/tools/registry.py"
        ).read_text(encoding="utf-8")

    def test_provider_destination_and_credential_name_are_fixed_by_dap(self) -> None:
        self.assertIn('BRAVE_API_HOSTNAME = "api.search.brave.com"', self.provider_source)
        self.assertIn('BRAVE_API_PATH = "/res/v1/web/search"', self.provider_source)
        self.assertIn('BRAVE_API_KEY_ENV = "DAP_BRAVE_SEARCH_API_KEY"', self.provider_source)
        self.assertIn("socket.AI_NUMERICHOST", self.provider_source)
        self.assertIn("server_hostname=BRAVE_API_HOSTNAME", self.provider_source)
        self.assertIn("ssl.create_default_context()", self.provider_source)

    def test_provider_secret_is_not_a_model_or_result_field(self) -> None:
        self.assertIn("provider_credential_exposed_to_model: Literal[False] = False", self.provider_source)
        self.assertIn("provider_credential_persisted: Literal[False] = False", self.provider_source)
        self.assertIn(
            "provider_credential_forwarded_to_result_url: Literal[False] = False",
            self.provider_source,
        )
        self.assertNotIn("subscription_token: str\n    provider_id", self.provider_source)
        self.assertNotIn("api_key: str\n", self.provider_source)

    def test_provider_does_not_accept_arbitrary_endpoint_or_request_headers(self) -> None:
        prohibited_tokens = (
            "base_url=",
            "endpoint_url=",
            "request_headers",
            "extra_headers",
            "follow_redirects",
            "allow_redirects",
            "trust_env",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        )
        lower = self.provider_source.lower()
        for token in prohibited_tokens:
            self.assertNotIn(token, lower)

    def test_search_candidates_are_explicitly_untrusted_and_require_retrieval(self) -> None:
        self.assertIn("candidate_is_untrusted: Literal[True] = True", self.provider_source)
        self.assertIn("candidate_is_retrieval_evidence: Literal[False] = False", self.provider_source)
        self.assertIn(
            "candidate_url_requires_dap_retrieval: Literal[True] = True",
            self.provider_source,
        )
        self.assertIn("remote_instructions_are_authority: Literal[False] = False", self.provider_source)
        self.assertIn("tool_selection_allowed: Literal[False] = False", self.provider_source)
        self.assertIn("InternetDestinationPolicy", self.provider_source)

    def test_provider_layer_has_no_privileged_or_agent_execution_dependency(self) -> None:
        prohibited_roots = {"guardian", "docker", "subprocess"}
        imported_roots: set[str] = set()
        for node in ast.walk(self.provider_tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue(prohibited_roots.isdisjoint(imported_roots))

        lower = self.provider_source.lower()
        for token in (
            "guardian_broker",
            "guardian_client",
            "systemctl",
            "/var/run/docker.sock",
            "docker.sock",
            "sudo ",
            "os.system(",
            "subprocess.",
            "agent_registry.register",
            "tool_registry.register",
            "mcp",
            "plugin",
        ):
            self.assertNotIn(token, lower)

    def test_12h_adapter_is_not_live_search_agent_authority_yet(self) -> None:
        research_block = self.agent_registry_source.split(
            'id="research-agent"', maxsplit=1
        )[1].split("agent_registry.register(", maxsplit=1)[0]
        self.assertEqual(research_block.count('"internet.research.retrieve"'), 1)
        self.assertNotIn('"web.search"', research_block)
        self.assertNotIn("Brave", self.tool_registry_source)
        self.assertNotIn("WebSearch", self.tool_registry_source)

        web_search_block = self.contract_source.split(
            'source_id="web-search"', maxsplit=1
        )[1].split(")", maxsplit=1)[0]
        self.assertIn("tool_id=None", web_search_block)
        self.assertIn("execution_enabled=False", web_search_block)


if __name__ == "__main__":
    unittest.main()
