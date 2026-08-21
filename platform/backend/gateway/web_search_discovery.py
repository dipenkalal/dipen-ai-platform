from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from gateway.research_query_fallback import (
    SEARCH_QUERY_FALLBACK_POLICY_ID,
    build_research_query_attempts,
)
from gateway.research_retrieval_hedge import (
    AUTOMATIC_RETRIEVAL_HEDGE_DELAY_SECONDS,
    AUTOMATIC_RETRIEVAL_HEDGE_MAX_CANDIDATES,
    AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID,
    execute_automatic_research_hedge,
)
from gateway.research_source_quality import (
    SOURCE_SELECTION_POLICY_ID,
    SOURCE_URL_DUPLICATE_POLICY_ID,
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

MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL = 2
MAX_AUTOMATIC_RETRIEVAL_CANDIDATES = AUTOMATIC_RETRIEVAL_HEDGE_MAX_CANDIDATES


class WebSearchDiscoveryError(RuntimeError):
    """Fail-closed discovery orchestration error with a stable code."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.diagnostics = dict(diagnostics or {})


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


class WebSearchAttemptDiagnostic(BaseModel):
    """Provider-attempt diagnostics with discovery text deliberately excluded."""

    model_config = ConfigDict(frozen=True)

    query: str
    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0, le=MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL)
    provider_result_count: int | None = Field(default=None, ge=0)
    considered_result_count: int | None = Field(default=None, ge=0)
    invalid_candidate_count: int | None = Field(default=None, ge=0)
    policy_rejected_candidate_count: int | None = Field(default=None, ge=0)
    provider_zero_results: bool | None = None
    admissible_candidate_zero_after_filtering: bool | None = None
    outcome: Literal["selected", "no-candidate"]
    provider_titles_included: Literal[False] = False
    provider_snippets_included: Literal[False] = False


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
    original_query: str | None = None
    search_attempt_count: int = Field(default=1, ge=1, le=3)
    search_queries_attempted: tuple[str, ...] = ()
    search_fallback_policy_id: str | None = None
    fallback_used: bool = False
    search_attempts: tuple[WebSearchAttemptDiagnostic, ...] = ()
    candidate_count: int = Field(ge=0)
    selected_urls: tuple[str, ...] = Field(
        max_length=MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL
    )
    retrieval_candidate_urls: tuple[str, ...] = Field(
        default=(),
        max_length=MAX_AUTOMATIC_RETRIEVAL_CANDIDATES,
    )
    retrieval_hedge_policy_id: str | None = None
    retrieval_hedge_started: bool = False
    source_selection_policy_id: str = SOURCE_SELECTION_POLICY_ID
    duplicate_normalization_policy_id: str = SOURCE_URL_DUPLICATE_POLICY_ID
    unique_source_family_count: int = Field(default=0, ge=0)
    selected_source_families: tuple[str, ...] = ()
    selected_quality_scores: tuple[int, ...] = ()
    skipped_exact_duplicate_count: int = Field(default=0, ge=0)
    skipped_canonical_duplicate_count: int = Field(default=0, ge=0)
    duplicate_family_fallback_count: int = Field(default=0, ge=0)
    selection_quality_is_factual_credibility: Literal[False] = False
    provider_search_duration_ms: float | None = Field(default=None, ge=0)
    retrieval_duration_ms: float | None = Field(default=None, ge=0)
    total_pipeline_duration_ms: float | None = Field(default=None, ge=0)
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
        enable_bounded_query_fallback: bool = False,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._provider = provider
        self._retrieval_tool = retrieval_tool or InternetResearchRetrieveTool()
        self._enable_bounded_query_fallback = enable_bounded_query_fallback
        self._clock = clock or time.perf_counter

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
            enable_bounded_query_fallback=True,
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

        total_started = self._clock()
        attempt_queries = (
            build_research_query_attempts(query)
            if self._enable_bounded_query_fallback
            else (query,)
        )
        attempts: list[WebSearchAttemptDiagnostic] = []
        provider_duration_ms = 0.0
        discovery: WebSearchDiscoveryProtocol | None = None
        selection: ResearchSourceSelectionResult | None = None
        retrieval_selection: ResearchSourceSelectionResult | None = None

        for attempt_query in attempt_queries:
            provider_started = self._clock()
            discovery = await self._provider.search(attempt_query)
            provider_duration_ms += max(
                0.0,
                (self._clock() - provider_started) * 1000.0,
            )
            selection = self._select_urls(discovery)
            retrieval_selection = self._select_retrieval_candidates(discovery)
            attempts.append(self._attempt_diagnostic(discovery, selection))
            if selection.selected_urls:
                break

        if discovery is None or selection is None or retrieval_selection is None:
            raise RuntimeError("search attempt plan produced no provider attempt")

        selected_urls = selection.selected_urls
        if not selected_urls:
            diagnostics = self._no_candidate_diagnostics(discovery)
            diagnostics.update(
                {
                    "search_attempt_count": len(attempts),
                    "search_queries_attempted": [item.query for item in attempts],
                    "search_fallback_policy_id": (
                        SEARCH_QUERY_FALLBACK_POLICY_ID
                        if self._enable_bounded_query_fallback
                        else None
                    ),
                    "attempts": [item.model_dump(mode="json") for item in attempts],
                }
            )
            if diagnostics.get("provider_zero_results") is True:
                detail = (
                    "Search provider returned zero raw results for every bounded query "
                    "attempt; no URL candidate was available for DAP retrieval."
                )
            elif diagnostics.get("admissible_candidate_zero_after_filtering") is True:
                detail = (
                    "Search provider returned raw results, but none survived DAP candidate "
                    "validation and destination policy."
                )
            else:
                detail = (
                    "Search provider returned no URL candidate eligible for bounded DAP retrieval."
                )
            raise WebSearchDiscoveryError(
                "no-search-candidates",
                detail,
                diagnostics=diagnostics,
            )

        retrieval_candidate_urls = retrieval_selection.selected_urls
        retrieval_started = self._clock()
        if isinstance(self._retrieval_tool, InternetResearchRetrieveTool):
            retrieval = await execute_automatic_research_hedge(
                self._retrieval_tool,
                {
                    "objective": normalized_objective,
                    "urls": list(retrieval_candidate_urls),
                },
                target_successes=min(
                    MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL,
                    len(retrieval_candidate_urls),
                ),
                hedge_delay_seconds=AUTOMATIC_RETRIEVAL_HEDGE_DELAY_SECONDS,
            )
        else:
            retrieval = await self._retrieval_tool.execute(
                {
                    "objective": normalized_objective,
                    "urls": list(selected_urls),
                }
            )
        retrieval_duration_ms = max(
            0.0,
            (self._clock() - retrieval_started) * 1000.0,
        )
        total_duration_ms = max(
            0.0,
            (self._clock() - total_started) * 1000.0,
        )
        retrieval_output = retrieval.output if isinstance(retrieval.output, dict) else None

        hedge_policy_id: str | None = None
        hedge_started = False
        if retrieval_output is not None:
            raw_accepted_urls = retrieval_output.get("accepted_urls")
            if isinstance(raw_accepted_urls, (list, tuple)):
                accepted_urls = tuple(str(value) for value in raw_accepted_urls)
                if (
                    len(accepted_urls) > MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL
                    or any(url not in retrieval_candidate_urls for url in accepted_urls)
                    or len(set(accepted_urls)) != len(accepted_urls)
                ):
                    raise RuntimeError(
                        "hedged retrieval returned an invalid accepted URL set"
                    )
                selected_urls = accepted_urls
            raw_policy_id = retrieval_output.get("hedge_policy_id")
            if isinstance(raw_policy_id, str):
                hedge_policy_id = raw_policy_id
            hedge_started = retrieval_output.get("hedge_started") is True

        selected_source_families, selected_quality_scores, duplicate_fallback_count = (
            self._accepted_selection_metadata(
                retrieval_selection,
                selected_urls,
            )
        )

        attempted_queries = tuple(item.query for item in attempts)
        pipeline_sha256 = self._pipeline_sha256(
            objective_sha256=objective_sha256,
            discovery=discovery,
            selection=selection,
            accepted_urls=selected_urls,
            retrieval_candidate_urls=retrieval_candidate_urls,
            original_query=query.query,
            attempted_queries=attempted_queries,
        )
        return WebSearchRetrievalPipelineResult(
            pipeline_id=f"web-search-pipeline-{pipeline_sha256[:24]}",
            pipeline_sha256=pipeline_sha256,
            objective_sha256=objective_sha256,
            provider_id=discovery.provider_id,
            discovery_id=discovery.discovery_id,
            discovery_sha256=discovery.discovery_sha256,
            query=discovery.query,
            original_query=query.query,
            search_attempt_count=len(attempts),
            search_queries_attempted=attempted_queries,
            search_fallback_policy_id=(
                SEARCH_QUERY_FALLBACK_POLICY_ID
                if self._enable_bounded_query_fallback
                else None
            ),
            fallback_used=len(attempts) > 1,
            search_attempts=tuple(attempts),
            candidate_count=len(discovery.candidates),
            selected_urls=selected_urls,
            retrieval_candidate_urls=retrieval_candidate_urls,
            retrieval_hedge_policy_id=hedge_policy_id,
            retrieval_hedge_started=hedge_started,
            source_selection_policy_id=selection.policy_id,
            duplicate_normalization_policy_id=(
                selection.duplicate_normalization_policy_id
            ),
            unique_source_family_count=len(set(selected_source_families)),
            selected_source_families=selected_source_families,
            selected_quality_scores=selected_quality_scores,
            skipped_exact_duplicate_count=retrieval_selection.skipped_exact_duplicate_count,
            skipped_canonical_duplicate_count=(
                retrieval_selection.skipped_canonical_duplicate_count
            ),
            duplicate_family_fallback_count=duplicate_fallback_count,
            provider_search_duration_ms=round(provider_duration_ms, 3),
            retrieval_duration_ms=round(retrieval_duration_ms, 3),
            total_pipeline_duration_ms=round(total_duration_ms, 3),
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
    def _select_retrieval_candidates(
        discovery: WebSearchDiscoveryProtocol,
    ) -> ResearchSourceSelectionResult:
        return select_source_diverse_candidates(
            discovery.candidates,
            limit=MAX_AUTOMATIC_RETRIEVAL_CANDIDATES,
        )

    @staticmethod
    def _accepted_selection_metadata(
        selection: ResearchSourceSelectionResult,
        selected_urls: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[int, ...], int]:
        item_by_url = {item.url: item for item in selection.items}
        if any(url not in item_by_url for url in selected_urls):
            raise RuntimeError("accepted URL was not admitted by source selection")

        families = tuple(canonical_source_family(url) for url in selected_urls)
        scores = tuple(item_by_url[url].selection_quality_score for url in selected_urls)
        duplicate_fallback_count = sum(
            item_by_url[url].selected_as_duplicate_family_fallback
            for url in selected_urls
        )
        return families, scores, duplicate_fallback_count

    @staticmethod
    def _attempt_diagnostic(
        discovery: WebSearchDiscoveryProtocol,
        selection: ResearchSourceSelectionResult,
    ) -> WebSearchAttemptDiagnostic:
        return WebSearchAttemptDiagnostic(
            query=discovery.query,
            candidate_count=len(discovery.candidates),
            selected_count=len(selection.selected_urls),
            provider_result_count=getattr(discovery, "provider_result_count", None),
            considered_result_count=getattr(
                discovery,
                "considered_result_count",
                None,
            ),
            invalid_candidate_count=getattr(
                discovery,
                "invalid_candidate_count",
                None,
            ),
            policy_rejected_candidate_count=getattr(
                discovery,
                "policy_rejected_candidate_count",
                None,
            ),
            provider_zero_results=getattr(discovery, "provider_zero_results", None),
            admissible_candidate_zero_after_filtering=getattr(
                discovery,
                "admissible_candidate_zero_after_filtering",
                None,
            ),
            outcome="selected" if selection.selected_urls else "no-candidate",
        )

    @staticmethod
    def _no_candidate_diagnostics(
        discovery: WebSearchDiscoveryProtocol,
    ) -> dict[str, Any]:
        diagnostics: dict[str, Any] = {}
        for field_name in (
            "provider_result_count",
            "considered_result_count",
            "invalid_candidate_count",
            "policy_rejected_candidate_count",
            "accepted_candidate_count",
            "provider_zero_results",
            "admissible_candidate_zero_after_filtering",
        ):
            value = getattr(discovery, field_name, None)
            if value is not None:
                diagnostics[field_name] = value
        return diagnostics

    @staticmethod
    def _pipeline_sha256(
        *,
        objective_sha256: str,
        discovery: WebSearchDiscoveryProtocol,
        selection: ResearchSourceSelectionResult | None = None,
        selected_urls: tuple[str, ...] | None = None,
        accepted_urls: tuple[str, ...] | None = None,
        retrieval_candidate_urls: tuple[str, ...] | None = None,
        original_query: str | None = None,
        attempted_queries: tuple[str, ...] | None = None,
    ) -> str:
        """Bind selection authority while preserving sealed Phase 12 helper compatibility."""

        if selection is not None and selected_urls is not None:
            raise ValueError("pipeline identity accepts selection or selected_urls, not both")
        if selection is None and selected_urls is None:
            raise ValueError("pipeline identity requires selected source URLs")
        if accepted_urls is not None and selection is None:
            raise ValueError("accepted URLs require a source selection authority")

        if selection is not None:
            selected_url_values = (
                accepted_urls if accepted_urls is not None else selection.selected_urls
            )
            selection_policy_id = selection.policy_id
            duplicate_policy_id = selection.duplicate_normalization_policy_id
            selected_source_families = tuple(
                canonical_source_family(url) for url in selected_url_values
            )
            score_by_url = {
                item.url: item.selection_quality_score for item in selection.items
            }
            selected_quality_scores = tuple(
                score_by_url[url]
                for url in selected_url_values
                if url in score_by_url
            )
        else:
            assert selected_urls is not None
            selected_url_values = selected_urls
            selection_policy_id = "phase12-selected-urls-compat-v1"
            duplicate_policy_id = "phase12-exact-url-compat-v1"
            selected_source_families = tuple(
                canonical_source_family(url) for url in selected_urls
            )
            selected_quality_scores = ()

        payload: dict[str, Any] = {
            "objective_sha256": objective_sha256,
            "provider_id": discovery.provider_id,
            "discovery_id": discovery.discovery_id,
            "discovery_sha256": discovery.discovery_sha256,
            "query": discovery.query,
            "source_selection_policy_id": selection_policy_id,
            "duplicate_normalization_policy_id": duplicate_policy_id,
            "selected_urls": list(selected_url_values),
            "selected_source_families": list(selected_source_families),
            "selected_quality_scores": list(selected_quality_scores),
            "retrieval_tool_id": "internet.research.retrieve",
        }
        if retrieval_candidate_urls is not None:
            payload["retrieval_candidate_urls"] = list(retrieval_candidate_urls)
            payload["retrieval_hedge_policy_id"] = AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID
        if original_query is not None:
            payload["original_query"] = original_query
        if attempted_queries is not None:
            payload["search_queries_attempted"] = list(attempted_queries)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
