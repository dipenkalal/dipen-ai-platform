from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from agents.truth_repository import AgentTruthRepository
from gateway.research_retrieval_repository import ResearchRetrievalRepository

RESEARCH_EVIDENCE_TABLE = "research_retrieval_evidence"
TASK_LEDGER_TABLE = "task_ledger"


@dataclass(frozen=True)
class ResearchBenchmarkBootstrapResult:
    evidence_table_existed_before: bool
    evidence_table_exists_after: bool
    schema_bootstrap_performed: bool
    task_ledger_before: int
    task_ledger_after: int
    research_evidence_before: int
    research_evidence_after: int

    @property
    def task_ledger_mutated(self) -> bool:
        return self.task_ledger_before != self.task_ledger_after


def _read_only_connection(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)


def _table_exists(database_path: Path, table: str) -> bool:
    with _read_only_connection(database_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    return row is not None


def _required_table_count(database_path: Path, table: str) -> int:
    if table != TASK_LEDGER_TABLE:
        raise ValueError("Phase 12J required-table count is limited to task_ledger.")
    if not _table_exists(database_path, table):
        raise RuntimeError(f"Required production table is missing: {table}")
    with _read_only_connection(database_path) as connection:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    if row is None:
        raise RuntimeError(f"Unable to count required production table: {table}")
    return int(row[0])


def _optional_evidence_count(database_path: Path) -> int:
    if not _table_exists(database_path, RESEARCH_EVIDENCE_TABLE):
        return 0
    with _read_only_connection(database_path) as connection:
        row = connection.execute(
            f"SELECT COUNT(*) FROM {RESEARCH_EVIDENCE_TABLE}"
        ).fetchone()
    if row is None:
        raise RuntimeError("Unable to count research retrieval evidence.")
    return int(row[0])


def bootstrap_research_evidence_schema(
    database_path: Path,
) -> ResearchBenchmarkBootstrapResult:
    """Make the lazily-created evidence table explicit before the live benchmark.

    Production Research workspace reads intentionally tolerate an absent evidence
    table until the first retrieval. The live benchmark needs a zero baseline
    before that first retrieval, so this helper performs the same repository
    initialization that the first `internet.research.retrieve` call would perform.
    It verifies that canonical task truth is unchanged across that schema bootstrap.
    """

    database_path = database_path.expanduser().resolve()
    task_before = _required_table_count(database_path, TASK_LEDGER_TABLE)
    evidence_existed_before = _table_exists(database_path, RESEARCH_EVIDENCE_TABLE)
    evidence_before = _optional_evidence_count(database_path)

    if not evidence_existed_before:
        truth_repository = AgentTruthRepository(database_path=database_path)
        ResearchRetrievalRepository(truth_repository, initialize=True)

    evidence_exists_after = _table_exists(database_path, RESEARCH_EVIDENCE_TABLE)
    task_after = _required_table_count(database_path, TASK_LEDGER_TABLE)
    evidence_after = _optional_evidence_count(database_path)

    if not evidence_exists_after:
        raise RuntimeError("Research retrieval evidence schema bootstrap did not complete.")
    if task_after != task_before:
        raise RuntimeError("Research evidence schema bootstrap mutated the task ledger.")
    if evidence_after != evidence_before:
        raise RuntimeError("Research evidence schema bootstrap unexpectedly changed evidence rows.")

    return ResearchBenchmarkBootstrapResult(
        evidence_table_existed_before=evidence_existed_before,
        evidence_table_exists_after=evidence_exists_after,
        schema_bootstrap_performed=not evidence_existed_before,
        task_ledger_before=task_before,
        task_ledger_after=task_after,
        research_evidence_before=evidence_before,
        research_evidence_after=evidence_after,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap the lazy Phase 12 research evidence schema safely."
    )
    parser.add_argument("--truth-db", type=Path, required=True)
    arguments = parser.parse_args()

    result = bootstrap_research_evidence_schema(arguments.truth_db)
    print(
        "evidence_table_existed_before|"
        f"{str(result.evidence_table_existed_before).lower()}"
    )
    print(
        "schema_bootstrap_performed|"
        f"{str(result.schema_bootstrap_performed).lower()}"
    )
    print(
        "evidence_table_exists_after|"
        f"{str(result.evidence_table_exists_after).lower()}"
    )
    print(f"task_ledger_before|{result.task_ledger_before}")
    print(f"task_ledger_after|{result.task_ledger_after}")
    print(f"research_evidence_before|{result.research_evidence_before}")
    print(f"research_evidence_after|{result.research_evidence_after}")
    print(f"task_ledger_mutated|{str(result.task_ledger_mutated).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
