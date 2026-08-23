from pathlib import Path

import pytest

from gateway.research_provider_phase16_slow_tail_probe import (
    PHASE16_H1_PROBE_VERSION,
    PHASE16_H1_REPEAT_COUNT,
    PHASE16_H1_TARGET_CASE_IDS,
    _component_totals,
    _isolated_repositories,
    _slow_source_diagnostic,
    _target_cases,
)
from gateway.research_retrieval_latency_probe_e2 import (
    RetrievalDetailTrace,
    SourceEndToEndTrace,
)


def _trace() -> RetrievalDetailTrace:
    return RetrievalDetailTrace(
        source_key_sha256="a" * 64,
        source_family="example.com",
        success=True,
        total_ms=1800.0,
        preflight_ms=1.0,
        dns_ms=100.0,
        admission_ms=1.0,
        fetch_ms=1600.0,
        connect_tls_ms=200.0,
        request_write_ms=1.0,
        response_header_ms=1200.0,
        response_body_ms=150.0,
        close_wait_ms=1.0,
        fetch_uninstrumented_ms=48.0,
        retriever_uninstrumented_ms=98.0,
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


def _record() -> SourceEndToEndTrace:
    return SourceEndToEndTrace(
        source_key_sha256="a" * 64,
        source_family="example.com",
        success=True,
        duration_ms=1800.0,
        attempt_count=1,
        transient_retry_count=0,
        recovered_after_retry=False,
        retriever_trace_count=1,
        retriever_total_ms=1800.0,
        retry_backoff_ms=0.0,
        tool_overhead_excluding_backoff_ms=0.0,
    )


def test_h1_contract_is_frozen_to_observed_slow_tail_cases() -> None:
    assert PHASE16_H1_PROBE_VERSION == "phase16h1.1"
    assert PHASE16_H1_REPEAT_COUNT == 3
    assert PHASE16_H1_TARGET_CASE_IDS == (
        "p16-usgs-earthquake-magnitude",
        "p16-overlay-filesystems",
        "p16-rfc9293-tcp",
        "p16-dns-over-https",
    )

    cases = _target_cases()
    assert tuple(case.case_id for case in cases) == PHASE16_H1_TARGET_CASE_IDS


def test_h1_component_diagnosis_preserves_hashed_source_identity() -> None:
    trace = _trace()
    record = _record()

    totals = _component_totals([trace], record)
    diagnostic = _slow_source_diagnostic(
        case_id="p16-rfc9293-tcp",
        category="standards",
        iteration=2,
        record=record,
        traces=[trace],
    )

    assert totals["response-header"] == 1200.0
    assert diagnostic.source_key_sha256 == "a" * 64
    assert diagnostic.source_family == "example.com"
    assert diagnostic.dominant_component == "response-header"
    assert "url" not in diagnostic.model_dump(mode="json")


def test_h1_truth_database_must_be_isolated_tmp_path(tmp_path: Path) -> None:
    retrieval, operations = _isolated_repositories(tmp_path / "phase16h1.db")
    assert retrieval is not None
    assert operations is not None

    with pytest.raises(ValueError, match="isolated /tmp database"):
        _isolated_repositories(
            Path("/home/dipen/dap/data/agent-history/agent-truth.db")
        )
