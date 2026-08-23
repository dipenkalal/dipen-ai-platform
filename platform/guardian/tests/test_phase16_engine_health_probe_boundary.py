from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE = REPO_ROOT / "platform/backend/gateway/research_engine_health_probe.py"
PROVIDER = REPO_ROOT / "platform/backend/gateway/searxng_search_provider.py"
ROADMAP = REPO_ROOT / "docs/phase16-research-provider-coverage-latency-roadmap.md"


class Phase16EngineHealthProbeBoundaryTests(unittest.TestCase):
    def test_probe_is_read_only_and_non_authoritative(self) -> None:
        source = PROBE.read_text(encoding="utf-8")

        self.assertIn('provider_configuration_mutated: Literal[False]', source)
        self.assertIn('production_truth_mutation_performed: Literal[False]', source)
        self.assertIn('smart_routing_research_activated: Literal[False]', source)
        self.assertIn('provider_switching_performed: Literal[False]', source)
        self.assertIn('generic_network_authority_expanded: Literal[False]', source)
        self.assertIn('automatic_knowledge_mutation_performed: Literal[False]', source)
        self.assertIn('destructive_evidence_cleanup_performed: Literal[False]', source)
        self.assertIn('guardian_contacted: Literal[False]', source)
        self.assertIn('privileged_host_action_performed: Literal[False]', source)

    def test_probe_records_no_provider_text_or_raw_engine_errors(self) -> None:
        source = PROBE.read_text(encoding="utf-8")
        provider = PROVIDER.read_text(encoding="utf-8")

        self.assertIn('provider_titles_or_snippets_recorded: Literal[False]', source)
        self.assertIn('raw_engine_error_text_recorded: Literal[False]', source)
        self.assertIn('raw_error_text_recorded: Literal[False]', provider)
        self.assertNotIn('item.get("title")', source)
        self.assertNotIn('item.get("content")', source)

    def test_probe_does_not_change_provider_configuration_or_authority(self) -> None:
        source = PROBE.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")

        self.assertIn("SearXNGWebSearchProvider()", source)
        self.assertIn("provider remains `searxng-local-v1`", roadmap)
        self.assertIn("does **not** activate smart-routing research", roadmap)
        self.assertIn(
            "Any future authority expansion requires a separate owner-approved milestone.",
            roadmap,
        )

    def test_probe_has_no_service_container_or_git_control(self) -> None:
        source = PROBE.read_text(encoding="utf-8").lower()

        for prohibited in (
            "systemctl",
            "docker ",
            "/var/run/docker.sock",
            "subprocess",
            "os.system",
            "sudo ",
            "telegram",
            "merge_pull_request",
            "git push",
        ):
            self.assertNotIn(prohibited, source)


if __name__ == "__main__":
    unittest.main()
