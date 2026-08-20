from __future__ import annotations

import unittest
from pathlib import Path


class Phase15ProviderReliabilityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.provider_source = (
            cls.repo_root / "platform/backend/gateway/searxng_search_provider.py"
        ).read_text(encoding="utf-8")
        cls.discovery_source = (
            cls.repo_root / "platform/backend/gateway/web_search_discovery.py"
        ).read_text(encoding="utf-8")
        cls.fallback_source = (
            cls.repo_root / "platform/backend/gateway/research_query_fallback.py"
        ).read_text(encoding="utf-8")
        cls.selection_source = (
            cls.repo_root / "platform/backend/gateway/research_source_quality.py"
        ).read_text(encoding="utf-8")
        cls.corpus_source = (
            cls.repo_root / "platform/backend/gateway/research_provider_corpus.py"
        ).read_text(encoding="utf-8")
        cls.live_benchmark_source = (
            cls.repo_root / "platform/backend/gateway/research_provider_live_benchmark.py"
        ).read_text(encoding="utf-8")
        cls.readiness_source = (
            cls.repo_root / "platform/backend/gateway/research_provider_readiness.py"
        ).read_text(encoding="utf-8")
        cls.routes_source = (
            cls.repo_root / "platform/backend/gateway/research_routes.py"
        ).read_text(encoding="utf-8")
        cls.executor_source = (
            cls.repo_root / "platform/backend/agents/research_executor.py"
        ).read_text(encoding="utf-8")
        cls.navigation_source = (
            cls.repo_root / "apps/dashboard/src/app/components/AppNavigation.tsx"
        ).read_text(encoding="utf-8")
        cls.roadmap_source = (
            cls.repo_root / "docs/phase15-research-provider-reliability-roadmap.md"
        ).read_text(encoding="utf-8")

    def test_provider_endpoint_remains_fixed_loopback(self) -> None:
        self.assertIn(
            'SEARXNG_HOST: Literal["127.0.0.1"] = "127.0.0.1"',
            self.provider_source,
        )
        self.assertIn("SEARXNG_PORT = 8888", self.provider_source)
        self.assertIn("socket.AI_NUMERICHOST", self.provider_source)
        self.assertIn("MAX_SEARXNG_PROVIDER_RESULT_SCAN = 20", self.provider_source)
        for token in (
            "os.getenv",
            "os.environ",
            "DAP_SEARXNG_URL",
            "SEARXNG_URL",
        ):
            self.assertNotIn(token, self.provider_source)

    def test_result_scanning_is_bounded_and_cannot_expand_retrieval_count(self) -> None:
        self.assertIn(
            "provider_results[:MAX_SEARXNG_PROVIDER_RESULT_SCAN]",
            self.provider_source,
        )
        self.assertIn("SEARXNG_CANDIDATE_RESERVOIR_LIMIT = 8", self.provider_source)
        self.assertIn("reservoir_limit = _candidate_reservoir_limit(query.count)", self.provider_source)
        self.assertIn("if len(candidate_records) >= reservoir_limit", self.provider_source)
        self.assertIn("additional_provider_request_performed: Literal[False]", self.provider_source)
        self.assertIn("MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL = 3", self.discovery_source)
        self.assertIn(
            "limit=MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL",
            self.discovery_source,
        )

    def test_no_candidate_diagnostics_do_not_change_stable_error_code(self) -> None:
        self.assertIn('"no-search-candidates"', self.discovery_source)
        for token in (
            '"provider_result_count"',
            '"considered_result_count"',
            '"invalid_candidate_count"',
            '"policy_rejected_candidate_count"',
            '"provider_zero_results"',
            '"admissible_candidate_zero_after_filtering"',
        ):
            self.assertIn(token, self.discovery_source)

    def test_query_fallback_is_owner_query_only_same_provider_and_bounded(self) -> None:
        self.assertIn("MAX_SEARCH_QUERY_ATTEMPTS = 3", self.fallback_source)
        self.assertIn("added_query_terms_allowed: bool = False", self.fallback_source)
        self.assertIn("provider_switching_allowed: bool = False", self.fallback_source)
        self.assertIn("model_generated_expansion_allowed: bool = False", self.fallback_source)
        self.assertIn("build_research_query_attempts(query)", self.discovery_source)
        self.assertIn("provider=SearXNGWebSearchProvider()", self.discovery_source)
        for token in ("httpx", "requests", "urlopen", "socket", "openai"):
            self.assertNotIn(token, self.fallback_source.lower())

    def test_duplicate_normalization_never_rewrites_selected_retrieval_url(self) -> None:
        self.assertIn(
            'SOURCE_URL_DUPLICATE_POLICY_ID = "dap-source-url-dedup-v2"',
            self.selection_source,
        )
        self.assertIn("canonical_source_url_duplicate_key", self.selection_source)
        self.assertIn("selected_urls = tuple(candidate.url", self.selection_source)
        self.assertIn("limit must be between 1 and 3", self.selection_source)
        self.assertIn("provider_title_used_as_evidence: bool = False", self.selection_source)
        self.assertIn("provider_snippet_used_as_evidence: bool = False", self.selection_source)

    def test_provider_and_retrieval_latency_are_observation_only(self) -> None:
        for token in (
            "provider_search_duration_ms",
            "retrieval_duration_ms",
            "total_pipeline_duration_ms",
        ):
            self.assertIn(token, self.discovery_source)
        for token in ("sleep(", "kill(", "terminate(", "send_signal("):
            self.assertNotIn(token, self.discovery_source.lower())

    def test_benchmark_corpus_is_frozen_before_live_execution(self) -> None:
        self.assertIn("PHASE15_CORPUS_MINIMUM_CASES = 30", self.corpus_source)
        self.assertEqual(self.corpus_source.count("ResearchProviderCorpusCase("), 31)
        for token in (
            '"official-documentation"',
            '"standards"',
            '"general-factual"',
            '"multi-source-technical"',
        ):
            self.assertIn(token, self.corpus_source)

    def test_live_benchmark_uses_isolated_truth_and_cannot_mutate_production_truth(self) -> None:
        self.assertIn("not str(resolved).startswith(\"/tmp/\")", self.live_benchmark_source)
        self.assertIn("LIVE_CASE_TIMEOUT_SECONDS = 60.0", self.live_benchmark_source)
        self.assertIn(
            "production_task_truth_mutation_performed",
            self.live_benchmark_source,
        )
        self.assertIn(
            "production_research_evidence_mutation_performed",
            self.live_benchmark_source,
        )
        self.assertIn("Literal[False] = False", self.live_benchmark_source)
        self.assertNotIn("TaskLedgerRecord", self.live_benchmark_source)
        self.assertNotIn("persist_task", self.live_benchmark_source)

    def test_readiness_is_get_only_observation_without_remediation_authority(self) -> None:
        self.assertIn('"/operations/provider-readiness"', self.routes_source)
        self.assertIn("@router.get", self.routes_source)
        self.assertNotIn("@router.post", self.routes_source)
        for token in (
            "smart_routing_research_activated: Literal[False] = False",
            "network_authority_granted: Literal[False] = False",
            "mutation_authority_granted: Literal[False] = False",
            "service_control_authority_granted: Literal[False] = False",
            "provider_reconfiguration_authority_granted: Literal[False] = False",
        ):
            self.assertIn(token, self.readiness_source)

    def test_research_agent_history_exposes_only_safe_phase15_diagnostics(self) -> None:
        for token in (
            '"search_diagnostics"',
            '"original_query"',
            '"search_attempt_count"',
            '"search_queries_attempted"',
            '"search_fallback_policy_id"',
            '"fallback_used"',
            '"search_attempts"',
            '"duplicate_normalization_policy_id"',
            '"skipped_canonical_duplicate_count"',
            '"provider_search_duration_ms"',
            '"retrieval_duration_ms"',
            '"total_pipeline_duration_ms"',
        ):
            self.assertIn(token, self.executor_source)
        self.assertIn('"provider_snippets_exposed_to_model": False', self.executor_source)
        self.assertIn('"provider_titles_exposed_to_model": False', self.executor_source)
        self.assertNotIn("candidate.title", self.executor_source)
        self.assertNotIn("candidate.snippet", self.executor_source)

    def test_phase15_adds_no_privileged_or_service_control_authority(self) -> None:
        combined = (
            f"{self.provider_source}\n{self.discovery_source}\n"
            f"{self.fallback_source}\n{self.selection_source}\n"
            f"{self.live_benchmark_source}\n{self.readiness_source}\n"
            f"{self.executor_source}"
        ).lower()
        for token in (
            "systemctl",
            "docker.sock",
            "/var/run/docker.sock",
            "subprocess",
            "os.system",
            "sudo ",
            "telegram",
            "guardianclient",
        ):
            self.assertNotIn(token, combined)

    def test_frontend_visibility_does_not_embed_provider_network_authority(self) -> None:
        self.assertIn('label: "Research"', self.navigation_source)
        self.assertIn('label: "Research Ops"', self.navigation_source)
        self.assertNotIn("127.0.0.1:8888", self.navigation_source)
        self.assertNotIn("/search?q=", self.navigation_source)

    def test_smart_routing_remains_explicitly_out_of_scope(self) -> None:
        self.assertIn("does **not** activate smart-routing research", self.roadmap_source)
        self.assertIn(
            "Any future authority expansion requires a separate owner-approved milestone.",
            self.roadmap_source,
        )


if __name__ == "__main__":
    unittest.main()
