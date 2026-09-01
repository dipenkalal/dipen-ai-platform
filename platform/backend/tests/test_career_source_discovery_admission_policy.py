from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from career.ats_identification import (
    identify_career_url,
)
from career.source_discovery import (
    DiscoveryState,
    transition_candidate,
)
from career.source_discovery_admission_policy import (
    ADMISSION_READINESS_POLICY_ID,
    SourceAdmissionPolicyError,
    advance_to_admission_ready,
    evaluate_admission_readiness,
)
from career.source_discovery_generation import (
    generate_discovery_candidate,
)


AT = datetime(
    2026, 9, 1, 5, 0,
    tzinfo=timezone.utc,
)


def endpoint():
    return generate_discovery_candidate(
        employer_name="ServiceNow",
        identification=(
            identify_career_url(
                "https://careers.smartrecruiters.com/"
                "ServiceNow"
            )
        ),
        discovery_research_evidence_id=(
            "research-retrieval-"
            "111111111111111111111111"
        ),
        observed_at=AT,
    )


def detail_proven():
    value = endpoint()

    value = transition_candidate(
        value,
        DiscoveryState.LISTING_PROVEN,
        at=AT + timedelta(minutes=1),
        listing_research_evidence_id=(
            "research-retrieval-"
            "222222222222222222222222"
        ),
    )

    return transition_candidate(
        value,
        DiscoveryState.DETAIL_PROVEN,
        at=AT + timedelta(minutes=2),
        detail_research_evidence_id=(
            "research-retrieval-"
            "333333333333333333333333"
        ),
    )


def test_policy_id_is_frozen():
    assert (
        ADMISSION_READINESS_POLICY_ID
        == "career-source-admission-readiness-v1"
    )


def test_detail_proven_candidate_is_eligible():
    decision = (
        evaluate_admission_readiness(
            detail_proven()
        )
    )

    assert decision.eligible is True
    assert decision.reason_codes == ()


def test_decision_is_deterministic():
    value = detail_proven()

    first = (
        evaluate_admission_readiness(
            value
        )
    )

    second = (
        evaluate_admission_readiness(
            value
        )
    )

    assert first == second


@pytest.mark.parametrize(
    "state",
    [
        DiscoveryState.DISCOVERED,
        DiscoveryState.ATS_IDENTIFIED,
        DiscoveryState.ENDPOINT_CANDIDATE,
        DiscoveryState.LISTING_PROVEN,
    ],
)
def test_pre_detail_states_are_not_eligible(
    state,
):
    value = detail_proven()

    # Build valid objects through the normal
    # progression rather than corrupting state.
    if state is DiscoveryState.DISCOVERED:
        unknown = generate_discovery_candidate(
            employer_name="Unknown",
            identification=(
                identify_career_url(
                    "https://example.com/careers"
                )
            ),
            discovery_research_evidence_id=(
                "research-retrieval-"
                "444444444444444444444444"
            ),
            observed_at=AT,
        )
        value = unknown

    elif state is DiscoveryState.ATS_IDENTIFIED:
        value = generate_discovery_candidate(
            employer_name="Unknown",
            identification=(
                identify_career_url(
                    "https://jobs.lever.co/"
                )
            ),
            discovery_research_evidence_id=(
                "research-retrieval-"
                "444444444444444444444444"
            ),
            observed_at=AT,
        )

    elif state is DiscoveryState.ENDPOINT_CANDIDATE:
        value = endpoint()

    elif state is DiscoveryState.LISTING_PROVEN:
        value = transition_candidate(
            endpoint(),
            DiscoveryState.LISTING_PROVEN,
            at=AT + timedelta(minutes=1),
            listing_research_evidence_id=(
                "research-retrieval-"
                "222222222222222222222222"
            ),
        )

    decision = (
        evaluate_admission_readiness(
            value
        )
    )

    assert decision.eligible is False
    assert (
        "state-not-detail-proven"
        in decision.reason_codes
    )


def test_policy_advances_exactly_one_state():
    value = detail_proven()

    advanced = (
        advance_to_admission_ready(
            value,
            at=AT + timedelta(minutes=3),
        )
    )

    assert (
        advanced.state
        is DiscoveryState.ADMISSION_READY
    )

    assert (
        advanced.provider_identity_key
        == value.provider_identity_key
    )

    assert (
        advanced.listing_research_evidence_id
        == value.listing_research_evidence_id
    )

    assert (
        advanced.detail_research_evidence_id
        == value.detail_research_evidence_id
    )

    assert advanced.admitted_source_id is None


def test_policy_does_not_create_source_binding():
    advanced = (
        advance_to_admission_ready(
            detail_proven(),
            at=AT + timedelta(minutes=3),
        )
    )

    assert advanced.admitted_source_id is None


def test_endpoint_candidate_cannot_skip_validation():
    with pytest.raises(
        SourceAdmissionPolicyError,
        match="state-not-detail-proven",
    ):
        advance_to_admission_ready(
            endpoint(),
            at=AT + timedelta(minutes=3),
        )


def test_policy_source_has_no_database_network_or_registry_authority():
    import ast
    from pathlib import Path

    path = Path(
        "career/"
        "source_discovery_admission_policy.py"
    )

    tree = ast.parse(
        path.read_text()
    )

    forbidden_modules = {
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

    violations = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(
                    alias.name == item
                    or alias.name.startswith(
                        item + "."
                    )
                    for item in forbidden_modules
                ):
                    violations.append(
                        alias.name
                    )

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""

            if any(
                module == item
                or module.startswith(
                    item + "."
                )
                for item in forbidden_modules
            ):
                violations.append(
                    module
                )

    assert violations == []



def test_policy_has_no_final_source_binding_assignment():
    from pathlib import Path

    text = Path(
        "career/"
        "source_discovery_admission_policy.py"
    ).read_text()

    assert "admitted_source_id=" not in text
