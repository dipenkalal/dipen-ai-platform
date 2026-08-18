from gateway.research_reliability_benchmark import (
    BENCHMARK_VERSION,
    run_benchmark,
)


def test_phase14_reliability_benchmark_passes_without_authority_expansion() -> None:
    report = run_benchmark(source_commit="a" * 40)

    assert report.benchmark_version == BENCHMARK_VERSION
    assert report.source_commit == "a" * 40
    assert report.case_count == 5
    assert report.cases_passed == 5
    assert report.completion_rate == 1.0
    assert report.all_cases_passed is True
    assert report.smart_routing_research_activated is False
    assert report.network_authority_expanded is False
    assert report.destructive_retention_action_performed is False
    assert len(report.report_sha256) == 64
    assert {case.name for case in report.cases} == {
        "source-family-diversity",
        "bounded-transient-retry",
        "operations-summary",
        "retention-dry-run",
        "provider-loopback-boundary",
    }
