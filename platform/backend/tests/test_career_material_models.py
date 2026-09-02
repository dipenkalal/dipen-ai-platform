import hashlib
from datetime import (
    datetime,
    timezone,
)

import pytest

from career.schemas import (
    CareerApplicationMaterial,
    CareerApplicationMaterialEvent,
    CareerApplicationMaterialVersion,
    CareerMaterialProvenance,
)


NOW = datetime(
    2026,
    9,
    2,
    6,
    45,
    tzinfo=timezone.utc,
)

APPLICATION_ID = "career-application-test-1"
JOB_ID = "career-job-test-1"
SNAPSHOT_ID = (
    "career-snapshot-"
    + ("a" * 24)
)


def _provenance(
    *,
    parent: str | None = None,
) -> CareerMaterialProvenance:
    return CareerMaterialProvenance(
        application_id=APPLICATION_ID,
        job_id=JOB_ID,
        snapshot_id=SNAPSHOT_ID,
        profile_version="master-v1",
        generator_kind="DAP_GENERATOR",
        model_provider="local",
        model_name="test-model",
        creation_mechanism="isolated-test",
        parent_material_version_id=parent,
    )


def _material() -> CareerApplicationMaterial:
    return CareerApplicationMaterial.build(
        application_id=APPLICATION_ID,
        material_kind="RESUME",
        label="primary",
        created_at=NOW,
    )


def _version_one(
) -> CareerApplicationMaterialVersion:
    material = _material()

    return CareerApplicationMaterialVersion.build(
        material_id=material.material_id,
        version_number=1,
        source_snapshot_id=SNAPSHOT_ID,
        content_format="MARKDOWN",
        content_text="# Resume",
        provenance=_provenance(),
        created_by_kind="DAP_GENERATOR",
        created_by_id="test-suite",
        created_at=NOW,
    )


def test_material_identity_is_deterministic() -> None:
    first = _material()

    second = CareerApplicationMaterial.build(
        application_id=APPLICATION_ID,
        material_kind="RESUME",
        label="primary",
        created_at=NOW,
    )

    assert first.material_id == second.material_id
    assert first.application_id == APPLICATION_ID


def test_material_version_hash_and_identity() -> None:
    version = _version_one()

    assert version.content_sha256 == hashlib.sha256(
        b"# Resume"
    ).hexdigest()

    assert version.version_number == 1
    assert version.parent_material_version_id is None
    assert version.provenance.snapshot_id == SNAPSHOT_ID


def test_material_version_rejects_tampering() -> None:
    version = _version_one()

    payload = version.model_dump(
        mode="python"
    )
    payload["content_text"] = "# Changed"

    with pytest.raises(
        ValueError,
        match="content_sha256",
    ):
        CareerApplicationMaterialVersion.model_validate(
            payload
        )


def test_second_version_requires_parent() -> None:
    material = _material()

    with pytest.raises(
        ValueError,
        match="requires explicit parent",
    ):
        CareerApplicationMaterialVersion.build(
            material_id=material.material_id,
            version_number=2,
            source_snapshot_id=SNAPSHOT_ID,
            content_format="MARKDOWN",
            content_text="# Revision",
            provenance=_provenance(),
            created_by_kind="DAP_GENERATOR",
            created_by_id="test-suite",
            created_at=NOW,
        )


def test_owner_only_material_review() -> None:
    version = _version_one()

    with pytest.raises(
        ValueError,
        match="owner-only",
    ):
        CareerApplicationMaterialEvent.build(
            material_version_id=(
                version.material_version_id
            ),
            event_kind="APPROVED",
            actor_kind="DAP_SYSTEM",
            actor_id="dap",
            reason="Invalid automated approval.",
            occurred_at=NOW,
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
            occurred_at=NOW,
        )
    )

    assert approved.event_kind == "APPROVED"
    assert approved.actor_kind == "OWNER"


def test_material_timestamp_must_be_aware() -> None:
    naive = datetime(
        2026,
        9,
        2,
        6,
        45,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        CareerApplicationMaterial.build(
            application_id=APPLICATION_ID,
            material_kind="APPLICATION_NOTES",
            label="notes",
            created_at=naive,
        )
