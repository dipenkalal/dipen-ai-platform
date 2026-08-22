from __future__ import annotations

import ast
import hashlib
import inspect
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from career.repository import CareerRepository


EXPECTED_PHASE16_DDL_SHA256 = (
    "421cd7dbbd259e3692cc7586e1ed1286"
    "e70e0945c845c62ec921088fb5aee436"
)

EXPECTED_CAREER_TABLES = {
    "career_application_events",
    "career_applications",
    "career_fit_assessments",
    "career_job_evidence_links",
    "career_job_postings",
    "career_job_snapshots",
    "career_sources",
}

EXPECTED_CAREER_INDEXES = {
    "idx_career_application_events",
    "idx_career_applications_job",
    "idx_career_applications_state",
    "idx_career_evidence_research",
    "idx_career_evidence_snapshot",
    "idx_career_fit_verdict",
    "idx_career_jobs_employer_req",
    "idx_career_jobs_state_seen",
    "idx_career_jobs_url",
    "idx_career_snapshots_freshness",
    "idx_career_snapshots_hash",
    "idx_career_snapshots_job",
    "idx_career_sources_employer",
    "idx_career_sources_state_tier",
}


class ExplicitTruthRepository:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = path
        self.connection_calls = 0

    @contextmanager
    def connection(
        self,
    ) -> Iterator[sqlite3.Connection]:

        self.connection_calls += 1

        connection = sqlite3.connect(
            self.path
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class BombTruthRepository:
    def __init__(self) -> None:
        self.connection_calls = 0

    @contextmanager
    def connection(self):
        self.connection_calls += 1

        raise AssertionError(
            "initialize=False must not touch "
            "the truth repository connection"
        )

        yield  # pragma: no cover


def _canonical_phase16_repository_path() -> Path:

    return (
        Path(__file__).parents[1]
        / "gateway"
        / "research_retrieval_repository.py"
    )


def _extract_create_table_statements(
    text: str,
) -> list[str]:

    pattern = re.compile(
        r"""
        CREATE\s+TABLE
        (?:\s+IF\s+NOT\s+EXISTS)?
        \s+
        ["'`\[]?
        research_retrieval_evidence
        ["'`\]]?
        \s*
        \(
        """,
        re.I | re.X,
    )

    output: list[str] = []
    position = 0

    while True:

        match = pattern.search(
            text,
            position,
        )

        if match is None:
            break

        opening = match.end() - 1

        depth = 0
        quote: str | None = None
        escape = False
        closing: int | None = None

        for index in range(
            opening,
            len(text),
        ):

            char = text[index]

            if quote is not None:

                if escape:
                    escape = False
                    continue

                if char == "\\":
                    escape = True
                    continue

                if char == quote:
                    quote = None

                continue

            if char in ("'", '"'):
                quote = char
                continue

            if char == "(":
                depth += 1
                continue

            if char == ")":
                depth -= 1

                if depth == 0:
                    closing = index
                    break

        if closing is None:
            raise AssertionError(
                "unbalanced canonical Phase16 DDL"
            )

        end = closing + 1

        while (
            end < len(text)
            and text[end].isspace()
        ):
            end += 1

        if (
            end < len(text)
            and text[end] == ";"
        ):
            end += 1

        output.append(
            text[
                match.start():
                end
            ].strip()
        )

        position = end

    return output


def _canonical_phase16_ddl() -> str:

    path = _canonical_phase16_repository_path()

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    definitions: dict[str, str] = {}

    for node in ast.walk(tree):

        if not (
            isinstance(
                node,
                ast.Constant,
            )
            and isinstance(
                node.value,
                str,
            )
        ):
            continue

        value = node.value

        if (
            "research_retrieval_evidence"
            not in value
            or "CREATE TABLE"
            not in value.upper()
        ):
            continue

        for statement in (
            _extract_create_table_statements(
                value
            )
        ):

            digest = hashlib.sha256(
                statement.encode(
                    "utf-8"
                )
            ).hexdigest()

            definitions[
                digest
            ] = statement

    assert len(definitions) == 1

    digest, ddl = next(
        iter(
            definitions.items()
        )
    )

    assert (
        digest
        == EXPECTED_PHASE16_DDL_SHA256
    )

    return ddl


def _seed_phase16_prerequisite(
    path: Path,
) -> None:

    ddl = _canonical_phase16_ddl()

    with sqlite3.connect(
        path
    ) as connection:

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            ddl
        )

        connection.commit()


