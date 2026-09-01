from __future__ import annotations

import hashlib
import json
import re

import pytest

from career.provider_identity import (
    ProviderIdentityError,
    canonicalize_provider_identity,
    supported_provider_kinds,
)


def _independent_expected(
    data: dict[str, str],
) -> tuple[str, str, str]:

    canonical = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    sha = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    key = (
        "career-provider-key-"
        + sha[:24]
    )

    return (
        canonical,
        sha,
        key,
    )


def test_supported_provider_kinds_are_frozen() -> None:

    assert supported_provider_kinds() == (
        "ashby",
        "greenhouse",
        "lever",
        "smartrecruiters",
        "workday",
    )


def test_workday_identity_is_deterministic() -> None:

    result = canonicalize_provider_identity(
        "workday",
        {
            "host": "td.wd3.myworkdayjobs.com",
            "tenant": "td",
            "site": "TD_Bank_Careers",
        },
    )

    expected = {
        "host": "td.wd3.myworkdayjobs.com",
        "provider_kind": "workday",
        "site": "TD_Bank_Careers",
        "tenant": "td",
    }

    canonical, sha, key = (
        _independent_expected(expected)
    )

    assert result.canonical_json == canonical
    assert result.identity_sha256 == sha
    assert result.provider_identity_key == key

    assert re.fullmatch(
        r"career-provider-key-[0-9a-f]{24}",
        result.provider_identity_key,
    )


def test_workday_host_and_provider_normalize() -> None:

    first = canonicalize_provider_identity(
        " WorkDay ",
        {
            "host": " TD.WD3.MYWORKDAYJOBS.COM. ",
            "tenant": " td ",
            "site": " TD_Bank_Careers ",
        },
    )

    second = canonicalize_provider_identity(
        "workday",
        {
            "host": "td.wd3.myworkdayjobs.com",
            "tenant": "td",
            "site": "TD_Bank_Careers",
        },
    )

    assert first == second


@pytest.mark.parametrize(
    ("provider", "identity"),
    [
        (
            "greenhouse",
            {
                "host": "job-boards.greenhouse.io",
                "board_token": "tailscale",
            },
        ),
        (
            "lever",
            {
                "host": "jobs.lever.co",
                "site": "shyftlabs",
            },
        ),
        (
            "ashby",
            {
                "host": "jobs.ashbyhq.com",
                "board": "sentry",
            },
        ),
        (
            "smartrecruiters",
            {
                "host": "api.smartrecruiters.com",
                "company_identifier": "ExampleCompany",
            },
        ),
    ],
)
def test_supported_provider_identity_shapes(
    provider: str,
    identity: dict[str, str],
) -> None:

    result = canonicalize_provider_identity(
        provider,
        identity,
    )

    assert result.provider_kind == provider

    assert len(
        result.identity_sha256
    ) == 64

    assert result.provider_identity_key.startswith(
        "career-provider-key-"
    )


def test_operational_workday_fields_are_rejected() -> None:

    with pytest.raises(
        ProviderIdentityError,
        match="Unexpected provider identity fields",
    ):

        canonicalize_provider_identity(
            "workday",
            {
                "host": "td.wd3.myworkdayjobs.com",
                "tenant": "td",
                "site": "TD_Bank_Careers",
                "max_pages": "25",
            },
        )


@pytest.mark.parametrize(
    "host",
    [
        "https://td.wd3.myworkdayjobs.com",
        "td.wd3.myworkdayjobs.com/jobs",
        "td.wd3.myworkdayjobs.com?x=1",
        "td.wd3.myworkdayjobs.com#fragment",
        "user@td.wd3.myworkdayjobs.com",
        "td.wd3.myworkdayjobs.com:443",
        "localhost",
        "",
    ],
)
def test_host_must_be_hostname_only(
    host: str,
) -> None:

    with pytest.raises(
        ProviderIdentityError
    ):

        canonicalize_provider_identity(
            "workday",
            {
                "host": host,
                "tenant": "td",
                "site": "TD_Bank_Careers",
            },
        )


def test_missing_field_rejected() -> None:

    with pytest.raises(
        ProviderIdentityError,
        match="Missing provider identity fields",
    ):

        canonicalize_provider_identity(
            "lever",
            {
                "host": "jobs.lever.co",
            },
        )


def test_unknown_provider_rejected() -> None:

    with pytest.raises(
        ProviderIdentityError,
        match="Unsupported provider_kind",
    ):

        canonicalize_provider_identity(
            "unknown",
            {
                "host": "example.com",
            },
        )


def test_opaque_identity_case_is_preserved() -> None:

    result = canonicalize_provider_identity(
        "ashby",
        {
            "host": "jobs.ashbyhq.com",
            "board": "CaseSensitiveBoard",
        },
    )

    assert (
        result.identity["board"]
        == "CaseSensitiveBoard"
    )


def test_identity_mapping_is_immutable() -> None:

    result = canonicalize_provider_identity(
        "greenhouse",
        {
            "host": "job-boards.greenhouse.io",
            "board_token": "tailscale",
        },
    )

    with pytest.raises(TypeError):
        result.identity["host"] = "evil.example"  # type: ignore[index]
