from __future__ import annotations

import pytest

from career.ats_identification import (
    ATSIdentificationError,
    ATSIdentificationStatus,
    identify_career_url,
)

from career.provider_identity import (
    canonicalize_provider_identity,
)


def endpoint(url):

    result = identify_career_url(
        url
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ENDPOINT_IDENTIFIED
    )

    return result


def test_unknown_custom_domain_unrecognized():

    result = identify_career_url(
        "https://careers.example.com/jobs"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .UNRECOGNIZED
    )

    assert result.provider_kind is None


def test_http_rejected():

    with pytest.raises(
        ATSIdentificationError
    ):
        identify_career_url(
            "http://jobs.lever.co/example"
        )


def test_surrounding_whitespace_rejected():

    with pytest.raises(
        ATSIdentificationError
    ):
        identify_career_url(
            " https://jobs.lever.co/example"
        )


def test_credentials_rejected():

    with pytest.raises(
        ATSIdentificationError
    ):
        identify_career_url(
            "https://user:pass@jobs.lever.co/example"
        )


def test_nondefault_port_rejected():

    with pytest.raises(
        ATSIdentificationError
    ):
        identify_career_url(
            "https://jobs.lever.co:8443/example"
        )


def test_query_fragment_do_not_affect_identity():

    a = endpoint(
        "https://jobs.lever.co/example"
    )

    b = endpoint(
        "https://jobs.lever.co/example"
        "?source=test#jobs"
    )

    assert (
        a.provider_identity_key
        == b.provider_identity_key
    )


def test_greenhouse_provider_only_root():

    result = identify_career_url(
        "https://job-boards.greenhouse.io"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ATS_IDENTIFIED
    )

    assert (
        result.provider_kind
        == "greenhouse"
    )

    assert (
        result.provider_identity_key
        is None
    )