def _career_tables(
    path: Path,
) -> set[str]:

    with sqlite3.connect(
        path
    ) as connection:

        return {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE
                    type = 'table'
                    AND name LIKE 'career_%'
                """
            )
        }


def _career_indexes(
    path: Path,
) -> set[str]:

    with sqlite3.connect(
        path
    ) as connection:

        return {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE
                    type = 'index'
                    AND name LIKE 'idx_career_%'
                """
            )
        }


def _schema_snapshot(
    path: Path,
) -> dict[tuple[str, str], str]:

    with sqlite3.connect(
        path
    ) as connection:

        rows = connection.execute(
            """
            SELECT
                type,
                name,
                COALESCE(sql, '')
            FROM sqlite_master
            WHERE
                name LIKE 'career_%'
                OR name LIKE 'idx_career_%'
            ORDER BY
                type,
                name
            """
        ).fetchall()

    return {
        (
            str(row[0]),
            str(row[1]),
        ):
            str(row[2])
        for row in rows
    }


def test_constructor_contract_preserves_initialize_true_default() -> None:

    signature = inspect.signature(
        CareerRepository
    )

    parameter = signature.parameters[
        "initialize"
    ]

    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )

    assert parameter.default is True


def test_initialize_false_touches_no_connection() -> None:

    truth = BombTruthRepository()

    repository = CareerRepository(
        truth,
        initialize=False,
    )

    assert repository is not None
    assert truth.connection_calls == 0


def test_empty_database_default_constructor_fails_closed(
    tmp_path: Path,
) -> None:

    path = (
        tmp_path
        / "empty-default.db"
    )

    truth = ExplicitTruthRepository(
        path
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Career persistence requires the Phase-16 "
            "research_retrieval_evidence table"
        ),
    ):
        CareerRepository(
            truth
        )

    assert _career_tables(
        path
    ) == set()


def test_canonical_phase16_prerequisite_is_bound_to_non_test_source() -> None:

    path = _canonical_phase16_repository_path()

    assert (
        path.name
        == "research_retrieval_repository.py"
    )

    assert "tests" not in path.parts

    ddl = _canonical_phase16_ddl()

    assert (
        hashlib.sha256(
            ddl.encode(
                "utf-8"
            )
        ).hexdigest()
        == EXPECTED_PHASE16_DDL_SHA256
    )


def test_explicit_initialize_creates_exact_career_schema(
    tmp_path: Path,
) -> None:

    path = (
        tmp_path
        / "explicit-initialize.db"
    )

    truth = ExplicitTruthRepository(
        path
    )

    repository = CareerRepository(
        truth,
        initialize=False,
    )

    assert truth.connection_calls == 0

    _seed_phase16_prerequisite(
        path
    )

    repository.initialize()

    assert (
        _career_tables(
            path
        )
        == EXPECTED_CAREER_TABLES
    )

    assert (
        _career_indexes(
            path
        )
        == EXPECTED_CAREER_INDEXES
    )


def test_default_initialize_succeeds_after_phase16_prerequisite(
    tmp_path: Path,
) -> None:

    path = (
        tmp_path
        / "default-initialize.db"
    )

    _seed_phase16_prerequisite(
        path
    )

    truth = ExplicitTruthRepository(
        path
    )

    repository = CareerRepository(
        truth
    )

    assert repository is not None

    assert (
        _career_tables(
            path
        )
        == EXPECTED_CAREER_TABLES
    )

    assert (
        _career_indexes(
            path
        )
        == EXPECTED_CAREER_INDEXES
    )


