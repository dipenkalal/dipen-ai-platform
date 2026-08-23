from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from typing import Iterator

import pytest

from career.connectors.contracts import (
    CareerDiscoveryCandidate,
)
from career.ingestion import (
    CareerVerifiedIngestionError,
    CareerVerifiedIngestionService,
    CareerVerifiedJobDetail,
)
from career.repository import CareerRepository


PHASE16_DDL_SHA256 = (
    "421cd7dbbd259e3692cc7586e1ed1286"
    "e70e0945c845c62ec921088fb5aee436"
)


class TruthRepository:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = path

    @contextmanager
    def connection(
        self,
    ) -> Iterator[
        sqlite3.Connection
    ]:

        connection = sqlite3.connect(
            self.path
        )

        connection.row_factory = (
            sqlite3.Row
        )

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


class FailingEvidenceRepository(
    CareerRepository
):

    def persist_evidence_link(
        self,
        link,
    ):
        raise RuntimeError(
            "synthetic evidence-link failure"
        )


def _utc(
    hour: int = 12,
) -> datetime:

    return datetime(
        2026,
        8,
        22,
        hour,
        0,
        tzinfo=timezone.utc,
    )


def _sha(
    value: str,
) -> str:

    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def _content_id(
    prefix: str,
    seed: str,
) -> str:

    return (
        prefix
        + "-"
        + _sha(
            seed
        )[:24]
    )


def _phase16_repository_path() -> Path:

    return (
        Path(__file__).parents[1]
        / "gateway"
        / "research_retrieval_repository.py"
    )


def _extract_phase16_ddl() -> str:

    path = (
        _phase16_repository_path()
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    candidates: list[str] = []

    for node in ast.walk(
        tree
    ):

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

        marker = (
            "CREATE TABLE IF NOT EXISTS "
            "research_retrieval_evidence"
        )

        if marker not in value:
            continue

        start = value.index(
            marker
        )

        opening = value.index(
            "(",
            start,
        )

        depth = 0
        quote: str | None = None
        closing: int | None = None

        for index in range(
            opening,
            len(value),
        ):

            char = value[index]

            if quote is not None:

                if char == quote:
                    quote = None

                continue

            if char in (
                "'",
                '"',
            ):
                quote = char
                continue

            if char == "(":
                depth += 1

            elif char == ")":

                depth -= 1

                if depth == 0:
                    closing = index
                    break

        assert closing is not None

        candidates.append(
            value[
                start:
                closing + 1
            ].strip()
        )

    assert len(
        set(
            candidates
        )
    ) == 1

    ddl = candidates[0]

    assert (
        _sha(
            ddl
        )
        == PHASE16_DDL_SHA256
    )

    return ddl


def _prepare_database(
    path: Path,
) -> CareerRepository:

    with sqlite3.connect(
        path
    ) as connection:

        connection.execute(
            _extract_phase16_ddl()
        )

        connection.commit()

    truth = TruthRepository(
        path
    )

    return CareerRepository(
        truth
    )


def _insert_evidence(
    path: Path,
    *,
    seed: str,
    final_url: str,
    normalized_hash: str,
    outcome: str = "succeeded",
) -> str:

    evidence_id = _content_id(
        "research-retrieval",
        seed,
    )

    evidence_json = json.dumps(
        {
            "normalized_text_sha256":
                normalized_hash,

            "final_url":
                final_url,
        },
        sort_keys=True,
    )

    with sqlite3.connect(
        path
    ) as connection:

        connection.execute(
            """
            INSERT INTO
            research_retrieval_evidence (
                evidence_id,
                evidence_sha256,
                request_id,
                canonical_task_id,
                outcome,
                stage,
                provider_id,
                requested_url,
                final_url,
                citation_id,
                content_evidence_id,
                evidence_json,
                stored_at
            )
            VALUES (
                ?, ?, ?, NULL, ?, ?, ?, ?, ?,
                NULL, NULL, ?, ?
            )
            """,
            (
                evidence_id,
                _sha(
                    "evidence:"
                    + seed
                ),
                (
                    "request-"
                    + _sha(
                        "request:"
                        + seed
                    )[:16]
                ),
                outcome,
                (
                    "completed"
                    if outcome
                    == "succeeded"
                    else "failed"
                ),
                "test-provider",
                final_url,
                (
                    final_url
                    if outcome
                    == "succeeded"
                    else None
                ),
                evidence_json,
                _utc().isoformat(),
            ),
        )

        connection.commit()

    return evidence_id


def _candidate(
    *,
    provider: str = "greenhouse",
    connector_kind: str | None = None,
    observed_at: datetime | None = None,
) -> CareerDiscoveryCandidate:

    connector_kind = (
        connector_kind
        or provider
    )

    return CareerDiscoveryCandidate.build(
        connector_id=(
            "career-connector-"
            + (
                "generic-employer-v1"
                if connector_kind
                == "generic_employer"
                else provider
                + "-v1"
            )
        ),
        connector_kind=connector_kind,
        employer_name="Example Corp",
        source_job_id="REQ-123",
        title_hint="Cloud Engineer",
        detail_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        discovery_research_evidence_id=(
            _content_id(
                "research-retrieval",
                "discovery-"
                + provider,
            )
        ),
        discovery_content_evidence_id=(
            _content_id(
                "internet-content",
                "discovery-content-"
                + provider,
            )
        ),
        discovery_normalized_text_sha256=(
            _sha(
                "discovery-normalized-"
                + provider
            )
        ),
        observed_at=(
            observed_at
            or _utc()
        ),
    )


def _detail(
    evidence_id: str,
    *,
    text: str = (
        "Verified Cloud Engineer "
        "job detail"
    ),
    observed_at: datetime | None = None,
) -> CareerVerifiedJobDetail:

    normalized_hash = _sha(
        text
    )

    return CareerVerifiedJobDetail(
        research_evidence_id=(
            evidence_id
        ),
        canonical_job_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        canonical_apply_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123/apply"
        ),
        title="Cloud Engineer",
        employer_name="Example Corp",
        description_text=text,
        normalized_text_sha256=(
            normalized_hash
        ),
        observed_at=(
            observed_at
            or _utc()
        ),
        location_text=(
            "Ontario, Canada"
        ),
        work_mode="HYBRID",
        employment_type="Full-time",
        posted_at=None,
        closing_at=None,
        salary_text=None,
        requirements={
            "experience":
                "0-3 years",
        },
    )