def test_greenhouse_us_endpoint():

    result = endpoint(
        "https://job-boards.greenhouse.io/"
        "tailscale/jobs/123"
    )

    expected = canonicalize_provider_identity(
        "greenhouse",
        {
            "host":
                "job-boards.greenhouse.io",
            "board_token":
                "tailscale",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )

    assert (
        result.canonical_career_url
        == "https://job-boards.greenhouse.io/tailscale"
    )


def test_greenhouse_eu_endpoint():

    result = endpoint(
        "https://job-boards.eu.greenhouse.io/"
        "teads1/jobs/123"
    )

    expected = canonicalize_provider_identity(
        "greenhouse",
        {
            "host":
                "job-boards.eu.greenhouse.io",
            "board_token":
                "teads1",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )


def test_greenhouse_invalid_board_does_not_guess():

    result = identify_career_url(
        "https://job-boards.greenhouse.io/%74ailscale"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ATS_IDENTIFIED
    )


def test_lever_endpoint():

    result = endpoint(
        "https://jobs.lever.co/shyftlabs/"
        "some-job-id"
    )

    expected = canonicalize_provider_identity(
        "lever",
        {
            "host":
                "jobs.lever.co",
            "site":
                "shyftlabs",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )


def test_lever_root_provider_only():

    result = identify_career_url(
        "https://jobs.lever.co"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ATS_IDENTIFIED
    )

    assert result.provider_kind == "lever"


def test_ashby_endpoint():

    result = endpoint(
        "https://jobs.ashbyhq.com/"
        "sentry/123"
    )

    expected = canonicalize_provider_identity(
        "ashby",
        {
            "host":
                "jobs.ashbyhq.com",
            "board":
                "sentry",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )


def test_ashby_root_provider_only():

    result = identify_career_url(
        "https://jobs.ashbyhq.com"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ATS_IDENTIFIED
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://careers.smartrecruiters.com/ServiceNow",
        "https://jobs.smartrecruiters.com/"
        "ServiceNow/744000000000000-example",
        "https://api.smartrecruiters.com/"
        "v1/companies/ServiceNow/postings",
    ],
)
def test_smartrecruiters_public_and_api_identity_same(
    url,
):

    result = endpoint(url)

    expected = canonicalize_provider_identity(
        "smartrecruiters",
        {
            "host":
                "api.smartrecruiters.com",
            "company_identifier":
                "ServiceNow",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )

    assert (
        result.canonical_career_url
        == "https://careers.smartrecruiters.com/ServiceNow"
    )


def test_smartrecruiters_root_provider_only():

    result = identify_career_url(
        "https://jobs.smartrecruiters.com"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ATS_IDENTIFIED
    )

    assert (
        result.provider_kind
        == "smartrecruiters"
    )


def test_workday_root_is_provider_only():

    result = identify_career_url(
        "https://bmo.wd3.myworkdayjobs.com"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ATS_IDENTIFIED
    )

    assert result.provider_kind == "workday"


def test_workday_site_without_locale():

    result = endpoint(
        "https://rbc.wd3.myworkdayjobs.com/"
        "RBCGLOBAL1/job/Toronto/example"
    )

    expected = canonicalize_provider_identity(
        "workday",
        {
            "host":
                "rbc.wd3.myworkdayjobs.com",
            "tenant":
                "rbc",
            "site":
                "RBCGLOBAL1",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )

    assert (
        result.canonical_career_url
        == "https://rbc.wd3.myworkdayjobs.com/RBCGLOBAL1"
    )


def test_workday_site_with_locale():

    result = endpoint(
        "https://td.wd3.myworkdayjobs.com/"
        "en-US/TD_Bank_Careers/job/example"
    )

    expected = canonicalize_provider_identity(
        "workday",
        {
            "host":
                "td.wd3.myworkdayjobs.com",
            "tenant":
                "td",
            "site":
                "TD_Bank_Careers",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )

    assert (
        result.canonical_career_url
        == "https://td.wd3.myworkdayjobs.com/"
        "en-US/TD_Bank_Careers"
    )


def test_workday_locale_not_in_identity():

    a = endpoint(
        "https://td.wd3.myworkdayjobs.com/"
        "en-US/TD_Bank_Careers"
    )

    b = endpoint(
        "https://td.wd3.myworkdayjobs.com/"
        "fr-CA/TD_Bank_Careers"
    )

    assert (
        a.provider_identity_key
        == b.provider_identity_key
    )


def test_workday_internal_api_path_does_not_guess_site():

    result = identify_career_url(
        "https://td.wd3.myworkdayjobs.com/"
        "wday/cxs/td/TD_Bank_Careers/jobs"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ATS_IDENTIFIED
    )

    assert (
        result.provider_identity_key
        is None
    )


def test_workday_tenant_comes_from_host():

    result = endpoint(
        "https://bmo.wd3.myworkdayjobs.com/"
        "Campus"
    )

    expected = canonicalize_provider_identity(
        "workday",
        {
            "host":
                "bmo.wd3.myworkdayjobs.com",
            "tenant":
                "bmo",
            "site":
                "Campus",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )


def test_explicit_443_allowed():

    result = endpoint(
        "https://jobs.lever.co:443/example"
    )

    assert result.provider_kind == "lever"


def test_result_endpoint_fields_complete():

    result = endpoint(
        "https://jobs.ashbyhq.com/sentry"
    )

    assert (
        result.provider_kind
        == "ashby"
    )

    assert (
        result.provider_identity_key
        is not None
    )

    assert (
        result.provider_identity_json
        is not None
    )

    assert (
        result.provider_identity_sha256
        is not None
    )

    assert (
        result.canonical_career_url
        is not None
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://jobs.le\nver.co/example",
        "https://jobs.le\rver.co/example",
        "https://jobs.le\tver.co/example",
        "\x01https://jobs.lever.co/example",
        "https://jobs.lever.co/\x00example",
    ],
)
def test_ascii_control_characters_rejected(
    url,
):
    with pytest.raises(
        ATSIdentificationError
    ):
        identify_career_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://jobs.lever.co\uff0fexample",
        "https://jobs.lever.co\uff20evil.example/example",
        "https://jobs.lever.co\uff1a443/example",
    ],
)
def test_invalid_nfkc_netloc_wrapped_as_domain_error(
    url,
):
    with pytest.raises(
        ATSIdentificationError
    ):
        identify_career_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://td.wd3.myworkdayjobs.com/en-US",
        "https://td.wd3.myworkdayjobs.com/en-US/",
        "https://td.wd3.myworkdayjobs.com/fr-CA",
        "https://td.wd3.myworkdayjobs.com/fr-CA/",
    ],
)
def test_workday_locale_only_is_provider_only(
    url,
):
    result = identify_career_url(url)

    assert (
        result.status
        == ATSIdentificationStatus
        .ATS_IDENTIFIED
    )

    assert (
        result.provider_kind
        == "workday"
    )

    assert (
        result.provider_identity_key
        is None
    )


def test_workday_locale_plus_site_still_identifies_endpoint():

    result = identify_career_url(
        "https://td.wd3.myworkdayjobs.com/"
        "en-US/TD_Bank_Careers"
    )

    assert (
        result.status
        == ATSIdentificationStatus
        .ENDPOINT_IDENTIFIED
    )

    expected = canonicalize_provider_identity(
        "workday",
        {
            "host":
                "td.wd3.myworkdayjobs.com",
            "tenant":
                "td",
            "site":
                "TD_Bank_Careers",
        },
    )

    assert (
        result.provider_identity_key
        == expected.provider_identity_key
    )
