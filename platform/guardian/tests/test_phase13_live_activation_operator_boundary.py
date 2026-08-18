from __future__ import annotations

import unittest
from pathlib import Path


class Phase13LiveActivationOperatorBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.source = (
            cls.repo_root / "scripts/phase13-provider-specific-research-live-activate.sh"
        ).read_text(encoding="utf-8")
        cls.lower = cls.source.lower()

    def test_operator_uses_only_fixed_backend_restart_and_diagnostic_journal(self) -> None:
        self.assertEqual(
            self.source.count("sudo systemctl restart dap-backend.service"),
            1,
        )
        self.assertEqual(
            self.source.count("sudo journalctl -u dap-backend.service"),
            1,
        )
        self.assertNotIn("systemctl restart docker", self.lower)
        self.assertNotIn("systemctl restart dap-guardian", self.lower)
        self.assertNotIn("systemctl start dap-guardian", self.lower)

    def test_operator_recreates_only_dashboard_and_never_touches_docker_daemon(self) -> None:
        self.assertIn(
            "docker compose up -d --no-deps --no-build --force-recreate dashboard",
            self.source,
        )
        self.assertNotIn("docker compose down", self.lower)
        self.assertNotIn("docker system prune", self.lower)
        self.assertNotIn("docker restart", self.lower)
        self.assertNotIn("/var/run/docker.sock", self.lower)
        self.assertNotIn("--privileged", self.lower)

    def test_dashboard_application_build_is_offline(self) -> None:
        self.assertIn("docker run --rm --network none", self.source)
        self.assertIn("docker build --pull=false --network=none", self.source)
        self.assertNotIn("npm ci", self.lower)
        self.assertNotIn("npm install", self.lower)

    def test_live_run_is_manual_research_agent_with_bounded_query(self) -> None:
        self.assertIn('"mode":"manual"', self.source)
        self.assertIn('"agent_id":"research-agent"', self.source)
        self.assertIn('"research_search_query":"IANA example domains purpose"', self.source)
        self.assertIn("selected_urls", self.source)
        self.assertIn("len(selected) <= 3", self.source)
        self.assertIn("provider_snippets_exposed_to_model", self.source)
        self.assertIn("provider_titles_exposed_to_model", self.source)
        self.assertIn("generic_network_client_exposed", self.source)
        self.assertIn("remote_scope_expansion_allowed", self.source)

    def test_negative_proofs_cover_smart_and_nonresearch_activation(self) -> None:
        self.assertIn('"mode":"smart"', self.source)
        self.assertIn('"agent_id":"coding-agent"', self.source)
        self.assertIn('[[ "$SMART_HTTP" == "400" ]]', self.source)
        self.assertIn('[[ "$AGENT_HTTP" == "400" ]]', self.source)

    def test_operator_cannot_merge_release_or_change_approval_authority(self) -> None:
        for token in (
            "git merge",
            "git push",
            "gh pr merge",
            "git tag",
            "github release",
            "dap_telegram_approvals_enabled=true",
            "guardian_broker",
            "systemctl enable",
        ):
            self.assertNotIn(token, self.lower)


if __name__ == "__main__":
    unittest.main()
