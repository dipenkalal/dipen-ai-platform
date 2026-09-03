from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

import career.routes as career_routes
from career.service import CareerMaterialRejected


class StubService:
    def __init__(self) -> None:
        self.calls = []

    def _reject(self, name, kwargs):
        self.calls.append((name, kwargs))
        raise CareerMaterialRejected(
            "route sentinel"
        )

    def create_cockpit_application(
        self,
        **kwargs,
    ):
        return self._reject(
            "create_cockpit_application",
            kwargs,
        )

    def transition_application(
        self,
        **kwargs,
    ):
        return self._reject(
            "transition_application",
            kwargs,
        )

    def advance_preparing_application_to_review(
        self,
        **kwargs,
    ):
        return self._reject(
            "advance_preparing_application_to_review",
            kwargs,
        )

    def approve_ready_application(
        self,
        **kwargs,
    ):
        return self._reject(
            "approve_ready_application",
            kwargs,
        )

    def create_material(
        self,
        **kwargs,
    ):
        return self._reject(
            "create_material",
            kwargs,
        )

    def create_cockpit_material_version(
        self,
        **kwargs,
    ):
        return self._reject(
            "create_cockpit_material_version",
            kwargs,
        )

    def mark_material_version_ready(
        self,
        **kwargs,
    ):
        return self._reject(
            "mark_material_version_ready",
            kwargs,
        )

    def approve_material_version(
        self,
        **kwargs,
    ):
        return self._reject(
            "approve_material_version",
            kwargs,
        )

    def reject_material_version(
        self,
        **kwargs,
    ):
        return self._reject(
            "reject_material_version",
            kwargs,
        )


def client():
    service = StubService()

    app = FastAPI()
    app.include_router(career_routes.router)

    app.dependency_overrides[
        career_routes.get_career_domain_service
    ] = lambda: service

    return TestClient(app), service


def assert_aware(value):
    assert isinstance(value, datetime)
    assert value.tzinfo is not None


def test_exact_frozen_route_counts():
    routes = career_routes.router.routes

    gets = [
        route for route in routes
        if "GET" in route.methods
    ]
    posts = [
        route for route in routes
        if "POST" in route.methods
    ]

    assert len(routes) == 18
    assert len(gets) == 10
    assert len(posts) == 8

    assert not any(
        route.methods
        & {"PUT", "PATCH", "DELETE"}
        for route in routes
    )


def test_create_application_has_server_fields():
    http, service = client()

    response = http.post(
        "/api/v1/career/jobs/"
        "career-job-http/application",
        json={
            "reason": "Shortlist.",
            "notes": "Owner note.",
        },
    )

    assert response.status_code == 409

    name, kwargs = service.calls[-1]

    assert name == "create_cockpit_application"
    assert set(kwargs) == {
        "job_id",
        "reason",
        "notes",
        "occurred_at",
    }

    assert_aware(kwargs["occurred_at"])


def test_caller_owner_and_actor_injection_rejected():
    http, service = client()

    response = http.post(
        "/api/v1/career/jobs/"
        "career-job-http/application",
        json={
            "reason": "Attempt.",
            "owner_id": "attacker",
        },
    )

    assert response.status_code == 422
    assert service.calls == []

    response = http.post(
        "/api/v1/career/applications/"
        "career-application-http/transitions",
        json={
            "to_state": "PREPARING",
            "reason": "Attempt.",
            "actor_kind":
                "DETERMINISTIC_SYSTEM",
        },
    )

    assert response.status_code == 422
    assert service.calls == []


def test_generic_transition_is_fixed_owner():
    http, service = client()

    response = http.post(
        "/api/v1/career/applications/"
        "career-application-http/transitions",
        json={
            "to_state": "PREPARING",
            "reason": "Prepare.",
        },
    )

    assert response.status_code == 409

    name, kwargs = service.calls[-1]

    assert name == "transition_application"
    assert kwargs["actor_kind"] == "OWNER"
    assert kwargs["actor_id"] == "dipen-owner"
    assert_aware(kwargs["occurred_at"])


