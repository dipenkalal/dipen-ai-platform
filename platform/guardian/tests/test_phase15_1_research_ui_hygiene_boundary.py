from __future__ import annotations

import unittest
from pathlib import Path


class Phase151ResearchUiHygieneBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.operations_source = (
            cls.repo_root / "platform/backend/gateway/research_operations.py"
        ).read_text(encoding="utf-8")
        cls.evidence_page = (
            cls.repo_root / "apps/dashboard/src/app/research/page.tsx"
        ).read_text(encoding="utf-8")
        cls.operations_page = (
            cls.repo_root / "apps/dashboard/src/app/research/operations/page.tsx"
        ).read_text(encoding="utf-8")
        cls.navigation_source = (
            cls.repo_root / "apps/dashboard/src/app/components/AppNavigation.tsx"
        ).read_text(encoding="utf-8")

    def test_failed_or_blocked_evidence_is_not_a_source_family(self) -> None:
        self.assertIn(
            'if record.evidence.outcome != "succeeded":',
            self.operations_source,
        )
        self.assertIn(
            'return None\n        url = record.evidence.final_url',
            self.operations_source,
        )

    def test_workspace_defaults_to_agent_run_scope_without_deleting_evidence(self) -> None:
        self.assertIn('useState<EvidenceView>("agent-runs")', self.evidence_page)
        self.assertIn("item.run !== null", self.evidence_page)
        self.assertIn("Research Agent runs", self.evidence_page)
        self.assertIn("All evidence", self.evidence_page)
        self.assertIn("Standalone evidence", self.evidence_page)
        self.assertIn(
            "stays immutable and remains available in All evidence",
            self.evidence_page,
        )
        for token in ("method: \"DELETE\"", "method: \"PATCH\"", "method: \"POST\""):
            self.assertNotIn(token, self.evidence_page)

    def test_operations_ui_distinguishes_historical_and_live_corpus_scopes(self) -> None:
        for token in (
            "Historical evidence success",
            "Historical evidence failure",
            "Metric scopes:",
            "percentages are not expected to match",
            "The isolated 30-case live corpus is the Phase 15 provider-quality gate",
            "Only successful retrieval evidence contributes to source-family analytics",
            "loopback safety probes",
            "reachability only",
        ):
            self.assertIn(token, self.operations_page)

    def test_navigation_overflow_is_scrollable_without_visible_browser_scrollbar(self) -> None:
        self.assertIn("overflow-x-auto", self.navigation_source)
        self.assertIn("[scrollbar-width:none]", self.navigation_source)
        self.assertIn("[&::-webkit-scrollbar]:hidden", self.navigation_source)
        self.assertIn("aria-label={item.label}", self.navigation_source)
        self.assertIn("title={item.label}", self.navigation_source)

    def test_hygiene_changes_add_no_research_or_privileged_authority(self) -> None:
        combined = (
            f"{self.evidence_page}\n{self.operations_page}\n{self.navigation_source}"
        ).lower()
        for token in (
            "http://127.0.0.1:8888",
            "/search?q=",
            "systemctl",
            "docker.sock",
            "/var/run/docker.sock",
            "sudo ",
            "guardianclient",
        ):
            self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
