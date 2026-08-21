from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTIC = REPO_ROOT / "platform/backend/gateway/research_provider_diagnostic.py"
ROADMAP = REPO_ROOT / "docs/phase16-research-provider-coverage-latency-roadmap.md"


class Phase16ProviderDiagnosticBoundaryTests(unittest.TestCase):
    def test_diagnostic_is_isolated_and_non_authoritative(self) -> None:
        source = DIAGNOSTIC.read_text(encoding="utf-8")

        self.assertIn('truth_database_scope: Literal["isolated-diagnostic"]', source)
        self.assertIn('provider_configuration_mutated: Literal[False]', source)
        self.assertIn('production_task_truth_mutation_performed: Literal[False]', source)
        self.assertIn(
            'production_research_evidence_mutation_performed: Literal[False]',
            source,
        )
        self.assertIn(
            'production_research_operations_mutation_performed: Literal[False]',
            source,
        )
        self.assertIn('smart_routing_research_activated: Literal[False]', source)
        self.assertIn('provider_switching_performed: Literal[False]', source)
        self.assertIn('generic_network_authority_expanded: Literal[False]', source)
        self.assertIn('guardian_contacted: Literal[False]', source)
        self.assertIn('privileged_host_action_performed: Literal[False]', source)

    def test_diagnostic_never_persists_provider_titles_or_snippets(self) -> None:
        source = DIAGNOSTIC.read_text(encoding="utf-8")

        self.assertIn('provider_titles_recorded: Literal[False]', source)
        self.assertIn('provider_snippets_recorded: Literal[False]', source)
        self.assertIn(
            'provider_titles_or_snippets_used_as_evidence: Literal[False]',
            source,
        )
        self.assertNotIn('item.get("title")', source)
        self.assertNotIn('item.get("snippet")', source)

    def test_provider_endpoint_and_retrieval_ceiling_are_not_changed_here(self) -> None:
        source = DIAGNOSTIC.read_text(encoding="utf-8")
        roadmap = ROADMAP.read_text(encoding="utf-8")

        self.assertIn("SearXNGWebSearchProvider()", source)
        self.assertIn("provider remains `searxng-local-v1`", roadmap)
        self.assertIn("selected retrieval ceiling remains at most three URLs", roadmap)
        self.assertIn("does **not** activate smart-routing research", roadmap)
        self.assertIn(
            "Any future authority expansion requires a separate owner-approved milestone.",
            roadmap,
        )

    def test_diagnostic_has_no_service_or_container_control(self) -> None:
        source = DIAGNOSTIC.read_text(encoding="utf-8").lower()

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
