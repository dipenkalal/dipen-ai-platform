from __future__ import annotations

import ast
from pathlib import Path

import pytest

from career.discovery_router import (
    EMPTY_PROVIDER_KIND,
    FAIL_CLOSED,
    GENERIC_PHASE16_FALLBACK,
    INVALID_PROVIDER_TARGET,
    MISSING_PROVIDER_TARGET,
    PROVIDER_SPECIFIC_CONNECTOR,
    UNKNOWN_PROVIDER,
    frozen_route_policy,
    resolve_discovery_route,
)


EXPECTED_STRUCTURED = {
    "greenhouse":
        "career.connectors.greenhouse",
    "lever":
        "career.connectors.lever",
    "ashby":
        "career.connectors.ashby",
    "smartrecruiters":
        "career.connectors.smartrecruiters",
}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("greenhouse", "greenhouse"),
        (" GreenHouse ", "greenhouse"),
        ("LEVER", "lever"),
        (" AshBy", "ashby"),
        (
            "SMARTRECRUITERS ",
            "smartrecruiters",
        ),
        (" WorkDay ", "workday"),
    ],
)
def test_provider_kind_normalization(
    raw: str,
    expected: str,
) -> None:
    target = {"opaque": "target"}

    decision = resolve_discovery_route(
        raw,
        target,
    )

    assert decision.provider_kind == expected


@pytest.mark.parametrize(
    ("provider", "module"),
    sorted(
        EXPECTED_STRUCTURED.items()
    ),
)
def test_structured_provider_routes(
    provider: str,
    module: str,
) -> None:
    target = {
        "employer": provider,
        "opaque_identifier": "value",
    }

    decision = resolve_discovery_route(
        provider,
        target,
    )

    assert (
        decision.route_kind
        == PROVIDER_SPECIFIC_CONNECTOR
    )

    assert (
        decision.connector_module
        == module
    )

    assert decision.reason == (
        "KNOWN_PROVIDER_ROUTE"
    )

    assert (
        decision.provider_target
        is target
    )

    assert (
        decision.phase16_network_owner
        is True
    )

    assert decision.endpoint is None

    assert (
        decision.network_request_created_by_router
        is False
    )


def test_workday_routes_only_to_generic_phase16() -> None:
    target = {
        "site_identifier": "opaque-site",
    }

    decision = resolve_discovery_route(
        "workday",
        target,
    )

    assert (
        decision.route_kind
        == GENERIC_PHASE16_FALLBACK
    )

    assert decision.connector_module is None

    assert decision.reason == (
        "WORKDAY_GENERIC_PHASE16_FALLBACK"
    )

    assert (
        decision.provider_target
        is target
    )

    assert decision.endpoint is None

    assert (
        decision.network_request_created_by_router
        is False
    )


def test_unknown_provider_fails_closed() -> None:
    target = {
        "target": "opaque",
    }

    decision = resolve_discovery_route(
        "unknown-provider",
        target,
    )

    assert decision.route_kind == FAIL_CLOSED
    assert decision.reason == UNKNOWN_PROVIDER
    assert decision.connector_module is None
    assert decision.endpoint is None

    assert (
        decision.provider_target
        is target
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        None,
    ],
)
def test_missing_provider_kind_fails_closed(
    raw: object,
) -> None:
    decision = resolve_discovery_route(  # type: ignore[arg-type]
        raw,
        {"target": "opaque"},
    )

    assert decision.route_kind == FAIL_CLOSED

    assert (
        decision.reason
        == EMPTY_PROVIDER_KIND
    )

    assert decision.connector_module is None


@pytest.mark.parametrize(
    "provider",
    [
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "workday",
    ],
)
def test_missing_known_provider_target_fails_closed(
    provider: str,
) -> None:
    decision = resolve_discovery_route(
        provider
    )

    assert decision.route_kind == FAIL_CLOSED

    assert (
        decision.reason
        == MISSING_PROVIDER_TARGET
    )

    assert decision.connector_module is None
    assert decision.provider_target is None
    assert decision.endpoint is None


def test_invalid_provider_target_fails_closed() -> None:
    decision = resolve_discovery_route(  # type: ignore[arg-type]
        "greenhouse",
        ["not", "a", "mapping"],
    )

    assert decision.route_kind == FAIL_CLOSED

    assert (
        decision.reason
        == INVALID_PROVIDER_TARGET
    )

    assert decision.connector_module is None
    assert decision.provider_target is None


def test_target_is_preserved_without_endpoint_inference() -> None:
    target = {
        "board_token":
            "opaque-board",
        "url_like_value":
            "https://example.invalid/internal-looking-value",
    }

    decision = resolve_discovery_route(
        "greenhouse",
        target,
    )

    assert (
        decision.provider_target
        is target
    )

    assert decision.endpoint is None


def test_research_context_cannot_change_route() -> None:
    target = {
        "company_identifier": "opaque",
    }

    baseline = resolve_discovery_route(
        "smartrecruiters",
        target,
    )

    with_context = resolve_discovery_route(
        "smartrecruiters",
        target,
        research_request_context={
            "network_authorized": True,
            "invent_endpoint": True,
        },
    )

    assert baseline == with_context


def test_same_input_produces_same_decision() -> None:
    target = {
        "job_board_name": "opaque",
    }

    first = resolve_discovery_route(
        "ashby",
        target,
    )

    second = resolve_discovery_route(
        "ashby",
        target,
    )

    assert first == second


def test_frozen_route_policy_is_exact() -> None:
    policy = frozen_route_policy()

    assert set(policy) == {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "workday",
    }

    for provider, module in (
        EXPECTED_STRUCTURED.items()
    ):
        assert policy[provider] == (
            PROVIDER_SPECIFIC_CONNECTOR,
            module,
        )

    assert policy["workday"] == (
        GENERIC_PHASE16_FALLBACK,
        None,
    )


def test_frozen_route_policy_is_immutable() -> None:
    policy = frozen_route_policy()

    with pytest.raises(TypeError):
        policy["greenhouse"] = (  # type: ignore[index]
            FAIL_CLOSED,
            None,
        )


def test_router_has_no_network_or_database_imports() -> None:
    source_path = (
        Path(__file__).parents[1]
        / "career"
        / "discovery_router.py"
    )

    tree = ast.parse(
        source_path.read_text(
            encoding="utf-8"
        ),
        filename=str(source_path),
    )

    forbidden_roots = {
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "urllib",
        "sqlite3",
        "sqlalchemy",
        "psycopg",
        "psycopg2",
        "asyncpg",
    }

    imported_roots = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_roots.add(
                    alias.name.split(
                        ".",
                        1,
                    )[0]
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_roots.add(
                    node.module.split(
                        ".",
                        1,
                    )[0]
                )

    assert (
        imported_roots
        & forbidden_roots
    ) == set()


def test_router_does_not_import_provider_connectors() -> None:
    source_path = (
        Path(__file__).parents[1]
        / "career"
        / "discovery_router.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(source_path),
    )

    imported_modules = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.update(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_modules.add(
                    node.module
                )

    assert not any(
        module.startswith(
            "career.connectors."
        )
        for module in imported_modules
    )


def test_router_has_no_workday_connector_route() -> None:
    source_path = (
        Path(__file__).parents[1]
        / "career"
        / "discovery_router.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    )

    assert (
        "career.connectors.workday"
        not in source
    )
