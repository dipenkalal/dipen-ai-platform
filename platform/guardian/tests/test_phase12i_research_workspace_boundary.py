from __future__ import annotations

import re
import unittest
from pathlib import Path


class Phase12IResearchWorkspaceBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.workspace_source = (
            cls.repo_root / "platform/backend/gateway/research_workspace.py"
        ).read_text(encoding="utf-8")
        cls.routes_source = (
            cls.repo_root / "platform/backend/gateway/research_routes.py"
        ).read_text(encoding="utf-8")
        cls.combined = f"{cls.workspace_source}\n{cls.routes_source}"

    def test_workspace_has_no_network_transport_or_provider_execution_surface(self) -> None:
        prohibited_imports = (
            r"^import\s+(?:aiohttp|httpx|requests|socket|ssl|subprocess)(?:\.|\s|$)",
            r"^from\s+(?:aiohttp|httpx|requests|socket|ssl|subprocess)(?:\.|\s)",
            r"^import\s+urllib\.request(?:\s|$)",
            r"^from\s+urllib\.request(?:\s|\.)",
        )
        for pattern in prohibited_imports:
            self.assertIsNone(re.search(pattern, self.combined, flags=re.MULTILINE))

        lower = self.combined.lower()
        for token in (
            "boundedinternetretriever",
            "searxngwebsearchprovider",
            "websearchretrievalpipeline",
            "tool_registry",
            "gateway_service.chat",
            "shared_http",
        ):
            self.assertNotIn(token, lower)

    def test_routes_are_get_only_and_repository_is_opened_without_initialization(self) -> None:
        lower = self.routes_source.lower()
        self.assertIn("@router.get(", lower)
        for token in (
            "@router.post(",
            "@router.put(",
            "@router.patch(",
            "@router.delete(",
        ):
            self.assertNotIn(token, lower)
        self.assertIn("initialize=false", lower.replace(" ", ""))

    def test_workspace_has_no_task_knowledge_or_evidence_mutation_path(self) -> None:
        lower = self.combined.lower()
        for token in (
            ".persist(",
            ".upsert_task(",
            "insert into ",
            "update task_ledger",
            "delete from ",
            "knowledge_repository",
            "qdrant",
            "agent_registry.register",
            "tool_registry.register",
        ):
            self.assertNotIn(token, lower)

    def test_workspace_exposes_explicit_read_only_provenance_contract(self) -> None:
        self.assertIn(
            'provenance_kind: Literal["internet_evidence"]',
            self.workspace_source,
        )
        self.assertIn(
            'workspace_mode: Literal["read_only"]',
            self.workspace_source,
        )
        self.assertIn(
            "ui_network_authority_granted: Literal[False] = False",
            self.workspace_source,
        )
        self.assertIn(
            "ui_mutation_authority_granted: Literal[False] = False",
            self.workspace_source,
        )
        self.assertIn(
            "search_candidate_metadata_included: Literal[False] = False",
            self.workspace_source,
        )

    def test_workspace_has_no_privileged_control_surface(self) -> None:
        lower = self.combined.lower()
        for token in (
            "guardian_broker",
            "guardian_client",
            "systemctl",
            "docker.sock",
            "/var/run/docker.sock",
            "os.system(",
            "subprocess.",
            "telegram",
            "github_token",
            "openai_api_key",
        ):
            self.assertNotIn(token, lower)


if __name__ == "__main__":
    unittest.main()
