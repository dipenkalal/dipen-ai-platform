from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS = REPO_ROOT / (
    "platform/backend/gateway/research_provider_phase16_validation_corpus.py"
)
RUNNER = REPO_ROOT / "platform/backend/gateway/research_provider_phase16_validation.py"
PHASE15 = REPO_ROOT / "platform/backend/gateway/research_provider_corpus.py"


class Phase16IndependentValidationBoundaryTests(unittest.TestCase):
    def test_validation_is_independent_and_does_not_modify_phase15_corpus(self) -> None:
        corpus = CORPUS.read_text(encoding="utf-8")
        phase15 = PHASE15.read_text(encoding="utf-8")

        self.assertIn(
            'PHASE16_VALIDATION_CORPUS_VERSION: Literal["phase16-validation-corpus-v1"]',
            corpus,
        )
        self.assertIn("PHASE16_VALIDATION_CORPUS_CASE_COUNT: Literal[24] = 24", corpus)
        self.assertIn("validate_phase16_validation_corpus", corpus)
        self.assertIn("PHASE15_PROVIDER_CORPUS", corpus)
        self.assertIn('PHASE15_CORPUS_VERSION = "phase15-provider-corpus-v1"', phase15)
        self.assertIn("PHASE15_CORPUS_MINIMUM_CASES = 30", phase15)

    def test_validation_reuses_frozen_provider_and_authority_contract(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")

        self.assertIn('PHASE16_VALIDATION_VERSION: Literal["phase16h.1"]', source)
        self.assertIn("SearXNGWebSearchProvider()", source)
        self.assertIn("InternetResearchRetrieveTool(", source)
        self.assertIn("enable_bounded_query_fallback=True", source)
        self.assertIn('truth_database_scope: Literal["isolated-phase16-validation"]', source)
        self.assertIn('frozen_phase15_corpus_modified: Literal[False]', source)
        self.assertIn('smart_routing_research_activated: Literal[False]', source)
        self.assertIn('provider_switching_performed: Literal[False]', source)
        self.assertIn('generic_network_authority_expanded: Literal[False]', source)
        self.assertIn('provider_titles_or_snippets_used_as_evidence: Literal[False]', source)
        self.assertIn('automatic_knowledge_mutation_performed: Literal[False]', source)
        self.assertIn('guardian_contacted: Literal[False]', source)
        self.assertIn('privileged_host_action_performed: Literal[False]', source)
        self.assertIn('not str(resolved).startswith("/tmp/")', source)

    def test_validation_does_not_expose_generic_network_or_host_control(self) -> None:
        lowered = RUNNER.read_text(encoding="utf-8").lower()

        for prohibited in (
            "requests.",
            "aiohttp",
            "urllib.request",
            "socket.socket",
            "asyncio.open_connection",
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

    def test_validation_keeps_frozen_phase16_targets(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")

        self.assertIn("MINIMUM_LIVE_SUCCESS_RATE", source)
        self.assertIn("MAXIMUM_LIVE_NO_CANDIDATE_RATE", source)
        self.assertIn("MINIMUM_LIVE_UNIQUE_SOURCE_FAMILY_RATE", source)
        self.assertIn("MAXIMUM_LIVE_DUPLICATE_CONTENT_RATE", source)
        self.assertIn("MAXIMUM_LIVE_RETRIEVAL_P95_MS", source)
        self.assertIn("LIVE_CASE_TIMEOUT_SECONDS", source)


if __name__ == "__main__":
    unittest.main()
