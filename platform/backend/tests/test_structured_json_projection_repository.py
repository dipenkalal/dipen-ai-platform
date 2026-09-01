from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest

from gateway.structured_json_projection import (
    LEVER_LIST_PROFILE_ID,
    StructuredJSONProjectionEvidence,
    project_structured_json,
)
from gateway.structured_json_projection_repository import (
    MAX_RECENT_PROJECTION_RECORDS,
    PROJECTION_EVIDENCE_TABLE,
    StructuredJSONProjectionParentBindingError,
    StructuredJSONProjectionPersistenceConflict,
    StructuredJSONProjectionRepository,
)

OBSERVED_AT = datetime(
    2026,
    8,
    24,
    12,
    0,
    tzinfo=timezone.utc,
)

SOURCE_URL = "https://api.lever.co/v0/postings/example?mode=json"

RESEARCH_EVIDENCE_ID = "research-retrieval-0123456789abcdef01234567"


class _TruthRepository:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = path

    @contextmanager
    def connection(
        self,
    ) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)

        connection.row_factory = sqlite3.Row

        try:
            yield connection

        finally:
            connection.close()


def _table_exists(
    truth: _TruthRepository,
    table: str,
) -> bool:
    with truth.connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table,),
        ).fetchone()

    assert row is not None

    return int(row[0]) == 1


def _create_research_parent_table(
    truth: _TruthRepository,
) -> None:
    with truth.connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            research_retrieval_evidence (
                evidence_id TEXT PRIMARY KEY,
                evidence_json TEXT NOT NULL
            )
            """
        )

        connection.commit()


def _body(
    label: str = "one",
) -> bytes:
    return json.dumps(
        [
            {
                "id": f"job-{label}",
                "text": (f"Cloud Engineer {label}"),
                "hostedUrl": (f"https://jobs.lever.co/example/job-{label}"),
                "applyUrl": (f"https://jobs.lever.co/example/job-{label}/apply"),
                "categories": {
                    "location": "Canada Remote",
                },
                "descriptionPlain": "not projected",
            }
        ],
        separators=(",", ":"),
    ).encode("utf-8")


def _projection(
    *,
    label: str = "one",
    research_evidence_id: str = (RESEARCH_EVIDENCE_ID),
    observed_at: datetime = (OBSERVED_AT),
) -> StructuredJSONProjectionEvidence:
    body = _body(label)

    return project_structured_json(
        profile_id=(LEVER_LIST_PROFILE_ID),
        body=body,
        research_evidence_id=(research_evidence_id),
        source_url=SOURCE_URL,
        source_body_sha256=(hashlib.sha256(body).hexdigest()),
        source_byte_count=len(body),
        source_content_type=("application/json"),
        observed_at=observed_at,
    )


def _parent_payload(
    evidence: StructuredJSONProjectionEvidence,
    *,
    source_body_sha256: str | None = None,
    byte_count: int | None = None,
    content_type: str | None = None,
    final_url: str | None = None,
    observed_at: datetime | None = None,
    outcome: str = "succeeded",
    stage: str = "completed",
) -> dict[str, object]:
    return {
        "evidence_id": evidence.research_evidence_id,
        "request_id": "research-request-0123456789abcdef01234567",
        "outcome": outcome,
        "stage": stage,
        "provider_id": "dap-public-http",
        "requested_url": SOURCE_URL,
        "final_url": (SOURCE_URL if final_url is None else final_url),
        "method": "GET",
        "status_code": 200,
        "content_type": (
            evidence.source_content_type if content_type is None else content_type
        ),
        "byte_count": (
            evidence.source_byte_count if byte_count is None else byte_count
        ),
        "source_body_sha256": (
            evidence.source_body_sha256
            if source_body_sha256 is None
            else source_body_sha256
        ),
        "observed_at": (
            evidence.observed_at if observed_at is None else observed_at
        ).isoformat(),
    }


def _seed_parent(
    truth: _TruthRepository,
    evidence: StructuredJSONProjectionEvidence,
    **overrides,
) -> None:
    _create_research_parent_table(truth)

    payload = _parent_payload(
        evidence,
        **overrides,
    )

    with truth.connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO
            research_retrieval_evidence (
                evidence_id,
                evidence_json
            )
            VALUES (?, ?)
            """,
            (
                evidence.research_evidence_id,
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
            ),
        )

        connection.commit()


