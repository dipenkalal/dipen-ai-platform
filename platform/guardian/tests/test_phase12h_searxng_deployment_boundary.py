from __future__ import annotations

import re
import unittest
from pathlib import Path


class Phase12HSearXNGDeploymentBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.deploy_dir = cls.repo_root / "deploy/phase12h-searxng"
        cls.compose_source = (cls.deploy_dir / "compose.yml").read_text(encoding="utf-8")
        cls.settings_source = (cls.deploy_dir / "settings.yml").read_text(encoding="utf-8")
        cls.env_example = (cls.deploy_dir / ".env.example").read_text(encoding="utf-8")

    def test_image_is_exactly_pinned_and_not_latest(self) -> None:
        self.assertIn(
            "ghcr.io/searxng/searxng:2026.7.28-c01178d03@sha256:"
            "80622959f0f3512e6623d6bdbcea9f13c8d22c8d9715c498d0ae2be1c8535930",
            self.compose_source,
        )
        self.assertIn("platform: linux/amd64", self.compose_source)
        self.assertNotIn(":latest", self.compose_source)

    def test_host_publication_is_loopback_only(self) -> None:
        self.assertIn('"127.0.0.1:8888:8080"', self.compose_source)
        self.assertNotIn('"0.0.0.0:8888:8080"', self.compose_source)
        self.assertNotIn('"8888:8080"', self.compose_source)
        self.assertNotIn("network_mode: host", self.compose_source)

    def test_container_has_no_privileged_host_control_surface(self) -> None:
        lower = self.compose_source.lower()
        self.assertIn("no-new-privileges:true", lower)
        self.assertIn("cap_drop:", lower)
        self.assertIn("- all", lower)
        for token in (
            "privileged: true",
            "/var/run/docker.sock",
            "pid: host",
            "ipc: host",
            "devices:",
        ):
            self.assertNotIn(token, lower)

    def test_local_configuration_enables_json_and_disables_public_features(self) -> None:
        self.assertIn("- json", self.settings_source)
        self.assertIn("safe_search: 2", self.settings_source)
        self.assertIn("limiter: false", self.settings_source)
        self.assertIn("public_instance: false", self.settings_source)
        self.assertIn("image_proxy: false", self.settings_source)
        self.assertIn("keep_only:", self.settings_source)

        match = re.search(
            r"keep_only:\n(?P<body>(?:\s{6}- [^\n]+\n)+)",
            self.settings_source,
        )
        self.assertIsNotNone(match)
        assert match is not None
        engines = [
            line.strip().removeprefix("- ")
            for line in match.group("body").splitlines()
            if line.strip().startswith("- ")
        ]
        self.assertGreaterEqual(len(engines), 1)
        self.assertLessEqual(len(engines), 8)
        self.assertEqual(len(engines), len(set(engines)))
        self.assertNotIn("use_default_settings: true", self.settings_source)

    def test_runtime_secret_is_local_only_and_no_paid_provider_key_is_declared(self) -> None:
        self.assertIn("SEARXNG_SECRET", self.compose_source)
        self.assertIn("SEARXNG_SECRET=replace-with-local-random-secret", self.env_example)
        combined = (self.compose_source + self.settings_source + self.env_example).lower()
        for token in (
            "dap_brave_search_api_key",
            "x-subscription-token",
            "api_key:",
            "authorization:",
        ):
            self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
