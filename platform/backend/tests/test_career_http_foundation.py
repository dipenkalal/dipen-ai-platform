from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import career.http_support as http_support
from career.http_schemas import (
    CareerAdvanceToReviewRequest,
    CareerApproveApplicationRequest,
    CareerCreateApplicationRequest,
    CareerCreateMaterialRequest,
    CareerCreateMaterialVersionRequest,
    CareerMarkMaterialReadyRequest,
    CareerMaterialDecisionRequest,
    CareerTransitionRequest,
)
from career.repository import (
    CareerPersistenceConflict,
)
from career.service import (
    CareerAdmissionRejected,
    CareerAuthorizationRejected,
    CareerMaterialRejected,
    CareerTransitionRejected,
)


REQUEST_MODELS = (
    CareerCreateApplicationRequest,
    CareerTransitionRequest,
    CareerAdvanceToReviewRequest,
    CareerApproveApplicationRequest,
    CareerCreateMaterialRequest,
    CareerCreateMaterialVersionRequest,
    CareerMarkMaterialReadyRequest,
    CareerMaterialDecisionRequest,
)

FORBIDDEN_FIELDS = {
    "owner_id",
    "actor_id",
    "actor_kind",
    "created_by_kind",
    "created_by_id",
    "occurred_at",
    "created_at",
    "updated_at",
}


def test_request_models_expose_no_authority_fields(
) -> None:
    for model in REQUEST_MODELS:
        fields = set(
            model.model_fields
        )

        assert not (
            fields & FORBIDDEN_FIELDS
        ), (
            model.__name__,
            fields & FORBIDDEN_FIELDS,
        )


def test_request_models_forbid_extra_authority(
) -> None:
    with pytest.raises(ValidationError):
        CareerAdvanceToReviewRequest(
            reason="Ready.",
            actor_kind=(
                "DETERMINISTIC_SYSTEM"
            ),
        )

    with pytest.raises(ValidationError):
        CareerApproveApplicationRequest(
            reason="Approved.",
            owner_id="attacker",
        )

    with pytest.raises(ValidationError):
        CareerCreateMaterialVersionRequest(
            source_snapshot_id=(
                "career-snapshot-test"
            ),
            content_format="MARKDOWN",
            content_text="Resume",
            created_by_kind="DAP_GENERATOR",
        )


def test_material_decision_validation(
) -> None:
    approved = CareerMaterialDecisionRequest(
        decision="approve",
    )

    assert approved.reason == ""

    with pytest.raises(
        ValidationError,
        match="rejection requires",
    ):
        CareerMaterialDecisionRequest(
            decision="reject",
            reason=" ",
        )


def test_required_reason_is_normalized(
) -> None:
    request = CareerCreateApplicationRequest(
        reason="  shortlist  ",
    )

    assert request.reason == "shortlist"

    with pytest.raises(ValidationError):
        CareerCreateApplicationRequest(
            reason="   ",
        )


def test_domain_dependency_uses_initialize_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    marker = object()

    class StubRepository:
        def __init__(
            self,
            truth_repository: object,
            *,
            initialize: bool = True,
        ) -> None:
            calls["truth_repository"] = (
                truth_repository
            )
            calls["initialize"] = initialize

    class StubService:
        def __init__(
            self,
            repository: object,
        ) -> None:
            calls["repository"] = (
                repository
            )

    monkeypatch.setattr(
        http_support,
        "agent_truth_repository",
        marker,
    )

    monkeypatch.setattr(
        http_support,
        "CareerRepository",
        StubRepository,
    )

    monkeypatch.setattr(
        http_support,
        "CareerDomainService",
        StubService,
    )

    service = (
        http_support
        .get_career_domain_service()
    )

    assert isinstance(
        service,
        StubService,
    )

    assert (
        calls["truth_repository"]
        is marker
    )

    assert calls["initialize"] is False


@pytest.mark.parametrize(
    ("error", "expected_status"),
    (
        (
            CareerAuthorizationRejected(
                "denied"
            ),
            403,
        ),
        (
            CareerAdmissionRejected(
                "admission"
            ),
            409,
        ),
        (
            CareerTransitionRejected(
                "transition"
            ),
            409,
        ),
        (
            CareerMaterialRejected(
                "material"
            ),
            409,
        ),
        (
            CareerPersistenceConflict(
                "conflict"
            ),
            409,
        ),
        (
            KeyError("missing"),
            404,
        ),
        (
            FileNotFoundError("database"),
            503,
        ),
        (
            sqlite3.OperationalError(
                "no such table: "
                "career_application_materials"
            ),
            503,
        ),
    ),
)
def test_error_mapping(
    error: Exception,
    expected_status: int,
) -> None:
    mapped = (
        http_support
        .career_http_exception(error)
    )

    assert isinstance(
        mapped,
        HTTPException,
    )

    assert (
        mapped.status_code
        == expected_status
    )


def test_unexpected_error_maps_to_500(
) -> None:
    mapped = (
        http_support
        .career_http_exception(
            RuntimeError("secret detail")
        )
    )

    assert mapped.status_code == 500

    assert (
        mapped.detail
        == "Career Cockpit internal error."
    )


def test_http_support_has_no_router_decorators(
) -> None:
    path = Path(
        http_support.__file__
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    decorators = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        for decorator in node.decorator_list:
            if (
                isinstance(
                    decorator,
                    ast.Call,
                )
                and isinstance(
                    decorator.func,
                    ast.Attribute,
                )
                and decorator.func.attr
                in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                }
            ):
                decorators.append(
                    decorator.func.attr
                )

    assert decorators == []
