from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gateway.web_search_provider import WebSearchQuery

SEARCH_QUERY_FALLBACK_POLICY_ID = "dap-searxng-bounded-query-fallback-v1"
MAX_SEARCH_QUERY_ATTEMPTS = 3


class ResearchQueryFallbackPlan(BaseModel):
    """Deterministic owner-query-only fallback plan for fixed local SearXNG."""

    model_config = ConfigDict(frozen=True)

    policy_id: str = SEARCH_QUERY_FALLBACK_POLICY_ID
    original_query: str
    queries: tuple[str, ...] = Field(min_length=1, max_length=MAX_SEARCH_QUERY_ATTEMPTS)
    maximum_attempt_count: int = Field(default=MAX_SEARCH_QUERY_ATTEMPTS, ge=1, le=3)
    model_generated_expansion_allowed: bool = False
    provider_switching_allowed: bool = False
    added_query_terms_allowed: bool = False


def build_research_query_fallback_plan(query: WebSearchQuery) -> ResearchQueryFallbackPlan:
    """Build at most three searches by removing edge tokens; never add query terms."""

    original = query.query
    tokens = original.split()
    variants = [original]

    if len(tokens) >= 4:
        variants.extend((" ".join(tokens[:-1]), " ".join(tokens[1:])))
    elif len(tokens) == 3:
        variants.extend((" ".join(tokens[:2]), " ".join(tokens[1:])))

    unique: list[str] = []
    for candidate in variants:
        normalized = " ".join(candidate.split())
        if not normalized or normalized in unique:
            continue
        unique.append(normalized)
        if len(unique) >= MAX_SEARCH_QUERY_ATTEMPTS:
            break

    return ResearchQueryFallbackPlan(
        original_query=original,
        queries=tuple(unique),
    )


def build_research_query_attempts(query: WebSearchQuery) -> tuple[WebSearchQuery, ...]:
    plan = build_research_query_fallback_plan(query)
    return tuple(
        WebSearchQuery(query=value, count=query.count)
        for value in plan.queries
    )
