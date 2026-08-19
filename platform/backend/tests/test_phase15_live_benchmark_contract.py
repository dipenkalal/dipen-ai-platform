from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agents.truth_repository import DEFAULT_TRUTH_DATABASE_PATH
from gateway.research_provider_live_benchmark import (
    LIVE_CASE_TIMEOUT_SECONDS,
    MAXIMUM_LIVE_DUPLICATE_CONTENT_RATE,
    MAXIMUM_LIVE_NO_CANDIDATE_RATE,
    MAXIMUM_LIVE_RETRIEVAL_P95_MS,
    MINIMUM_LIVE_SUCCESS_RATE,
    MINIMUM_LIVE_UNIQUE_SOURCE_FAMILY_RATE,
    Phase15LiveThresholds,
    _isolated_truth_repository,
    _percentile,
)


def test_phase15_live_thresholds_are_frozen_before_live_corpus() -> None:
    thresholds = Phase15LiveThresholds()

    assert thresholds.minimum_success_rate == MINIMUM_LIVE_SUCCESS_RATE == 0.95
    assert thresholds.maximum_no_candidate_rate == MAXIMUM_LIVE_NO_CANDIDATE_RATE == 0.05
    assert (
        thresholds.minimum_unique_source_family_rate
        == MINIMUM_LIVE_UNIQUE_SOURCE_FAMILY_RATE
        == 0.80
    )
    assert (
        thresholds.maximum_duplicate_content_rate
        == MAXIMUM_LIVE_DUPLICATE_CONTENT_RATE
        == 0.20
    )
    assert thresholds.maximum_retrieval_p95_ms == MAXIMUM_LIVE_RETRIEVAL_P95_MS == 1500.0
    assert thresholds.maximum_case_wall_clock_seconds == LIVE_CASE_TIMEOUT_SECONDS == 60.0


def test_percentile_is_deterministic_nearest_rank() -> None:
    assert _percentile([], 0.95) is None
    assert _percentile([500.0, 100.0, 300.0, 200.0, 400.0], 0.50) == 300.0
    assert _percentile([500.0, 100.0, 300.0, 200.0, 400.0], 0.95) == 500.0


def test_live_benchmark_truth_database_must_be_isolated_tmp(tmp_path: Path) -> None:
    benchmark_db = tmp_path / "phase15-live.db"
    _isolated_truth_repository(benchmark_db)

    connection = sqlite3.connect(benchmark_db)
    try:
        task_count = connection.execute("SELECT COUNT(*) FROM task_ledger").fetchone()
        evidence_table = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='research_retrieval_evidence'"
        ).fetchone()
        operations_table = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='research_operations_events'"
        ).fetchone()
    finally:
        connection.close()

    assert task_count == (0,)
    assert evidence_table == (1,)
    assert operations_table == (1,)

    with pytest.raises(ValueError, match="isolated /tmp database"):
        _isolated_truth_repository(DEFAULT_TRUTH_DATABASE_PATH)

    with pytest.raises(ValueError, match="isolated /tmp database"):
        _isolated_truth_repository(Path("/var/tmp/not-phase15.db"))
