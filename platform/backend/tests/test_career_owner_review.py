from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.truth_repository import (
    AgentTruthRepository,
)
import career.routes as career_routes
from career.repository import CareerRepository
from career.schemas import (
    CareerApplication,
    CareerApplicationApproval,
    CareerApplicationEvent,
    CareerApplicationMaterial,
    CareerApplicationMaterialEvent,
    CareerApplicationMaterialVersion,
    CareerApplicationReadiness,
    CareerJobPosting,
    CareerJobSnapshot,
    CareerMaterialProvenance,
    CareerOwnerReviewPackage,
    CareerOwnerReviewQueue,
    CareerSource,
)
from career.service import (
    CareerDomainService,
    CareerMaterialRejected,
)
from gateway.research_retrieval_repository import (
    ResearchRetrievalRepository,
)


NOW = datetime(
    2026,
    9,
    3,
    18,
    30,
    tzinfo=timezone.utc,
)

CONTENT_HASH = "c" * 64


def _real_repository(
    tmp_path: Path,
) -> tuple[
    CareerRepository,
    CareerJobPosting,
    CareerJobSnapshot,
]:
    db = tmp_path / "owner-review.db"

    truth = AgentTruthRepository(db)

    ResearchRetrievalRepository(
        truth
    )

    repository = CareerRepository(
        truth
    )

    source = CareerSource(
        source_id="career-source-owner-review",
        display_name="Owner Review Careers",
        employer_name="Owner Review Employer",
        source_kind="official_structured_ats",
        connector_kind="greenhouse",
        trust_tier=3,
        canonical_base_url=(
            "https://example.test/careers"
        ),
        state="active",
        last_verified_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )

    repository.upsert_source(source)

    job = CareerJobPosting(
        job_id="career-job-owner-review",
        employer_name="Owner Review Employer",
        requisition_id="OR-1",
        canonical_job_url=(
            "https://example.test/jobs/1"
        ),
        canonical_apply_url=(
            "https://example.test/jobs/1/apply"
        ),
        current_snapshot_id=None,
        verification_state="RETRIEVED",
        lifecycle_state="ACTIVE",
        first_seen_at=NOW,
        last_seen_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )

    repository.upsert_job(job)

    snapshot = CareerJobSnapshot.build(
        job_id=job.job_id,
        source_id=source.source_id,
        title="Cloud Support Engineer",
        employer_name="Owner Review Employer",
        location_text="Toronto, ON",
        work_mode="HYBRID",
        employment_type="Full-time",
        description_text=(
            "Support cloud infrastructure."
        ),
        posted_at=(
            NOW - timedelta(hours=2)
        ),
        freshness_state="WITHIN_72H",
        normalized_text_sha256=(
            CONTENT_HASH
        ),
        observed_at=NOW,
    )

    repository.persist_snapshot(snapshot)

    payload = job.model_dump(
        mode="python"
    )

    payload["current_snapshot_id"] = (
        snapshot.snapshot_id
    )
    payload["verification_state"] = (
        "VERIFIED"
    )
    payload["updated_at"] = (
        NOW + timedelta(seconds=1)
    )

    job = CareerJobPosting.model_validate(
        payload
    )

    repository.upsert_job(job)

    return (
        repository,
        job,
        snapshot,
    )


def _application_counts(
    repository: CareerRepository,
) -> tuple[int, ...]:
    tables = (
        "career_applications",
        "career_application_events",
        "career_application_materials",
        "career_application_material_versions",
        "career_application_material_events",
    )

    with repository._connection() as connection:
        return tuple(
            connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in tables
        )


