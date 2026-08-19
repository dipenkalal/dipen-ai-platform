from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

from gateway.web_search_provider import WebSearchCandidate

SOURCE_SELECTION_POLICY_ID = "dap-source-family-diversity-v1"
SOURCE_URL_DUPLICATE_POLICY_ID = "dap-source-url-dedup-v2"
_TRACKING_QUERY_NAMES = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "msclkid",
    }
)


class ResearchSourceSelectionItem(BaseModel):
    """Explainable URL-selection quality; this is not a factual credibility score."""

    model_config = ConfigDict(frozen=True)

    rank: int = Field(ge=1, le=20)
    url: str
    source_family: str
    selection_quality_score: int = Field(ge=0, le=100)
    selected: bool
    selected_as_duplicate_family_fallback: bool = False
    reason: str
    factual_credibility_assessed: bool = False
    provider_title_used_as_evidence: bool = False
    provider_snippet_used_as_evidence: bool = False


class ResearchSourceSelectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str = SOURCE_SELECTION_POLICY_ID
    duplicate_normalization_policy_id: str = SOURCE_URL_DUPLICATE_POLICY_ID
    candidate_count: int = Field(ge=0)
    unique_url_count: int = Field(ge=0)
    unique_source_family_count: int = Field(ge=0)
    skipped_exact_duplicate_count: int = Field(ge=0)
    skipped_canonical_duplicate_count: int = Field(default=0, ge=0)
    duplicate_family_fallback_count: int = Field(ge=0)
    selected_urls: tuple[str, ...]
    selected_source_families: tuple[str, ...]
    selected_quality_scores: tuple[int, ...]
    items: tuple[ResearchSourceSelectionItem, ...]
    factual_credibility_assessed: bool = False
    provider_titles_or_snippets_used_as_evidence: bool = False


def canonical_source_family(url: str) -> str:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise ValueError("source URL must contain a hostname")
    if hostname.startswith("www.") and len(hostname) > 4:
        hostname = hostname[4:]
    return hostname


def canonical_source_url_duplicate_key(url: str) -> str:
    """Normalize only duplicate-noise; selected URLs themselves are never rewritten."""

    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise ValueError("source URL must contain a hostname")

    scheme = parsed.scheme.lower()
    port = parsed.port
    default_port = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    path = parsed.path or "/"

    query_pairs = []
    for name, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_name = name.lower()
        if normalized_name.startswith("utm_") or normalized_name in _TRACKING_QUERY_NAMES:
            continue
        query_pairs.append((name, value))
    query_pairs.sort(key=lambda pair: (pair[0], pair[1]))

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            urlencode(query_pairs, doseq=True),
            "",
        )
    )


def select_source_diverse_candidates(
    candidates: Sequence[WebSearchCandidate],
    *,
    limit: int,
) -> ResearchSourceSelectionResult:
    if limit < 1 or limit > 3:
        raise ValueError("source-diversity selection limit must be between 1 and 3")

    ordered = sorted(candidates, key=lambda candidate: candidate.rank)
    unique_candidates: list[WebSearchCandidate] = []
    seen_urls: set[str] = set()
    seen_duplicate_keys: set[str] = set()
    skipped_exact_duplicates = 0
    skipped_canonical_duplicates = 0

    for candidate in ordered:
        if not candidate.candidate_url_requires_dap_retrieval:
            continue
        if candidate.candidate_is_retrieval_evidence:
            continue
        if candidate.url in seen_urls:
            skipped_exact_duplicates += 1
            continue
        duplicate_key = canonical_source_url_duplicate_key(candidate.url)
        if duplicate_key in seen_duplicate_keys:
            skipped_canonical_duplicates += 1
            continue
        seen_urls.add(candidate.url)
        seen_duplicate_keys.add(duplicate_key)
        unique_candidates.append(candidate)

    selected: list[WebSearchCandidate] = []
    selected_families: set[str] = set()

    for candidate in unique_candidates:
        family = canonical_source_family(candidate.url)
        if family in selected_families:
            continue
        selected.append(candidate)
        selected_families.add(family)
        if len(selected) >= limit:
            break

    duplicate_family_fallback_urls: set[str] = set()
    if len(selected) < limit:
        already_selected_urls = {candidate.url for candidate in selected}
        for candidate in unique_candidates:
            if candidate.url in already_selected_urls:
                continue
            selected.append(candidate)
            duplicate_family_fallback_urls.add(candidate.url)
            if len(selected) >= limit:
                break

    selected_urls = tuple(candidate.url for candidate in selected)
    selected_source_families = tuple(
        canonical_source_family(candidate.url) for candidate in selected
    )
    selected_quality_scores = tuple(
        _selection_quality_score(
            candidate.rank,
            duplicate_family=candidate.url in duplicate_family_fallback_urls,
        )
        for candidate in selected
    )

    all_families = {
        canonical_source_family(candidate.url) for candidate in unique_candidates
    }
    selected_url_set = set(selected_urls)
    items = tuple(
        ResearchSourceSelectionItem(
            rank=candidate.rank,
            url=candidate.url,
            source_family=canonical_source_family(candidate.url),
            selection_quality_score=_selection_quality_score(
                candidate.rank,
                duplicate_family=candidate.url in duplicate_family_fallback_urls,
            ),
            selected=candidate.url in selected_url_set,
            selected_as_duplicate_family_fallback=(
                candidate.url in duplicate_family_fallback_urls
            ),
            reason=_selection_reason(
                selected=candidate.url in selected_url_set,
                duplicate_family_fallback=(
                    candidate.url in duplicate_family_fallback_urls
                ),
            ),
        )
        for candidate in unique_candidates
    )

    return ResearchSourceSelectionResult(
        candidate_count=len(ordered),
        unique_url_count=len(unique_candidates),
        unique_source_family_count=len(all_families),
        skipped_exact_duplicate_count=skipped_exact_duplicates,
        skipped_canonical_duplicate_count=skipped_canonical_duplicates,
        duplicate_family_fallback_count=len(duplicate_family_fallback_urls),
        selected_urls=selected_urls,
        selected_source_families=selected_source_families,
        selected_quality_scores=selected_quality_scores,
        items=items,
    )


def _selection_quality_score(rank: int, *, duplicate_family: bool) -> int:
    score = 100 - ((rank - 1) * 8)
    if duplicate_family:
        score -= 25
    return max(0, min(100, score))


def _selection_reason(*, selected: bool, duplicate_family_fallback: bool) -> str:
    if selected and duplicate_family_fallback:
        return "selected-after-unique-source-families-exhausted"
    if selected:
        return "selected-for-rank-and-source-family-diversity"
    return "not-selected-within-bounded-retrieval-limit"
