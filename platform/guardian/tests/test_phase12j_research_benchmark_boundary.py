from __future__ import annotations

import re
import unittest
from pathlib import Path


class Phase12JResearchBenchmarkBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.source = (
            cls.repo_root / "platform/backend/gateway/research_benchmark.py"
        ).read_text(encoding="utf-8")
        cls.lower = cls.source.lower()

    def test_benchmark_has_no_privileged_or_service_control_surface(self) -> None:
        for token in (
            "systemctl",
            "docker.sock",
            "/var/run/docker.sock",
            "guardian_client",
            "guardian_broker",
            "telegram",
            "openai_api_key",
            "github_token",
        ):
            self.assertNotIn(token, self.lower)

        # Adversarial benchmark data intentionally contains the word "sudo".
        # Reject executable privilege paths rather than hostile quoted content.
        compact = self.lower.replace(" ", "")
        self.assertNotIn('["sudo",', self.lower)
        self.assertNotIn("('sudo',", self.lower)
        self.assertNotIn("os.system(", self.lower)
        self.assertNotIn("shell=true", compact)

    def test_benchmark_does_not_gain_task_or_knowledge_mutation_authority(self) -> None:
        for token in (
            "insert into task_ledger",
            "update task_ledger",
            "delete from task_ledger",
            "knowledge_repository",
            "qdrant",
            ".upsert_task(",
            "tool_registry.register",
            "agent_registry.register",
        ):
            self.assertNotIn(token, self.lower)
        self.assertIn('task_ledger_mutated: literal[false] = false', self.lower)
        self.assertIn(
            'automatic_knowledge_mutation_performed: literal[false] = false',
            self.lower,
        )

    def test_benchmark_uses_only_fixed_git_read_for_source_identity(self) -> None:
        self.assertIn('["git", "rev-parse", "head"]', self.lower)
        self.assertNotIn("shell=true", self.lower.replace(" ", ""))
        self.assertNotRegex(
            self.source,
            re.compile(r"subprocess\.(?:Popen|call|check_call|check_output)\("),
        )

    def test_benchmark_output_is_outside_source_checkout(self) -> None:
        self.assertIn(
            'DEFAULT_OUTPUT = Path("/tmp/phase12j-research-benchmark.json")',
            self.source,
        )
        self.assertNotIn("git commit", self.lower)
        self.assertNotIn("git push", self.lower)
        self.assertIn("main_merge_performed: Literal[False] = False", self.source)
        self.assertIn("deployment_performed: Literal[False] = False", self.source)

    def test_benchmark_search_path_is_fixed_to_local_searxng(self) -> None:
        self.assertIn("WebSearchRetrievalPipeline.searxng_local()", self.source)
        self.assertIn("SEARXNG_PROVIDER_ID", self.source)
        self.assertNotIn("BraveWebSearchProvider", self.source)
        self.assertNotIn("provider_credential", self.lower)

    def test_benchmark_frozen_matrix_contains_required_safety_probes(self) -> None:
        for slug in (
            'slug="public-retrieval"',
            'slug="ssrf-rejection"',
            'slug="failure-recovery"',
            'slug="searxng-to-retrieval"',
            'slug="prompt-injection-boundary"',
        ):
            self.assertIn(slug, self.source)


if __name__ == "__main__":
    unittest.main()
