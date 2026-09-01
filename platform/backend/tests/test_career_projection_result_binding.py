from __future__ import annotations

import hashlib
from datetime import (
    datetime,
    timezone,
)

import pytest

from career.connectors.contracts import (
    CareerConnectorDescriptor,
    CareerConnectorParseInput,
    CareerConnectorResult,
    CareerDiscoveryCandidate,
)
from career.connectors.lever import (
    LEVER_CONNECTOR_ID,
)
from career.retrieval import (
    CareerPhase16RetrievalBundle,
    CareerRetrievalOrchestrationError,
    CareerRetrievalOrchestrator,
)
from gateway.research_retrieval_evidence import (
    ResearchRetrievalEvidence,
)
from gateway.structured_json_projection import (
    StructuredJSONProjectionEvidence,
)
from gateway.untrusted_internet_content import (
    UntrustedInternetEvidence,
)

SOURCE_URL = "https://api.lever.co/v0/postings/projection-binding-test?mode=json"

OBSERVED_AT = datetime(
    2026,
    8,
    24,
    19,
    0,
    tzinfo=timezone.utc,
)

SOURCE_BODY_SHA = "a" * 64

RESEARCH_EVIDENCE_ID = "research-retrieval-0123456789abcdef01234567"

CONTENT_EVIDENCE_ID = "internet-content-0123456789abcdef01234567"

PROJECTION_EVIDENCE_ID = "structured-json-projection-0123456789abcdef01234567"

NORMALIZED_TEXT = '[{"id":"normalized-prefix"}]'

NORMALIZED_SHA = hashlib.sha256(NORMALIZED_TEXT.encode("utf-8")).hexdigest()

PROJECTION_TEXT = '[{"id":"projected-complete"}]'

PROJECTION_SHA = hashlib.sha256(PROJECTION_TEXT.encode("utf-8")).hexdigest()


def _content() -> UntrustedInternetEvidence:
    from hashlib import sha256

    from gateway.internet_transport import (
        InternetRetrievalResult,
    )
    from gateway.research_retrieval_service import (
        build_phase16_structured_content_normalizer,
    )

    body = b'[{"applyUrl":"https://jobs.example.test/apply/job-1","categories":{"commitment":"Full-time","location":"Toronto, ON","team":"Engineering"},"hostedUrl":"https://jobs.example.test/jobs/job-1","id":"job-1","text":"Cloud Engineer"}]'

    retrieval = InternetRetrievalResult(
        requested_url=SOURCE_URL,
        final_url=SOURCE_URL,
        method="GET",
        status_code=200,
        reason="OK",
        content_type="application/json",
        content_length=len(body),
        body=body,
        body_sha256=sha256(body).hexdigest(),
        byte_count=len(body),
        hops=(),
    )

    return build_phase16_structured_content_normalizer().normalize(retrieval)


def _research() -> ResearchRetrievalEvidence:
    from hashlib import sha256

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
    from gateway.research_retrieval_service import (
        build_phase16_structured_content_normalizer,
    )

    body = b'[{"applyUrl":"https://jobs.example.test/apply/job-1","categories":{"commitment":"Full-time","location":"Toronto, ON","team":"Engineering"},"hostedUrl":"https://jobs.example.test/jobs/job-1","id":"job-1","text":"Cloud Engineer"}]'

    retrieval = InternetRetrievalResult(
        requested_url=SOURCE_URL,
        final_url=SOURCE_URL,
        method="GET",
        status_code=200,
        reason="OK",
        content_type="application/json",
        content_length=len(body),
        body=body,
        body_sha256=sha256(body).hexdigest(),
        byte_count=len(body),
        hops=(),
    )

    content = build_phase16_structured_content_normalizer().normalize(retrieval)

    request = research_request_factory.build(
        ResearchRequestIntent(
            objective=("Offline Career structured projection result-binding fixture"),
            source_kinds=("public_web",),
            max_sources=1,
        )
    )

    return ResearchRetrievalEvidenceFactory().build_success(
        request=request,
        retrieval=retrieval,
        content=content,
        observed_at=OBSERVED_AT,
    )


