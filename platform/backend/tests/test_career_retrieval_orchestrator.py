from __future__ import annotations

import hashlib
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest
from pydantic import ValidationError

from career.connectors.contracts import (
    CareerConnectorParseInput,
    CareerConnectorResult,
)
from career.connectors.greenhouse import (
    GreenhouseJobBoardConnector,
)
from career.retrieval import (
    CareerPhase16RetrievalBundle,
    CareerRetrievalOrchestrationError,
    CareerRetrievalOrchestrator,
    Phase16CareerRetrievalGateway,
)
from gateway.internet_transport import (
    InternetRetrievalResult,
)
from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
)
from gateway.research_retrieval_evidence import (
    ResearchRetrievalEvidenceFactory,
)
from gateway.untrusted_internet_content import (
    UntrustedInternetContentNormalizer,
)


NOW = datetime(
    2026,
    8,
    20,
    21,
    0,
    tzinfo=timezone.utc,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "career"
    / "greenhouse_jobs.json"
)


def _connector() -> GreenhouseJobBoardConnector:
    return GreenhouseJobBoardConnector(
        board_token="acme",
        employer_name="Acme",
    )


def _phase16_objects(
    *,
    media_type: str = "application/json",
    final_url: str | None = None,
):
    connector = _connector()
    requested_url = connector.jobs_url

    if media_type == "application/json":
        body = FIXTURE.read_bytes()
    else:
        body = b"plain-text-phase16-evidence"

    final_url = final_url or requested_url

    retrieval = InternetRetrievalResult(
        requested_url=requested_url,
        final_url=final_url,
        method="GET",
        status_code=200,
        reason="OK",
        content_type=media_type,
        content_length=len(body),
        body=body,
        body_sha256=hashlib.sha256(
            body
        ).hexdigest(),
        byte_count=len(body),
        hops=(),
    )

    content = (
        UntrustedInternetContentNormalizer()
        .normalize(retrieval)
    )

    request = research_request_factory.build(
        ResearchRequestIntent(
            objective=(
                "Discover public Greenhouse jobs"
            ),
            source_kinds=("public_web",),
            max_sources=1,
        )
    )

    evidence = (
        ResearchRetrievalEvidenceFactory()
        .build_success(
            request=request,
            retrieval=retrieval,
            content=content,
            observed_at=NOW,
        )
    )

    return (
        requested_url,
        retrieval,
        content,
        evidence,
    )


def _bundle(
    *,
    media_type: str = "application/json",
) -> CareerPhase16RetrievalBundle:
    (
        requested_url,
        _retrieval,
        content,
        evidence,
    ) = _phase16_objects(
        media_type=media_type
    )

    return CareerPhase16RetrievalBundle(
        requested_url=requested_url,
        retrieval_evidence=evidence,
        content_evidence=content,
    )


class FakePhase16Gateway:
    def __init__(
        self,
        bundle: CareerPhase16RetrievalBundle,
    ) -> None:
        self.bundle = bundle
        self.calls: list[
            tuple[str, str]
        ] = []

    async def retrieve_public_url(
        self,
        *,
        objective: str,
        url: str,
    ) -> CareerPhase16RetrievalBundle:
        self.calls.append(
            (
                objective,
                url,
            )
        )

        return self.bundle


def test_bundle_binds_phase16_retrieval_and_content() -> None:
    bundle = _bundle()

    evidence = bundle.retrieval_evidence
    content = bundle.content_evidence

    assert evidence.outcome == "succeeded"
    assert evidence.stage == "completed"
    assert evidence.method == "GET"

    assert (
        evidence.content_evidence_id
        == content.evidence_id
    )

    assert (
        evidence.normalized_text_sha256
        == content.normalized_text_sha256
    )

    assert (
        bundle.network_execution_owner
        == "phase16-research-gateway"
    )

    assert (
        bundle.career_truth_mutation_allowed
        is False
    )

    assert (
        bundle.application_authority_granted
        is False
    )


def test_bundle_rejects_redirected_final_url() -> None:
    (
        requested_url,
        _retrieval,
        content,
        evidence,
    ) = _phase16_objects(
        final_url=(
            "https://boards-api.greenhouse.io/"
            "v1/boards/other/jobs"
        )
    )

    with pytest.raises(
        ValidationError,
        match="Redirected final URL",
    ):
        CareerPhase16RetrievalBundle(
            requested_url=requested_url,
            retrieval_evidence=evidence,
            content_evidence=content,
        )


def test_bundle_rejects_content_hash_mismatch() -> None:
    (
        requested_url,
        _retrieval,
        content,
        evidence,
    ) = _phase16_objects()

    tampered = content.model_copy(
        update={
            "normalized_text_sha256":
                "0" * 64
        }
    )

    with pytest.raises(
        ValidationError,
        match="Normalized text hash",
    ):
        CareerPhase16RetrievalBundle(
            requested_url=requested_url,
            retrieval_evidence=evidence,
            content_evidence=tampered,
        )


