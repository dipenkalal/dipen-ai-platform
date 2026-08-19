from __future__ import annotations

import unittest
from pathlib import Path


class Phase14ProviderRecoveryBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.path = cls.repo_root / "scripts/phase14_research_operations_provider_recovery.py"
        cls.source = cls.path.read_text(encoding="utf-8")
        cls.lower = cls.source.lower()

    def test_recovery_bridge_is_present_and_bounded(self) -> None:
        self.assertTrue(self.path.is_file())
        self.assertIn("MIN_SUCCESSFUL_RUNS = 2", self.source)
        self.assertIn("MIN_OPERATIONS_EVENTS = 5", self.source)
        self.assertIn("MAX_FALLBACK_ATTEMPTS = 3", self.source)
        self.assertEqual(self.source.count('"mode": "manual"'), 1)
        self.assertEqual(self.source.count('"agent_id": "research-agent"'), 1)

    def test_recovery_bridge_uses_only_fixed_loopback_agent_endpoint(self) -> None:
        self.assertIn(
            'BACKEND_RUN_URL = "http://127.0.0.1:8002/api/v1/agents/run"',
            self.source,
        )
        for token in (
            "https://",
            "0.0.0.0",
            "api.telegram.org",
            "docker.sock",
            "requests.get(",
            "httpx.",
            "socket.",
        ):
            self.assertNotIn(token, self.lower)

    def test_recovery_reconciles_only_one_failed_instrumented_task(self) -> None:
        self.assertIn("expected exactly one unrecorded failed task", self.source)
        self.assertIn('verify_task(failed_run_id, "failed")', self.source)
        self.assertIn('assigned == ["research-agent"]', self.source)
        self.assertIn('requested_by', self.source)
        self.assertIn("failed search unexpectedly changed evidence count", self.source)
        self.assertIn("failed search unexpectedly changed retrieval operations count", self.source)

    def test_recovery_does_not_change_runtime_source(self) -> None:
        self.assertIn("allowed_source_transition", self.source)
        self.assertIn('"scripts/phase14"', self.source)
        self.assertIn('"platform/guardian/tests/test_phase14"', self.source)
        self.assertIn('".github/workflows/phase14"', self.source)
        self.assertIn('"docs/phase14"', self.source)
        self.assertIn("runtime source changed since live backend load", self.source)

    def test_recovery_has_no_service_or_container_authority(self) -> None:
        for token in (
            "sudo",
            "systemctl restart",
            "systemctl start",
            "systemctl stop",
            "docker ",
            "docker.compose",
            "subprocess.popen",
        ):
            self.assertNotIn(token, self.lower)

    def test_recovery_cannot_merge_release_or_expand_approval_authority(self) -> None:
        for token in (
            "git merge",
            "git push",
            "gh pr merge",
            "git tag",
            "github release",
            "dap_telegram_approvals_enabled=true",
            "guardian",
        ):
            self.assertNotIn(token, self.lower)

    def test_recovery_delegates_only_to_guarded_phase14_operator(self) -> None:
        self.assertIn(
            'LIVE_OPERATOR = REPO / "scripts/phase14-research-operations-live-burnin.sh"',
            self.source,
        )
        self.assertIn(
            '["bash", str(LIVE_OPERATOR), args.expected_head]',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
