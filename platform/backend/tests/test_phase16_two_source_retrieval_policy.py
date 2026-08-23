from __future__ import annotations

from gateway.research_retrieval_hedge import (
    AUTOMATIC_RETRIEVAL_HEDGE_DELAY_SECONDS,
    AUTOMATIC_RETRIEVAL_HEDGE_MAX_CANDIDATES,
    AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID,
    AUTOMATIC_RETRIEVAL_HEDGE_TARGET_SUCCESSES,
)
from gateway.research_source_quality import (
    select_source_diverse_candidates,
)
from gateway.searxng_search_provider import (
    SEARXNG_CANDIDATE_RESERVOIR_LIMIT,
)
from gateway.web_search_discovery import (
    MAX_AUTOMATIC_RETRIEVAL_CANDIDATES,
    MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL,
)
from gateway.web_search_provider import (
    WebSearchCandidate,
)
from tools.internet_research_tools import (
    MAX_EXPLICIT_RESEARCH_URLS,
    InternetResearchRetrieveTool,
)


def _candidate(
    rank: int,
    url: str,
) -> WebSearchCandidate:
    return WebSearchCandidate(
        rank=rank,
        title=f"Provider title {rank}",
        url=url,
        snippet="provider metadata only",
    )


def test_phase16_automatic_search_evidence_target_remains_two_sources() -> None:
    assert MAX_SEARCH_CANDIDATES_FOR_RETRIEVAL == 2
    assert AUTOMATIC_RETRIEVAL_HEDGE_TARGET_SUCCESSES == 2


def test_phase16_automatic_hedge_is_bounded_to_one_standby_candidate() -> None:
    assert MAX_AUTOMATIC_RETRIEVAL_CANDIDATES == 3
    assert AUTOMATIC_RETRIEVAL_HEDGE_MAX_CANDIDATES == 3
    assert AUTOMATIC_RETRIEVAL_HEDGE_DELAY_SECONDS == 0.75
    assert (
        AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID
        == "dap-bounded-two-of-three-retrieval-hedge-v1"
    )


def test_phase16_explicit_owner_url_retrieval_remains_bounded_to_three() -> None:
    assert MAX_EXPLICIT_RESEARCH_URLS == 3

    urls = [
        "https://one.example/source",
        "https://two.example/source",
        "https://three.example/source",
    ]

    assert (
        InternetResearchRetrieveTool._parse_urls(
            urls
        )
        == tuple(urls)
    )

    rejected = (
        InternetResearchRetrieveTool._parse_urls(
            [
                *urls,
                "https://four.example/source",
            ]
        )
    )

    assert isinstance(rejected, str)
    assert "At most 3" in rejected


def test_phase16_provider_candidate_reservoir_remains_eight() -> None:
    assert (
        SEARXNG_CANDIDATE_RESERVOIR_LIMIT
        == 8
    )


def test_phase16_two_source_selection_prefers_distinct_source_families() -> None:
    result = select_source_diverse_candidates(
        (
            _candidate(
                1,
                "https://one.example/article",
            ),
            _candidate(
                2,
                "https://two.example/article",
            ),
            _candidate(
                3,
                "https://three.example/article",
            ),
        ),
        limit=2,
    )

    assert result.selected_urls == (
        "https://one.example/article",
        "https://two.example/article",
    )

    assert result.selected_source_families == (
        "one.example",
        "two.example",
    )

    assert (
        result.duplicate_family_fallback_count
        == 0
    )

    assert (
        result.provider_titles_or_snippets_used_for_selection
        is False
    )

    assert (
        result.provider_titles_or_snippets_used_as_evidence
        is False
    )

    assert result.remote_probe_used_for_selection is False


def test_phase16_two_source_selection_keeps_duplicate_family_fallback_bounded() -> None:
    result = select_source_diverse_candidates(
        (
            _candidate(
                1,
                "https://same.example/one",
            ),
            _candidate(
                2,
                "https://same.example/two",
            ),
            _candidate(
                3,
                "https://same.example/three",
            ),
        ),
        limit=2,
    )

    assert len(result.selected_urls) == 2
    assert result.selected_urls == (
        "https://same.example/one",
        "https://same.example/two",
    )

    assert (
        result.duplicate_family_fallback_count
        == 1
    )


def test_phase16_low_level_selector_still_supports_three_for_bounded_standby() -> None:
    result = select_source_diverse_candidates(
        (
            _candidate(
                1,
                "https://one.example/article",
            ),
            _candidate(
                2,
                "https://two.example/article",
            ),
            _candidate(
                3,
                "https://three.example/article",
            ),
        ),
        limit=3,
    )

    assert len(result.selected_urls) == 3
