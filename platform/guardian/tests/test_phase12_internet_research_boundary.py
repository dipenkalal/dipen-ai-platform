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
        cls.destination_source = (
            cls.repo_root / "platform/backend/gateway/internet_destination_policy.py"
        ).read_text(encoding="utf-8")
        cls.transport_source = (
            cls.repo_root / "platform/backend/gateway/internet_transport.py"
        ).read_text(encoding="utf-8")

    def test_phase12_contracts_have_no_network_or_process_transport(self) -> None:
        prohibited_imports = (
            r"^import\s+(?:aiohttp|httpx|requests|socket|subprocess)(?:\.|\s|$)",
            r"^from\s+(?:aiohttp|httpx|requests|socket|subprocess)(?:\.|\s)",
            r"^import\s+urllib\.request(?:\s|$)",
            r"^from\s+urllib\.request(?:\s|\.)",
        )
        for source_name, source in (
            ("boundary policy", self.policy_source),
            ("request contract", self.contract_source),
            ("destination policy", self.destination_source),
        ):
            for pattern in prohibited_imports:
                self.assertIsNone(
                    re.search(pattern, source, flags=re.MULTILINE),
                    msg=f"Phase 12 {source_name} must remain transport-free: {pattern}",
                )

    def test_destination_policy_does_not_resolve_dns_or_open_sockets(self) -> None:
        for token in ("getaddrinfo", "gethostbyname", "create_connection", "socket.socket"):
            self.assertNotIn(token, self.destination_source)
        self.assertIn("from urllib.parse import", self.destination_source)
        self.assertIn("import ipaddress", self.destination_source)

    def test_transport_is_the_only_phase12_network_capability_surface(self) -> None:
        self.assertIn("getaddrinfo", self.transport_source)
        self.assertIn("asyncio.open_connection", self.transport_source)
        self.assertIn("socket.AI_NUMERICHOST", self.transport_source)
        self.assertIn("server_hostname=admission.hostname", self.transport_source)
        self.assertIn('tls_context.set_alpn_protocols(["http/1.1"])', self.transport_source)
        self.assertIn("ssl.create_default_context()", self.transport_source)

    def test_transport_has_no_tls_auth_or_proxy_bypass(self) -> None:
        prohibited_tokens = (
            "cert_none",
            "_create_unverified_context",
            "check_hostname = false",
            "trust_env",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "proxy-authorization:",
            "authorization:",
            "cookie:",
            "set-cookie:",
            "follow_redirects",
            "allow_redirects",
        )
        lower = self.transport_source.lower()
        for token in prohibited_tokens:
            self.assertNotIn(token, lower)

    def test_transport_has_fixed_read_only_request_surface(self) -> None:
        self.assertIn('_ALLOWED_METHODS = frozenset({"GET", "HEAD"})', self.destination_source)
        self.assertIn("Accept-Encoding: identity", self.transport_source)
        self.assertIn("Connection: close", self.transport_source)
        self.assertNotIn("request_headers", self.transport_source)
        self.assertNotIn("extra_headers", self.transport_source)

    def test_transport_has_no_privileged_or_execution_control_dependency(self) -> None:
        prohibited_tokens = (
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
            "openai_api_key",
            "github_token",
            "telegram",
        )
        lower = self.transport_source.lower()
        for token in prohibited_tokens:
            self.assertNotIn(token, lower)

    def test_phase12_policy_layers_have_no_privileged_control_plane_dependency(self) -> None:
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
        combined = "\n".join(
            (self.policy_source, self.contract_source, self.destination_source)
        ).lower()
        for token in prohibited_tokens:
            self.assertNotIn(token, combined)

    def test_12d_transport_does_not_self_register_or_import_agent_registry(self) -> None:
        self.assertNotIn("tools.registry", self.transport_source)
        self.assertNotIn("agents.registry", self.transport_source)
        self.assertNotIn("tool_registry.register", self.transport_source)
        self.assertNotIn("agent_registry.register", self.transport_source)

    def test_source_registry_keeps_search_disabled_and_public_web_explicitly_bounded(self) -> None:
        public_web_block = self.contract_source.split(
            'source_id="public-web"', maxsplit=1
        )[1].split("ResearchSourceDefinition(", maxsplit=1)[0]
        web_search_block = self.contract_source.split(
            'source_id="web-search"', maxsplit=1
        )[1].split(")", maxsplit=1)[0]

        self.assertIn('provider_id="dap-public-http"', public_web_block)
        self.assertIn('tool_id="internet.research.retrieve"', public_web_block)
        self.assertIn("execution_enabled=True", public_web_block)
        self.assertIn("untrusted_content=True", public_web_block)

        self.assertIn('provider_id="unconfigured-search-provider"', web_search_block)
        self.assertIn("tool_id=None", web_search_block)
        self.assertIn("execution_enabled=False", web_search_block)
        self.assertIn("untrusted_content=True", web_search_block)


if __name__ == "__main__":
    unittest.main()