def _row_count(
    path: Path,
    table: str,
) -> int:

    with sqlite3.connect(
        path
    ) as connection:

        row = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()

    assert row is not None

    return int(
        row[0]
    )


def test_candidate_only_cannot_claim_verified_state(
    tmp_path: Path,
) -> None:

    path = tmp_path / "candidate-only.db"

    repository = _prepare_database(
        path
    )

    service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    with pytest.raises(
        CareerVerifiedIngestionError,
        match="Candidate-only",
    ):
        service.ingest_verified_candidate(
            candidate=_candidate(),
            detail=None,
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )

    assert (
        _row_count(
            path,
            "career_job_postings",
        )
        == 0
    )


def test_missing_verification_evidence_fails_closed(
    tmp_path: Path,
) -> None:

    path = tmp_path / "missing-evidence.db"

    repository = _prepare_database(
        path
    )

    service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    detail = _detail(
        _content_id(
            "research-retrieval",
            "missing",
        )
    )

    with pytest.raises(
        CareerVerifiedIngestionError,
        match="requires existing",
    ):
        service.ingest_verified_candidate(
            candidate=_candidate(),
            detail=detail,
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )

    assert (
        _row_count(
            path,
            "career_job_postings",
        )
        == 0
    )


def test_evidence_hash_mismatch_fails_closed(
    tmp_path: Path,
) -> None:

    path = tmp_path / "hash-mismatch.db"

    repository = _prepare_database(
        path
    )

    evidence_id = _insert_evidence(
        path,
        seed="hash-mismatch",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            "different content"
        ),
    )

    service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    with pytest.raises(
        CareerVerifiedIngestionError,
        match="normalized-content hash",
    ):
        service.ingest_verified_candidate(
            candidate=_candidate(),
            detail=_detail(
                evidence_id
            ),
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )


