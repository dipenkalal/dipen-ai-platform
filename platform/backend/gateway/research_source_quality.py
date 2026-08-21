from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

from gateway.web_search_provider import WebSearchCandidate

SOURCE_SELECTION_POLICY_ID = "dap-source-family-diversity-url-resilience-v2"
SOURCE_URL_DUPLICATE_POLICY_ID = "dap-source-url-dedup-v2"
SOURCE_RETRIEVAL_RESILIENCE_POLICY_ID = "dap-url-retrieval-resilience-v1"
_TRACKING_QUERY_NAMES = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "msclkid",
    }
)
_DOCUMENTATION_HOST_LABELS = frozenset(
    {
        "api",
        "developer",
        "developers",
        "docs",
        "documentation",
        "reference",
        "standards",
    }
)
_DOCUMENTATION_PATH_SEGMENTS = frozenset(
    {
        "api",
        "developer",
        "developers",
        "docs",
        "documentation",
        "guide",
        "guides",
        "manual",
        "reference",
        "references",
        "spec",
        "specification",
        "specifications",
        "standard",
        "standards",
    }
)
_STATIC_DOCUMENT_SUFFIXES = (".htm", ".html", ".txt")


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
    retrieval_resilience_signals: tuple[str, ...] = ()
    factual_credibility_assessed: bool = False
    provider_title_used_as_evidence: bool = False
    provider_snippet_used_as_evidence: bool = False


class ResearchSourceSelectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str = SOURCE_SELECTION_POLICY_ID
    duplicate_normalization_policy_id: str = SOURCE_URL_DUPLICATE_POLICY_ID
    retrieval_resilience_policy_id: str = SOURCE_RETRIEVAL_RESILIENCE_POLICY_ID
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
    provider_titles_or_snippets_used_for_selection: bool = False
    remote_probe_used_for_selection: bool = False


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


def source_retrieval_resilience_signals(url: str) -> tuple[str, ...]:
    """Return bounded URL-structure signals only; never inspect provider text or content."""

    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        raise ValueError("source URL must contain a hostname")

    signals: list[str] = []
    host_labels = tuple(label for label in hostname.split(".") if label)
    if host_labels and host_labels[0] in _DOCUMENTATION_HOST_LABELS:
        signals.append("documentation-host")

    path_segments = tuple(
        segment.casefold() for segment in parsed.path.split("/") if segment
    )
    normalized_stems = tuple(segment.rsplit(".", 1)[0] for segment in path_segments)
    if any(
        segment in _DOCUMENTATION_PATH_SEGMENTS
        or stem in _DOCUMENTATION_PATH_SEGMENTS
        or stem.startswith("rfc") and stem[3:].isdigit()
        for segment, stem in zip(path_segments, normalized_stems, strict=True)
    ):
        signals.append("documentation-or-standard-path")

    if parsed.path.casefold().endswith(_STATIC_DOCUMENT_SUFFIXES):
        signals.append("static-document-path")

    if hostname.endswith(".gov") or ".gov." in hostname:
        signals.append("government-host")
    elif hostname.endswith(".edu") or ".edu." in hostname:
        signals.append("education-host")

    return tuple(signals)


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

    resilient_order = sorted(
        unique_candidates,
        key=lambda candidate: (
            -_selection_quality_score(candidate, duplicate_family=False),
            candidate.rank,
            candidate.url,
        ),
    )

    selected: list[WebSearchCandidate] = []
    selected_families: set[str] = set()

    for candidate in resilient_order:
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
        for candidate in resilient_order:
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
            candidate,
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
                candidate,
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
            retrieval_resilience_signals=source_retrieval_resilience_signals(
                candidate.url
            ),
        )
        for candidate in resilient_order
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


def _selection_quality_score(
    candidate: WebSearchCandidate,
    *,
    duplicate_family: bool,
) -> int:
    score = 100 - ((candidate.rank - 1) * 8)
    signal_weights = {
        "documentation-host": 12,
        "documentation-or-standard-path": 12,
        "static-document-path": 4,
        "government-host": 8,
        "education-host": 6,
    }
    for signal in source_retrieval_resilience_signals(candidate.url):
        score += signal_weights[signal]
    if duplicate_family:
        score -= 25
    return max(0, min(100, score))


def _selection_reason(*, selected: bool, duplicate_family_fallback: bool) -> str:
    if selected and duplicate_family_fallback:
        return "selected-after-unique-source-families-exhausted"
    if selected:
        return "selected-for-source-family-diversity-and-url-retrieval-resilience"
    return "not-selected-within-bounded-retrieval-limit"
