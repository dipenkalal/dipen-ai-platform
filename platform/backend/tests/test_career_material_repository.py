from __future__ import annotations

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

from career.repository import (
    CareerPersistenceConflict,
    CareerRepository,
)
from career.schemas import (
    CareerApplicationMaterial,
    CareerApplicationMaterialEvent,
    CareerApplicationMaterialVersion,
    CareerJobSnapshot,
    CareerMaterialProvenance,
)


NOW = datetime(
    2026,
    9,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)

SOURCE_ID = "career-source-material-test"
JOB_ID = "career-job-material-test"
APPLICATION_ID = "career-application-material-test"
TEST_SNAPSHOT = CareerJobSnapshot.build(
    job_id=JOB_ID,
    source_id=SOURCE_ID,
    title="Cloud Engineer",
    employer_name="Material Employer",
    description_text="Test description.",
    freshness_state="WITHIN_72H",
    normalized_text_sha256=("c" * 64),
    observed_at=NOW,
    location_text="Toronto, ON",
    work_mode="HYBRID",
    employment_type="Full-time",
    posted_at=NOW,
    requirements={},
)

SNAPSHOT_ID = TEST_SNAPSHOT.snapshot_id


class MaterialTruthRepository:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = path

    @contextmanager
    def connection(
        self,
    ) -> Iterator[sqlite3.Connection]:
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


