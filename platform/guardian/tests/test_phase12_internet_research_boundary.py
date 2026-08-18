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
        cls.agent_registry_source = (
            cls.repo_root / "platform/backend/agents/registry.py"
        ).read_text(encoding="utf-8")
        cls.tool_registry_source = (
            cls.repo_root / "platform/backend/tools/registry.py"
        ).read_text(encoding="utf-8")

    def test_12a_policy_has_no_network_or_process_transport(self) -> None:
        prohibited_imports = (
            r"^import\s+(?:aiohttp|httpx|requests|socket|subprocess|urllib)",
            r"^from\s+(?:aiohttp|httpx|requests|socket|subprocess|urllib)(?:\.|\s)",
        )
        for pattern in prohibited_imports:
            self.assertIsNone(
                re.search(pattern, self.policy_source, flags=re.MULTILINE),
                msg=f"Phase 12A policy must remain transport-free: {pattern}",
            )

    def test_12a_policy_has_no_privileged_control_plane_dependency(self) -> None:
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
        for token in prohibited_tokens:
            self.assertNotIn(token, self.policy_source.lower())

    def test_research_agent_has_no_internet_tool_during_12a(self) -> None:
        research_block = self.agent_registry_source.split(
            'id="research-agent"', maxsplit=1
        )[1].split("agent_registry.register(", maxsplit=1)[0]

        self.assertIn('"knowledge.search"', research_block)
        self.assertNotIn('"internet.', research_block)
        self.assertNotIn('"web.', research_block)

    def test_tool_registry_registers_no_internet_transport_during_12a(self) -> None:
        self.assertNotIn("Internet", self.tool_registry_source)
        self.assertNotIn("WebSearch", self.tool_registry_source)
        self.assertNotIn("WebFetch", self.tool_registry_source)
        self.assertNotIn("internet_tools", self.tool_registry_source)


if __name__ == "__main__":
    unittest.main()
