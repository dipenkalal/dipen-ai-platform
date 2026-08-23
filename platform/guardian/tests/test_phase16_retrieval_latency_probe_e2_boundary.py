from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE = REPO_ROOT / "platform/backend/gateway/research_retrieval_latency_probe_e2.py"


class Phase16RetrievalLatencyProbeE2BoundaryTests(unittest.TestCase):
    def test_probe_is_diagnostic_only_and_isolated(self) -> None:
        source = PROBE.read_text(encoding="utf-8")

        self.assertIn(
            'PHASE16_RETRIEVAL_LATENCY_E2_VERSION: Literal["phase16e2.1"]',
            source,
        )
        self.assertIn('truth_database_scope: Literal["isolated-diagnostic"]', source)
        self.assertIn('provider_configuration_mutated: Literal[False]', source)
        self.assertIn('transport_behavior_mutated: Literal[False]', source)
        self.assertIn('transport_timeout_mutated: Literal[False]', source)
        self.assertIn('retry_policy_mutated: Literal[False]', source)
        self.assertIn('concurrency_policy_mutated: Literal[False]', source)
        self.assertIn('smart_routing_research_activated: Literal[False]', source)
        self.assertIn('provider_switching_performed: Literal[False]', source)
        self.assertIn('generic_network_authority_expanded: Literal[False]', source)
        self.assertIn('provider_titles_or_snippets_recorded: Literal[False]', source)
        self.assertIn('guardian_contacted: Literal[False]', source)
        self.assertIn('privileged_host_action_performed: Literal[False]', source)
        self.assertIn('not str(resolved).startswith("/tmp/")', source)

    def test_probe_measures_frozen_phase15_source_target_without_changing_it(self) -> None:
        source = PROBE.read_text(encoding="utf-8")

        self.assertIn("MAXIMUM_LIVE_RETRIEVAL_P95_MS", source)
        self.assertIn("frozen_retrieval_source_p95_ms", source)
        self.assertIn("nearest_rank_percentile", source)
        self.assertIn("TRANSIENT_RETRY_BACKOFF_SECONDS", source)
        self.assertIn("tool_overhead_excluding_backoff_ms", source)

    def test_probe_reuses_sealed_provider_and_transport(self) -> None:
        source = PROBE.read_text(encoding="utf-8")

        self.assertIn("SearXNGWebSearchProvider()", source)
        self.assertIn("BoundedInternetRetriever(", source)
        self.assertIn("PinnedHTTPSFetcher(", source)
        self.assertIn("InternetResearchRetrieveTool(", source)
        self.assertIn("PHASE15_PROVIDER_CORPUS", source)
        self.assertIn("enable_bounded_query_fallback=True", source)

    def test_probe_does_not_expose_generic_http_or_deployment_authority(self) -> None:
        lowered = PROBE.read_text(encoding="utf-8").lower()

        for prohibited in (
            "httpx",
            "requests.",
            "aiohttp",
            "subprocess",
            "docker compose",
            "docker run",
            "systemctl",
            "sudo ",
            "os.system",
        ):
            self.assertNotIn(prohibited, lowered)


if __name__ == "__main__":
    unittest.main()
