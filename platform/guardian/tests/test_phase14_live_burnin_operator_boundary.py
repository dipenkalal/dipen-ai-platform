from __future__ import annotations

import unittest
from pathlib import Path


class Phase14LiveBurninOperatorBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.source = (
            cls.repo_root / "scripts/phase14-research-operations-live-burnin.sh"
        ).read_text(encoding="utf-8")
        cls.lower = cls.source.lower()

    def test_operator_restarts_only_backend_once(self) -> None:
        self.assertEqual(
            self.source.count("sudo systemctl restart dap-backend.service"),
            1,
        )
        self.assertEqual(
            self.source.count("sudo journalctl -u dap-backend.service"),
            1,
        )
        for token in (
            "systemctl restart docker",
            "systemctl restart dap-guardian",
            "systemctl start dap-guardian",
            "systemctl restart dap-searxng",
            "docker restart dap-searxng",
        ):
            self.assertNotIn(token, self.lower)

    def test_operator_recreates_only_dashboard(self) -> None:
        self.assertIn(
            "docker compose up -d --no-deps --no-build --force-recreate dashboard",
            self.source,
        )
        self.assertNotIn("docker compose down", self.lower)
        self.assertNotIn("docker system prune", self.lower)
        self.assertNotIn("docker restart", self.lower)
        self.assertNotIn("/var/run/docker.sock", self.lower)
        self.assertNotIn("--privileged", self.lower)

    def test_dashboard_build_is_offline_and_cleanup_is_fixed(self) -> None:
        self.assertIn('sudo rm -rf -- "$DASH/.next"', self.source)
        self.assertIn("docker run --rm --network none", self.source)
        self.assertIn("docker build --pull=false --network=none", self.source)
        self.assertIn('--user "$(id -u):$(id -g)"', self.source)
        self.assertNotIn("npm ci", self.lower)
        self.assertNotIn("npm install", self.lower)
        self.assertNotIn("sudo rm -rf /", self.lower)

    def test_live_research_is_manual_only_and_bounded(self) -> None:
        self.assertIn('"mode": "manual"', self.source)
        self.assertIn('"agent_id": "research-agent"', self.source)
        self.assertIn("MIN_BURNIN_RUNS=2", self.source)
        self.assertIn("MAX_BURNIN_RUNS=3", self.source)
        self.assertIn("MIN_BURNIN_OPERATIONS_EVENTS=5", self.source)
        self.assertIn("0 < len(selected) <= 3", self.source)
        self.assertIn(
            "source_selection_policy_id",
            self.source,
        )
        self.assertIn(
            "selection_quality_is_factual_credibility",
            self.source,
        )
        self.assertIn("provider_snippets_exposed_to_model", self.source)
        self.assertIn("provider_titles_exposed_to_model", self.source)
        self.assertIn("generic_network_client_exposed", self.source)
        self.assertIn("remote_scope_expansion_allowed", self.source)

    def test_smart_search_is_negative_proof_only(self) -> None:
        self.assertIn('"mode":"smart"', self.source)
        self.assertIn('[[ "$SMART_HTTP" == "400" ]]', self.source)
        self.assertIn("smart_routing_research_disabled|PASS", self.source)
        self.assertEqual(
            self.source.count('"mode":"smart"'),
            1,
        )

    def test_resume_state_prevents_duplicate_burnin(self) -> None:
        self.assertIn(
            'STATE="/tmp/dap-phase14-research-operations-live-state.json"',
            self.source,
        )
        self.assertIn("phase14_resume_state|VALID", self.source)
        self.assertIn("manual_research_burnin|RESUME_ALREADY_COMPLETE", self.source)
        self.assertIn("resume_task_count|MISMATCH_STOP", self.source)
        self.assertIn("resume_evidence_count|MISMATCH_STOP", self.source)
        self.assertIn("resume_operations_count|MISMATCH_STOP", self.source)
        self.assertIn("resume_backend_pid|MISMATCH_STOP", self.source)

    def test_retention_and_operations_proof_is_read_only(self) -> None:
        self.assertIn("evidence_deleted", self.source)
        self.assertIn("automatic_deletion_enabled", self.source)
        self.assertIn("automatic_archive_enabled", self.source)
        self.assertIn("service_control_authority_granted", self.source)
        self.assertIn("workspace_mode", self.source)
        self.assertIn("network_authority_granted", self.source)
        self.assertIn("mutation_authority_granted", self.source)
        for method in ("PUT", "PATCH", "DELETE"):
            self.assertNotIn(f"-X {method}", self.source)

    def test_operator_cannot_merge_release_or_expand_approval_authority(self) -> None:
        for token in (
            "git merge",
            "git push",
            "gh pr merge",
            "git tag",
            "github release",
            "dap_telegram_approvals_enabled=true",
            "systemctl enable",
            "systemctl start dap-guardian",
            "systemctl restart dap-guardian",
        ):
            self.assertNotIn(token, self.lower)


if __name__ == "__main__":
    unittest.main()
