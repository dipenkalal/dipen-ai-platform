from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from gateway.research_source_quality import (
    SOURCE_SELECTION_POLICY_ID,
    ResearchSourceSelectionResult,
    canonical_source_family,
    select_source_diverse_candidates,
)
from gateway.searxng_search_provider import SearXNGWebSearchProvider
from gateway.web_search_provider import (
    BraveWebSearchProvider,
    WebSearchCandidate,
    WebSearchQuery,
)
from tools.base import ToolExecutionResult
from tools.internet_research_tools import InternetResearchRetrieveTool

MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL = 3


class WebSearchDiscoveryError(RuntimeError):
    """Fail-closed discovery orchestration error with a stable code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WebSearchDiscoveryProtocol(Protocol):
    provider_id: str
    discovery_id: str
    discovery_sha256: str
    query: str
    candidates: tuple[WebSearchCandidate, ...]


class WebSearchProviderProtocol(Protocol):
    async def search(self, query: WebSearchQuery) -> WebSearchDiscoveryProtocol: ...


class InternetResearchToolProtocol(Protocol):
    async def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult: ...


class WebSearchRetrievalPipelineResult(BaseModel):
    """Search discovery plus sealed DAP retrieval with provider snippets excluded."""

    model_config = ConfigDict(frozen=True)

    pipeline_id: str = Field(pattern=r"^web-search-pipeline-[0-9a-f]{24}$")
    pipeline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    objective_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_id: str
    discovery_id: str
    discovery_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    query: str
    candidate_count: int = Field(ge=0)
    selected_urls: tuple[str, ...] = Field(
        max_length=MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL
    )
    source_selection_policy_id: str = SOURCE_SELECTION_POLICY_ID
    unique_source_family_count: int = Field(default=0, ge=0)
    selected_source_families: tuple[str, ...] = ()
    selected_quality_scores: tuple[int, ...] = ()
    skipped_exact_duplicate_count: int = Field(default=0, ge=0)
    duplicate_family_fallback_count: int = Field(default=0, ge=0)
    selection_quality_is_factual_credibility: Literal[False] = False
    retrieval_tool_id: Literal["internet.research.retrieve"] = (
        "internet.research.retrieve"
    )
    retrieval_success: bool
    retrieval_output: dict[str, Any] | None = None
    retrieval_error: str | None = None
    disposition: Literal["succeeded", "failed"]
    provider_snippets_are_evidence: Literal[False] = False
    provider_snippets_exposed_to_model: Literal[False] = False
    provider_titles_exposed_to_model: Literal[False] = False
    search_candidates_are_retrieval_evidence: Literal[False] = False
    candidate_urls_require_full_dap_retrieval: Literal[True] = True
    provider_credential_exposed_to_model: Literal[False] = False
    provider_credential_forwarded_to_result_url: Literal[False] = False
    generic_network_client_exposed: Literal[False] = False
    remote_scope_expansion_allowed: Literal[False] = False
    automatic_knowledge_mutation_performed: Literal[False] = False
    task_ledger_mutation_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False


class WebSearchRetrievalPipeline:
    """Discover URL candidates, then route selected URLs through sealed retrieval."""

    def __init__(
        self,
        *,
        provider: WebSearchProviderProtocol,
        retrieval_tool: InternetResearchToolProtocol | None = None,
    ) -> None:
        self._provider = provider
        self._retrieval_tool = retrieval_tool or InternetResearchRetrieveTool()

    @classmethod
    def brave_from_environment(
        cls,
        *,
        retrieval_tool: InternetResearchToolProtocol | None = None,
    ) -> WebSearchRetrievalPipeline:
        return cls(
            provider=BraveWebSearchProvider.from_environment(),
            retrieval_tool=retrieval_tool,
        )

    @classmethod
    def searxng_local(
        cls,
        *,
        retrieval_tool: InternetResearchToolProtocol | None = None,
    ) -> WebSearchRetrievalPipeline:
        return cls(
            provider=SearXNGWebSearchProvider(),
            retrieval_tool=retrieval_tool,
        )

    async def run(
        self,
        *,
        objective: str,
        query: WebSearchQuery,
    ) -> WebSearchRetrievalPipelineResult:
        normalized_objective = " ".join(objective.split())
        if len(normalized_objective) < 3:
            raise WebSearchDiscoveryError(
                "objective-required",
                "A research objective is required for search discovery retrieval.",
            )
        objective_sha256 = hashlib.sha256(
            normalized_objective.encode("utf-8")
        ).hexdigest()

        discovery = await self._provider.search(query)
        selection = self._select_urls(discovery)
        selected_urls = selection.selected_urls
        if not selected_urls:
            raise WebSearchDiscoveryError(
                "no-search-candidates",
                "Search provider returned no URL candidate eligible for bounded DAP retrieval.",
            )

        retrieval = await self._retrieval_tool.execute(
            {
                "objective": normalized_objective,
                "urls": list(selected_urls),
            }
        )
        retrieval_output = retrieval.output if isinstance(retrieval.output, dict) else None
        pipeline_sha256 = self._pipeline_sha256(
            objective_sha256=objective_sha256,
            discovery=discovery,
            selection=selection,
        )
        return WebSearchRetrievalPipelineResult(
            pipeline_id=f"web-search-pipeline-{pipeline_sha256[:24]}",
            pipeline_sha256=pipeline_sha256,
            objective_sha256=objective_sha256,
            provider_id=discovery.provider_id,
            discovery_id=discovery.discovery_id,
            discovery_sha256=discovery.discovery_sha256,
            query=discovery.query,
            candidate_count=len(discovery.candidates),
            selected_urls=selected_urls,
            source_selection_policy_id=selection.policy_id,
            unique_source_family_count=selection.unique_source_family_count,
            selected_source_families=selection.selected_source_families,
            selected_quality_scores=selection.selected_quality_scores,
            skipped_exact_duplicate_count=selection.skipped_exact_duplicate_count,
            duplicate_family_fallback_count=selection.duplicate_family_fallback_count,
            retrieval_success=retrieval.success,
            retrieval_output=retrieval_output,
            retrieval_error=retrieval.error,
            disposition="succeeded" if retrieval.success else "failed",
        )

    @staticmethod
    def _select_urls(
        discovery: WebSearchDiscoveryProtocol,
    ) -> ResearchSourceSelectionResult:
        return select_source_diverse_candidates(
            discovery.candidates,
            limit=MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL,
        )

    @staticmethod
    def _pipeline_sha256(
        *,
        objective_sha256: str,
        discovery: WebSearchDiscoveryProtocol,
        selection: ResearchSourceSelectionResult | None = None,
        selected_urls: tuple[str, ...] | None = None,
    ) -> str:
        """Bind live Phase 14 selection metadata while accepting the sealed Phase 12 helper call."""

        if selection is not None and selected_urls is not None:
            raise ValueError("pipeline identity accepts selection or selected_urls, not both")
        if selection is None and selected_urls is None:
            raise ValueError("pipeline identity requires selected source URLs")

        if selection is not None:
            selected_url_values = selection.selected_urls
            selection_policy_id = selection.policy_id
            selected_source_families = selection.selected_source_families
            selected_quality_scores = selection.selected_quality_scores
        else:
            assert selected_urls is not None
            selected_url_values = selected_urls
            selection_policy_id = "phase12-selected-urls-compat-v1"
            selected_source_families = tuple(
                canonical_source_family(url) for url in selected_urls
            )
            selected_quality_scores = ()

        payload = {
            "objective_sha256": objective_sha256,
            "provider_id": discovery.provider_id,
            "discovery_id": discovery.discovery_id,
            "discovery_sha256": discovery.discovery_sha256,
            "query": discovery.query,
            "source_selection_policy_id": selection_policy_id,
            "selected_urls": list(selected_url_values),
            "selected_source_families": list(selected_source_families),
            "selected_quality_scores": list(selected_quality_scores),
            "retrieval_tool_id": "internet.research.retrieve",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
