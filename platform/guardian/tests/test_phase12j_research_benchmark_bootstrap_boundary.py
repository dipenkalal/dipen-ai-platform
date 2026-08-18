from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BOOTSTRAP = (
    REPO_ROOT
    / "platform"
    / "backend"
    / "gateway"
    / "research_benchmark_bootstrap.py"
)


class Phase12JResearchBenchmarkBootstrapBoundaryTests(unittest.TestCase):
    def test_bootstrap_is_narrow_database_schema_only_helper(self) -> None:
        source = BOOTSTRAP.read_text(encoding="utf-8")

        self.assertIn("ResearchRetrievalRepository", source)
        self.assertIn("AgentTruthRepository", source)
        self.assertIn('RESEARCH_EVIDENCE_TABLE = "research_retrieval_evidence"', source)
        self.assertIn('TASK_LEDGER_TABLE = "task_ledger"', source)
        self.assertIn("task_after != task_before", source)
        self.assertIn("evidence_after != evidence_before", source)

        forbidden = (
            "subprocess",
            "os.system",
            "systemctl",
            "docker.sock",
            "docker compose",
            "sudo ",
            "requests.",
            "httpx.",
            "urllib.request",
            "socket.",
            "guardian-broker",
            "telegram",
            "git merge",
            "git push",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source.lower())

    def test_bootstrap_does_not_embed_task_or_knowledge_mutation_sql(self) -> None:
        source = BOOTSTRAP.read_text(encoding="utf-8").lower()

        forbidden_sql = (
            "insert into task_ledger",
            "update task_ledger",
            "delete from task_ledger",
            "drop table task_ledger",
            "insert into knowledge",
            "update knowledge",
            "delete from knowledge",
        )
        for token in forbidden_sql:
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
