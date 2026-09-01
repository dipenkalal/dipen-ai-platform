from datetime import datetime, timezone

import pytest

from career.ats_identification import identify_career_url
from career.source_discovery import DiscoveryState
from career.source_discovery_generation import (
    DiscoveryGenerationError,
    discovery_candidate_id_for,
    generate_discovery_candidate,
)


AT = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)


def generate(
    url: str,
    *,
    employer: str = "Example Employer",
    evidence: str = "research-evidence-1",
    at: datetime = AT,
):
    identification = identify_career_url(url)
    return generate_discovery_candidate(
        employer_name=employer,
        identification=identification,
        discovery_research_evidence_id=evidence,
        observed_at=at,
    )


def test_unrecognized_maps_to_discovered():
    candidate = generate("https://example.com/careers")

    assert candidate.state is DiscoveryState.DISCOVERED
    assert candidate.provider_kind is None
    assert candidate.provider_identity_key is None
    assert candidate.canonical_career_url is None


def test_provider_only_maps_to_ats_identified():
    candidate = generate("https://jobs.lever.co/")

    assert candidate.state is DiscoveryState.ATS_IDENTIFIED
    assert candidate.provider_kind == "lever"
    assert candidate.provider_identity_key is None
    assert candidate.provider_identity_json is None
    assert candidate.provider_identity_sha256 is None
    assert candidate.canonical_career_url is None


def test_endpoint_maps_to_endpoint_candidate():
    candidate = generate(
        "https://jobs.lever.co/shyftlabs",
        employer="ShyftLabs",
    )

    assert candidate.state is DiscoveryState.ENDPOINT_CANDIDATE
    assert candidate.provider_kind == "lever"
    assert candidate.provider_identity_key is not None
    assert candidate.canonical_career_url is not None


def test_discovery_evidence_is_propagated_exactly():
    candidate = generate(
        "https://jobs.ashbyhq.com/sentry",
        evidence="research-evidence-xyz",
    )

    assert (
        candidate.discovery_research_evidence_id
        == "research-evidence-xyz"
    )


def test_generator_never_manufactures_downstream_evidence_or_admission():
    candidate = generate("https://jobs.ashbyhq.com/sentry")

    assert candidate.listing_research_evidence_id is None
    assert candidate.detail_research_evidence_id is None
    assert candidate.admitted_source_id is None
    assert candidate.last_error_code is None


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/careers",
        "https://jobs.lever.co/",
        "https://jobs.lever.co/shyftlabs",
    ],
)
def test_generator_maximum_state_is_endpoint_candidate(url):
    candidate = generate(url)

    assert candidate.state in {
        DiscoveryState.DISCOVERED,
        DiscoveryState.ATS_IDENTIFIED,
        DiscoveryState.ENDPOINT_CANDIDATE,
    }

    assert candidate.state not in {
        DiscoveryState.LISTING_PROVEN,
        DiscoveryState.DETAIL_PROVEN,
        DiscoveryState.ADMISSION_READY,
        DiscoveryState.ADMITTED,
    }


def test_discovery_candidate_namespace_is_distinct():
    candidate = generate("https://jobs.lever.co/shyftlabs")

    assert candidate.discovery_candidate_id.startswith(
        "career-discovery-candidate-"
    )
    assert not candidate.discovery_candidate_id.startswith(
        "career-source-key-"
    )
    assert not candidate.discovery_candidate_id.startswith(
        "career-provider-key-"
    )


def test_timestamp_and_evidence_are_not_identity_inputs():
    identification = identify_career_url(
        "https://jobs.lever.co/shyftlabs"
    )

    first = generate_discovery_candidate(
        employer_name="ShyftLabs",
        identification=identification,
        discovery_research_evidence_id="research-1",
        observed_at=datetime(
            2026, 9, 1, 0, 0, tzinfo=timezone.utc
        ),
    )

    second = generate_discovery_candidate(
        employer_name="ShyftLabs",
        identification=identification,
        discovery_research_evidence_id="research-2",
        observed_at=datetime(
            2026, 9, 2, 0, 0, tzinfo=timezone.utc
        ),
    )

    assert (
        first.discovery_candidate_id
        == second.discovery_candidate_id
    )


def test_endpoint_identity_ignores_employer_display_spelling():
    identification = identify_career_url(
        "https://jobs.lever.co/shyftlabs"
    )

    left = discovery_candidate_id_for(
        employer_name="ShyftLabs",
        identification=identification,
    )
    right = discovery_candidate_id_for(
        employer_name="SHYFT LABS INC.",
        identification=identification,
    )

    assert left == right


@pytest.mark.parametrize(
    ("canonical_url", "detail_url"),
    [
        (
            "https://job-boards.greenhouse.io/lush",
            "https://job-boards.greenhouse.io/lush/jobs/123456",
        ),
        (
            "https://jobs.lever.co/shyftlabs",
            "https://jobs.lever.co/shyftlabs/123456",
        ),
        (
            "https://jobs.ashbyhq.com/sentry",
            "https://jobs.ashbyhq.com/sentry/123456",
        ),
    ],
)
def test_canonical_and_detail_urls_converge(
    canonical_url,
    detail_url,
):
    canonical = generate(
        canonical_url,
        employer="Convergence Employer",
    )
    detail = generate(
        detail_url,
        employer="Convergence Employer",
    )

    assert canonical.state is DiscoveryState.ENDPOINT_CANDIDATE
    assert detail.state is DiscoveryState.ENDPOINT_CANDIDATE

    assert (
        canonical.provider_identity_key
        == detail.provider_identity_key
    )
    assert (
        canonical.discovery_candidate_id
        == detail.discovery_candidate_id
    )


