from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_QUALITY = REPO_ROOT / "platform/backend/gateway/research_source_quality.py"
SEARXNG_PROVIDER = REPO_ROOT / "platform/backend/gateway/searxng_search_provider.py"
DISCOVERY = REPO_ROOT / "platform/backend/gateway/web_search_discovery.py"
TRANSPORT = REPO_ROOT / "platform/backend/gateway/internet_transport.py"
VALIDATION_CORPUS = REPO_ROOT / (
    "platform/backend/gateway/research_provider_phase16_validation_corpus.py"
)


class Phase16SourceSelectionResilienceBoundaryTests(unittest.TestCase):
    def test_h2_is_generic_and_has_no_observed_slow_source_exception(self) -> None:
        quality = SOURCE_QUALITY.read_text(encoding="utf-8")
        provider = SEARXNG_PROVIDER.read_text(encoding="utf-8")
        combined = (quality + provider).casefold()

        self.assertIn(
            'SOURCE_SELECTION_POLICY_ID = "dap-source-family-diversity-url-resilience-v2"',
            quality,
        )
        self.assertIn(
            'SOURCE_RETRIEVAL_RESILIENCE_POLICY_ID = "dap-url-retrieval-resilience-v1"',
            quality,
        )
        self.assertIn(
            'SEARXNG_CANDIDATE_RESILIENCE_POLICY_ID = '
            '"dap-searxng-provider-support-reservoir-v1"',
            provider,
        )
        self.assertNotIn("atscontainers.com", combined)
        self.assertNotIn("github.com", combined)
        self.assertNotIn("p16-overlay-filesystems", combined)
        self.assertNotIn("p16-rfc9293-tcp", combined)

    def test_h2_reservoir_uses_same_fixed_provider_response_only(self) -> None:
        provider = SEARXNG_PROVIDER.read_text(encoding="utf-8")

        self.assertIn("SEARXNG_CANDIDATE_RESERVOIR_LIMIT = 8", provider)
        self.assertIn("MAX_SEARXNG_PROVIDER_RESULT_SCAN = 20", provider)
        self.assertIn("additional_provider_request_performed: Literal[False]", provider)
        self.assertIn("candidate_provider_support_names_recorded: Literal[False]", provider)
        self.assertIn(
            "provider_titles_or_snippets_used_for_candidate_ranking: Literal[False]",
            provider,
        )
        self.assertIn('SEARXNG_HOST: Literal["127.0.0.1"] = "127.0.0.1"', provider)
        self.assertIn("SEARXNG_PORT = 8888", provider)
        self.assertIn('"Accept-Encoding: identity"', provider)
        self.assertNotIn('"count": query.count', provider)

    def test_h2_keeps_final_remote_retrieval_ceiling_at_three(self) -> None:
        quality = SOURCE_QUALITY.read_text(encoding="utf-8")
        discovery = DISCOVERY.read_text(encoding="utf-8")

        self.assertIn("if limit < 1 or limit > 3:", quality)
        self.assertIn("MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL = 3", discovery)
        self.assertIn("limit=MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL", discovery)
        self.assertIn('remote_scope_expansion_allowed: Literal[False]', discovery)

    def test_h2_does_not_use_provider_text_or_remote_probe_for_selection(self) -> None:
        quality = SOURCE_QUALITY.read_text(encoding="utf-8")

        self.assertIn(
            "provider_titles_or_snippets_used_for_selection: bool = False",
            quality,
        )
        self.assertIn("remote_probe_used_for_selection: bool = False", quality)
        self.assertIn("factual_credibility_assessed: bool = False", quality)
        self.assertIn("source_retrieval_resilience_signals(candidate.url)", quality)

        lowered = quality.casefold()
        for prohibited in (
            "requests.",
            "aiohttp",
            "urllib.request",
            "socket.socket",
            "subprocess",
            "systemctl",
            "docker run",
            "docker compose",
            "sudo ",
        ):
            self.assertNotIn(prohibited, lowered)

    def test_h2_preserves_identity_transport_and_independent_corpus(self) -> None:
        transport = TRANSPORT.read_text(encoding="utf-8")
        corpus = VALIDATION_CORPUS.read_text(encoding="utf-8")

        self.assertIn('"Accept-Encoding: identity"', transport)
        self.assertNotIn('"Accept-Encoding: gzip, identity"', transport)
        self.assertIn(
            'PHASE16_VALIDATION_CORPUS_VERSION: Literal['
            '"phase16-validation-corpus-v1"',
            corpus,
        )
        self.assertIn("PHASE16_VALIDATION_CORPUS_CASE_COUNT: Literal[24] = 24", corpus)


if __name__ == "__main__":
    unittest.main()