def _projection() -> StructuredJSONProjectionEvidence:
    from hashlib import sha256

    from gateway.structured_json_projection import (
        project_structured_json,
    )

    body = b'[{"applyUrl":"https://jobs.example.test/apply/job-1","categories":{"commitment":"Full-time","location":"Toronto, ON","team":"Engineering"},"hostedUrl":"https://jobs.example.test/jobs/job-1","id":"job-1","text":"Cloud Engineer"}]'

    research = _research()

    return project_structured_json(
        profile_id="lever-list-v1",
        body=body,
        research_evidence_id=(research.evidence_id),
        source_url=SOURCE_URL,
        source_body_sha256=(sha256(body).hexdigest()),
        source_byte_count=len(body),
        source_content_type=("application/json"),
        observed_at=research.observed_at,
    )


def _bundle(
    projection: (StructuredJSONProjectionEvidence | None) = None,
) -> CareerPhase16RetrievalBundle:
    return CareerPhase16RetrievalBundle(
        requested_url=SOURCE_URL,
        retrieval_evidence=_research(),
        content_evidence=_content(),
        projection_evidence=(projection or _projection()),
    )


class _Gateway:
    def __init__(
        self,
        bundle: CareerPhase16RetrievalBundle,
    ) -> None:
        self.bundle = bundle
        self.calls = 0

    async def retrieve_public_url(
        self,
        *,
        objective: str,
        url: str,
    ) -> CareerPhase16RetrievalBundle:
        assert objective
        assert url == SOURCE_URL

        self.calls += 1

        return self.bundle


class _EmptyProjectionConnector:
    def __init__(
        self,
        *,
        tamper_field: str | None = None,
        tamper_value: object = None,
    ) -> None:
        self.tamper_field = tamper_field
        self.tamper_value = tamper_value
        self.seen_input = None

    @property
    def descriptor(
        self,
    ) -> CareerConnectorDescriptor:
        return CareerConnectorDescriptor(
            connector_id=LEVER_CONNECTOR_ID,
            connector_kind="lever",
            display_name=("Projection Binding Test"),
            priority=1,
            response_media_types=("application/json",),
        )

    def parse_candidates(
        self,
        parse_input: CareerConnectorParseInput,
    ) -> CareerConnectorResult:
        self.seen_input = parse_input

        result = CareerConnectorResult.build(
            connector_id=LEVER_CONNECTOR_ID,
            parse_input=parse_input,
            candidates=(),
        )

        if self.tamper_field is not None:
            result = result.model_copy(
                update={
                    self.tamper_field: self.tamper_value,
                },
            )

        return result


@pytest.mark.asyncio
async def test_projection_bundle_and_result_bind_exact_mode() -> None:
    research = _research()
    projection = _projection()

    gateway = _Gateway(_bundle(projection=projection))

    connector = _EmptyProjectionConnector()

    result = await CareerRetrievalOrchestrator(gateway).retrieve_candidates(
        connector=connector,
        objective=("Validate projection result binding"),
        source_url=SOURCE_URL,
    )

    assert gateway.calls == 1

    parse_input = connector.seen_input

    assert parse_input is not None

    assert parse_input.parser_input_kind == "phase16_structured_json_projection"

    assert parse_input.research_evidence_id == research.evidence_id

    assert parse_input.research_evidence_id == projection.research_evidence_id

    assert parse_input.projection_evidence_id == projection.projection_evidence_id

    assert parse_input.parser_text == projection.projection_text

    assert parse_input.parser_text_sha256 == projection.projection_sha256

    assert parse_input.source_body_sha256 == projection.source_body_sha256

    assert result.parser_input_kind == "phase16_structured_json_projection"

    assert result.research_evidence_id == research.evidence_id

    assert result.projection_evidence_id == projection.projection_evidence_id

    assert result.content_evidence_id is None

    assert result.parser_text_sha256 == projection.projection_sha256

    assert result.source_body_sha256 == projection.source_body_sha256

    assert result.normalized_text_sha256 == projection.projection_sha256

    assert result.candidates == ()
    assert result.candidate_count == 0

    assert result.metadata_is_job_truth is False
    assert result.production_truth_mutation_allowed is False
    assert result.application_authority_granted is False