def test_evidence_final_url_mismatch_fails_closed(
    tmp_path: Path,
) -> None:

    path = tmp_path / "url-mismatch.db"

    repository = _prepare_database(
        path
    )

    text = (
        "Verified Cloud Engineer "
        "job detail"
    )

    evidence_id = _insert_evidence(
        path,
        seed="url-mismatch",
        final_url=(
            "https://jobs.example.com/"
            "jobs/OTHER"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    with pytest.raises(
        CareerVerifiedIngestionError,
        match="final URL",
    ):
        service.ingest_verified_candidate(
            candidate=_candidate(),
            detail=_detail(
                evidence_id,
                text=text,
            ),
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )


@pytest.mark.parametrize(
    "provider",
    (
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
    ),
)
def test_provider_specific_candidates_use_common_verified_ingestion(
    tmp_path: Path,
    provider: str,
) -> None:

    path = (
        tmp_path
        / f"{provider}.db"
    )

    repository = _prepare_database(
        path
    )

    text = (
        "Verified Cloud Engineer "
        "job detail"
    )

    evidence_id = _insert_evidence(
        path,
        seed=provider,
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    result = (
        CareerVerifiedIngestionService(
            repository
        )
        .ingest_verified_candidate(
            candidate=_candidate(
                provider=provider
            ),
            detail=_detail(
                evidence_id,
                text=text,
            ),
            provider_kind=provider,
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )
    )

    assert (
        result.verification_state
        == "VERIFIED"
    )

    assert (
        result.freshness_state
        == "UNKNOWN"
    )

    stored = repository.get_job(
        result.job_id
    )

    assert stored is not None

    assert (
        stored.verification_state
        == "VERIFIED"
    )


def test_workday_generic_fallback_uses_same_verification_standard(
    tmp_path: Path,
) -> None:

    path = tmp_path / "workday.db"

    repository = _prepare_database(
        path
    )

    text = (
        "Verified Cloud Engineer "
        "job detail"
    )

    evidence_id = _insert_evidence(
        path,
        seed="workday",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    result = (
        CareerVerifiedIngestionService(
            repository
        )
        .ingest_verified_candidate(
            candidate=_candidate(
                provider="workday",
                connector_kind=(
                    "generic_employer"
                ),
            ),
            detail=_detail(
                evidence_id,
                text=text,
            ),
            provider_kind="workday",
            route_kind=(
                "GENERIC_PHASE16_FALLBACK"
            ),
        )
    )

    assert (
        result.verification_state
        == "VERIFIED"
    )

    assert (
        result.freshness_state
        == "UNKNOWN"
    )


def test_wrong_provider_route_fails_closed(
    tmp_path: Path,
) -> None:

    path = tmp_path / "route.db"

    repository = _prepare_database(
        path
    )

    text = (
        "Verified Cloud Engineer "
        "job detail"
    )

    evidence_id = _insert_evidence(
        path,
        seed="route",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    with pytest.raises(
        CareerVerifiedIngestionError,
        match="provider-specific route",
    ):
        CareerVerifiedIngestionService(
            repository
        ).ingest_verified_candidate(
            candidate=_candidate(),
            detail=_detail(
                evidence_id,
                text=text,
            ),
            provider_kind="greenhouse",
            route_kind=(
                "GENERIC_PHASE16_FALLBACK"
            ),
        )

    assert (
        _row_count(
            path,
            "career_job_postings",
        )
        == 0
    )


def test_unknown_provider_fails_closed(
    tmp_path: Path,
) -> None:

    path = tmp_path / "unknown.db"

    repository = _prepare_database(
        path
    )

    text = (
        "Verified Cloud Engineer "
        "job detail"
    )

    evidence_id = _insert_evidence(
        path,
        seed="unknown",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    with pytest.raises(
        CareerVerifiedIngestionError,
        match="Unknown Career provider",
    ):
        CareerVerifiedIngestionService(
            repository
        ).ingest_verified_candidate(
            candidate=_candidate(),
            detail=_detail(
                evidence_id,
                text=text,
            ),
            provider_kind="unknown",
            route_kind=(
                "GENERIC_PHASE16_FALLBACK"
            ),
        )


def test_repeated_identical_ingestion_is_idempotent(
    tmp_path: Path,
) -> None:

    path = tmp_path / "idempotent.db"

    repository = _prepare_database(
        path
    )

    text = (
        "Verified Cloud Engineer "
        "job detail"
    )

    evidence_id = _insert_evidence(
        path,
        seed="idempotent",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    kwargs = {
        "candidate":
            _candidate(),

        "detail":
            _detail(
                evidence_id,
                text=text,
            ),

        "provider_kind":
            "greenhouse",

        "route_kind":
            "PROVIDER_SPECIFIC_CONNECTOR",
    }

    first = (
        service
        .ingest_verified_candidate(
            **kwargs
        )
    )

    second = (
        service
        .ingest_verified_candidate(
            **kwargs
        )
    )

    assert first == second

    assert (
        _row_count(
            path,
            "career_sources",
        )
        == 1
    )

    assert (
        _row_count(
            path,
            "career_job_postings",
        )
        == 1
    )

    assert (
        _row_count(
            path,
            "career_job_snapshots",
        )
        == 1
    )

    assert (
        _row_count(
            path,
            "career_job_evidence_links",
        )
        == 1
    )


def test_same_content_new_evidence_reuses_snapshot(
    tmp_path: Path,
) -> None:

    path = tmp_path / "same-content.db"

    repository = _prepare_database(
        path
    )

    text = (
        "Verified Cloud Engineer "
        "job detail"
    )

    first_time = _utc()

    second_time = (
        first_time
        + timedelta(
            hours=2
        )
    )

    first_evidence = _insert_evidence(
        path,
        seed="same-content-1",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    second_evidence = _insert_evidence(
        path,
        seed="same-content-2",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    first = (
        service
        .ingest_verified_candidate(
            candidate=_candidate(
                observed_at=first_time
            ),
            detail=_detail(
                first_evidence,
                text=text,
                observed_at=first_time,
            ),
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )
    )

    second = (
        service
        .ingest_verified_candidate(
            candidate=_candidate(
                observed_at=second_time
            ),
            detail=_detail(
                second_evidence,
                text=text,
                observed_at=second_time,
            ),
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )
    )

    assert (
        first.snapshot_id
        == second.snapshot_id
    )

    assert (
        _row_count(
            path,
            "career_job_snapshots",
        )
        == 1
    )

    assert (
        _row_count(
            path,
            "career_job_evidence_links",
        )
        == 2
    )


def test_changed_content_preserves_snapshot_history(
    tmp_path: Path,
) -> None:

    path = tmp_path / "changed-content.db"

    repository = _prepare_database(
        path
    )

    first_text = (
        "Verified Cloud Engineer "
        "job detail v1"
    )

    second_text = (
        "Verified Cloud Engineer "
        "job detail v2"
    )

    first_evidence = _insert_evidence(
        path,
        seed="changed-1",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            first_text
        ),
    )

    second_evidence = _insert_evidence(
        path,
        seed="changed-2",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            second_text
        ),
    )

    service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    first = (
        service
        .ingest_verified_candidate(
            candidate=_candidate(),
            detail=_detail(
                first_evidence,
                text=first_text,
            ),
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )
    )

    second_time = (
        _utc()
        + timedelta(
            hours=1
        )
    )

    second = (
        service
        .ingest_verified_candidate(
            candidate=_candidate(
                observed_at=second_time
            ),
            detail=_detail(
                second_evidence,
                text=second_text,
                observed_at=second_time,
            ),
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )
    )

    assert (
        first.snapshot_id
        != second.snapshot_id
    )

    assert (
        _row_count(
            path,
            "career_job_snapshots",
        )
        == 2
    )

    stored = repository.get_job(
        second.job_id
    )

    assert stored is not None

    assert (
        stored.current_snapshot_id
        == second.snapshot_id
    )


def test_failed_evidence_reconciliation_leaves_no_new_verified_state(
    tmp_path: Path,
) -> None:

    path = tmp_path / "failure.db"

    base = _prepare_database(
        path
    )

    text = (
        "Verified Cloud Engineer "
        "job detail"
    )

    evidence_id = _insert_evidence(
        path,
        seed="failure",
        final_url=(
            "https://jobs.example.com/"
            "jobs/REQ-123"
        ),
        normalized_hash=_sha(
            text
        ),
    )

    repository = (
        FailingEvidenceRepository(
            base.truth_repository,
            initialize=False,
        )
    )

    service = (
        CareerVerifiedIngestionService(
            repository
        )
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic evidence-link failure",
    ):
        service.ingest_verified_candidate(
            candidate=_candidate(),
            detail=_detail(
                evidence_id,
                text=text,
            ),
            provider_kind="greenhouse",
            route_kind=(
                "PROVIDER_SPECIFIC_CONNECTOR"
            ),
        )

    with sqlite3.connect(
        path
    ) as connection:

        row = connection.execute(
            """
            SELECT
                verification_state,
                current_snapshot_id
            FROM career_job_postings
            """
        ).fetchone()

    assert row is not None

    assert (
        row[0]
        != "VERIFIED"
    )

    assert row[1] is None


def test_ingestion_layer_has_no_network_or_application_authority() -> None:

    path = (
        Path(__file__).parents[1]
        / "career"
        / "ingestion.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    forbidden_module_prefixes = {
        "aiohttp",
        "http.client",
        "httpx",
        "paramiko",
        "playwright",
        "requests",
        "selenium",
        "socket",
        "urllib.error",
        "urllib.request",
        "urllib.robotparser",
    }

    import_targets: set[str] = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            import_targets.update(
                alias.name
                for alias in node.names
            )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            import_targets.update(
                (
                    node.module
                    + "."
                    + alias.name
                )
                for alias in node.names
            )

    forbidden_targets = {
        target
        for target in import_targets
        if any(
            target == prefix
            or target.startswith(
                prefix + "."
            )
            for prefix
            in forbidden_module_prefixes
        )
    }

    assert (
        forbidden_targets
        == set()
    )

    assert (
        "urllib.parse.urlsplit"
        in import_targets
    )

    forbidden_methods = {
        "apply",
        "auto_apply",
        "score",
        "shortlist",
        "submit",
        "submit_application",
        "send_application",
    }

    definitions = {
        node.name
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    assert (
        definitions
        & forbidden_methods
    ) == set()
