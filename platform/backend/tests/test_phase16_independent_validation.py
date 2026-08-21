from __future__ import annotations

from pathlib import Path

import pytest

from gateway.research_provider_corpus import PHASE15_PROVIDER_CORPUS
from gateway.research_provider_phase16_validation import (
    PHASE16_VALIDATION_VERSION,
    Phase16ValidationThresholds,
    _isolated_repositories,
    _percentile,
)
from gateway.research_provider_phase16_validation_corpus import (
    PHASE16_VALIDATION_CORPUS,
    PHASE16_VALIDATION_CORPUS_CASE_COUNT,
    PHASE16_VALIDATION_CORPUS_VERSION,
    validate_phase16_validation_corpus,
)


def test_phase16_validation_corpus_is_balanced_and_independent() -> None:
    validate_phase16_validation_corpus()

    assert PHASE16_VALIDATION_CORPUS_VERSION == "phase16-validation-corpus-v1"
    assert PHASE16_VALIDATION_CORPUS_CASE_COUNT == 24
    assert len(PHASE16_VALIDATION_CORPUS) == 24

    categories = [case.category for case in PHASE16_VALIDATION_CORPUS]
    assert set(categories) == {
        "official-documentation",
        "standards",
        "general-factual",
        "multi-source-technical",
    }
    for category in set(categories):
        assert categories.count(category) == 6

    phase15_ids = {case.case_id for case in PHASE15_PROVIDER_CORPUS}
    phase15_queries = {case.query.casefold().strip() for case in PHASE15_PROVIDER_CORPUS}
    assert not phase15_ids.intersection(
        case.case_id for case in PHASE16_VALIDATION_CORPUS
    )
    assert not phase15_queries.intersection(
        case.query.casefold().strip() for case in PHASE16_VALIDATION_CORPUS
    )


def test_phase16_validation_reuses_frozen_phase15_targets() -> None:
    thresholds = Phase16ValidationThresholds()

    assert PHASE16_VALIDATION_VERSION == "phase16h.1"
    assert thresholds.minimum_success_rate == 0.95
    assert thresholds.maximum_no_candidate_rate == 0.05
    assert thresholds.minimum_unique_source_family_rate == 0.80
    assert thresholds.maximum_duplicate_content_rate == 0.20
    assert thresholds.maximum_retrieval_p95_ms == 1500.0
    assert thresholds.maximum_case_wall_clock_seconds == 60.0


def test_phase16_validation_percentile_uses_nearest_rank() -> None:
    assert _percentile([], 0.95) is None
    assert _percentile([10.0], 0.95) == 10.0
    assert _percentile([1.0, 2.0, 3.0, 4.0], 0.50) == 2.0
    assert _percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_phase16_validation_rejects_non_tmp_truth_database() -> None:
    with pytest.raises(ValueError, match="isolated /tmp database"):
        _isolated_repositories(Path("/home/dipen/dap/data/agent-history/agent-truth.db"))


def test_phase16_validation_accepts_tmp_truth_database(tmp_path: Path) -> None:
    database = tmp_path / "phase16-validation.db"
    retrieval, operations = _isolated_repositories(database)

    assert retrieval is not None
    assert operations is not None