def test_repository_ready_queue_filters_orders_and_does_not_mutate(
    tmp_path: Path,
) -> None:
    repository, job, _ = (
        _real_repository(tmp_path)
    )

    applications = (
        CareerApplication(
            application_id=(
                "career-application-owner-ready-a"
            ),
            job_id=job.job_id,
            state="READY_FOR_REVIEW",
            created_at=NOW,
            updated_at=(
                NOW + timedelta(seconds=10)
            ),
        ),
        CareerApplication(
            application_id=(
                "career-application-owner-preparing"
            ),
            job_id=job.job_id,
            state="PREPARING",
            created_at=NOW,
            updated_at=(
                NOW + timedelta(seconds=11)
            ),
        ),
        CareerApplication(
            application_id=(
                "career-application-owner-ready-b"
            ),
            job_id=job.job_id,
            state="READY_FOR_REVIEW",
            created_at=NOW,
            updated_at=(
                NOW + timedelta(seconds=12)
            ),
        ),
    )

    for application in applications:
        repository.upsert_application(
            application
        )

    before = _application_counts(
        repository
    )

    result = (
        repository
        .list_ready_for_review_applications()
    )

    after = _application_counts(
        repository
    )

    assert [
        item.application_id
        for item in result
    ] == [
        "career-application-owner-ready-a",
        "career-application-owner-ready-b",
    ]

    assert all(
        item.state == "READY_FOR_REVIEW"
        for item in result
    )

    assert before == after


def _projection_graph(
    *,
    application_state: str = (
        "READY_FOR_REVIEW"
    ),
    with_snapshot: bool = True,
):
    application = CareerApplication(
        application_id=(
            "career-application-owner-projection"
        ),
        job_id="career-job-owner-projection",
        state=application_state,
        created_at=NOW,
        updated_at=NOW,
    )

    snapshot = CareerJobSnapshot.build(
        job_id=application.job_id,
        source_id=(
            "career-source-owner-projection"
        ),
        title="Infrastructure Analyst",
        employer_name="Projection Employer",
        description_text=(
            "Support infrastructure systems."
        ),
        freshness_state="WITHIN_72H",
        normalized_text_sha256=("d" * 64),
        observed_at=NOW,
        location_text="Windsor, ON",
        work_mode="HYBRID",
        employment_type="Full-time",
        posted_at=(
            NOW - timedelta(hours=3)
        ),
    )

    job = CareerJobPosting(
        job_id=application.job_id,
        employer_name="Projection Employer",
        requisition_id="PROJ-1",
        canonical_job_url=(
            "https://example.test/projection/1"
        ),
        canonical_apply_url=None,
        current_snapshot_id=(
            snapshot.snapshot_id
            if with_snapshot
            else None
        ),
        verification_state="VERIFIED",
        lifecycle_state="ACTIVE",
        first_seen_at=NOW,
        last_seen_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )

    readiness = CareerApplicationReadiness(
        application_id=(
            application.application_id
        ),
        ready=True,
        blockers=(),
    )

    approval = CareerApplicationApproval(
        application_id=(
            application.application_id
        ),
        approved=True,
        blockers=(),
    )

    application_event = (
        CareerApplicationEvent.build(
            application_id=(
                application.application_id
            ),
            from_state="PREPARING",
            to_state="READY_FOR_REVIEW",
            actor_kind=(
                "DETERMINISTIC_SYSTEM"
            ),
            actor_id="career-material-readiness",
            reason="Package ready.",
            occurred_at=(
                NOW + timedelta(seconds=1)
            ),
        )
    )

    material = CareerApplicationMaterial.build(
        application_id=(
            application.application_id
        ),
        material_kind="RESUME",
        label="primary",
        created_at=(
            NOW + timedelta(seconds=2)
        ),
    )

    provenance_v1 = CareerMaterialProvenance(
        application_id=(
            application.application_id
        ),
        job_id=application.job_id,
        snapshot_id=snapshot.snapshot_id,
        generator_kind="DAP_GENERATOR",
        creation_mechanism="unit-test",
    )

    version_v1 = (
        CareerApplicationMaterialVersion.build(
            material_id=material.material_id,
            version_number=1,
            source_snapshot_id=(
                snapshot.snapshot_id
            ),
            content_format="MARKDOWN",
            content_text="# Resume v1",
            provenance=provenance_v1,
            created_by_kind="DAP_GENERATOR",
            created_by_id="owner-review-test",
            created_at=(
                NOW + timedelta(seconds=3)
            ),
        )
    )

    provenance_v2 = CareerMaterialProvenance(
        application_id=(
            application.application_id
        ),
        job_id=application.job_id,
        snapshot_id=snapshot.snapshot_id,
        generator_kind="OWNER",
        creation_mechanism="owner-edit",
        parent_material_version_id=(
            version_v1.material_version_id
        ),
    )

    version_v2 = (
        CareerApplicationMaterialVersion.build(
            material_id=material.material_id,
            version_number=2,
            source_snapshot_id=(
                snapshot.snapshot_id
            ),
            content_format="MARKDOWN",
            content_text="# Resume v2",
            provenance=provenance_v2,
            created_by_kind="OWNER",
            created_by_id="dipen-owner",
            created_at=(
                NOW + timedelta(seconds=4)
            ),
            parent_material_version_id=(
                version_v1.material_version_id
            ),
        )
    )

    latest_event = (
        CareerApplicationMaterialEvent.build(
            material_version_id=(
                version_v2.material_version_id
            ),
            event_kind=(
                "MARKED_READY_FOR_REVIEW"
            ),
            actor_kind="OWNER",
            actor_id="dipen-owner",
            reason="Latest resume ready.",
            occurred_at=(
                NOW + timedelta(seconds=5)
            ),
        )
    )

    return {
        "application": application,
        "job": job,
        "snapshot": snapshot,
        "readiness": readiness,
        "approval": approval,
        "application_event": (
            application_event
        ),
        "material": material,
        "version_v1": version_v1,
        "version_v2": version_v2,
        "latest_event": latest_event,
    }


