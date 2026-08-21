from pathlib import Path

import pytest

from gateway.research_retrieval_latency_probe import (
    PHASE16_RETRIEVAL_LATENCY_VERSION,
    RetrievalStageTrace,
    _isolated_repositories,
    percentile,
    summarize_stage_timings,
)


def _trace(*, total: float, fetch: float, dns: float = 10.0) -> RetrievalStageTrace:
    return RetrievalStageTrace(
        source_family="example.com",
        success=True,
        total_ms=total,
        preflight_ms=1.0,
        dns_ms=dns,
        admission_ms=1.0,
        fetch_ms=fetch,
        uninstrumented_overhead_ms=max(0.0, total - fetch - dns - 2.0),
        preflight_count=1,
        dns_count=1,
        admission_count=1,
        fetch_count=1,
        redirect_hop_count=1,
    )


def test_latency_probe_version_is_frozen() -> None:
    assert PHASE16_RETRIEVAL_LATENCY_VERSION == "phase16e1.1"


def test_percentile_is_deterministic() -> None:
    assert percentile([], 0.95) == 0.0
    assert percentile([10.0], 0.95) == 10.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.50) == 25.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.95) == 38.5


def test_summary_identifies_fetch_as_dominant_stage() -> None:
    traces = [
        _trace(total=1000.0, fetch=900.0),
        _trace(total=2000.0, fetch=1850.0),
        _trace(total=3000.0, fetch=2800.0),
    ]

    p50, p95, dominant, fetch_share_p50, over_1500 = summarize_stage_timings(traces)

    assert dominant == "fetch"
    assert p50["total"] == 2000.0
    assert p95["fetch"] > p95["dns"]
    assert 0.8 < fetch_share_p50 <= 1.0
    assert over_1500 == 2


def test_failed_traces_do_not_distort_success_latency_summary() -> None:
    traces = [
        _trace(total=1000.0, fetch=900.0),
        RetrievalStageTrace(
            source_family="example.net",
            success=False,
            error_code="connect-timeout",
            total_ms=9000.0,
            preflight_ms=1.0,
            dns_ms=1.0,
            admission_ms=1.0,
            fetch_ms=8990.0,
            uninstrumented_overhead_ms=7.0,
            preflight_count=1,
            dns_count=1,
            admission_count=1,
            fetch_count=1,
            redirect_hop_count=1,
        ),
    ]

    p50, p95, dominant, _fetch_share_p50, over_1500 = summarize_stage_timings(traces)

    assert p50["total"] == 1000.0
    assert p95["total"] == 1000.0
    assert dominant == "fetch"
    assert over_1500 == 0


def test_truth_database_must_be_isolated_tmp_path(tmp_path: Path) -> None:
    safe_path = tmp_path / "phase16e.db"
    retrieval, operations = _isolated_repositories(safe_path)
    assert retrieval is not None
    assert operations is not None

    with pytest.raises(ValueError, match="isolated /tmp database"):
        _isolated_repositories(Path("/home/dipen/dap/data/agent-history/agent-truth.db"))