def test_projection_bundle_rejects_parent_sha_mismatch() -> None:
    from hashlib import sha256

    from gateway.structured_json_projection import (
        project_structured_json,
    )

    research = _research()

    alternate_body = b'[{"applyUrl":"https://jobs.example.test/apply/job-2","categories":{"commitment":"Full-time","location":"Ottawa, ON","team":"Infrastructure"},"hostedUrl":"https://jobs.example.test/jobs/job-2","id":"job-2","text":"Cloud Platform Engineer"}]'

    projection = project_structured_json(
        profile_id="lever-list-v1",
        body=alternate_body,
        research_evidence_id=(research.evidence_id),
        source_url=SOURCE_URL,
        source_body_sha256=(sha256(alternate_body).hexdigest()),
        source_byte_count=len(alternate_body),
        source_content_type=("application/json"),
        observed_at=research.observed_at,
    )

    assert projection.source_body_sha256 != research.source_body_sha256

    with pytest.raises(
        ValueError,
        match="source body hash",
    ):
        _bundle(projection=projection)


def test_projection_bundle_rejects_parent_byte_count_mismatch() -> None:
    projection = _projection().model_copy(
        update={
            "source_byte_count": 4097,
        },
    )

    with pytest.raises(
        ValueError,
        match="source byte count",
    ):
        _bundle(projection=projection)


@pytest.mark.asyncio
async def test_result_binding_rejects_projection_id_tamper() -> None:
    connector = _EmptyProjectionConnector(
        tamper_field=("projection_evidence_id"),
        tamper_value=("structured-json-projection-ffffffffffffffffffffffff"),
    )

    with pytest.raises(
        CareerRetrievalOrchestrationError,
        match="projection evidence",
    ):
        await CareerRetrievalOrchestrator(_Gateway(_bundle())).retrieve_candidates(
            connector=connector,
            objective=("Reject projection ID tamper"),
            source_url=SOURCE_URL,
        )


@pytest.mark.asyncio
async def test_result_binding_rejects_parser_hash_tamper() -> None:
    connector = _EmptyProjectionConnector(
        tamper_field="parser_text_sha256",
        tamper_value="e" * 64,
    )

    with pytest.raises(
        CareerRetrievalOrchestrationError,
        match="parser_text_sha256",
    ):
        await CareerRetrievalOrchestrator(_Gateway(_bundle())).retrieve_candidates(
            connector=connector,
            objective=("Reject parser hash tamper"),
            source_url=SOURCE_URL,
        )


@pytest.mark.asyncio
async def test_result_binding_rejects_source_hash_tamper() -> None:
    connector = _EmptyProjectionConnector(
        tamper_field="source_body_sha256",
        tamper_value="f" * 64,
    )

    with pytest.raises(
        CareerRetrievalOrchestrationError,
        match="source body hash",
    ):
        await CareerRetrievalOrchestrator(_Gateway(_bundle())).retrieve_candidates(
            connector=connector,
            objective=("Reject source hash tamper"),
            source_url=SOURCE_URL,
        )


def test_structured_nonempty_candidates_fail_closed_until_provenance_phase() -> None:
    projection = _projection()

    parse_input = CareerConnectorParseInput(
        parser_input_kind=("phase16_structured_json_projection"),
        research_evidence_id=(projection.research_evidence_id),
        source_body_sha256=(projection.source_body_sha256),
        source_url=projection.source_url,
        media_type=(projection.source_content_type),
        observed_at=projection.observed_at,
        parser_text=(projection.projection_text),
        parser_text_sha256=(projection.projection_sha256),
        projection_evidence_id=(projection.projection_evidence_id),
        complete_document_parse=True,
        source_record_count=1,
        projected_record_count=1,
        projection_truncated=False,
    )

    candidate = CareerDiscoveryCandidate.build(
        connector_id=LEVER_CONNECTOR_ID,
        connector_kind="lever",
        employer_name="Projection Test",
        source_job_id="job-1",
        title_hint="Cloud Support Engineer",
        detail_url=("https://jobs.example.test/job-1"),
        discovery_research_evidence_id=(RESEARCH_EVIDENCE_ID),
        discovery_content_evidence_id=(CONTENT_EVIDENCE_ID),
        discovery_normalized_text_sha256=(PROJECTION_SHA),
        observed_at=OBSERVED_AT,
    )

    with pytest.raises(
        ValueError,
        match="provenance binding",
    ):
        CareerConnectorResult.build(
            connector_id=LEVER_CONNECTOR_ID,
            parse_input=parse_input,
            candidates=(candidate,),
        )
