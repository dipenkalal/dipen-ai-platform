from gateway.research_engine_health_probe import (
    Phase16EngineProbeResult,
    infer_suspected_failure_mode,
)
from gateway.searxng_search_provider import SearXNGEngineFailure


def _probe(
    *,
    probe_id: str,
    role: str,
    outcome: str,
    failures: tuple[SearXNGEngineFailure, ...] = (),
) -> Phase16EngineProbeResult:
    return Phase16EngineProbeResult(
        probe_id=probe_id,
        query="bounded engine probe query",
        role=role,
        outcome=outcome,
        provider_result_count=10 if outcome == "results" else 0,
        accepted_candidate_count=3 if outcome == "results" else 0,
        unresponsive_engines=failures,
    )


def test_rate_limit_or_suspension_is_engine_blocking() -> None:
    probes = (
        _probe(
            probe_id="control",
            role="control",
            outcome="zero-results",
            failures=(
                SearXNGEngineFailure(
                    engine_name="startpage",
                    failure_class="too-many-requests",
                    suspended=True,
                ),
            ),
        ),
    )

    assert infer_suspected_failure_mode(probes) == "upstream-engine-blocking"


def test_controls_succeed_but_non_control_zero_is_query_specific() -> None:
    probes = (
        _probe(probe_id="control-a", role="control", outcome="results"),
        _probe(probe_id="standard", role="standards", outcome="zero-results"),
        _probe(probe_id="control-b", role="control", outcome="results"),
    )

    assert infer_suspected_failure_mode(probes) == "query-specific-zero-results"


def test_transport_error_is_classified_separately() -> None:
    probes = (
        _probe(
            probe_id="control",
            role="control",
            outcome="provider-transport-error",
        ),
    )

    assert infer_suspected_failure_mode(probes) == "provider-transport-instability"


def test_probe_contract_does_not_record_provider_or_raw_engine_text() -> None:
    probe = _probe(
        probe_id="control",
        role="control",
        outcome="zero-results",
        failures=(
            SearXNGEngineFailure(
                engine_name="brave",
                failure_class="captcha",
            ),
        ),
    )
    dumped = probe.model_dump(mode="json")

    assert dumped["provider_titles_or_snippets_recorded"] is False
    assert dumped["raw_engine_error_text_recorded"] is False
    assert dumped["unresponsive_engines"][0]["raw_error_text_recorded"] is False
    assert "title" not in dumped
    assert "snippet" not in dumped
