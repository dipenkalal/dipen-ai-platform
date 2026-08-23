from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = REPO_ROOT / (
    "platform/backend/gateway/research_provider_phase16_slow_tail_probe.py"
)
TRANSPORT = REPO_ROOT / "platform/backend/gateway/internet_transport.py"


class Phase16SlowTailProbeBoundaryTests(unittest.TestCase):
    def test_h1_is_targeted_and_repeats_only_observed_slow_tail_cases(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")

        self.assertIn('PHASE16_H1_PROBE_VERSION: Literal["phase16h1.1"]', source)
        self.assertIn("PHASE16_H1_REPEAT_COUNT: Literal[3] = 3", source)
        for case_id in (
            "p16-usgs-earthquake-magnitude",
            "p16-overlay-filesystems",
            "p16-rfc9293-tcp",
            "p16-dns-over-https",
        ):
            self.assertIn(f'"{case_id}"', source)

    def test_h1_reuses_sealed_provider_retrieval_and_e2_instrumentation(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")

        self.assertIn("SearXNGWebSearchProvider()", source)
        self.assertIn("InternetResearchRetrieveTool(", source)
        self.assertIn("DetailedLatencyTracingRetriever()", source)
        self.assertIn("enable_bounded_query_fallback=True", source)
        self.assertIn("MAXIMUM_LIVE_RETRIEVAL_P95_MS", source)
        self.assertIn("PHASE16_H1_CASE_TIMEOUT_SECONDS = 60.0", source)
        self.assertIn('truth_database_scope: Literal["isolated-phase16-h1-diagnostic"]', source)

    def test_h1_has_no_authority_or_runtime_mutation_controls(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")

        for marker in (
            'target_corpus_modified: Literal[False]',
            'provider_configuration_mutated: Literal[False]',
            'transport_behavior_mutated: Literal[False]',
            'transport_timeout_mutated: Literal[False]',
            'retry_policy_mutated: Literal[False]',
            'concurrency_policy_mutated: Literal[False]',
            'production_task_truth_mutation_performed: Literal[False]',
            'production_research_evidence_mutation_performed: Literal[False]',
            'production_research_operations_mutation_performed: Literal[False]',
            'smart_routing_research_activated: Literal[False]',
            'provider_switching_performed: Literal[False]',
            'generic_network_authority_expanded: Literal[False]',
            'provider_titles_or_snippets_recorded: Literal[False]',
            'automatic_knowledge_mutation_performed: Literal[False]',
            'destructive_evidence_cleanup_performed: Literal[False]',
            'guardian_contacted: Literal[False]',
            'privileged_host_action_performed: Literal[False]',
        ):
            self.assertIn(marker, source)

        lowered = source.lower()
        for prohibited in (
            "requests.",
            "aiohttp",
            "urllib.request",
            "socket.socket",
            "subprocess",
            "docker compose",
            "docker run",
            "systemctl",
            "sudo ",
            "os.system",
            "guardian_client",
            "guardian_broker",
        ):
            self.assertNotIn(prohibited, lowered)

    def test_production_transport_remains_identity_only(self) -> None:
        transport = TRANSPORT.read_text(encoding="utf-8")

        self.assertIn('"Accept-Encoding: identity"', transport)
        self.assertNotIn('"Accept-Encoding: gzip, identity"', transport)


if __name__ == "__main__":
    unittest.main()
