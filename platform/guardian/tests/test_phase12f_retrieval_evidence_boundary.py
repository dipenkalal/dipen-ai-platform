from __future__ import annotations

import re
import unittest
from pathlib import Path


class Phase12FRetrievalEvidenceBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.evidence_source = (
            cls.repo_root / "platform/backend/gateway/research_retrieval_evidence.py"
        ).read_text(encoding="utf-8")
        cls.repository_source = (
            cls.repo_root / "platform/backend/gateway/research_retrieval_repository.py"
        ).read_text(encoding="utf-8")

    def test_evidence_factory_has_no_network_or_process_transport(self) -> None:
        prohibited_imports = (
            r"^import\s+(?:aiohttp|httpx|requests|socket|ssl|subprocess)(?:\.|\s|$)",
            r"^from\s+(?:aiohttp|httpx|requests|socket|ssl|subprocess)(?:\.|\s)",
            r"^import\s+urllib\.request(?:\s|$)",
            r"^from\s+urllib\.request(?:\s|\.)",
        )
        combined = f"{self.evidence_source}\n{self.repository_source}"
        for pattern in prohibited_imports:
            self.assertIsNone(re.search(pattern, combined, flags=re.MULTILINE))

    def test_repository_cannot_mutate_canonical_task_or_knowledge_truth(self) -> None:
        lower = self.repository_source.lower()
        for token in (
            ".upsert_task(",
            "insert into task_ledger",
            "update task_ledger",
            "delete from task_ledger",
            "knowledge_repository",
            "knowledge_documents",
            "qdrant",
        ):
            self.assertNotIn(token, lower)
        self.assertIn("get_task(", lower)
        self.assertIn("research_retrieval_evidence", lower)

    def test_evidence_and_repository_have_no_privileged_control_surface(self) -> None:
        lower = f"{self.evidence_source}\n{self.repository_source}".lower()
        for token in (
            "guardian_broker",
            "guardian_client",
            "systemctl",
            "/var/run/docker.sock",
            "docker.sock",
            "os.system(",
            "subprocess.",
            "agent_registry.register",
            "tool_registry.register",
            "openai_api_key",
            "github_token",
            "telegram",
        ):
            self.assertNotIn(token, lower)

    def test_persisted_record_declares_additive_non_mutating_semantics(self) -> None:
        self.assertIn("evidence_persisted: Literal[True] = True", self.repository_source)
        self.assertIn("task_ledger_mutated: Literal[False] = False", self.repository_source)
        self.assertIn("knowledge_mutated: Literal[False] = False", self.repository_source)
        self.assertIn("evidence_is_additive_only: Literal[True] = True", self.evidence_source)
        self.assertIn(
            "task_ledger_mutation_performed: Literal[False] = False",
            self.evidence_source,
        )
        self.assertIn(
            "automatic_knowledge_mutation_performed: Literal[False] = False",
            self.evidence_source,
        )

    def test_repository_is_idempotent_and_conflict_aware(self) -> None:
        self.assertIn("BEGIN IMMEDIATE", self.repository_source)
        self.assertIn("ResearchRetrievalPersistenceConflict", self.repository_source)
        self.assertIn("WHERE evidence_id = ?", self.repository_source)
        self.assertIn("evidence_sha256", self.repository_source)


if __name__ == "__main__":
    unittest.main()