class ProjectionRepository:
    def __init__(
        self,
        graph,
        *,
        include_snapshot: bool = True,
        missing_job: bool = False,
    ) -> None:
        self.graph = graph
        self.include_snapshot = include_snapshot
        self.missing_job = missing_job

    def list_ready_for_review_applications(
        self,
    ):
        return (
            self.graph["application"],
        )

    def get_application(
        self,
        application_id: str,
    ):
        if (
            application_id
            == self.graph[
                "application"
            ].application_id
        ):
            return self.graph["application"]

        return None

    def get_job(
        self,
        job_id: str,
    ):
        if self.missing_job:
            return None

        if job_id == self.graph["job"].job_id:
            return self.graph["job"]

        return None

    def get_snapshot(
        self,
        snapshot_id: str,
    ):
        if not self.include_snapshot:
            return None

        if (
            snapshot_id
            == self.graph[
                "snapshot"
            ].snapshot_id
        ):
            return self.graph["snapshot"]

        return None

    def list_application_events(
        self,
        application_id: str,
    ):
        return (
            self.graph[
                "application_event"
            ],
        )

    def list_application_materials(
        self,
        application_id: str,
    ):
        return (
            self.graph["material"],
        )

    def list_material_versions(
        self,
        material_id: str,
    ):
        return (
            self.graph["version_v1"],
            self.graph["version_v2"],
        )

    def list_material_events(
        self,
        material_version_id: str,
    ):
        if (
            material_version_id
            == self.graph[
                "version_v2"
            ].material_version_id
        ):
            return (
                self.graph["latest_event"],
            )

        return ()


class ProjectionService(
    CareerDomainService
):
    def __init__(
        self,
        repository,
        *,
        readiness,
        approval,
    ) -> None:
        super().__init__(repository)
        self._review_readiness = readiness
        self._review_approval = approval

    def evaluate_application_readiness(
        self,
        *,
        application_id: str,
    ):
        return self._review_readiness

    def evaluate_application_approval(
        self,
        *,
        application_id: str,
    ):
        return self._review_approval


def _projection_service(
    graph,
    *,
    include_snapshot: bool = True,
    missing_job: bool = False,
):
    repository = ProjectionRepository(
        graph,
        include_snapshot=include_snapshot,
        missing_job=missing_job,
    )

    return ProjectionService(
        repository,
        readiness=graph["readiness"],
        approval=graph["approval"],
    )


def test_service_queue_is_read_only_and_snapshot_optional(
) -> None:
    graph = _projection_graph(
        with_snapshot=False
    )

    service = _projection_service(
        graph,
        include_snapshot=False,
    )

    queue = service.list_owner_review_queue()

    assert isinstance(
        queue,
        CareerOwnerReviewQueue,
    )

    assert queue.total == 1

    item = queue.items[0]

    assert (
        item.application.state
        == "READY_FOR_REVIEW"
    )

    assert item.current_snapshot is None

    assert (
        item.job.job_id
        == graph["job"].job_id
    )

    assert item.readiness.ready is True
    assert item.approval.approved is True