def test_repeated_initialize_is_schema_idempotent(
    tmp_path: Path,
) -> None:

    path = (
        tmp_path
        / "initialize-idempotent.db"
    )

    _seed_phase16_prerequisite(
        path
    )

    truth = ExplicitTruthRepository(
        path
    )

    repository = CareerRepository(
        truth,
        initialize=False,
    )

    repository.initialize()

    before = _schema_snapshot(
        path
    )

    repository.initialize()

    after = _schema_snapshot(
        path
    )

    assert before == after


def test_each_career_table_has_primary_key(
    tmp_path: Path,
) -> None:

    path = (
        tmp_path
        / "primary-keys.db"
    )

    _seed_phase16_prerequisite(
        path
    )

    truth = ExplicitTruthRepository(
        path
    )

    CareerRepository(
        truth
    )

    with sqlite3.connect(
        path
    ) as connection:

        for table in sorted(
            EXPECTED_CAREER_TABLES
        ):

            columns = connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()

            assert any(
                int(column[5]) > 0
                for column in columns
            ), table


def test_frozen_schema_contains_foreign_key_relationships(
    tmp_path: Path,
) -> None:

    path = (
        tmp_path
        / "foreign-keys.db"
    )

    _seed_phase16_prerequisite(
        path
    )

    truth = ExplicitTruthRepository(
        path
    )

    CareerRepository(
        truth
    )

    with sqlite3.connect(
        path
    ) as connection:

        foreign_key_counts = {
            table:
                len(
                    connection.execute(
                        f"PRAGMA foreign_key_list({table})"
                    ).fetchall()
                )
            for table in (
                EXPECTED_CAREER_TABLES
            )
        }

    assert (
        sum(
            foreign_key_counts.values()
        )
        > 0
    )

    assert (
        foreign_key_counts[
            "career_job_evidence_links"
        ]
        > 0
    )

    assert (
        foreign_key_counts[
            "career_job_snapshots"
        ]
        > 0
    )


def test_fit_assessment_has_unique_identity_constraint(
    tmp_path: Path,
) -> None:

    path = (
        tmp_path
        / "unique-fit.db"
    )

    _seed_phase16_prerequisite(
        path
    )

    truth = ExplicitTruthRepository(
        path
    )

    CareerRepository(
        truth
    )

    with sqlite3.connect(
        path
    ) as connection:

        indexes = connection.execute(
            """
            PRAGMA index_list(
                career_fit_assessments
            )
            """
        ).fetchall()

    assert any(
        int(row[2]) == 1
        for row in indexes
    )


def test_repository_source_has_no_network_client_imports() -> None:

    path = (
        Path(__file__).parents[1]
        / "career"
        / "repository.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        ),
        filename=str(path),
    )

    forbidden = {
        "aiohttp",
        "httpx",
        "requests",
        "socket",
        "urllib",
        "paramiko",
    }

    imports: set[str] = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            imports.update(
                alias.name.split(
                    ".",
                    1,
                )[0]
                for alias in node.names
            )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imports.add(
                node.module.split(
                    ".",
                    1,
                )[0]
            )

    assert (
        imports
        & forbidden
    ) == set()


def test_repository_has_no_production_truth_db_literal() -> None:

    path = (
        Path(__file__).parents[1]
        / "career"
        / "repository.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    assert (
        "/home/dipen/dap/data/"
        "agent-history/agent-truth.db"
        not in source
    )


def test_repository_exposes_no_application_submission_method() -> None:

    forbidden = {
        "apply",
        "auto_apply",
        "send_application",
        "submit",
        "submit_application",
    }

    methods = {
        name
        for name, value
        in inspect.getmembers(
            CareerRepository
        )
        if inspect.isfunction(
            value
        )
    }

    assert (
        methods
        & forbidden
    ) == set()
