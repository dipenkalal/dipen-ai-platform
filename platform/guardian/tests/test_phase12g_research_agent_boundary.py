from __future__ import annotations

import re
import unittest
from pathlib import Path


class Phase12GResearchAgentBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.tool_source = (
            cls.repo_root / "platform/backend/tools/internet_research_tools.py"
        ).read_text(encoding="utf-8")
        cls.tool_registry_source = (
            cls.repo_root / "platform/backend/tools/registry.py"
        ).read_text(encoding="utf-8")
        cls.agent_registry_source = (
            cls.repo_root / "platform/backend/agents/registry.py"
        ).read_text(encoding="utf-8")
        cls.research_executor_source = (
            cls.repo_root / "platform/backend/agents/research_executor.py"
        ).read_text(encoding="utf-8")
        cls.service_source = (
            cls.repo_root / "platform/backend/agents/service.py"
        ).read_text(encoding="utf-8")
        cls.contract_source = (
            cls.repo_root / "platform/backend/gateway/research_contract.py"
        ).read_text(encoding="utf-8")

    def test_exactly_one_bounded_internet_research_tool_is_registered(self) -> None:
        self.assertIn("InternetResearchRetrieveTool", self.tool_registry_source)
        self.assertEqual(
            self.tool_registry_source.count("InternetResearchRetrieveTool()"),
            1,
        )
        for token in ("WebSearch", "WebFetch", "AgentReach", "MCP", "Plugin"):
            self.assertNotIn(token, self.tool_registry_source)

    def test_research_agent_exposes_only_knowledge_and_bounded_public_web(self) -> None:
        block = self.agent_registry_source.split('id="research-agent"', maxsplit=1)[1].split(
            "agent_registry.register(", maxsplit=1
        )[0]
        self.assertIn('"knowledge.search"', block)
        self.assertIn('"internet.research.retrieve"', block)
        self.assertNotIn('"web.search"', block)
        self.assertNotIn('"web.fetch"', block)
        self.assertNotIn('"system.status"', block)

    def test_public_web_is_promoted_but_search_remains_disabled(self) -> None:
        public_web = self.contract_source.split('source_id="public-web"', maxsplit=1)[1].split(
            "ResearchSourceDefinition(", maxsplit=1
        )[0]
        web_search = self.contract_source.split('source_id="web-search"', maxsplit=1)[1].split(
            ")", maxsplit=1
        )[0]
        self.assertIn('tool_id="internet.research.retrieve"', public_web)
        self.assertIn("execution_enabled=True", public_web)
        self.assertIn("tool_id=None", web_search)
        self.assertIn("execution_enabled=False", web_search)

    def test_tool_accepts_only_explicit_bounded_urls_and_no_remote_scope_expansion(self) -> None:
        self.assertIn("MAX_EXPLICIT_RESEARCH_URLS = 3", self.tool_source)
        self.assertIn('arguments.get("urls")', self.tool_source)
        self.assertIn('"remote_scope_expansion_allowed": False', self.tool_source)
        self.assertNotRegex(self.tool_source, r"re\.findall\([^\n]*https?://")
        self.assertNotIn("urljoin(", self.tool_source)
        self.assertNotIn("BeautifulSoup", self.tool_source)

    def test_tool_has_no_privileged_or_provider_credential_surface(self) -> None:
        lower = self.tool_source.lower()
        for token in (
            "guardian_broker",
            "guardian_client",
            "systemctl",
            "/var/run/docker.sock",
            "docker.sock",
            "os.system(",
            "subprocess.",
            "openai_api_key",
            "github_token",
            "authorization:",
            "cookie:",
            "proxy-authorization:",
            "sudo ",
        ):
            self.assertNotIn(token, lower)

    def test_research_executor_invokes_internet_tool_only_from_explicit_request_field(self) -> None:
        self.assertIn("if request.research_urls:", self.research_executor_source)
        self.assertIn('tool_registry.get("internet.research.retrieve")', self.research_executor_source)
        self.assertIn('"urls": list(request.research_urls)', self.research_executor_source)
        self.assertIn("Only explicit research_urls supplied by", self.research_executor_source)
        self.assertIn("remote content", self.research_executor_source.lower())
        self.assertNotIn("urljoin(", self.research_executor_source)

    def test_service_fails_closed_if_urls_route_to_non_research_agent(self) -> None:
        self.assertIn("_validate_research_url_scope", self.service_source)
        self.assertIn('request.agent_id != "research-agent"', self.service_source)
        self.assertIn("research_urls are admitted only", self.service_source)

    def test_direct_and_instrumented_runtime_use_same_research_enabled_executor(self) -> None:
        self.assertIn(
            "research_enabled_agent_executor as agent_executor",
            self.service_source,
        )
        runtime_source = (
            self.repo_root / "platform/backend/agents/runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn("research_enabled_agent_executor", runtime_source)
        self.assertNotIn("from agents.executor import agent_executor", runtime_source)

    def test_no_generic_network_library_is_added_to_agent_executor_layer(self) -> None:
        combined = f"{self.research_executor_source}\n{self.service_source}"
        prohibited_imports = (
            r"^import\s+(?:aiohttp|httpx|requests|socket|ssl|urllib)(?:\.|\s|$)",
            r"^from\s+(?:aiohttp|httpx|requests|socket|ssl|urllib)(?:\.|\s)",
        )
        for pattern in prohibited_imports:
            self.assertIsNone(re.search(pattern, combined, flags=re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