def test_smartrecruiters_public_and_api_urls_converge():
    public = generate(
        "https://careers.smartrecruiters.com/ServiceNow",
        employer="ServiceNow",
    )
    api = generate(
        "https://api.smartrecruiters.com/v1/companies/"
        "ServiceNow/postings",
        employer="ServiceNow",
    )

    assert public.state is DiscoveryState.ENDPOINT_CANDIDATE
    assert api.state is DiscoveryState.ENDPOINT_CANDIDATE

    assert public.provider_identity_key == api.provider_identity_key
    assert public.discovery_candidate_id == api.discovery_candidate_id


def test_workday_locale_variants_converge():
    no_locale = generate(
        "https://td.wd3.myworkdayjobs.com/TD_Bank_Careers",
        employer="TD",
    )
    english = generate(
        "https://td.wd3.myworkdayjobs.com/en-US/"
        "TD_Bank_Careers",
        employer="TD",
    )
    french = generate(
        "https://td.wd3.myworkdayjobs.com/fr-CA/"
        "TD_Bank_Careers",
        employer="TD",
    )

    ids = {
        no_locale.discovery_candidate_id,
        english.discovery_candidate_id,
        french.discovery_candidate_id,
    }

    provider_keys = {
        no_locale.provider_identity_key,
        english.provider_identity_key,
        french.provider_identity_key,
    }

    assert len(ids) == 1
    assert len(provider_keys) == 1


def test_query_and_fragment_variants_converge():
    base = generate(
        "https://jobs.lever.co/shyftlabs",
        employer="ShyftLabs",
    )
    variant = generate(
        "https://jobs.lever.co/shyftlabs"
        "?department=engineering#jobs",
        employer="ShyftLabs",
    )

    assert (
        base.provider_identity_key
        == variant.provider_identity_key
    )
    assert (
        base.discovery_candidate_id
        == variant.discovery_candidate_id
    )


def test_provider_only_query_and_fragment_variants_converge():
    base = generate(
        "https://jobs.lever.co/",
        employer="Unknown Employer",
    )
    variant = generate(
        "https://jobs.lever.co/?x=1#fragment",
        employer="Unknown Employer",
    )

    assert base.state is DiscoveryState.ATS_IDENTIFIED
    assert variant.state is DiscoveryState.ATS_IDENTIFIED
    assert (
        base.discovery_candidate_id
        == variant.discovery_candidate_id
    )


def test_workday_locale_only_provider_observations_converge():
    english = generate(
        "https://td.wd3.myworkdayjobs.com/en-US",
        employer="TD",
    )
    french = generate(
        "https://td.wd3.myworkdayjobs.com/fr-CA",
        employer="TD",
    )

    assert english.state is DiscoveryState.ATS_IDENTIFIED
    assert french.state is DiscoveryState.ATS_IDENTIFIED

    assert (
        english.discovery_candidate_id
        == french.discovery_candidate_id
    )


def test_endpoint_copies_exact_sealed_provider_fields():
    identification = identify_career_url(
        "https://td.wd3.myworkdayjobs.com/en-US/"
        "TD_Bank_Careers"
    )

    candidate = generate_discovery_candidate(
        employer_name="TD",
        identification=identification,
        discovery_research_evidence_id="research-td",
        observed_at=AT,
    )

    assert candidate.provider_kind == identification.provider_kind
    assert (
        candidate.provider_identity_key
        == identification.provider_identity_key
    )
    assert (
        candidate.provider_identity_json
        == identification.provider_identity_json
    )
    assert (
        candidate.provider_identity_sha256
        == identification.provider_identity_sha256
    )
    assert (
        candidate.canonical_career_url
        == identification.canonical_career_url
    )


def test_same_provider_endpoint_converges_across_employer_labels():
    left = generate(
        "https://jobs.ashbyhq.com/sentry",
        employer="Sentry",
    )
    right = generate(
        "https://jobs.ashbyhq.com/sentry/jobs/anything",
        employer="Sentry Software",
    )

    assert left.provider_identity_key == right.provider_identity_key
    assert left.discovery_candidate_id == right.discovery_candidate_id


def test_unrecognized_query_fragment_variants_converge():
    first = generate(
        "https://example.com/careers?src=one#jobs",
        employer="Example",
    )
    second = generate(
        "https://example.com/careers?src=two#different",
        employer="Example",
    )

    assert first.state is DiscoveryState.DISCOVERED
    assert second.state is DiscoveryState.DISCOVERED
    assert first.discovery_candidate_id == second.discovery_candidate_id


def test_employer_case_and_spacing_normalize_before_partial_identity():
    first = generate(
        "https://jobs.lever.co/",
        employer="Example Employer",
    )
    second = generate(
        "https://jobs.lever.co/",
        employer="example   employer",
    )

    assert first.discovery_candidate_id == second.discovery_candidate_id


def test_evidence_id_surrounding_whitespace_is_rejected():
    identification = identify_career_url(
        "https://jobs.lever.co/shyftlabs"
    )

    with pytest.raises(DiscoveryGenerationError):
        generate_discovery_candidate(
            employer_name="ShyftLabs",
            identification=identification,
            discovery_research_evidence_id=" evidence-1 ",
            observed_at=AT,
        )
