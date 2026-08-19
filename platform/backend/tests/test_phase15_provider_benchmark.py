from gateway.research_provider_benchmark import (
    BENCHMARK_VERSION,
    run_phase15_provider_benchmark,
)
from gateway.research_provider_corpus import (
    PHASE15_CORPUS_MINIMUM_CASES,
    PHASE15_CORPUS_VERSION,
    PHASE15_PROVIDER_CORPUS,
    validate_phase15_provider_corpus,
)


def test_phase15_corpus_is_frozen_at_thirty_cases_across_all_categories() -> None:
    validate_phase15_provider_corpus()

    assert PHASE15_CORPUS_VERSION == "phase15-provider-corpus-v1"
    assert PHASE15_CORPUS_MINIMUM_CASES == 30
    assert len(PHASE15_PROVIDER_CORPUS) == 30
    assert len({case.case_id for case in PHASE15_PROVIDER_CORPUS}) == 30
    assert {case.category for case in PHASE15_PROVIDER_CORPUS} == {
        "official-documentation",
        "standards",
        "general-factual",
        "multi-source-technical",
    }


def test_phase15_offline_provider_benchmark_is_deterministic_and_authority_safe() -> None:
    first = run_phase15_provider_benchmark(source_commit="a" * 40)
    second = run_phase15_provider_benchmark(source_commit="a" * 40)

    assert first == second
    assert first.benchmark_version == BENCHMARK_VERSION == "phase15h.1"
    assert first.case_count == 30
    assert first.cases_passed == 30
    assert first.all_cases_passed is True
    assert len(first.report_sha256) == 64
    assert first.smart_routing_research_activated is False
    assert first.provider_switching_allowed is False
    assert first.generic_network_authority_expanded is False
    assert first.provider_titles_or_snippets_used_as_evidence is False
    assert first.automatic_knowledge_mutation_performed is False
    assert first.destructive_evidence_cleanup_performed is False
    assert first.guardian_contacted is False
    assert all(item.selected_url_count == 3 for item in first.cases)
    assert all(item.selected_unique_source_family_count == 3 for item in first.cases)
    assert all(item.skipped_canonical_duplicate_count == 1 for item in first.cases)
    assert all(item.owner_query_only_fallback is True for item in first.cases)
    assert all(item.passed is True for item in first.cases)
