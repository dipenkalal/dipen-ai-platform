from __future__ import annotations

import pytest

from gateway.internet_destination_policy import (
    InternetDestinationIntent,
    InternetDestinationPolicy,
    InternetDestinationRequest,
)

PUBLIC_IPV4 = "93.184.216.34"
PUBLIC_IPV6 = "2606:4700:4700::1111"


def _decision(
    url: str,
    *,
    addresses: tuple[str, ...] = (PUBLIC_IPV4,),
    method: str = "GET",
    redirect_depth: int = 0,
):
    return InternetDestinationPolicy().evaluate(
        InternetDestinationRequest(
            url=url,
            method=method,
            resolved_addresses=addresses,
            redirect_depth=redirect_depth,
        )
    )


def test_public_https_preflight_is_safe_to_resolve_but_performs_no_dns() -> None:
    preflight = InternetDestinationPolicy().preflight(
        InternetDestinationIntent(
            url="https://Example.COM/research?q=dap#fragment",
            method=" get ",
        )
    )

    assert preflight.disposition == "accepted"
    assert preflight.findings == ()
    assert preflight.admission is not None
    assert preflight.admission.canonical_url == "https://example.com/research?q=dap"
    assert preflight.admission.hostname == "example.com"
    assert preflight.admission.method == "GET"
    assert preflight.admission.dns_resolution_performed is False
    assert preflight.admission.transport_execution_enabled is False


def test_public_https_destination_is_admitted_deterministically() -> None:
    first = _decision("https://Example.COM/research?q=dap#fragment")
    second = _decision("https://example.com/research?q=dap")

    assert first.disposition == "accepted"
    assert first.findings == ()
    assert first.admission is not None
    assert first.admission == second.admission
    assert first.admission.canonical_url == "https://example.com/research?q=dap"
    assert first.admission.approved_addresses == (PUBLIC_IPV4,)
    assert first.admission.transport_execution_enabled is False
    assert first.admission.redirect_revalidation_required is True


def test_head_is_allowed_but_mutating_methods_are_rejected() -> None:
    head = _decision("https://example.com/", method=" head ")
    post = _decision("https://example.com/", method="POST")

    assert head.disposition == "accepted"
    assert post.disposition == "rejected"
    assert {finding.rule_id for finding in post.findings} == {"unsupported-method"}


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/",
        "file:///etc/passwd",
        "data:text/plain,hello",
        "javascript:alert(1)",
    ],
)
def test_non_https_schemes_are_rejected_before_dns(url: str) -> None:
    preflight = InternetDestinationPolicy().preflight(
        InternetDestinationIntent(url=url)
    )
    decision = _decision(url)

    assert preflight.disposition == "rejected"
    assert decision.disposition == "rejected"
    assert "unsupported-scheme" in {finding.rule_id for finding in decision.findings}


def test_credential_bearing_urls_are_rejected_before_dns() -> None:
    url = "https://owner:secret@example.com/research"
    preflight = InternetDestinationPolicy().preflight(InternetDestinationIntent(url=url))
    decision = _decision(url)

    assert preflight.disposition == "rejected"
    assert decision.disposition == "rejected"
    assert "url-credentials" in {finding.rule_id for finding in decision.findings}


@pytest.mark.parametrize(
    "hostname",
    [
        "localhost",
        "api.localhost",
        "service.local",
        "db.internal",
        "host.docker.internal",
        "gateway.docker.internal",
        "metadata.google.internal",
    ],
)
def test_local_internal_and_container_hostnames_are_rejected_before_dns(
    hostname: str,
) -> None:
    url = f"https://{hostname}/"
    preflight = InternetDestinationPolicy().preflight(InternetDestinationIntent(url=url))
    decision = _decision(url)

    assert preflight.disposition == "rejected"
    assert decision.disposition == "rejected"
    assert "blocked-hostname" in {finding.rule_id for finding in decision.findings}


@pytest.mark.parametrize(
    "url",
    [
        "https://exa mple.com/",
        "https://bad_label.example/",
        "https://-bad.example/",
        "https://bad-.example/",
    ],
)
def test_invalid_hostname_syntax_is_rejected_before_dns(url: str) -> None:
    preflight = InternetDestinationPolicy().preflight(InternetDestinationIntent(url=url))

    assert preflight.disposition == "rejected"
    assert "invalid-hostname" in {finding.rule_id for finding in preflight.findings}


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "127.0.0.1",
        "169.254.169.254",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
    ],
)
def test_non_public_resolved_addresses_are_rejected(address: str) -> None:
    decision = _decision("https://example.com/", addresses=(address,))

    assert decision.disposition == "rejected"
    assert "non-public-address" in {finding.rule_id for finding in decision.findings}


def test_mixed_public_and_private_dns_answers_fail_closed() -> None:
    decision = _decision(
        "https://example.com/",
        addresses=(PUBLIC_IPV4, "127.0.0.1"),
    )

    assert decision.disposition == "rejected"
    assert decision.admission is None


def test_invalid_resolver_output_is_rejected() -> None:
    decision = _decision("https://example.com/", addresses=("not-an-ip",))

    assert decision.disposition == "rejected"
    assert "invalid-resolved-address" in {
        finding.rule_id for finding in decision.findings
    }


def test_nonstandard_https_port_is_rejected_before_dns() -> None:
    url = "https://example.com:8443/research"
    preflight = InternetDestinationPolicy().preflight(InternetDestinationIntent(url=url))
    decision = _decision(url)

    assert preflight.disposition == "rejected"
    assert decision.disposition == "rejected"
    assert "unsupported-port" in {finding.rule_id for finding in decision.findings}


def test_public_ipv6_dns_answer_is_admitted() -> None:
    decision = _decision("https://example.com/", addresses=(PUBLIC_IPV6,))

    assert decision.disposition == "accepted"
    assert decision.admission is not None
    assert decision.admission.approved_addresses == (PUBLIC_IPV6,)


def test_ip_literal_must_match_resolver_supplied_address() -> None:
    matched = _decision(f"https://{PUBLIC_IPV4}/", addresses=(PUBLIC_IPV4,))
    mismatched = _decision(f"https://{PUBLIC_IPV4}/", addresses=(PUBLIC_IPV6,))

    assert matched.disposition == "accepted"
    assert mismatched.disposition == "rejected"
    assert "literal-address-mismatch" in {
        finding.rule_id for finding in mismatched.findings
    }


def test_redirect_depth_is_bound_into_destination_admission() -> None:
    direct = _decision("https://example.com/final", redirect_depth=0)
    redirected = _decision("https://example.com/final", redirect_depth=1)

    assert direct.admission is not None
    assert redirected.admission is not None
    assert direct.admission.admission_sha256 != redirected.admission.admission_sha256
    assert redirected.admission.redirect_depth == 1


def test_redirect_depth_above_policy_cap_fails_validation() -> None:
    with pytest.raises(ValueError):
        InternetDestinationRequest(
            url="https://example.com/",
            resolved_addresses=(PUBLIC_IPV4,),
            redirect_depth=4,
        )


def test_duplicate_resolved_addresses_fail_validation() -> None:
    with pytest.raises(ValueError, match="resolved addresses must be unique"):
        InternetDestinationRequest(
            url="https://example.com/",
            resolved_addresses=(PUBLIC_IPV4, PUBLIC_IPV4),
        )
