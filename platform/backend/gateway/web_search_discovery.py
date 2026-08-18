from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from gateway.web_search_provider import (
    BraveWebSearchProvider,
    WebSearchDiscoveryResult,
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


class WebSearchProviderProtocol(Protocol):
    async def search(self, query: WebSearchQuery) -> WebSearchDiscoveryResult: ...


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
        selected_urls = self._select_urls(discovery)
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
            selected_urls=selected_urls,
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
            retrieval_success=retrieval.success,
            retrieval_output=retrieval_output,
            retrieval_error=retrieval.error,
            disposition="succeeded" if retrieval.success else "failed",
        )

    @staticmethod
    def _select_urls(discovery: WebSearchDiscoveryResult) -> tuple[str, ...]:
        ordered = sorted(discovery.candidates, key=lambda candidate: candidate.rank)
        selected: list[str] = []
        for candidate in ordered:
            if not candidate.candidate_url_requires_dap_retrieval:
                continue
            if candidate.candidate_is_retrieval_evidence:
                continue
            if candidate.url in selected:
                continue
            selected.append(candidate.url)
            if len(selected) >= MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL:
                break
        return tuple(selected)

    @staticmethod
    def _pipeline_sha256(
        *,
        objective_sha256: str,
        discovery: WebSearchDiscoveryResult,
        selected_urls: tuple[str, ...],
    ) -> str:
        payload = {
            "objective_sha256": objective_sha256,
            "provider_id": discovery.provider_id,
            "discovery_id": discovery.discovery_id,
            "discovery_sha256": discovery.discovery_sha256,
            "query": discovery.query,
            "selected_urls": list(selected_urls),
            "retrieval_tool_id": "internet.research.retrieve",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
