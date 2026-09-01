import ast
from pathlib import Path

import pytest

from career.source_discovery_shadow_population import (
    ShadowPopulationError,
    ShadowTargetInput,
    build_shadow_population,
    build_shadow_target,
)


def item(
    provider,
    employer,
    url,
):
    return ShadowTargetInput(
        provider_kind=provider,
        employer_name=employer,
        career_url=url,
    )


def test_complete_endpoint_builds_shadow():
    result = build_shadow_target(
        item(
            "lever",
            "ShyftLabs",
            "https://jobs.lever.co/shyftlabs",
        )
    )

    assert result.provider_kind == "lever"

    assert (
        result.shadow_target_id
        .startswith(
            "career-shadow-target-"
        )
    )

    assert (
        result.provider_identity_key
        .startswith(
            "career-provider-key-"
        )
    )


def test_incomplete_endpoint_rejected():
    with pytest.raises(
        ShadowPopulationError,
    ):
        build_shadow_target(
            item(
                "lever",
                "Unknown",
                "https://jobs.lever.co/",
            )
        )


def test_provider_mismatch_rejected():
    with pytest.raises(
        ShadowPopulationError,
    ):
        build_shadow_target(
            item(
                "ashby",
                "Wrong",
                "https://jobs.lever.co/shyftlabs",
            )
        )


def test_query_fragment_converges():
    a = build_shadow_target(
        item(
            "lever",
            "A",
            "https://jobs.lever.co/shyftlabs",
        )
    )

    b = build_shadow_target(
        item(
            "lever",
            "B",
            "https://jobs.lever.co/"
            "shyftlabs?team=x#jobs",
        )
    )

    assert (
        a.provider_identity_key
        == b.provider_identity_key
    )

    assert (
        a.shadow_target_id
        == b.shadow_target_id
    )


def test_workday_locale_converges():
    a = build_shadow_target(
        item(
            "workday",
            "TD",
            "https://td.wd3.myworkdayjobs.com/"
            "en-US/TD_Bank_Careers",
        )
    )

    b = build_shadow_target(
        item(
            "workday",
            "TD",
            "https://td.wd3.myworkdayjobs.com/"
            "fr-CA/TD_Bank_Careers",
        )
    )

    assert (
        a.provider_identity_key
        == b.provider_identity_key
    )


def test_duplicate_endpoint_rejected():
    values = (
        item(
            "lever",
            "A",
            "https://jobs.lever.co/shyftlabs",
        ),
        item(
            "lever",
            "B",
            "https://jobs.lever.co/shyftlabs",
        ),
    )

    with pytest.raises(
        ShadowPopulationError,
    ):
        build_shadow_population(
            values
        )


def test_namespaces_are_distinct():
    value = build_shadow_target(
        item(
            "ashby",
            "Sentry",
            "https://jobs.ashbyhq.com/sentry",
        )
    )

    for prefix in (
        "career-source-key-",
        "career-provider-key-",
        "career-discovery-candidate-",
    ):
        assert not (
            value.shadow_target_id
            .startswith(prefix)
        )


def test_shadow_has_zero_authority():
    value = build_shadow_target(
        item(
            "greenhouse",
            "Lush",
            "https://job-boards."
            "greenhouse.io/lush",
        )
    )

    assert (
        value.authoritative_registry_member
        is False
    )

    assert (
        value.research_evidence_present
        is False
    )

    assert (
        value.admission_authority_granted
        is False
    )

    assert (
        value.application_authority_granted
        is False
    )


def test_source_has_no_external_authority():
    tree = ast.parse(
        Path(
            "career/"
            "source_discovery_shadow_population.py"
        ).read_text()
    )

    forbidden = {
        "requests",
        "httpx",
        "socket",
        "sqlite3",
        "sqlalchemy",
        "aiohttp",
        "urllib.request",
        "subprocess",
        "career.repository",
        "career.source_discovery_repository",
        "career.phase16_retrieval_adapter",
    }

    found = []

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            modules = [
                alias.name
                for alias in node.names
            ]

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            modules = [
                node.module or ""
            ]

        else:
            continue

        for module in modules:
            if any(
                module == value
                or module.startswith(
                    value + "."
                )
                for value in forbidden
            ):
                found.append(
                    module
                )

    assert found == []
