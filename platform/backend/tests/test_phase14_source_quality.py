from gateway.research_source_quality import (
    SOURCE_SELECTION_POLICY_ID,
    canonical_source_family,
    select_source_diverse_candidates,
)
from gateway.web_search_provider import WebSearchCandidate


def _candidate(rank: int, url: str) -> WebSearchCandidate:
    return WebSearchCandidate(
        rank=rank,
        title=f"Candidate {rank}",
        url=url,
        snippet="provider metadata only",
    )


def test_canonical_source_family_strips_only_www_alias() -> None:
    assert canonical_source_family("https://www.example.com/path") == "example.com"
    assert canonical_source_family("https://docs.example.com/path") == "docs.example.com"


def test_selection_prefers_unique_source_families_before_duplicate_family() -> None:
    result = select_source_diverse_candidates(
        (
            _candidate(1, "https://www.example.com/one"),
            _candidate(2, "https://example.com/two"),
            _candidate(3, "https://docs.example.org/three"),
            _candidate(4, "https://example.net/four"),
        ),
        limit=3,
    )

    assert result.policy_id == SOURCE_SELECTION_POLICY_ID
    assert result.selected_urls == (
        "https://www.example.com/one",
        "https://docs.example.org/three",
        "https://example.net/four",
    )
    assert result.selected_source_families == (
        "example.com",
        "docs.example.org",
        "example.net",
    )
    assert result.duplicate_family_fallback_count == 0
    assert result.factual_credibility_assessed is False
    assert result.provider_titles_or_snippets_used_as_evidence is False


def test_selection_uses_duplicate_family_only_after_unique_families_exhausted() -> None:
    result = select_source_diverse_candidates(
        (
            _candidate(1, "https://www.example.com/one"),
            _candidate(2, "https://example.com/two"),
            _candidate(3, "https://example.com/three"),
        ),
        limit=3,
    )

    assert result.selected_urls == (
        "https://www.example.com/one",
        "https://example.com/two",
        "https://example.com/three",
    )
    assert result.unique_source_family_count == 1
    assert result.duplicate_family_fallback_count == 2
    assert result.selected_quality_scores[0] > result.selected_quality_scores[1]
    assert all(item.factual_credibility_assessed is False for item in result.items)


def test_exact_url_duplicates_are_suppressed_before_selection() -> None:
    result = select_source_diverse_candidates(
        (
            _candidate(1, "https://example.com/one"),
            _candidate(2, "https://example.com/one"),
            _candidate(3, "https://example.org/two"),
        ),
        limit=3,
    )

    assert result.unique_url_count == 2
    assert result.skipped_exact_duplicate_count == 1
    assert result.selected_urls == (
        "https://example.com/one",
        "https://example.org/two",
    )


def test_selection_limit_cannot_exceed_sealed_retrieval_ceiling() -> None:
    try:
        select_source_diverse_candidates(
            (_candidate(1, "https://example.com/one"),),
            limit=4,
        )
    except ValueError as exc:
        assert "between 1 and 3" in str(exc)
    else:
        raise AssertionError("selection limit above three must fail closed")
