from __future__ import annotations

import re
import unittest
from pathlib import Path


class Phase12InternetResearchBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.policy_source = (
            cls.repo_root / "platform/backend/gateway/internet_research_policy.py"
        ).read_text(encoding="utf-8")
        cls.contract_source = (
            cls.repo_root / "platform/backend/gateway/research_contract.py"
        ).read_text(encoding="utf-8")
        cls.agent_registry_source = (
            cls.repo_root / "platform/backend/agents/registry.py"
        ).read_text(encoding="utf-8")
        cls.tool_registry_source = (
            cls.repo_root / "platform/backend/tools/registry.py"
        ).read_text(encoding="utf-8")

    def test_12a_and_12b_contracts_have_no_network_or_process_transport(self) -> None:
        prohibited_imports = (
            r"^import\s+(?:aiohttp|httpx|requests|socket|subprocess|urllib)",
            r"^from\s+(?:aiohttp|httpx|requests|socket|subprocess|urllib)(?:\.|\s)",
        )
        for source_name, source in (
            ("policy", self.policy_source),
            ("request contract", self.contract_source),
        ):
            for pattern in prohibited_imports:
                self.assertIsNone(
                    re.search(pattern, source, flags=re.MULTILINE),
                    msg=f"Phase 12 {source_name} must remain transport-free: {pattern}",
                )

    def test_phase12_contracts_have_no_privileged_control_plane_dependency(self) -> None:
        prohibited_tokens = (
            "guardian_broker",
            "guardian_client",
            "systemctl",
            "/var/run/docker.sock",
            "docker.sock",
            "sudo ",
            "os.system(",
            "subprocess.",
        )
        combined = (self.policy_source + "\n" + self.contract_source).lower()
        for token in prohibited_tokens:
            self.assertNotIn(token, combined)

    def test_research_agent_has_no_internet_tool_before_transport_gate(self) -> None:
        research_block = self.agent_registry_source.split(
            'id="research-agent"', maxsplit=1
        )[1].split("agent_registry.register(", maxsplit=1)[0]

        self.assertIn('"knowledge.search"', research_block)
        self.assertNotIn('"internet.', research_block)
        self.assertNotIn('"web.', research_block)

    def test_tool_registry_registers_no_internet_transport_before_transport_gate(self) -> None:
        self.assertNotIn("Internet", self.tool_registry_source)
        self.assertNotIn("WebSearch", self.tool_registry_source)
        self.assertNotIn("WebFetch", self.tool_registry_source)
        self.assertNotIn("internet_tools", self.tool_registry_source)

    def test_public_web_and_search_sources_are_contract_only(self) -> None:
        self.assertIn('source_id="public-web"', self.contract_source)
        self.assertIn('source_id="web-search"', self.contract_source)
        self.assertGreaterEqual(self.contract_source.count("execution_enabled=False"), 2)
        self.assertGreaterEqual(self.contract_source.count("tool_id=None"), 2)


if __name__ == "__main__":
    unittest.main()