def _canonical_evidence_json(
    evidence: StructuredJSONProjectionEvidence,
) -> str:
    return json.dumps(
        evidence.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _count(
    truth: _TruthRepository,
    table: str,
) -> int:
    with truth.connection() as connection:
        row = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()

    assert row is not None

    return int(row[0])


def test_initialize_false_creates_no_projection_table(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    StructuredJSONProjectionRepository(
        truth,
        initialize=False,
    )

    assert (
        _table_exists(
            truth,
            PROJECTION_EVIDENCE_TABLE,
        )
        is False
    )


def test_initialize_creates_dedicated_projection_table_and_indexes(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    StructuredJSONProjectionRepository(truth)

    assert _table_exists(
        truth,
        PROJECTION_EVIDENCE_TABLE,
    )

    with truth.connection() as connection:
        columns = {
            str(row["name"])
            for row in connection.execute(
                """
                PRAGMA table_info(
                    "structured_json_projection_evidence"
                )
                """
            ).fetchall()
        }

        indexes = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                  AND tbl_name =
                      'structured_json_projection_evidence'
                """
            ).fetchall()
        }

    assert {
        "projection_evidence_id",
        "evidence_sha256",
        "research_evidence_id",
        "projector_id",
        "projection_profile_id",
        "projection_profile_version",
        "source_url",
        "source_body_sha256",
        "source_byte_count",
        "source_content_type",
        "complete_document_parse",
        "source_root_kind",
        "source_record_count",
        "projected_record_count",
        "projection_sha256",
        "projection_char_count",
        "projection_truncated",
        "evidence_json",
        "stored_at",
    } == columns

    assert {
        "idx_structured_json_projection_research",
        "idx_structured_json_projection_profile",
        "idx_structured_json_projection_source_body",
    }.issubset(indexes)


def test_persist_and_get_round_trip_full_immutable_evidence(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
    )

    repository = StructuredJSONProjectionRepository(truth)

    persisted = repository.persist(evidence)

    restored = repository.get(evidence.projection_evidence_id)

    assert restored is not None

    assert persisted.evidence == evidence

    assert restored.evidence == evidence

    assert restored.evidence_sha256 == persisted.evidence_sha256

    assert restored.evidence_persisted is True

    assert restored.task_ledger_mutated is False

    assert restored.knowledge_mutated is False

    assert restored.career_truth_mutated is False


def test_repository_uses_full_canonical_evidence_hash_not_projection_hash(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
    )

    repository = StructuredJSONProjectionRepository(truth)

    persisted = repository.persist(evidence)

    canonical = _canonical_evidence_json(evidence)

    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    assert persisted.evidence_sha256 == expected_hash

    assert persisted.evidence_sha256 != evidence.projection_sha256

    with truth.connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM structured_json_projection_evidence
            WHERE projection_evidence_id = ?
            """,
            (evidence.projection_evidence_id,),
        ).fetchone()

    assert row is not None

    assert str(row["evidence_json"]) == canonical

    restored = StructuredJSONProjectionEvidence.model_validate_json(
        str(row["evidence_json"])
    )

    assert restored == evidence


def test_projected_columns_match_full_evidence(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
    )

    repository = StructuredJSONProjectionRepository(truth)

    repository.persist(evidence)

    with truth.connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM structured_json_projection_evidence
            WHERE projection_evidence_id = ?
            """,
            (evidence.projection_evidence_id,),
        ).fetchone()

    assert row is not None

    assert row["projection_evidence_id"] == evidence.projection_evidence_id

    assert row["research_evidence_id"] == evidence.research_evidence_id

    assert row["projector_id"] == evidence.projector_id

    assert row["projection_profile_id"] == evidence.projection_profile_id

    assert row["source_body_sha256"] == evidence.source_body_sha256

    assert int(row["source_byte_count"]) == evidence.source_byte_count

    assert int(row["source_record_count"]) == evidence.source_record_count

    assert int(row["projected_record_count"]) == evidence.projected_record_count

    assert row["projection_sha256"] == evidence.projection_sha256

    assert int(row["projection_truncated"]) == 0


def test_idempotent_replay_returns_original_stored_record(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
    )

    repository = StructuredJSONProjectionRepository(truth)

    first = repository.persist(evidence)

    second = repository.persist(evidence)

    assert first.evidence_sha256 == second.evidence_sha256

    assert first.stored_at == second.stored_at

    assert (
        _count(
            truth,
            PROJECTION_EVIDENCE_TABLE,
        )
        == 1
    )


def test_conflicting_reuse_of_projection_evidence_id_fails_closed(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
    )

    repository = StructuredJSONProjectionRepository(truth)

    repository.persist(evidence)

    conflicting = evidence.model_copy(
        update={
            "source_root_kind": "object",
        }
    )

    with pytest.raises(
        StructuredJSONProjectionPersistenceConflict,
    ):
        repository.persist(conflicting)

    assert (
        _count(
            truth,
            PROJECTION_EVIDENCE_TABLE,
        )
        == 1
    )


def test_missing_parent_research_evidence_fails_closed(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    _create_research_parent_table(truth)

    evidence = _projection()

    repository = StructuredJSONProjectionRepository(truth)

    with pytest.raises(
        StructuredJSONProjectionParentBindingError,
        match="existing Phase16 Research",
    ):
        repository.persist(evidence)

    assert (
        _count(
            truth,
            PROJECTION_EVIDENCE_TABLE,
        )
        == 0
    )


@pytest.mark.parametrize(
    (
        "override",
        "expected_message",
    ),
    [
        (
            {
                "source_body_sha256": "0" * 64,
            },
            "body SHA-256",
        ),
        (
            {
                "byte_count": 999,
            },
            "byte count",
        ),
        (
            {
                "content_type": "text/html",
            },
            "content type",
        ),
        (
            {
                "final_url": "https://example.test/wrong",
            },
            "source URL",
        ),
        (
            {
                "observed_at": OBSERVED_AT + timedelta(seconds=1),
            },
            "observed_at",
        ),
        (
            {
                "outcome": "failed",
            },
            "must have succeeded",
        ),
        (
            {
                "stage": "transport",
            },
            "must be completed",
        ),
    ],
)
def test_parent_binding_mismatches_fail_closed(
    tmp_path: Path,
    override: dict[str, object],
    expected_message: str,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
        **override,
    )

    repository = StructuredJSONProjectionRepository(truth)

    with pytest.raises(
        StructuredJSONProjectionParentBindingError,
        match=expected_message,
    ):
        repository.persist(evidence)

    assert (
        _count(
            truth,
            PROJECTION_EVIDENCE_TABLE,
        )
        == 0
    )


def test_list_for_research_evidence_and_profile_are_bound(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
    )

    repository = StructuredJSONProjectionRepository(truth)

    repository.persist(evidence)

    by_research = repository.list_for_research_evidence(evidence.research_evidence_id)

    by_profile = repository.list_for_profile(evidence.projection_profile_id)

    assert [record.evidence.projection_evidence_id for record in by_research] == [
        evidence.projection_evidence_id
    ]

    assert [record.evidence.projection_evidence_id for record in by_profile] == [
        evidence.projection_evidence_id
    ]

    assert (
        repository.list_for_research_evidence("research-retrieval-missing000000000000")
        == []
    )

    assert repository.list_for_profile("missing-profile") == []


def test_list_recent_is_bounded(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    first = _projection(
        label="one",
        research_evidence_id=("research-retrieval-111111111111111111111111"),
    )

    second = _projection(
        label="two",
        research_evidence_id=("research-retrieval-222222222222222222222222"),
        observed_at=(OBSERVED_AT + timedelta(seconds=1)),
    )

    _seed_parent(
        truth,
        first,
    )

    _seed_parent(
        truth,
        second,
    )

    repository = StructuredJSONProjectionRepository(truth)

    repository.persist(first)
    repository.persist(second)

    recent = repository.list_recent(limit=1)

    assert len(recent) == 1

    with pytest.raises(
        ValueError,
    ):
        repository.list_recent(limit=0)

    with pytest.raises(
        ValueError,
    ):
        repository.list_recent(limit=(MAX_RECENT_PROJECTION_RECORDS + 1))


def test_corrupted_persisted_evidence_json_hash_fails_closed(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
    )

    repository = StructuredJSONProjectionRepository(truth)

    repository.persist(evidence)

    with truth.connection() as connection:
        connection.execute(
            """
            UPDATE structured_json_projection_evidence
            SET evidence_json = ?
            WHERE projection_evidence_id = ?
            """,
            (
                "{}",
                evidence.projection_evidence_id,
            ),
        )

        connection.commit()

    with pytest.raises(
        StructuredJSONProjectionPersistenceConflict,
        match="hash",
    ):
        repository.get(evidence.projection_evidence_id)


def test_projection_repository_does_not_mutate_parent_research_rows(
    tmp_path: Path,
) -> None:
    truth = _TruthRepository(tmp_path / "truth.db")

    evidence = _projection()

    _seed_parent(
        truth,
        evidence,
    )

    research_before = _count(
        truth,
        "research_retrieval_evidence",
    )

    repository = StructuredJSONProjectionRepository(truth)

    repository.persist(evidence)

    research_after = _count(
        truth,
        "research_retrieval_evidence",
    )

    assert research_before == 1
    assert research_after == 1

    assert (
        _count(
            truth,
            PROJECTION_EVIDENCE_TABLE,
        )
        == 1
    )

    assert (
        _table_exists(
            truth,
            "task_ledger",
        )
        is False
    )

    assert (
        _table_exists(
            truth,
            "career_sources",
        )
        is False
    )


def test_projection_repository_has_no_network_client_or_authority() -> None:
    path = (
        Path(__file__).parents[1]
        / "gateway"
        / "structured_json_projection_repository.py"
    )

    text = path.read_text(encoding="utf-8")

    assert "requests" not in text
    assert "httpx" not in text
    assert "aiohttp" not in text
    assert "urllib.request" not in text
    assert "socket." not in text
    assert "sqlite3.connect(" not in text

    assert "career_truth_mutated" in text

    assert "StructuredJSONProjectionEvidence" in text

    assert "UntrustedInternetEvidence" not in text
