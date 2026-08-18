from __future__ import annotations

import sqlite3
from pathlib import Path

from agents.truth_repository import AgentTruthRepository
from gateway.research_benchmark_bootstrap import (
    RESEARCH_EVIDENCE_TABLE,
    TASK_LEDGER_TABLE,
    _optional_evidence_count,
    _table_exists,
    bootstrap_research_evidence_schema,
)


def _count(database_path: Path, table: str) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def test_bootstrap_creates_only_missing_research_evidence_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "truth.db"
    AgentTruthRepository(database_path=database_path)

    assert _table_exists(database_path, TASK_LEDGER_TABLE) is True
    assert _table_exists(database_path, RESEARCH_EVIDENCE_TABLE) is False
    assert _optional_evidence_count(database_path) == 0

    task_before = _count(database_path, TASK_LEDGER_TABLE)
    result = bootstrap_research_evidence_schema(database_path)

    assert result.evidence_table_existed_before is False
    assert result.schema_bootstrap_performed is True
    assert result.evidence_table_exists_after is True
    assert result.research_evidence_before == 0
    assert result.research_evidence_after == 0
    assert result.task_ledger_before == task_before
    assert result.task_ledger_after == task_before
    assert result.task_ledger_mutated is False
    assert _table_exists(database_path, RESEARCH_EVIDENCE_TABLE) is True


def test_bootstrap_is_idempotent_after_evidence_schema_exists(tmp_path: Path) -> None:
    database_path = tmp_path / "truth.db"
    AgentTruthRepository(database_path=database_path)

    first = bootstrap_research_evidence_schema(database_path)
    second = bootstrap_research_evidence_schema(database_path)

    assert first.schema_bootstrap_performed is True
    assert second.evidence_table_existed_before is True
    assert second.schema_bootstrap_performed is False
    assert second.evidence_table_exists_after is True
    assert second.research_evidence_before == 0
    assert second.research_evidence_after == 0
    assert second.task_ledger_mutated is False


def test_bootstrap_requires_existing_task_ledger(tmp_path: Path) -> None:
    database_path = tmp_path / "truth.db"
    sqlite3.connect(database_path).close()

    try:
        bootstrap_research_evidence_schema(database_path)
    except RuntimeError as exc:
        assert "Required production table is missing: task_ledger" in str(exc)
    else:
        raise AssertionError("missing task_ledger must fail closed")