@pytest.mark.asyncio
async def test_orchestrator_parses_greenhouse_bundle() -> None:
    bundle = _bundle()
    gateway = FakePhase16Gateway(
        bundle
    )

    orchestrator = (
        CareerRetrievalOrchestrator(
            gateway
        )
    )

    result = (
        await orchestrator.retrieve_candidates(
            connector=_connector(),
            objective=(
                "Discover public Greenhouse jobs"
            ),
            source_url=(
                _connector().jobs_url
            ),
        )
    )

    assert result.candidate_count == 2

    assert [
        candidate.source_job_id
        for candidate in result.candidates
    ] == [
        "900001",
        "900002",
    ]


@pytest.mark.asyncio
async def test_orchestrator_calls_gateway_once_exactly() -> None:
    bundle = _bundle()
    gateway = FakePhase16Gateway(
        bundle
    )

    orchestrator = (
        CareerRetrievalOrchestrator(
            gateway
        )
    )

    await orchestrator.retrieve_candidates(
        connector=_connector(),
        objective=(
            "  Discover Greenhouse jobs  "
        ),
        source_url=_connector().jobs_url,
    )

    assert gateway.calls == [
        (
            "Discover Greenhouse jobs",
            _connector().jobs_url,
        )
    ]


@pytest.mark.asyncio
async def test_short_objective_rejected_before_gateway() -> None:
    gateway = FakePhase16Gateway(
        _bundle()
    )

    orchestrator = (
        CareerRetrievalOrchestrator(
            gateway
        )
    )

    with pytest.raises(
        CareerRetrievalOrchestrationError,
        match="at least 3",
    ):
        await orchestrator.retrieve_candidates(
            connector=_connector(),
            objective="x",
            source_url=_connector().jobs_url,
        )

    assert gateway.calls == []


@pytest.mark.asyncio
async def test_connector_media_type_gate_fails_closed() -> None:
    gateway = FakePhase16Gateway(
        _bundle(
            media_type="text/plain"
        )
    )

    orchestrator = (
        CareerRetrievalOrchestrator(
            gateway
        )
    )

    with pytest.raises(
        CareerRetrievalOrchestrationError,
        match="media type",
    ):
        await orchestrator.retrieve_candidates(
            connector=_connector(),
            objective=(
                "Discover Greenhouse jobs"
            ),
            source_url=_connector().jobs_url,
        )


@pytest.mark.asyncio
async def test_cross_provenance_result_is_rejected() -> None:
    bundle = _bundle()

    class CrossProvenanceConnector:
        @property
        def descriptor(self):
            return _connector().descriptor

        def parse_candidates(
            self,
            parse_input:
                CareerConnectorParseInput,
        ) -> CareerConnectorResult:
            wrong = parse_input.model_copy(
                update={
                    "research_evidence_id": (
                        "research-retrieval-"
                        "333333333333333333333333"
                    )
                }
            )

            return CareerConnectorResult.build(
                connector_id=(
                    self.descriptor.connector_id
                ),
                parse_input=wrong,
                candidates=(),
            )

    orchestrator = (
        CareerRetrievalOrchestrator(
            FakePhase16Gateway(
                bundle
            )
        )
    )

    with pytest.raises(
        CareerRetrievalOrchestrationError,
        match="research evidence",
    ):
        await orchestrator.retrieve_candidates(
            connector=CrossProvenanceConnector(),
            objective=(
                "Discover Greenhouse jobs"
            ),
            source_url=_connector().jobs_url,
        )


@pytest.mark.asyncio
async def test_result_remains_non_authoritative() -> None:
    orchestrator = (
        CareerRetrievalOrchestrator(
            FakePhase16Gateway(
                _bundle()
            )
        )
    )

    result = (
        await orchestrator.retrieve_candidates(
            connector=_connector(),
            objective=(
                "Discover Greenhouse jobs"
            ),
            source_url=_connector().jobs_url,
        )
    )

    assert result.metadata_is_job_truth is False

    assert (
        result.production_truth_mutation_allowed
        is False
    )

    assert (
        result.application_authority_granted
        is False
    )

    for candidate in result.candidates:
        assert (
            candidate.metadata_is_job_truth
            is False
        )

        assert (
            candidate.freshness_verified
            is False
        )

        assert (
            candidate.eligible_for_scoring
            is False
        )

        assert (
            candidate.eligible_for_shortlist
            is False
        )


def test_gateway_protocol_is_runtime_checkable() -> None:
    gateway = FakePhase16Gateway(
        _bundle()
    )

    assert isinstance(
        gateway,
        Phase16CareerRetrievalGateway,
    )


def test_bundle_uses_raw_normalized_content_not_prompt_envelope() -> None:
    bundle = _bundle()

    content = bundle.content_evidence

    assert content.normalized_text

    assert (
        "DAP UNTRUSTED INTERNET EVIDENCE"
        not in content.normalized_text
    )

    assert (
        hashlib.sha256(
            content.normalized_text.encode(
                "utf-8"
            )
        ).hexdigest()
        == content.normalized_text_sha256
    )
