from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gateway.research_provider_corpus import (
    PHASE15_CORPUS_VERSION,
    PHASE15_PROVIDER_CORPUS,
    validate_phase15_provider_corpus,
)
from gateway.research_query_fallback import build_research_query_fallback_plan
from gateway.research_source_quality import select_source_diverse_candidates
from gateway.web_search_provider import WebSearchCandidate, WebSearchQuery

BENCHMARK_VERSION = "phase15h.1"


class Phase15ProviderBenchmarkCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    query_attempt_count: int = Field(ge=1, le=3)
    selected_url_count: int = Field(ge=0, le=3)
    selected_unique_source_family_count: int = Field(ge=0, le=3)
    skipped_canonical_duplicate_count: int = Field(ge=0)
    owner_query_only_fallback: bool
    selected_urls_require_full_dap_retrieval: Literal[True] = True
    passed: bool


class Phase15ProviderBenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    benchmark_version: Literal["phase15h.1"] = BENCHMARK_VERSION
    corpus_version: str = PHASE15_CORPUS_VERSION
    source_commit: str
    case_count: int = Field(ge=30)
    cases_passed: int = Field(ge=0)
    all_cases_passed: bool
    cases: tuple[Phase15ProviderBenchmarkCaseResult, ...]
    smart_routing_research_activated: Literal[False] = False
    provider_switching_allowed: Literal[False] = False
    generic_network_authority_expanded: Literal[False] = False
    provider_titles_or_snippets_used_as_evidence: Literal[False] = False
    automatic_knowledge_mutation_performed: Literal[False] = False
    destructive_evidence_cleanup_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _fixture_candidates(case_id: str) -> tuple[WebSearchCandidate, ...]:
    return (
        WebSearchCandidate(
            rank=1,
            title="Fixture candidate A",
            url=f"https://docs-a.example/{case_id}?topic=1&utm_source=fixture#section",
            snippet="fixture metadata only",
        ),
        WebSearchCandidate(
            rank=2,
            title="Fixture tracking duplicate A",
            url=f"https://docs-a.example/{case_id}?utm_medium=fixture&topic=1",
            snippet="fixture metadata only",
        ),
        WebSearchCandidate(
            rank=3,
            title="Fixture candidate B",
            url=f"https://docs-b.example/{case_id}",
            snippet="fixture metadata only",
        ),
        WebSearchCandidate(
            rank=4,
            title="Fixture candidate C",
            url=f"https://docs-c.example/{case_id}",
            snippet="fixture metadata only",
        ),
    )


def _case_result(case_id: str, category: str, query: str) -> Phase15ProviderBenchmarkCaseResult:
    fallback = build_research_query_fallback_plan(
        WebSearchQuery(query=query, count=5)
    )
    original_tokens = set(fallback.original_query.split())
    owner_query_only = all(
        set(attempt.split()) <= original_tokens
        for attempt in fallback.queries
    )
    selection = select_source_diverse_candidates(
        _fixture_candidates(case_id),
        limit=3,
    )
    selected_family_count = len(set(selection.selected_source_families))
    passed = bool(
        owner_query_only
        and len(fallback.queries) <= 3
        and len(selection.selected_urls) == 3
        and selected_family_count == 3
        and selection.skipped_canonical_duplicate_count == 1
        and selection.factual_credibility_assessed is False
        and selection.provider_titles_or_snippets_used_as_evidence is False
    )
    return Phase15ProviderBenchmarkCaseResult(
        case_id=case_id,
        category=category,
        query_attempt_count=len(fallback.queries),
        selected_url_count=len(selection.selected_urls),
        selected_unique_source_family_count=selected_family_count,
        skipped_canonical_duplicate_count=selection.skipped_canonical_duplicate_count,
        owner_query_only_fallback=owner_query_only,
        passed=passed,
    )


def run_phase15_provider_benchmark(*, source_commit: str) -> Phase15ProviderBenchmarkReport:
    validate_phase15_provider_corpus()
    results = tuple(
        _case_result(case.case_id, case.category, case.query)
        for case in PHASE15_PROVIDER_CORPUS
    )
    cases_passed = sum(item.passed for item in results)
    payload = {
        "benchmark_version": BENCHMARK_VERSION,
        "corpus_version": PHASE15_CORPUS_VERSION,
        "source_commit": source_commit,
        "case_count": len(results),
        "cases_passed": cases_passed,
        "all_cases_passed": cases_passed == len(results),
        "cases": [item.model_dump(mode="json") for item in results],
        "smart_routing_research_activated": False,
        "provider_switching_allowed": False,
        "generic_network_authority_expanded": False,
        "provider_titles_or_snippets_used_as_evidence": False,
        "automatic_knowledge_mutation_performed": False,
        "destructive_evidence_cleanup_performed": False,
        "guardian_contacted": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    report_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Phase15ProviderBenchmarkReport(
        **payload,
        report_sha256=report_sha256,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = run_phase15_provider_benchmark(source_commit=args.source_commit)
    args.output.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"benchmark_version|{report.benchmark_version}")
    print(f"case_count|{report.case_count}")
    print(f"cases_passed|{report.cases_passed}")
    print(f"all_cases_passed|{str(report.all_cases_passed).lower()}")
    print(f"report_sha256|{report.report_sha256}")
    return 0 if report.all_cases_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