def _seed_phase16(
    path: Path,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE
            research_retrieval_evidence (
                evidence_id TEXT PRIMARY KEY
            )
            """
        )
        connection.commit()


def _repository(
    tmp_path: Path,
) -> tuple[
    CareerRepository,
    Path,
]:
    path = tmp_path / "material-lab.db"

    _seed_phase16(path)

    repository = CareerRepository(
        MaterialTruthRepository(path)
    )

    _seed_career_parents(path)

    return repository, path


def _seed_career_parents(
    path: Path,
) -> None:
    instant = NOW.isoformat()

    with sqlite3.connect(path) as connection:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            """
            INSERT INTO career_sources (
                source_id,
                display_name,
                employer_name,
                source_kind,
                connector_kind,
                trust_tier,
                canonical_base_url,
                state,
                last_verified_at,
                last_error_code,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                SOURCE_ID,
                "Material Test",
                "Material Employer",
                "official_structured_ats",
                "greenhouse",
                3,
                "https://example.com/jobs",
                "active",
                instant,
                None,
                instant,
                instant,
            ),
        )

        connection.execute(
            """
            INSERT INTO career_job_postings (
                job_id,
                employer_name,
                requisition_id,
                canonical_job_url,
                canonical_apply_url,
                current_snapshot_id,
                verification_state,
                lifecycle_state,
                first_seen_at,
                last_seen_at,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                JOB_ID,
                "Material Employer",
                "REQ-1",
                "https://example.com/jobs/1",
                "https://example.com/jobs/1/apply",
                None,
                "VERIFIED",
                "ACTIVE",
                instant,
                instant,
                instant,
                instant,
            ),
        )

        connection.execute(
            """
            INSERT INTO career_job_snapshots (
                snapshot_id,
                job_id,
                source_id,
                title,
                employer_name,
                location_text,
                work_mode,
                employment_type,
                description_text,
                description_sha256,
                posted_at,
                closing_at,
                freshness_state,
                salary_text,
                requirements_json,
                normalized_text_sha256,
                observed_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                TEST_SNAPSHOT.snapshot_id,
                TEST_SNAPSHOT.job_id,
                TEST_SNAPSHOT.source_id,
                TEST_SNAPSHOT.title,
                TEST_SNAPSHOT.employer_name,
                TEST_SNAPSHOT.location_text,
                TEST_SNAPSHOT.work_mode,
                TEST_SNAPSHOT.employment_type,
                TEST_SNAPSHOT.description_text,
                TEST_SNAPSHOT.description_sha256,
                (
                    TEST_SNAPSHOT.posted_at.isoformat()
                    if TEST_SNAPSHOT.posted_at
                    else None
                ),
                None,
                TEST_SNAPSHOT.freshness_state,
                TEST_SNAPSHOT.salary_text,
                "{}",
                TEST_SNAPSHOT.normalized_text_sha256,
                TEST_SNAPSHOT.observed_at.isoformat(),
            ),
        )

        connection.execute(
            """
            INSERT INTO career_applications (
                application_id,
                job_id,
                state,
                owner_approved_at,
                applied_confirmed_at,
                applied_confirmation_kind,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                APPLICATION_ID,
                JOB_ID,
                "SHORTLISTED",
                None,
                None,
                None,
                None,
                instant,
                instant,
            ),
        )

        connection.commit()


def _material(
    *,
    label: str = "primary",
    created_at: datetime = NOW,
) -> CareerApplicationMaterial:
    return CareerApplicationMaterial.build(
        application_id=APPLICATION_ID,
        material_kind="RESUME",
        label=label,
        created_at=created_at,
    )


def _provenance(
    *,
    snapshot_id: str = SNAPSHOT_ID,
    parent: str | None = None,
) -> CareerMaterialProvenance:
    return CareerMaterialProvenance(
        application_id=APPLICATION_ID,
        job_id=JOB_ID,
        snapshot_id=snapshot_id,
        profile_version="master-v1",
        generator_kind="DAP_GENERATOR",
        model_provider="local",
        model_name="repository-test",
        creation_mechanism="isolated-repository-test",
        parent_material_version_id=parent,
    )


def _version_one(
    material: CareerApplicationMaterial,
) -> CareerApplicationMaterialVersion:
    return CareerApplicationMaterialVersion.build(
        material_id=material.material_id,
        version_number=1,
        source_snapshot_id=SNAPSHOT_ID,
        content_format="MARKDOWN",
        content_text="# Resume v1",
        provenance=_provenance(),
        created_by_kind="DAP_GENERATOR",
        created_by_id="repository-test",
        created_at=NOW,
    )


def test_initialize_adds_exact_material_schema(
    tmp_path: Path,
) -> None:
    repository, path = _repository(
        tmp_path
    )

    assert repository is not None

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name LIKE
                      'career_application_material%'
                """
            )
        }

        indexes = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='index'
                  AND (
                    name LIKE
                      'idx_career_application_material%'
                    OR name LIKE
                      'idx_career_material_%'
                  )
                """
            )
        }

    assert tables == {
        "career_application_materials",
        "career_application_material_versions",
        "career_application_material_events",
    }

    assert indexes == {
        "idx_career_application_materials_application",
        "idx_career_material_versions_material",
        "idx_career_material_events_version",
    }


def test_material_round_trip_and_idempotency(
    tmp_path: Path,
) -> None:
    repository, _ = _repository(
        tmp_path
    )

    material = _material()

    first = repository.persist_material(
        material
    )

    second = repository.persist_material(
        material
    )

    assert first == material
    assert second == material

    assert (
        repository.get_material(
            material.material_id
        )
        == material
    )

    assert (
        repository.list_application_materials(
            APPLICATION_ID
        )
        == [material]
    )


def test_material_identity_fields_are_immutable(
    tmp_path: Path,
) -> None:
    repository, _ = _repository(
        tmp_path
    )

    original = _material()

    repository.persist_material(
        original
    )

    conflicting = _material(
        created_at=NOW + timedelta(seconds=1)
    )

    assert (
        conflicting.material_id
        == original.material_id
    )

    with pytest.raises(
        CareerPersistenceConflict,
        match="different content",
    ):
        repository.persist_material(
            conflicting
        )


def test_material_requires_known_application(
    tmp_path: Path,
) -> None:
    repository, _ = _repository(
        tmp_path
    )

    material = (
        CareerApplicationMaterial.build(
            application_id=(
                "career-application-unknown"
            ),
            material_kind="RESUME",
            label="primary",
            created_at=NOW,
        )
    )

    with pytest.raises(
        ValueError,
        match="unknown application",
    ):
        repository.persist_material(
            material
        )


def test_version_round_trip_and_provenance_json(
    tmp_path: Path,
) -> None:
    repository, _ = _repository(
        tmp_path
    )

    material = repository.persist_material(
        _material()
    )

    version = _version_one(material)

    stored = repository.persist_material_version(
        version
    )

    assert stored == version

    assert (
        repository.get_material_version(
            version.material_version_id
        )
        == version
    )

    assert (
        repository.list_material_versions(
            material.material_id
        )
        == [version]
    )


def test_version_parent_must_belong_to_same_material(
    tmp_path: Path,
) -> None:
    repository, _ = _repository(
        tmp_path
    )

    first_material = repository.persist_material(
        _material(label="primary")
    )

    second_material = repository.persist_material(
        _material(label="secondary")
    )

    parent = repository.persist_material_version(
        _version_one(first_material)
    )

    provenance = _provenance(
        parent=parent.material_version_id
    )

    child = (
        CareerApplicationMaterialVersion.build(
            material_id=second_material.material_id,
            version_number=2,
            source_snapshot_id=SNAPSHOT_ID,
            parent_material_version_id=(
                parent.material_version_id
            ),
            content_format="MARKDOWN",
            content_text="# Wrong lineage",
            provenance=provenance,
            created_by_kind="DAP_GENERATOR",
            created_by_id="repository-test",
            created_at=(
                NOW + timedelta(seconds=1)
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="different material",
    ):
        repository.persist_material_version(
            child
        )


def test_version_sequence_must_increment_parent(
    tmp_path: Path,
) -> None:
    repository, _ = _repository(
        tmp_path
    )

    material = repository.persist_material(
        _material()
    )

    parent = repository.persist_material_version(
        _version_one(material)
    )

    provenance = _provenance(
        parent=parent.material_version_id
    )

    child = (
        CareerApplicationMaterialVersion.build(
            material_id=material.material_id,
            version_number=3,
            source_snapshot_id=SNAPSHOT_ID,
            parent_material_version_id=(
                parent.material_version_id
            ),
            content_format="MARKDOWN",
            content_text="# Resume v3",
            provenance=provenance,
            created_by_kind="DAP_GENERATOR",
            created_by_id="repository-test",
            created_at=(
                NOW + timedelta(seconds=1)
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="increment parent",
    ):
        repository.persist_material_version(
            child
        )


def test_material_event_round_trip_and_history(
    tmp_path: Path,
) -> None:
    repository, _ = _repository(
        tmp_path
    )

    material = repository.persist_material(
        _material()
    )

    version = repository.persist_material_version(
        _version_one(material)
    )

    created = (
        CareerApplicationMaterialEvent.build(
            material_version_id=(
                version.material_version_id
            ),
            event_kind="CREATED",
            actor_kind="DAP_SYSTEM",
            actor_id="dap",
            reason="Draft created.",
            occurred_at=NOW,
        )
    )

    approved = (
        CareerApplicationMaterialEvent.build(
            material_version_id=(
                version.material_version_id
            ),
            event_kind="APPROVED",
            actor_kind="OWNER",
            actor_id="dipen",
            reason="Owner approved exact version.",
            occurred_at=(
                NOW + timedelta(seconds=1)
            ),
        )
    )

    assert (
        repository.persist_material_event(
            created
        )
        == created
    )

    assert (
        repository.persist_material_event(
            approved
        )
        == approved
    )

    assert (
        repository.list_material_events(
            version.material_version_id
        )
        == [
            created,
            approved,
        ]
    )


def test_material_event_requires_known_version(
    tmp_path: Path,
) -> None:
    repository, _ = _repository(
        tmp_path
    )

    event = (
        CareerApplicationMaterialEvent.build(
            material_version_id=(
                "career-material-version-"
                + ("d" * 24)
            ),
            event_kind="CREATED",
            actor_kind="DAP_SYSTEM",
            actor_id="dap",
            reason="Impossible event.",
            occurred_at=NOW,
        )
    )

    with pytest.raises(
        ValueError,
        match="unknown material version",
    ):
        repository.persist_material_event(
            event
        )


def test_material_tables_preserve_integrity(
    tmp_path: Path,
) -> None:
    repository, path = _repository(
        tmp_path
    )

    material = repository.persist_material(
        _material()
    )

    version = repository.persist_material_version(
        _version_one(material)
    )

    repository.persist_material_event(
        CareerApplicationMaterialEvent.build(
            material_version_id=(
                version.material_version_id
            ),
            event_kind="CREATED",
            actor_kind="DAP_SYSTEM",
            actor_id="dap",
            reason="Created.",
            occurred_at=NOW,
        )
    )

    with sqlite3.connect(path) as connection:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        fk = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    assert integrity == "ok"
    assert fk == []