def test_service_queue_fails_closed_on_missing_job(
) -> None:
    graph = _projection_graph()

    service = _projection_service(
        graph,
        missing_job=True,
    )

    with pytest.raises(
        KeyError,
        match="job was not found",
    ):
        service.list_owner_review_queue()


def test_service_package_rejects_non_ready_application(
) -> None:
    graph = _projection_graph(
        application_state="PREPARING"
    )

    service = _projection_service(
        graph
    )

    with pytest.raises(
        CareerMaterialRejected,
        match="not ready for owner review",
    ):
        service.get_owner_review_package(
            application_id=(
                graph[
                    "application"
                ].application_id
            )
        )


def test_service_package_uses_latest_material_graph(
) -> None:
    graph = _projection_graph()

    service = _projection_service(
        graph
    )

    package = (
        service.get_owner_review_package(
            application_id=(
                graph[
                    "application"
                ].application_id
            )
        )
    )

    assert isinstance(
        package,
        CareerOwnerReviewPackage,
    )

    assert (
        package.application.state
        == "READY_FOR_REVIEW"
    )

    assert (
        package.current_snapshot.snapshot_id
        == graph["snapshot"].snapshot_id
    )

    assert len(
        package.application_events
    ) == 1

    assert len(package.materials) == 1

    review_material = package.materials[0]

    assert (
        review_material.latest_version
        .material_version_id
        == graph[
            "version_v2"
        ].material_version_id
    )

    assert (
        review_material.latest_version
        .version_number
        == 2
    )

    assert len(
        review_material.latest_version_events
    ) == 1

    assert (
        review_material
        .latest_version_events[0]
        .material_version_id
        == graph[
            "version_v2"
        ].material_version_id
    )


class HttpOwnerReviewStub:
    def __init__(
        self,
        queue: CareerOwnerReviewQueue,
        package: CareerOwnerReviewPackage,
    ) -> None:
        self.queue = queue
        self.package = package
        self.calls: list[
            tuple[str, str | None]
        ] = []

    def list_owner_review_queue(
        self,
    ):
        self.calls.append(
            ("queue", None)
        )
        return self.queue

    def get_owner_review_package(
        self,
        *,
        application_id: str,
    ):
        self.calls.append(
            ("package", application_id)
        )
        return self.package


def test_http_owner_review_routes_are_get_only(
) -> None:
    graph = _projection_graph()

    projection_service = (
        _projection_service(graph)
    )

    queue = (
        projection_service
        .list_owner_review_queue()
    )

    package = (
        projection_service
        .get_owner_review_package(
            application_id=(
                graph[
                    "application"
                ].application_id
            )
        )
    )

    service = HttpOwnerReviewStub(
        queue,
        package,
    )

    app = FastAPI()
    app.include_router(
        career_routes.router
    )

    app.dependency_overrides[
        career_routes
        .get_career_domain_service
    ] = lambda: service

    client = TestClient(app)

    queue_response = client.get(
        "/api/v1/career/owner-review/queue"
    )

    assert queue_response.status_code == 200

    queue_payload = queue_response.json()

    assert queue_payload["total"] == 1

    application_id = (
        graph[
            "application"
        ].application_id
    )

    package_response = client.get(
        "/api/v1/career/applications/"
        f"{application_id}/owner-review"
    )

    assert package_response.status_code == 200

    assert (
        package_response.json()[
            "application"
        ][
            "application_id"
        ]
        == application_id
    )

    assert service.calls == [
        ("queue", None),
        ("package", application_id),
    ]

    routes = {
        route.path: set(
            route.methods
        )
        for route in career_routes.router.routes
        if "owner-review" in route.path
    }

    assert routes == {
        (
            "/api/v1/career/"
            "owner-review/queue"
        ): {"GET"},
        (
            "/api/v1/career/"
            "applications/"
            "{application_id}/owner-review"
        ): {"GET"},
    }


