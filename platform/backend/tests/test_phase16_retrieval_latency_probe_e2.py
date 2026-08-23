from pathlib import Path

import pytest

from gateway.research_retrieval_latency_probe_e2 import (
    PHASE16_RETRIEVAL_LATENCY_E2_VERSION,
    RetrievalDetailTrace,
    SourceEndToEndTrace,
    _isolated_repositories,
    nearest_rank_percentile,
    percentile,
    summarize_fetch_components,
    summarize_retriever_stages,
)


def _trace(
    *,
    total: float,
    fetch: float,
    connect_tls: float,
    response_header: float,
    response_body: float,
    dns: float = 10.0,
) -> RetrievalDetailTrace:
    fetch_uninstrumented = max(
        0.0,
        fetch - connect_tls - response_header - response_body - 2.0,
    )
    return RetrievalDetailTrace(
        source_key_sha256="a" * 64,
        source_family="example.com",
        success=True,
        total_ms=total,
        preflight_ms=1.0,
        dns_ms=dns,
        admission_ms=1.0,
        fetch_ms=fetch,
        connect_tls_ms=connect_tls,
        request_write_ms=1.0,
        response_header_ms=response_header,
        response_body_ms=response_body,
        close_wait_ms=1.0,
        fetch_uninstrumented_ms=fetch_uninstrumented,
        retriever_uninstrumented_ms=max(0.0, total - fetch - dns - 2.0),
        preflight_count=1,
        dns_count=1,
        admission_count=1,
        fetch_count=1,
        connection_attempt_count=1,
        request_drain_count=1,
        response_header_read_count=1,
        response_body_read_count=1,
        close_wait_count=1,
        redirect_hop_count=1,
    )


def test_phase16e2_probe_version_is_frozen() -> None:
    assert PHASE16_RETRIEVAL_LATENCY_E2_VERSION == "phase16e2.1"


def test_percentiles_include_exact_phase15_nearest_rank_metric() -> None:
    values = [100.0, 200.0, 300.0, 400.0, 500.0]

    assert percentile([], 0.95) == 0.0
    assert percentile(values, 0.50) == 300.0
    assert nearest_rank_percentile([], 0.95) is None
    assert nearest_rank_percentile(values, 0.50) == 300.0
    assert nearest_rank_percentile(values, 0.95) == 500.0


def test_retriever_summary_still_identifies_fetch_as_dominant_outer_stage() -> None:
    traces = [
        _trace(
            total=1000.0,
            fetch=900.0,
            connect_tls=150.0,
            response_header=650.0,
            response_body=90.0,
        ),
        _trace(
            total=2000.0,
            fetch=1850.0,
            connect_tls=200.0,
            response_header=1450.0,
            response_body=180.0,
        ),
    ]

    p50, p95 = summarize_retriever_stages(traces)

    assert p95["fetch"] > p95["dns"]
    assert p50["total"] == 1500.0


def test_fetch_component_summary_can_identify_response_header_wait() -> None:
    traces = [
        _trace(
            total=1000.0,
            fetch=900.0,
            connect_tls=150.0,
            response_header=650.0,
            response_body=90.0,
        ),
        _trace(
            total=2000.0,
            fetch=1850.0,
            connect_tls=200.0,
            response_header=1450.0,
            response_body=180.0,
        ),
        _trace(
            total=1200.0,
            fetch=1000.0,
            connect_tls=180.0,
            response_header=700.0,
            response_body=100.0,
        ),
    ]

    _p50, p95, dominant = summarize_fetch_components(traces)

    assert dominant == "response-header"
    assert p95["response-header"] > p95["connect-tls"]
    assert p95["response-header"] > p95["response-body"]


def test_failed_traces_do_not_distort_success_fetch_summary() -> None:
    successful = _trace(
        total=800.0,
        fetch=700.0,
        connect_tls=100.0,
        response_header=500.0,
        response_body=80.0,
    )
    failed = successful.model_copy(
        update={
            "success": False,
            "error_code": "connect-timeout",
            "total_ms": 9000.0,
            "fetch_ms": 8900.0,
            "connect_tls_ms": 8800.0,
        }
    )

    _p50, p95, dominant = summarize_fetch_components([successful, failed])

    assert p95["connect-tls"] == 100.0
    assert dominant == "response-header"


def test_source_record_models_exact_frozen_per_source_duration() -> None:
    record = SourceEndToEndTrace(
        source_key_sha256="b" * 64,
        source_family="example.org",
        success=True,
        duration_ms=1499.0,
        attempt_count=2,
        transient_retry_count=1,
        recovered_after_retry=True,
        retry_trigger_error_code="connect-timeout",
        retriever_trace_count=2,
        retriever_total_ms=1200.0,
        retry_backoff_ms=250.0,
        tool_overhead_excluding_backoff_ms=49.0,
    )

    assert record.duration_ms == 1499.0
    assert record.retry_backoff_ms == 250.0
    assert record.tool_overhead_excluding_backoff_ms == 49.0


def test_truth_database_must_be_isolated_tmp_path(tmp_path: Path) -> None:
    safe_path = tmp_path / "phase16e2.db"
    retrieval, operations = _isolated_repositories(safe_path)
    assert retrieval is not None
    assert operations is not None

    with pytest.raises(ValueError, match="isolated /tmp database"):
        _isolated_repositories(Path("/home/dipen/dap/data/agent-history/agent-truth.db"))
