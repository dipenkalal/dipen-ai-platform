from __future__ import annotations

from typing import (
    Literal,
    Protocol,
    runtime_checkable,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from career.connectors.contracts import (
    CareerConnector,
    CareerConnectorParseInput,
    CareerConnectorResult,
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


class CareerRetrievalOrchestrationError(RuntimeError):
    """Fail-closed Career retrieval orchestration error."""


class CareerPhase16RetrievalBundle(BaseModel):
    """
    Internal handoff from the sealed Phase-16 retrieval
    boundary to Career.

    This is not a network implementation.

    The bundle carries both terminal immutable retrieval
    evidence and the exact normalized untrusted-content
    object created during that same Phase-16 retrieval.
    """

    model_config = ConfigDict(frozen=True)

    requested_url: str = Field(
        min_length=8,
        max_length=4000,
    )

    retrieval_evidence: ResearchRetrievalEvidence

    content_evidence: UntrustedInternetEvidence

    projection_evidence: StructuredJSONProjectionEvidence | None = None

    network_execution_owner: Literal["phase16-research-gateway"] = (
        "phase16-research-gateway"
    )

    career_truth_mutation_allowed: Literal[False] = False

    application_authority_granted: Literal[False] = False

    browser_authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def validate_phase16_binding(
        self,
    ) -> CareerPhase16RetrievalBundle:
        evidence = self.retrieval_evidence
        content = self.content_evidence

        if evidence.outcome != "succeeded":
            raise ValueError(
                "Career retrieval bundle requires "
                "successful Phase-16 retrieval evidence"
            )

        if evidence.stage != "completed":
            raise ValueError(
                "Successful Career retrieval evidence must use completed stage"
            )

        if evidence.method == "GET":
            # Preserve the sealed Career GET handoff.
            pass

        elif evidence.method == "POST":
            # The sole POST Career handoff is the bounded
            # public Workday CXS jobs-listing operation.
            # Phase16 still owns DNS/TLS/HTTP admission.
            from urllib.parse import urlsplit
            import re

            if evidence.request_body_sha256 is None:
                raise ValueError(
                    "Career Workday POST bundle requires "
                    "Phase16 request-body SHA-256 binding"
                )

            if evidence.content_type != "application/json":
                raise ValueError(
                    "Career Workday POST bundle requires "
                    "application/json evidence"
                )

            parsed = urlsplit(
                evidence.requested_url
            )

            if (
                parsed.scheme.lower() != "https"
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError(
                    "Career Workday POST bundle requires "
                    "credential-free HTTPS"
                )

            try:
                port = parsed.port
            except ValueError as exc:
                raise ValueError(
                    "Career Workday POST bundle contains "
                    "an invalid port"
                ) from exc

            if port not in {
                None,
                443,
            }:
                raise ValueError(
                    "Career Workday POST bundle permits "
                    "only HTTPS port 443"
                )

            hostname = (
                parsed.hostname
                .lower()
                .rstrip(".")
            )

            if (
                not hostname.endswith(
                    ".myworkdayjobs.com"
                )
                or hostname
                == "myworkdayjobs.com"
            ):
                raise ValueError(
                    "Career POST bundle is restricted "
                    "to *.myworkdayjobs.com"
                )

            if (
                parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "Career Workday POST bundle may not "
                    "contain query or fragment data"
                )

            segments = (
                parsed.path.split("/")
            )

            if (
                len(segments) != 6
                or segments[0] != ""
                or segments[1] != "wday"
                or segments[2] != "cxs"
                or segments[5] != "jobs"
            ):
                raise ValueError(
                    "Career Workday POST bundle requires "
                    "the exact CXS jobs-listing path"
                )

            tenant = segments[3]
            site = segments[4]

            safe_segment = (
                r"[A-Za-z0-9._~-]+"
            )

            if (
                re.fullmatch(
                    safe_segment,
                    tenant,
                )
                is None
                or re.fullmatch(
                    safe_segment,
                    site,
                )
                is None
            ):
                raise ValueError(
                    "Career Workday POST bundle contains "
                    "an invalid tenant or site segment"
                )

            host_tenant = (
                hostname
                .split(".", 1)[0]
            )

            if (
                host_tenant.casefold()
                != tenant.casefold()
            ):
                raise ValueError(
                    "Career Workday POST bundle tenant "
                    "does not match the hostname"
                )

            if self.projection_evidence is not None:
                raise ValueError(
                    "Career Workday POST bundle does not "
                    "yet admit structured projection mode"
                )

        else:
            raise ValueError(
                "Career source retrieval must use GET "
                "or bounded Workday CXS POST"
            )

        if evidence.requested_url != self.requested_url:
            raise ValueError(
                "Phase-16 requested URL does not match Career approved source URL"
            )

        if evidence.final_url is None:
            raise ValueError("Successful Phase-16 evidence must contain final_url")

        # C.4A deliberately admits no redirect-derived
        # Career source identity. Any future widening must
        # be explicit and separately reviewed.
        if evidence.final_url != self.requested_url:
            raise ValueError(
                "Redirected final URL is not admitted "
                "by the C.4A Career retrieval contract"
            )

        if content.source_url != evidence.final_url:
            raise ValueError(
                "Untrusted content source URL does not match Phase-16 final URL"
            )

        if evidence.content_evidence_id != content.evidence_id:
            raise ValueError(
                "Content evidence ID does not match Phase-16 retrieval evidence"
            )

        if evidence.content_evidence_sha256 != content.evidence_sha256:
            raise ValueError(
                "Content evidence hash does not match Phase-16 retrieval evidence"
            )

        if evidence.normalized_text_sha256 != content.normalized_text_sha256:
            raise ValueError(
                "Normalized text hash does not match Phase-16 retrieval evidence"
            )

        if evidence.source_body_sha256 != content.source_body_sha256:
            raise ValueError(
                "Source body hash does not match Phase-16 content evidence"
            )

        if evidence.content_type != content.media_type:
            raise ValueError(
                "Content media type does not match Phase-16 retrieval evidence"
            )

        if content.authority_granted:
            raise ValueError("Untrusted internet content must never grant authority")

        if content.retrieval_scope_expansion_allowed:
            raise ValueError(
                "Untrusted internet content may not expand retrieval scope"
            )

        if content.credential_use_allowed:
            raise ValueError(
                "Untrusted internet content may not request credential use"
            )

        projection = self.projection_evidence

        if projection is not None:
            if evidence.content_type != "application/json":
                raise ValueError(
                    "Structured projection requires application/json Research evidence"
                )

            if projection.research_evidence_id != evidence.evidence_id:
                raise ValueError(
                    "Projection research evidence ID does not match Phase-16 evidence"
                )

            if projection.source_body_sha256 != evidence.source_body_sha256:
                raise ValueError(
                    "Projection source body hash does not match Phase-16 evidence"
                )

            if projection.source_byte_count != evidence.byte_count:
                raise ValueError(
                    "Projection source byte count does not match Phase-16 evidence"
                )

            if projection.source_content_type != evidence.content_type:
                raise ValueError(
                    "Projection source content type does not match Phase-16 evidence"
                )

            if projection.source_content_type != content.media_type:
                raise ValueError(
                    "Projection media type does not match normalized content evidence"
                )

            if projection.source_url != evidence.final_url:
                raise ValueError(
                    "Projection source URL does not match Phase-16 final URL"
                )

            if projection.source_url != content.source_url:
                raise ValueError(
                    "Projection source URL does not match content evidence"
                )

            if projection.observed_at != evidence.observed_at:
                raise ValueError(
                    "Projection observation time does not match Phase-16 evidence"
                )

            if projection.complete_document_parse is not True:
                raise ValueError("Projection must prove complete document parsing")

            if projection.projection_truncated:
                raise ValueError("Projection may not be truncated")

            if projection.source_record_count != projection.projected_record_count:
                raise ValueError("Projection source/projected record counts must match")

            if any(
                (
                    projection.metadata_is_job_truth,
                    projection.career_truth_mutation_allowed,
                    projection.application_authority_granted,
                    projection.browser_authority_granted,
                    projection.credential_use_allowed,
                    projection.retrieval_scope_expansion_allowed,
                )
            ):
                raise ValueError(
                    "Structured projection may not grant Career or execution authority"
                )
        return self


@runtime_checkable
class Phase16CareerRetrievalGateway(Protocol):
    """
    Narrow injected boundary implemented later by a
    Phase-16-native adapter.

    C.4A intentionally provides no concrete network
    implementation.
    """

    async def retrieve_public_url(
        self,
        *,
        objective: str,
        url: str,
    ) -> CareerPhase16RetrievalBundle: ...


class CareerRetrievalOrchestrator:
    """
    Convert sealed Phase-16 retrieval evidence into
    pure Career connector input.

    This object owns no DNS, sockets, TLS, browser,
    database repository, or ATS submission client.
    """

    def __init__(
        self,
        gateway: Phase16CareerRetrievalGateway,
    ) -> None:
        self._gateway = gateway

    async def retrieve_candidates(
        self,
        *,
        connector: CareerConnector,
        objective: str,
        source_url: str,
    ) -> CareerConnectorResult:
        objective = objective.strip()

        if len(objective) < 3:
            raise CareerRetrievalOrchestrationError(
                "Career retrieval objective must contain at least 3 characters"
            )

        if source_url != source_url.strip():
            raise CareerRetrievalOrchestrationError(
                "Career source URL must already be normalized"
            )

        if not source_url:
            raise CareerRetrievalOrchestrationError("Career source URL is required")

        descriptor = connector.descriptor

        if descriptor.connector_owns_network:
            raise CareerRetrievalOrchestrationError(
                "Career connector may not own network authority"
            )

        if descriptor.credentials_required:
            raise CareerRetrievalOrchestrationError(
                "Career connector may not require credentials"
            )

        if descriptor.application_submission_supported:
            raise CareerRetrievalOrchestrationError(
                "Career connector may not support application submission"
            )

        if descriptor.browser_authority_granted:
            raise CareerRetrievalOrchestrationError(
                "Career connector may not own browser authority"
            )

        bundle = await self._gateway.retrieve_public_url(
            objective=objective,
            url=source_url,
        )

        if bundle.requested_url != source_url:
            raise CareerRetrievalOrchestrationError(
                "Phase-16 bundle URL does not match Career source request"
            )

        evidence = bundle.retrieval_evidence
        content = bundle.content_evidence

        if content.media_type not in descriptor.response_media_types:
            raise CareerRetrievalOrchestrationError(
                "Retrieved media type is not admitted by the connector descriptor"
            )

        projection = bundle.projection_evidence

        if projection is None:
            parse_input = CareerConnectorParseInput(
                parser_input_kind=("phase16_normalized_content"),
                research_evidence_id=(evidence.evidence_id),
                source_body_sha256=(evidence.source_body_sha256),
                source_url=source_url,
                media_type=content.media_type,
                observed_at=evidence.observed_at,
                parser_text=content.normalized_text,
                parser_text_sha256=(content.normalized_text_sha256),
                content_evidence_id=(content.evidence_id),
            )
        else:
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
                complete_document_parse=(projection.complete_document_parse),
                source_record_count=(projection.source_record_count),
                projected_record_count=(projection.projected_record_count),
                projection_truncated=(projection.projection_truncated),
            )

        result = connector.parse_candidates(parse_input)

        self._validate_result_binding(
            result=result,
            connector_id=descriptor.connector_id,
            source_url=source_url,
            evidence=evidence,
            content=content,
            parse_input=parse_input,
        )

        return result

    @staticmethod
    @staticmethod
    def _validate_result_binding(
        *,
        result: CareerConnectorResult,
        connector_id: str,
        source_url: str,
        evidence: ResearchRetrievalEvidence,
        content: UntrustedInternetEvidence,
        parse_input: CareerConnectorParseInput,
    ) -> None:
        if result.connector_id != connector_id:
            raise CareerRetrievalOrchestrationError(
                "Connector result identity does not match selected connector"
            )

        if result.parser_input_kind != parse_input.parser_input_kind:
            raise CareerRetrievalOrchestrationError(
                "Connector result parser input mode does not match selected input"
            )

        if result.research_evidence_id != parse_input.research_evidence_id:
            raise CareerRetrievalOrchestrationError(
                "Connector result research evidence "
                "does not match selected parser input"
            )

        if result.research_evidence_id != evidence.evidence_id:
            raise CareerRetrievalOrchestrationError(
                "Connector result research evidence does not match Phase-16 evidence"
            )

        if result.source_url != source_url:
            raise CareerRetrievalOrchestrationError(
                "Connector result source URL does not match Career source request"
            )

        if result.source_url != parse_input.source_url:
            raise CareerRetrievalOrchestrationError(
                "Connector result source URL does not match selected parser input"
            )

        if result.normalized_text_sha256 != parse_input.parser_text_sha256:
            raise CareerRetrievalOrchestrationError(
                "Connector result parser hash does not match selected parser input"
            )

        if result.observed_at != parse_input.observed_at:
            raise CareerRetrievalOrchestrationError(
                "Connector result observation time does not match selected parser input"
            )

        if parse_input.parser_input_kind == "phase16_structured_json_projection":
            if result.content_evidence_id is not None:
                raise CareerRetrievalOrchestrationError(
                    "Projection connector result may not claim legacy content evidence"
                )

            if result.projection_evidence_id != parse_input.projection_evidence_id:
                raise CareerRetrievalOrchestrationError(
                    "Connector result projection evidence "
                    "does not match selected projection"
                )

            if result.parser_text_sha256 != parse_input.parser_text_sha256:
                raise CareerRetrievalOrchestrationError(
                    "Connector result parser_text_sha256 "
                    "does not match projection input"
                )

            if result.source_body_sha256 != parse_input.source_body_sha256:
                raise CareerRetrievalOrchestrationError(
                    "Connector result source body hash does not match projection input"
                )

        else:
            if result.content_evidence_id != content.evidence_id:
                raise CareerRetrievalOrchestrationError(
                    "Connector result content evidence does not match Phase-16 evidence"
                )

            if result.content_evidence_id != parse_input.content_evidence_id:
                raise CareerRetrievalOrchestrationError(
                    "Connector result content evidence "
                    "does not match legacy parser input"
                )

            if result.projection_evidence_id is not None:
                raise CareerRetrievalOrchestrationError(
                    "Legacy connector result may not claim projection evidence"
                )

            if result.normalized_text_sha256 != content.normalized_text_sha256:
                raise CareerRetrievalOrchestrationError(
                    "Connector result normalized hash does not match Phase-16 content"
                )

            if (
                result.parser_text_sha256 is not None
                and result.parser_text_sha256 != parse_input.parser_text_sha256
            ):
                raise CareerRetrievalOrchestrationError(
                    "Legacy connector result parser hash does not match parser input"
                )

            if (
                result.source_body_sha256 is not None
                and result.source_body_sha256 != parse_input.source_body_sha256
            ):
                raise CareerRetrievalOrchestrationError(
                    "Legacy connector result source hash does not match parser input"
                )

        if result.metadata_is_job_truth:
            raise CareerRetrievalOrchestrationError(
                "Connector result may not become Career job truth"
            )

        if result.production_truth_mutation_allowed:
            raise CareerRetrievalOrchestrationError(
                "Connector result may not mutate Career production truth"
            )

        if result.application_authority_granted:
            raise CareerRetrievalOrchestrationError(
                "Connector result may not grant application authority"
            )
