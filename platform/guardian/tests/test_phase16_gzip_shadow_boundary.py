from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = (
    REPO_ROOT
    / "platform/backend/gateway/research_retrieval_gzip_experiment.py"
)
PRODUCTION_TRANSPORT = REPO_ROOT / "platform/backend/gateway/internet_transport.py"


class Phase16GzipShadowBoundaryTests(unittest.TestCase):
    def test_experiment_is_explicitly_shadow_only(self) -> None:
        source = EXPERIMENT.read_text(encoding="utf-8")

        self.assertIn(
            'PHASE16_GZIP_EXPERIMENT_VERSION: Literal["phase16f1.1"]',
            source,
        )
        self.assertIn(
            'EXPERIMENT_TRANSPORT_ID = "dap-pinned-https-http1-gzip-shadow-v1"',
            source,
        )
        self.assertIn('"production_transport_mutated": False', source)
        self.assertIn('"production_truth_mutation_performed": False', source)
        self.assertIn('"smart_routing_research_activated": False', source)
        self.assertIn('"provider_switching_performed": False', source)
        self.assertIn('"generic_network_authority_expanded": False', source)
        self.assertIn('"guardian_contacted": False', source)
        self.assertIn('"privileged_host_action_performed": False', source)

    def test_experiment_accepts_only_identity_and_gzip_with_two_byte_ceilings(self) -> None:
        source = EXPERIMENT.read_text(encoding="utf-8")

        self.assertIn('replacement = b"Accept-Encoding: gzip, identity\\r\\n"', source)
        self.assertIn('{"identity", "gzip"}', source)
        self.assertIn('"accepted_content_encodings": ["identity", "gzip"]', source)
        self.assertIn('"wire_body_ceiling_bytes": limits.max_body_bytes', source)
        self.assertIn('"decoded_body_ceiling_bytes": limits.max_body_bytes', source)
        self.assertIn("decoder.decompress(payload, max_decoded_bytes + 1)", source)
        self.assertIn("decoder.unconsumed_tail", source)
        self.assertIn("decoder.eof", source)
        self.assertIn("decoder.unused_data", source)
        self.assertNotIn('"br"', source)
        self.assertNotIn('"deflate"', source)
        self.assertNotIn('"zstd"', source)

    def test_sealed_production_transport_remains_identity_only(self) -> None:
        source = PRODUCTION_TRANSPORT.read_text(encoding="utf-8")

        self.assertIn('TRANSPORT_ID = "dap-pinned-https-http1-v1"', source)
        self.assertIn('"Accept-Encoding: identity"', source)
        self.assertIn('"content-encoding-unsupported"', source)
        self.assertNotIn('"Accept-Encoding: gzip, identity"', source)

    def test_experiment_has_no_new_service_or_generic_client_authority(self) -> None:
        lowered = EXPERIMENT.read_text(encoding="utf-8").lower()

        for prohibited in (
            "aiohttp",
            "httpx",
            "requests",
            "urllib.request",
            "subprocess",
            "docker compose",
            "docker run",
            "systemctl",
            "sudo ",
            "os.system",
            "guardian_broker",
            "openai_api_key",
            "github_token",
            "telegram",
        ):
            self.assertNotIn(prohibited, lowered)


if __name__ == "__main__":
    unittest.main()
