from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from fastapi import FastAPI
from fastapi.testclient import TestClient

import career.routes as career_routes


NOW = datetime(
    2026,
    9,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)


class StubCareerDomainService:
    def __init__(self) -> None:
        self.calls: list[
            tuple[str, str]
        ] = []

    def get_cockpit_application(
        self,
        *,
        application_id: str,
    ):
        self.calls.append(
            (
                "application",
                application_id,
            )
        )

        if application_id.endswith(
            "missing"
        ):
            raise KeyError(
                "Career application "
                "was not found."
            )

        return {
            "application_id":
                application_id,
            "job_id":
                "career-job-http",
            "state":
                "PREPARING",
            "owner_approved_at":
                None,
            "applied_confirmed_at":
                None,
            "applied_confirmation_kind":
                None,
            "notes":
                None,
            "created_at":
                NOW,
            "updated_at":
                NOW,
        }

    def list_cockpit_application_events(
        self,
        *,
        application_id: str,
    ):
        self.calls.append(
            (
                "application-events",
                application_id,
            )
        )
        return ()

    def get_cockpit_application_readiness(
        self,
        *,
        application_id: str,
    ):
        self.calls.append(
            (
                "readiness",
                application_id,
            )
        )

        return {
            "application_id":
                application_id,
            "ready":
                False,
            "blockers": (
                {
                    "code":
                        "PRIMARY_RESUME_MISSING",
                    "material_id":
                        None,
                    "material_version_id":
                        None,
                },
            ),
        }

    def list_cockpit_application_materials(
        self,
        *,
        application_id: str,
    ):
        self.calls.append(
            (
                "materials",
                application_id,
            )
        )
        return ()

    def list_cockpit_material_versions(
        self,
        *,
        material_id: str,
    ):
        self.calls.append(
            (
                "versions",
                material_id,
            )
        )
        return ()

    def list_cockpit_material_events(
        self,
        *,
        material_version_id: str,
    ):
        self.calls.append(
            (
                "material-events",
                material_version_id,
            )
        )
        return ()


def _client():
    service = StubCareerDomainService()

    app = FastAPI()
    app.include_router(
        career_routes.router
    )

    app.dependency_overrides[
        career_routes
        .get_career_domain_service
    ] = lambda: service

    return (
        TestClient(app),
        service,
    )


def test_read_route_surface_is_preserved(
) -> None:
    get_routes = {
        route.path
        for route in career_routes.router.routes
        if "GET" in route.methods
    }

    assert get_routes == {
        "/api/v1/career/summary",
        "/api/v1/career/jobs",
        (
            "/api/v1/career/applications/"
            "{application_id}"
        ),
        (
            "/api/v1/career/applications/"
            "{application_id}/events"
        ),
        (
            "/api/v1/career/applications/"
            "{application_id}/readiness"
        ),
        (
            "/api/v1/career/applications/"
            "{application_id}/materials"
        ),
        (
            "/api/v1/career/materials/"
            "{material_id}/versions"
        ),
        (
            "/api/v1/career/material-versions/"
            "{material_version_id}/events"
        ),
    }


def test_get_application_route(
) -> None:
    client, service = _client()

    response = client.get(
        "/api/v1/career/applications/"
        "career-application-http"
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "application_id"
        ]
        == "career-application-http"
    )

    assert service.calls == [
        (
            "application",
            "career-application-http",
        )
    ]


def test_application_read_collections(
) -> None:
    client, _ = _client()

    events = client.get(
        "/api/v1/career/applications/"
        "career-application-http/events"
    )

    assert events.status_code == 200
    assert events.json() == {
        "total": 0,
        "items": [],
    }

    materials = client.get(
        "/api/v1/career/applications/"
        "career-application-http/materials"
    )

    assert materials.status_code == 200

    assert materials.json() == {
        "total": 0,
        "items": [],
    }


def test_readiness_route(
) -> None:
    client, _ = _client()

    response = client.get(
        "/api/v1/career/applications/"
        "career-application-http/readiness"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["ready"] is False

    assert (
        payload["blockers"][0]["code"]
        == "PRIMARY_RESUME_MISSING"
    )


def test_material_read_collections(
) -> None:
    client, _ = _client()

    versions = client.get(
        "/api/v1/career/materials/"
        "career-material-"
        + "a" * 24
        + "/versions"
    )

    assert versions.status_code == 200

    assert versions.json() == {
        "total": 0,
        "items": [],
    }

    events = client.get(
        "/api/v1/career/material-versions/"
        "career-material-version-"
        + "b" * 24
        + "/events"
    )

    assert events.status_code == 200

    assert events.json() == {
        "total": 0,
        "items": [],
    }


def test_unknown_application_maps_to_404(
) -> None:
    client, _ = _client()

    response = client.get(
        "/api/v1/career/applications/"
        "career-application-missing"
    )

    assert response.status_code == 404


def test_no_unfrozen_http_methods_exposed(
) -> None:
    methods = {
        method
        for route in career_routes.router.routes
        for method in route.methods
    }

    assert not (
        methods
        & {
            "PUT",
            "PATCH",
            "DELETE",
        }
    )