def test_generic_guarded_targets_blocked():
    for target in (
        "READY_FOR_REVIEW",
        "OWNER_APPROVED",
        "APPLIED_CONFIRMED",
    ):
        http, service = client()

        response = http.post(
            "/api/v1/career/applications/"
            "career-application-http/transitions",
            json={
                "to_state": target,
                "reason": "Bypass.",
            },
        )

        assert response.status_code == 403
        assert service.calls == []


def test_dedicated_review_and_approval_routes():
    http, service = client()

    response = http.post(
        "/api/v1/career/applications/"
        "career-application-http/"
        "advance-to-review",
        json={"reason": "Ready."},
    )

    assert response.status_code == 409
    assert (
        service.calls[-1][0]
        == "advance_preparing_application_to_review"
    )

    http, service = client()

    response = http.post(
        "/api/v1/career/applications/"
        "career-application-http/approve",
        json={"reason": "Approved."},
    )

    assert response.status_code == 409
    assert (
        service.calls[-1][0]
        == "approve_ready_application"
    )


def test_material_version_uses_path_aware_domain_guard():
    http, service = client()

    material_id = (
        "career-material-" + "a" * 24
    )

    parent = (
        "career-material-version-"
        + "b" * 24
    )

    response = http.post(
        "/api/v1/career/materials/"
        + material_id
        + "/versions",
        json={
            "source_snapshot_id":
                "career-snapshot-http",
            "content_format": "MARKDOWN",
            "content_text": "# Resume",
            "parent_material_version_id":
                parent,
        },
    )

    assert response.status_code == 409

    name, kwargs = service.calls[-1]

    assert (
        name
        == "create_cockpit_material_version"
    )

    assert kwargs["material_id"] == material_id

    assert (
        kwargs["parent_material_version_id"]
        == parent
    )

    assert "created_by_kind" not in kwargs
    assert "created_by_id" not in kwargs
    assert_aware(kwargs["occurred_at"])


def test_creator_impersonation_rejected():
    http, service = client()

    response = http.post(
        "/api/v1/career/materials/"
        "career-material-"
        + "a" * 24
        + "/versions",
        json={
            "source_snapshot_id":
                "career-snapshot-http",
            "content_format": "MARKDOWN",
            "content_text": "# Resume",
            "created_by_kind":
                "DAP_GENERATOR",
        },
    )

    assert response.status_code == 422
    assert service.calls == []


def test_ready_route_is_fixed_owner():
    http, service = client()

    version = (
        "career-material-version-"
        + "c" * 24
    )

    response = http.post(
        "/api/v1/career/material-versions/"
        + version
        + "/ready",
        json={"reason": "Ready."},
    )

    assert response.status_code == 409

    _, kwargs = service.calls[-1]

    assert kwargs["actor_kind"] == "OWNER"
    assert kwargs["actor_id"] == "dipen-owner"
    assert_aware(kwargs["occurred_at"])


def test_material_decision_is_fixed_owner():
    http, service = client()

    version = (
        "career-material-version-"
        + "d" * 24
    )

    response = http.post(
        "/api/v1/career/material-versions/"
        + version
        + "/decision",
        json={"decision": "approve"},
    )

    assert response.status_code == 409

    name, kwargs = service.calls[-1]

    assert name == "approve_material_version"
    assert kwargs["owner_id"] == "dipen-owner"

    http, service = client()

    response = http.post(
        "/api/v1/career/material-versions/"
        + version
        + "/decision",
        json={
            "decision": "reject",
            "reason": "Revise.",
        },
    )

    assert response.status_code == 409

    name, kwargs = service.calls[-1]

    assert name == "reject_material_version"
    assert kwargs["owner_id"] == "dipen-owner"


def test_client_timestamp_rejected():
    http, service = client()

    response = http.post(
        "/api/v1/career/applications/"
        "career-application-http/approve",
        json={
            "reason": "Approve.",
            "occurred_at":
                "2026-09-02T12:00:00Z",
        },
    )

    assert response.status_code == 422
    assert service.calls == []


def test_no_submission_surface():
    values = {
        (
            route.path
            + "|"
            + route.name
        ).lower()
        for route in career_routes.router.routes
    }

    forbidden = (
        "submit",
        "auto_apply",
        "auto-apply",
        "send_application",
        "send-application",
        "applied-confirmed",
    )

    assert not any(
        token in value
        for value in values
        for token in forbidden
    )
