from pathlib import Path

import pytest

from gateway.research_provider_diagnostic import (
    Phase16AttemptDiagnostic,
    _isolated_repositories,
    classify_no_candidate_attempts,
)


def _attempt(
    *,
    provider_results: int,
    invalid: int = 0,
    rejected: int = 0,
    provider_zero: bool = False,
    filtered_zero: bool = False,
) -> Phase16AttemptDiagnostic:
    return Phase16AttemptDiagnostic(
        query="bounded diagnostic query",
        candidate_count=0,
        selected_count=0,
        provider_result_count=provider_results,
        considered_result_count=provider_results,
        invalid_candidate_count=invalid,
        policy_rejected_candidate_count=rejected,
        provider_zero_results=provider_zero,
        admissible_candidate_zero_after_filtering=filtered_zero,
        outcome="no-candidate",
    )


def test_all_zero_provider_attempts_are_classified_as_provider_zero() -> None:
    attempts = (
        _attempt(provider_results=0, provider_zero=True),
        _attempt(provider_results=0, provider_zero=True),
        _attempt(provider_results=0, provider_zero=True),
    )

    assert classify_no_candidate_attempts(attempts) == "provider-zero-results"


def test_raw_results_filtered_by_dap_are_classified_separately() -> None:
    attempts = (
        _attempt(
            provider_results=4,
            rejected=4,
            filtered_zero=True,
        ),
    )

    assert classify_no_candidate_attempts(attempts) == "dap-filtered-zero"


def test_invalid_raw_results_are_classified_as_dap_filtered_zero() -> None:
    attempts = (
        _attempt(provider_results=3, invalid=3),
    )

    assert classify_no_candidate_attempts(attempts) == "dap-filtered-zero"


def test_ambiguous_no_candidate_case_does_not_claim_provider_zero() -> None:
    attempts = (
        _attempt(provider_results=0, provider_zero=False),
    )

    assert classify_no_candidate_attempts(attempts) == "unclassified-no-candidate"


def test_attempt_contract_excludes_provider_text() -> None:
    dumped = _attempt(provider_results=0, provider_zero=True).model_dump(mode="json")

    assert dumped["provider_titles_recorded"] is False
    assert dumped["provider_snippets_recorded"] is False
    assert "title" not in dumped
    assert "snippet" not in dumped


def test_diagnostic_truth_database_must_be_under_tmp(tmp_path: Path) -> None:
    outside_tmp = Path.cwd() / "phase16-diagnostic.db"

    with pytest.raises(ValueError, match="isolated /tmp database"):
        _isolated_repositories(outside_tmp)

    isolated = tmp_path / "phase16-diagnostic.db"
    retrieval, operations = _isolated_repositories(isolated)

    assert retrieval is not None
    assert operations is not None
