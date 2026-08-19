from __future__ import annotations

import unittest
from pathlib import Path


class Phase14ResearchOperationsBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.tool_source = (
            cls.repo_root / "platform/backend/tools/internet_research_tools.py"
        ).read_text(encoding="utf-8")
        cls.routes_source = (
            cls.repo_root / "platform/backend/gateway/research_routes.py"
        ).read_text(encoding="utf-8")
        cls.operations_source = (
            cls.repo_root / "platform/backend/gateway/research_operations.py"
        ).read_text(encoding="utf-8")
        cls.health_source = (
            cls.repo_root / "platform/backend/gateway/research_provider_health.py"
        ).read_text(encoding="utf-8")
        cls.resource_source = (
            cls.repo_root / "platform/backend/gateway/research_resource_snapshot.py"
        ).read_text(encoding="utf-8")
        cls.selection_source = (
            cls.repo_root / "platform/backend/gateway/research_source_quality.py"
        ).read_text(encoding="utf-8")
        cls.roadmap_source = (
            cls.repo_root / "docs/phase14-research-operations-reliability-roadmap.md"
        ).read_text(encoding="utf-8")

    def test_smart_routing_research_remains_out_of_scope(self) -> None:
        self.assertIn("smart-routing research activation", self.roadmap_source)
        self.assertIn(
            "Smart-routing research is **not** activated by 14J",
            self.roadmap_source,
        )

    def test_retry_is_single_same_url_transient_get_only(self) -> None:
        self.assertIn("MAX_TRANSIENT_RETRIES_PER_URL = 1", self.tool_source)
        self.assertIn('method="GET"', self.tool_source)
        self.assertIn("_TRANSIENT_TRANSPORT_ERROR_CODES", self.tool_source)
        transient_block = self.tool_source.split(
            "_TRANSIENT_TRANSPORT_ERROR_CODES = frozenset(", 1
        )[1].split(")\n\nRepositoryFactory", 1)[0]
        for prohibited in (
            '"destination-preflight-rejected"',
            '"destination-addresses-rejected"',
            '"content-type-unsupported"',
            '"content-body-too-large"',
            '"redirect-limit-exceeded"',
        ):
            self.assertNotIn(prohibited, transient_block)

    def test_operations_routes_are_get_only(self) -> None:
        self.assertIn('@router.get(\n    "/operations"', self.routes_source)
        self.assertIn(
            '@router.get(\n    "/operations/provider-health"',
            self.routes_source,
        )
        self.assertIn(
            '@router.get(\n    "/operations/resource-snapshot"',
            self.routes_source,
        )
        self.assertIn(
            '@router.get(\n    "/operations/retention-plan"',
            self.routes_source,
        )
        for method in ("post", "put", "patch", "delete"):
            self.assertNotIn(f'@router.{method}(\n    "/operations', self.routes_source)

    def test_retention_is_non_destructive(self) -> None:
        for token in (
            "automatic_deletion_enabled: Literal[False] = False",
            "automatic_archive_enabled: Literal[False] = False",
            "evidence_deleted: Literal[False] = False",
            "evidence_mutated: Literal[False] = False",
        ):
            self.assertIn(token, self.operations_source)
        upper_source = self.operations_source.upper()
        for token in (" DELETE ", "DROP TABLE", "VACUUM"):
            self.assertNotIn(token, upper_source)

    def test_provider_health_is_fixed_loopback_without_service_control(self) -> None:
        self.assertIn("SEARXNG_HOST", self.health_source)
        self.assertIn("SEARXNG_PORT", self.health_source)
        self.assertIn("socket.AI_NUMERICHOST", self.health_source)
        self.assertIn(
            "service_control_authority_granted: Literal[False]",
            self.health_source,
        )
        for token in (
            "systemctl",
            "subprocess",
            "docker",
            "sudo ",
            "os.system",
        ):
            self.assertNotIn(token, self.health_source.lower())

    def test_resource_snapshot_is_observation_only(self) -> None:
        self.assertIn('scope: Literal["dap-backend-process"]', self.resource_source)
        self.assertIn("research_specific_attribution: Literal[False]", self.resource_source)
        self.assertIn("read_only: Literal[True]", self.resource_source)
        self.assertIn(
            "service_control_authority_granted: Literal[False]",
            self.resource_source,
        )
        for token in (
            "terminate(",
            "kill(",
            "send_signal(",
            "systemctl",
            "subprocess",
            "docker",
            "sudo ",
        ):
            self.assertNotIn(token, self.resource_source.lower())

    def test_selection_quality_never_claims_factual_credibility(self) -> None:
        self.assertIn(
            "factual_credibility_assessed: bool = False",
            self.selection_source,
        )
        self.assertIn(
            "provider_title_used_as_evidence: bool = False",
            self.selection_source,
        )
        self.assertIn(
            "provider_snippet_used_as_evidence: bool = False",
            self.selection_source,
        )
        self.assertIn("limit must be between 1 and 3", self.selection_source)


if __name__ == "__main__":
    unittest.main()