def test_real_domain_ready_for_review_projection_is_read_only(
    tmp_path: Path,
) -> None:
    repository, job, snapshot = (
        _real_repository(tmp_path)
    )

    application = CareerApplication(
        application_id=(
            "career-application-owner-real-domain"
        ),
        job_id=job.job_id,
        state="PREPARING",
        created_at=(
            NOW + timedelta(seconds=10)
        ),
        updated_at=(
            NOW + timedelta(seconds=10)
        ),
    )

    repository.upsert_application(
        application
    )

    service = CareerDomainService(
        repository
    )

    material = service.create_material(
        application_id=(
            application.application_id
        ),
        material_kind="RESUME",
        label="primary",
        created_at=(
            NOW + timedelta(seconds=11)
        ),
    )

    version = (
        service.create_initial_material_version(
            material_id=material.material_id,
            source_snapshot_id=(
                snapshot.snapshot_id
            ),
            content_format="MARKDOWN",
            content_text=(
                "# Real-domain resume"
            ),
            created_by_kind="DAP_GENERATOR",
            created_by_id="owner-review-real-test",
            creation_mechanism="unit-test",
            profile_version="master-v1",
            model_provider="local",
            model_name="test-model",
            occurred_at=(
                NOW + timedelta(seconds=12)
            ),
        )
    )

    service.mark_material_version_ready(
        material_version_id=(
            version.material_version_id
        ),
        actor_kind="OWNER",
        actor_id="dipen-owner",
        reason="Real-domain resume ready.",
        occurred_at=(
            NOW + timedelta(seconds=13)
        ),
    )

    preparing_readiness = (
        service.evaluate_application_readiness(
            application_id=(
                application.application_id
            )
        )
    )

    assert preparing_readiness.ready is True

    advanced = (
        service
        .advance_preparing_application_to_review(
            application_id=(
                application.application_id
            ),
            reason=(
                "Real-domain package ready "
                "for owner review."
            ),
            occurred_at=(
                NOW + timedelta(seconds=14)
            ),
        )
    )

    assert advanced.state == "READY_FOR_REVIEW"

    application_before = (
        repository.get_application(
            application.application_id
        )
    )

    events_before = tuple(
        repository.list_application_events(
            application.application_id
        )
    )

    materials_before = tuple(
        repository.list_application_materials(
            application.application_id
        )
    )

    versions_before = tuple(
        repository.list_material_versions(
            material.material_id
        )
    )

    material_events_before = tuple(
        repository.list_material_events(
            version.material_version_id
        )
    )

    counts_before = _application_counts(
        repository
    )

    queue = service.list_owner_review_queue()

    package = (
        service.get_owner_review_package(
            application_id=(
                application.application_id
            )
        )
    )

    counts_after = _application_counts(
        repository
    )

    application_after = (
        repository.get_application(
            application.application_id
        )
    )

    events_after = tuple(
        repository.list_application_events(
            application.application_id
        )
    )

    materials_after = tuple(
        repository.list_application_materials(
            application.application_id
        )
    )

    versions_after = tuple(
        repository.list_material_versions(
            material.material_id
        )
    )

    material_events_after = tuple(
        repository.list_material_events(
            version.material_version_id
        )
    )

    assert queue.total == 1

    assert (
        queue.items[0]
        .application.application_id
        == application.application_id
    )

    assert (
        queue.items[0].application.state
        == "READY_FOR_REVIEW"
    )

    assert (
        queue.items[0].job.job_id
        == job.job_id
    )

    assert (
        queue.items[0]
        .current_snapshot.snapshot_id
        == snapshot.snapshot_id
    )

    # Phase 2B owner-review projection must preserve the
    # proven readiness of the package after lifecycle advancement.
    assert queue.items[0].readiness.ready is True

    assert (
        package.application.application_id
        == application.application_id
    )

    assert (
        package.application.state
        == "READY_FOR_REVIEW"
    )

    assert (
        package.job.job_id
        == job.job_id
    )

    assert (
        package.current_snapshot.snapshot_id
        == snapshot.snapshot_id
    )

    assert package.readiness.ready is True

    assert len(package.materials) == 1

    review_material = package.materials[0]

    assert (
        review_material.material.material_id
        == material.material_id
    )

    assert (
        review_material.latest_version
        .material_version_id
        == version.material_version_id
    )

    assert (
        review_material.latest_version
        .source_snapshot_id
        == snapshot.snapshot_id
    )

    assert (
        package.approval.approved
        is False
    )

    assert counts_before == counts_after

    assert application_before == application_after

    assert (
        application_after.state
        == "READY_FOR_REVIEW"
    )

    assert events_before == events_after
    assert materials_before == materials_after
    assert versions_before == versions_after

    assert (
        material_events_before
        == material_events_after
    )
